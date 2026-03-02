#!/usr/bin/env python3
"""
Bond-Order Correction for Docked Ligand Poses
================================================
Problem:  PDBQT → SDF conversion strips bond orders (everything becomes
          single bonds).  PoseView then draws a saturated, wrong structure.

Solution: Use RDKit AssignBondOrdersFromTemplate to graft correct bond
          orders from a SMILES template onto the docked 3D geometry while
          preserving all atomic coordinates and score properties.

Usage:
    python app.py \
        --input  docked_pose.sdf \
        --smiles "C1=CC=C(C=C1)C2=CC(=O)C3=C(O2)C=C(C(=C3O)O)O" \
        --output poseview_ready.sdf

    # or with explicit name for multi-ligand batches:
    python app.py --input batch.sdf --smiles "..." --output fixed.sdf --name Baicalein
"""

import argparse
import copy
import sys
from pathlib import Path

from rdkit import Chem
from rdkit.Chem import AllChem, rdMolAlign


# ─── Core fixer ───────────────────────────────────────────────────────────────

def smiles_to_template(smiles: str) -> Chem.Mol:
    """
    Build a sanitised, kekulised template from a SMILES string.

    AssignBondOrdersFromTemplate requires the template to have explicit
    bond orders (not aromatic perception), so we kekulise and set
    NoAromatic = True to avoid the 'aromatic bond but not flagged' error
    that occasionally surfaces with fused ring systems like flavones.
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"RDKit could not parse SMILES: {smiles!r}")

    # Kekulise so every bond is either SINGLE, DOUBLE, or TRIPLE —
    # this is what AssignBondOrdersFromTemplate expects on the template side.
    Chem.Kekulize(mol, clearAromaticFlags=True)
    return mol


def fix_bond_orders(
    probe: Chem.Mol,
    template: Chem.Mol,
    preserve_props: bool = True,
) -> Chem.Mol:
    """
    Assign correct bond orders from *template* onto *probe* (docked geometry).

    Parameters
    ----------
    probe        : molecule read from the SDF written by obabel/Open Babel
                   (all bonds are single, coordinates are correct)
    template     : kekulised molecule built from the reference SMILES
    preserve_props: carry over all SD-tag properties from the original probe

    Returns
    -------
    fixed        : new molecule with correct bond orders AND original 3D coords
    """
    # Strip explicit Hs that Open Babel sometimes adds — they confuse the
    # substructure match inside AssignBondOrdersFromTemplate.
    probe_noH = Chem.RemoveHs(probe, sanitize=False)

    try:
        fixed = AllChem.AssignBondOrdersFromTemplate(template, probe_noH)
    except ValueError as exc:
        raise RuntimeError(
            "AssignBondOrdersFromTemplate failed — atom count or connectivity "
            f"mismatch between probe and template.\n  Detail: {exc}\n"
            "  Tip: make sure your SMILES matches the ligand that was docked."
        ) from exc

    # Sanitise the result (recalculates aromaticity, valences, etc.)
    try:
        Chem.SanitizeMol(fixed)
    except Exception as exc:
        raise RuntimeError(f"Sanitisation failed after bond-order assignment: {exc}") from exc

    # Copy SD-tag properties (Vina score, RMSD, pose number …)
    if preserve_props:
        for prop_name in probe.GetPropsAsDict():
            val = probe.GetProp(prop_name)
            fixed.SetProp(prop_name, val)

    return fixed


# ─── Multi-pose SDF pipeline ──────────────────────────────────────────────────

def process_sdf(
    input_sdf: str,
    smiles: str,
    output_sdf: str,
    mol_name: str | None = None,
) -> dict:
    """
    Read every conformer / pose from *input_sdf*, fix bond orders using
    *smiles* as the template, and write corrected poses to *output_sdf*.

    Returns a summary dict with counts and per-pose results.
    """
    template = smiles_to_template(smiles)

    supplier = Chem.SDMolSupplier(input_sdf, sanitize=False, removeHs=False)
    writer   = Chem.SDWriter(output_sdf)

    results   = []
    n_ok      = 0
    n_fail    = 0

    for pose_idx, mol in enumerate(supplier):
        pose_num = pose_idx + 1

        if mol is None:
            print(f"  [pose {pose_num}] ⚠  Could not read — skipped", file=sys.stderr)
            n_fail += 1
            results.append({"pose": pose_num, "status": "READ_ERROR", "score": None})
            continue

        # ── Extract Vina score from SD tags before we strip anything ─────────
        score = _extract_score(mol)

        try:
            fixed = fix_bond_orders(mol, template, preserve_props=True)
        except RuntimeError as exc:
            print(f"  [pose {pose_num}] ✗  {exc}", file=sys.stderr)
            n_fail += 1
            results.append({"pose": pose_num, "status": "FIX_ERROR", "score": score})
            continue

        # ── Set molecule name ─────────────────────────────────────────────────
        name = mol_name or mol.GetProp("_Name") or f"pose_{pose_num}"
        fixed.SetProp("_Name", f"{name}_pose{pose_num}")

        # ── Ensure Vina score is written as a named SD tag (for PoseView) ─────
        if score is not None:
            fixed.SetProp("Vina_affinity_kcal_mol", f"{score:.4f}")

        writer.write(fixed)
        n_ok += 1
        print(f"  [pose {pose_num}] ✓  fixed  |  score = {score if score else 'N/A'}")
        results.append({"pose": pose_num, "status": "OK", "score": score})

    writer.close()
    return {"n_ok": n_ok, "n_fail": n_fail, "poses": results}


# ─── Score extraction helpers ─────────────────────────────────────────────────

def _extract_score(mol: Chem.Mol) -> float | None:
    """
    Pull the docking score from the SD molecule, trying several common
    tag names used by obabel / gnina / AutoDock Vina.
    """
    tag_candidates = [
        "minimizedAffinity",   # obabel default from PDBQT REMARK
        "VINA",
        "docking_score",
        "Affinity",
        "affinity",
    ]
    for tag in tag_candidates:
        if mol.HasProp(tag):
            try:
                return float(mol.GetProp(tag))
            except (ValueError, TypeError):
                pass

    # Fall back: grep the raw REMARK lines stored in the title block
    title = mol.GetProp("_Name") if mol.HasProp("_Name") else ""
    if "REMARK VINA RESULT" in title:
        parts = title.split()
        for i, p in enumerate(parts):
            if p == "RESULT:" and i + 1 < len(parts):
                try:
                    return float(parts[i + 1])
                except ValueError:
                    pass
    return None


# ─── Validation helper ────────────────────────────────────────────────────────

def validate_fix(original_sdf: str, fixed_sdf: str) -> None:
    """
    Quick sanity check: print atom count, aromatic ring count, and formal
    charge for each pose in both files so you can confirm the fix worked.
    """
    def _ring_info(mol):
        ri       = mol.GetRingInfo()
        arom_n   = sum(
            1 for ring in ri.AtomRings()
            if all(mol.GetAtomWithIdx(i).GetIsAromatic() for i in ring)
        )
        return ri.NumRings(), arom_n

    orig_mols  = [m for m in Chem.SDMolSupplier(original_sdf,  sanitize=False) if m]
    fixed_mols = [m for m in Chem.SDMolSupplier(fixed_sdf,     sanitize=True)  if m]

    print("\n── Validation ─────────────────────────────────────────────────────")
    print(f"  {'Pose':>5}  {'Atoms (orig→fix)':>18}  "
          f"{'Rings (orig→fix)':>18}  {'Arom rings (fix)':>17}")
    for i, (o, f) in enumerate(zip(orig_mols, fixed_mols), 1):
        o_noH = Chem.RemoveHs(o, sanitize=False)
        f_noH = Chem.RemoveHs(f)
        nr_o, na_o = _ring_info(o_noH)
        nr_f, na_f = _ring_info(f_noH)
        print(f"  {i:>5}  {o_noH.GetNumAtoms():>8} → {f_noH.GetNumAtoms():<7}  "
              f"{nr_o:>8} → {nr_f:<7}  {na_f:>17}")
    print("────────────────────────────────────────────────────────────────────\n")


# ─── Convenience: fix a single SDF from within Python (importable) ────────────

def fix_docked_sdf(
    input_sdf: str,
    smiles: str,
    output_sdf: str | None = None,
    mol_name: str | None   = None,
) -> str:
    """
    High-level wrapper — fix *input_sdf* and return the path to the output.
    If *output_sdf* is None a path is derived automatically.
    """
    if output_sdf is None:
        p = Path(input_sdf)
        output_sdf = str(p.parent / (p.stem + "_bondfix.sdf"))

    summary = process_sdf(input_sdf, smiles, output_sdf, mol_name=mol_name)
    print(f"\n✓  {summary['n_ok']} poses fixed  |  {summary['n_fail']} failed  → {output_sdf}")
    validate_fix(input_sdf, output_sdf)
    return output_sdf


# ─── Streamlit integration snippet (drop into your app.py) ───────────────────
# To use inside the Streamlit docking app, replace the PoseView SDF path with:
#
#   from app import fix_docked_sdf
#
#   corrected_sdf = fix_docked_sdf(
#       input_sdf  = original_out_sdf,   # path written by obabel
#       smiles     = smiles_in,           # the SMILES used to prepare the ligand
#       output_sdf = str(WORKDIR / f"{lig_name}_pv_ready.sdf"),
#       mol_name   = lig_name,
#   )
#   # Then pass corrected_sdf to _call_poseview() instead of the raw SDF.


# ─── CLI ─────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--input",  "-i", required=True,
                   help="Path to SDF produced from PDBQT (bond orders broken)")
    p.add_argument("--smiles", "-s", required=True,
                   help="Reference SMILES with correct bond orders")
    p.add_argument("--output", "-o", default=None,
                   help="Output SDF path (default: <input>_bondfix.sdf)")
    p.add_argument("--name",   "-n", default=None,
                   help="Override molecule name in output (optional)")
    p.add_argument("--validate", action="store_true", default=True,
                   help="Print validation summary after fixing (default: on)")
    p.add_argument("--no-validate", dest="validate", action="store_false")
    return p


def main() -> None:
    parser = _build_parser()
    args   = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        sys.exit(f"❌  Input file not found: {args.input}")

    output_path = args.output or str(input_path.parent / (input_path.stem + "_bondfix.sdf"))

    print(f"📂  Input  : {args.input}")
    print(f"🧬  SMILES : {args.smiles[:80]}{'…' if len(args.smiles) > 80 else ''}")
    print(f"📝  Output : {output_path}\n")

    summary = process_sdf(args.input, args.smiles, output_path, mol_name=args.name)

    if args.validate:
        validate_fix(args.input, output_path)

    print(f"✅  Done — {summary['n_ok']} pose(s) written to {output_path}")
    if summary["n_fail"]:
        print(f"⚠   {summary['n_fail']} pose(s) could not be fixed (see warnings above)")
        sys.exit(1)


if __name__ == "__main__":
    main()
