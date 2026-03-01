#!/usr/bin/env python3
"""
app.py -- Bond-order correction for PoseView-ready SDF files

Root cause
----------
PDBQT stores no bond orders. OpenBabel reconstructs them heuristically on
PDBQT->SDF conversion. For conjugated/aromatic systems (flavones, etc.) this
yields wrong hybridisation: sp3 atoms in aromatic rings, missing double bonds.
PoseView then draws an incorrect 2D structure.

Solution
--------
RDKit AssignBondOrdersFromTemplate copies correct bond types from a template
built from the original SMILES, preserving 3D docking xyz exactly.

CLI
---
  # Fix best pose (0-based index 0):
  python app.py --smiles SMILES --input docked.sdf --output pv_ready.sdf

  # Fix ALL poses in one SDF:
  python app.py --smiles SMILES --input all.sdf --output fixed.sdf --all-poses

  # Use a reference SDF instead of SMILES:
  python app.py --template-sdf ref.sdf --input docked.sdf --output pv_ready.sdf

  # Batch directory (one *_out.sdf per ligand):
  python app.py --smiles-file sm.txt --input-dir lig/ --output-dir fixed/

  # Validate:
  python app.py --smiles SMILES --input docked.sdf --output pv.sdf --validate

Library
-------
  from app import fix_bond_orders_single, fix_bond_orders_batch
  from app import get_poseview_ready_sdf  # Streamlit drop-in
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path
from typing import Optional

try:
    from rdkit import Chem
    from rdkit.Chem import AllChem, rdFMCS
    from rdkit.Chem.AllChem import AssignBondOrdersFromTemplate
except ImportError as e:
    sys.exit(f"RDKit required: {e}")


# =============================================================================
# 1. Template construction
# =============================================================================

def template_from_smiles(smiles: str) -> Chem.Mol:
    """
    Build a sanitised, H-stripped RDKit Mol from a SMILES string.

    This mol is used purely as a bond-order donor -- 3D coordinates
    are not required and are not present.

    Parameters
    ----------
    smiles : str
        Valid SMILES with correct bond orders.
        Example (baicalein):
        "C1=CC=C(C=C1)C2=CC(=O)C3=C(O2)C=C(C(=C3O)O)O"

    Returns
    -------
    Chem.Mol -- sanitised template

    Raises
    ------
    ValueError if RDKit cannot parse the SMILES.
    """
    mol = Chem.MolFromSmiles(smiles.strip())
    if mol is None:
        raise ValueError(f"Cannot parse SMILES: {smiles!r}")
    mol = Chem.RemoveHs(mol)
    Chem.SanitizeMol(mol)
    return mol


def template_from_sdf(path: str | Path) -> Chem.Mol:
    """
    Load the first valid molecule from a reference SDF that already has
    correct bond orders (e.g. the pre-docking ligand SDF from a crystal
    structure or CSD entry).

    Parameters
    ----------
    path : path to a reference SDF with correct bond orders

    Returns
    -------
    Chem.Mol -- first valid, sanitised molecule

    Raises
    ------
    ValueError if the file contains no usable molecules.
    """
    suppl = Chem.SDMolSupplier(str(path), sanitize=True, removeHs=True)
    mol = next((m for m in suppl if m is not None), None)
    if mol is None:
        raise ValueError(f"No valid molecule in: {path}")
    return mol


# =============================================================================
# 2. Core single-molecule repair
# =============================================================================

def fix_single_mol(
    docked: Chem.Mol,
    template: Chem.Mol,
    *,
    preserve_props: bool = True,
) -> Optional[Chem.Mol]:
    """
    Copy correct bond orders from *template* into *docked* while preserving
    the original 3D docking coordinates exactly.

    Algorithm
    ---------
    1. Strip explicit H from the docked mol.
       OpenBabel often adds H with wrong connectivity after PDBQT->SDF;
       removing them prevents atom-count mismatches with the H-free template.

    2. AssignBondOrdersFromTemplate (RDKit).
       Finds a substructure match between docked heavy atoms and template,
       copies bond types and aromaticity flags atom-pair by atom-pair.
       The 3D conformer is retained verbatim.

    3. Sanitize (aromaticity perception, valence check).

    4. Re-add H with 3D coordinates so PoseView receives a complete mol.

    5. Copy SD-tag properties (Vina scores, pose index, etc.).

    Parameters
    ----------
    docked         : from PDBQT->SDF conversion  -- wrong bonds, correct xyz
    template       : from SMILES or ref SDF       -- correct bonds, no xyz
    preserve_props : propagate all SD-tags to the returned mol

    Returns
    -------
    Fixed Chem.Mol, or None on unrecoverable failure (warning printed).
    """
    # 1 -- strip H
    try:
        noh = Chem.RemoveHs(docked, sanitize=False)
    except Exception:
        noh = docked

    # 2 -- assign bond orders; fall back to MCS on atom-count mismatch
    try:
        fixed = AssignBondOrdersFromTemplate(template, noh)
    except ValueError as exc:
        fixed = _mcs_fallback(noh, template)
        if fixed is None:
            warnings.warn(
                f"[fix_single_mol] Primary assignment failed + MCS fallback empty: {exc}"
            )
            return None

    # 3 -- sanitise
    try:
        Chem.SanitizeMol(fixed)
    except Exception as exc:
        warnings.warn(f"[fix_single_mol] Sanitisation warning: {exc}")

    # 4 -- re-add H with 3D coords for a chemically complete output
    try:
        fixed = AllChem.AddHs(fixed, addCoords=True)
    except Exception:
        pass

    # 5 -- copy SD-tag properties (Vina scores, pose index, etc.)
    if preserve_props:
        try:
            for k, v in docked.GetPropsAsDict().items():
                fixed.SetProp(k, str(v))
        except Exception:
            pass
        try:
            name = docked.GetProp("_Name")
            if name:
                fixed.SetProp("_Name", name)
        except Exception:
            pass

    return fixed


# =============================================================================
# 3. MCS fallback for atom-count discrepancies
# =============================================================================

def _mcs_fallback(noh: Chem.Mol, template: Chem.Mol) -> Optional[Chem.Mol]:
    """
    When heavy-atom counts differ (tautomers, atoms lost in bad PDBQT
    conversion), find the Maximum Common Substructure and patch bond orders
    for matched atoms only.  Bonds outside the MCS keep original types.

    This is best-effort -- always visually inspect the output.

    Returns
    -------
    Partially repaired Chem.Mol, or None if the MCS is too small to trust.
    """
    try:
        mcs = rdFMCS.FindMCS(
            [noh, template],
            atomCompare=rdFMCS.AtomCompare.CompareAnyHeavyAtom,
            bondCompare=rdFMCS.BondCompare.CompareAny,
            matchValences=False,
            ringMatchesRingOnly=True,
            completeRingsOnly=True,
            timeout=10,
        )
        if mcs.numAtoms < 4:
            return None  # too small to be reliable

        mcs_mol = Chem.MolFromSmarts(mcs.smartsString)
        if mcs_mol is None:
            return None

        dm = noh.GetSubstructMatch(mcs_mol)
        tm = template.GetSubstructMatch(mcs_mol)
        if not dm or not tm:
            return None

        d2t: dict[int, int] = dict(zip(dm, tm))
        em = Chem.RWMol(noh)

        for bond in template.GetBonds():
            tb = bond.GetBeginAtomIdx()
            te = bond.GetEndAtomIdx()
            db = next((d for d, t in d2t.items() if t == tb), None)
            de = next((d for d, t in d2t.items() if t == te), None)
            if db is None or de is None:
                continue
            b = em.GetBondBetweenAtoms(db, de)
            if b:
                b.SetBondType(bond.GetBondType())
                b.SetIsAromatic(bond.GetIsAromatic())

        return em.GetMol()
    except Exception as exc:
        warnings.warn(f"[_mcs_fallback] {exc}")
        return None


# =============================================================================
# 4. Public API -- single pose
# =============================================================================

def fix_bond_orders_single(
    input_sdf:    str | Path,
    output_sdf:   str | Path,
    smiles:       Optional[str] = None,
    template_sdf: Optional[str | Path] = None,
    pose_index:   int = 0,
) -> bool:
    """
    Fix bond orders for ONE pose from *input_sdf* and write to *output_sdf*.

    Exactly one of *smiles* or *template_sdf* must be provided.

    Parameters
    ----------
    input_sdf    : PDBQT-converted SDF  (wrong bonds, correct docking xyz)
    output_sdf   : destination for the corrected SDF
    smiles       : SMILES with correct bond orders  [mutually exclusive]
    template_sdf : reference SDF with correct bonds [mutually exclusive]
    pose_index   : 0-based pose to fix (0 = best Vina pose)

    Returns
    -------
    True on success, False on failure.
    """
    if smiles is None and template_sdf is None:
        raise ValueError("Provide smiles or template_sdf.")

    tpl   = template_from_smiles(smiles) if smiles else template_from_sdf(template_sdf)
    suppl = Chem.SDMolSupplier(str(input_sdf), sanitize=False, removeHs=False)
    mols  = [m for m in suppl if m is not None]

    if not mols:
        print(f"[ERROR] No molecules in {input_sdf}", file=sys.stderr)
        return False

    if pose_index >= len(mols):
        print(f"[WARN] pose_index {pose_index} out of range; using last pose.",
              file=sys.stderr)
        pose_index = len(mols) - 1

    fixed = fix_single_mol(mols[pose_index], tpl)
    if fixed is None:
        print("[ERROR] Bond-order assignment failed.", file=sys.stderr)
        return False

    w = Chem.SDWriter(str(output_sdf))
    w.write(fixed)
    w.close()
    print(f"[OK] Written -> {output_sdf}")
    return True


# =============================================================================
# 5. Public API -- all poses in one SDF  (BONUS)
# =============================================================================

def fix_bond_orders_batch(
    input_sdf:    str | Path,
    output_sdf:   str | Path,
    smiles:       Optional[str] = None,
    template_sdf: Optional[str | Path] = None,
) -> dict:
    """
    Fix bond orders for ALL poses stored in *input_sdf*.

    Useful when the SDF holds multiple Vina poses and you want to browse or
    submit any pose to PoseView.

    Each fixed pose receives a 1-based ``pose_index`` SD property.
    All other SD properties (Vina scores, etc.) are preserved.

    Returns
    -------
    dict{"success": int, "failed": int}
    """
    if smiles is None and template_sdf is None:
        raise ValueError("Provide smiles or template_sdf.")

    tpl    = template_from_smiles(smiles) if smiles else template_from_sdf(template_sdf)
    suppl  = Chem.SDMolSupplier(str(input_sdf), sanitize=False, removeHs=False)
    writer = Chem.SDWriter(str(output_sdf))
    stats  = {"success": 0, "failed": 0}

    for i, mol in enumerate(suppl):
        if mol is None:
            print(f"[WARN] Pose {i+1}: parse error -- skipped.", file=sys.stderr)
            stats["failed"] += 1
            continue
        fixed = fix_single_mol(mol, tpl)
        if fixed is None:
            print(f"[WARN] Pose {i+1}: fix failed -- skipped.", file=sys.stderr)
            stats["failed"] += 1
            continue
        fixed.SetIntProp("pose_index", i + 1)
        writer.write(fixed)
        stats["success"] += 1
        print(f"[OK] Pose {i+1} fixed.")

    writer.close()
    ok   = stats["success"]
    fail = stats["failed"]
    print(f"Batch done: {ok} fixed, {fail} failed. -> {output_sdf}")
    return stats


# =============================================================================
# 6. Public API -- directory of per-ligand SDFs  (BONUS)
# =============================================================================

def fix_bond_orders_dir(
    input_dir:   str | Path,
    output_dir:  str | Path,
    smiles_file: str | Path,
) -> None:
    """
    Fix bond orders for every ``*_out.sdf`` file in *input_dir*.

    *smiles_file* is a plain-text file with one "SMILES  name" pair per line.
    The name is matched case-insensitively against the SDF filename stem.

    Output files are written to *output_dir* as ``*_fixed.sdf``.
    """
    input_dir  = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    smap: dict[str, str] = {}
    with open(smiles_file) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 1)
            if len(parts) == 2:
                smap[parts[1].strip().lower()] = parts[0]

    for sdf in sorted(input_dir.glob("*_out.sdf")):
        stem = sdf.stem.replace("_out", "").lower()
        smi  = smap.get(stem) or next(
            (v for k, v in smap.items() if stem in k or k in stem), None
        )
        if not smi:
            print(f"[WARN] {sdf.name}: no SMILES match -- skipped.")
            continue
        out = output_dir / sdf.name.replace("_out.sdf", "_fixed.sdf")
        fix_bond_orders_batch(input_sdf=sdf, output_sdf=out, smiles=smi)


# =============================================================================
# 7. Streamlit drop-in helper
# =============================================================================

def get_poseview_ready_sdf(
    pose_sdf:    str | Path,
    smiles:      str,
    output_path: Optional[str | Path] = None,
) -> tuple:
    """
    Drop-in helper for the Streamlit docking app.

    Replaces the raw PDBQT-converted pose SDF with a bond-order-corrected
    version and returns both the file path and raw bytes for st.download_button.

    Integration
    -----------
    In the Streamlit app, locate the PoseView call block and change:

        # BEFORE (bond orders may be wrong)
        _url, _err = _call_poseview(_rec, sp)

    To:

        from app import get_poseview_ready_sdf
        sp_fixed, _ = get_poseview_ready_sdf(
            pose_sdf    = sp,
            smiles      = st.session_state.prot_smiles,
            output_path = str(WORKDIR / "pv_ready.sdf"),
        )
        _url, _err = _call_poseview(_rec, sp_fixed)  # correct bonds

    Parameters
    ----------
    pose_sdf    : pose SDF from PDBQT conversion  (may have wrong bond orders)
    smiles      : SMILES with correct bond orders (protonated form is fine)
    output_path : write destination; auto-generated next to pose_sdf if None

    Returns
    -------
    (output_path_str, file_bytes_or_None)
    Bytes are None on failure; original file path returned for graceful fallback.
    """
    pose_sdf = Path(pose_sdf)
    if output_path is None:
        output_path = pose_sdf.parent / (pose_sdf.stem + "_pv_ready.sdf")
    output_path = Path(output_path)

    ok = fix_bond_orders_single(
        input_sdf  = pose_sdf,
        output_sdf = output_path,
        smiles     = smiles,
        pose_index = 0,
    )
    if not ok:
        warnings.warn(
            "Bond-order fix failed -- returning original SDF. "
            "PoseView may draw an incorrect 2D structure."
        )
        return str(pose_sdf), None

    return str(output_path), output_path.read_bytes()


# =============================================================================
# 8. Validation helper
# =============================================================================

def validate_fix(original_smiles: str, fixed_sdf: str | Path) -> None:
    """
    Compare canonical SMILES of the template vs. the fixed SDF.

    Prints a structured report including aromatic bond counts.
    A canonical SMILES mismatch is not always a true failure -- 3D embedding
    can occasionally affect ring perception.  Always visually inspect output.
    """
    tpl     = template_from_smiles(original_smiles)
    t_canon = Chem.MolToSmiles(tpl, isomericSmiles=False)

    suppl = Chem.SDMolSupplier(str(fixed_sdf), sanitize=True, removeHs=True)
    fixed = next((m for m in suppl if m is not None), None)
    if fixed is None:
        print("[VALIDATE] Cannot load fixed SDF.")
        return

    f_canon = Chem.MolToSmiles(fixed, isomericSmiles=False)
    match   = t_canon == f_canon
    arom_t  = sum(1 for b in tpl.GetBonds()   if b.GetIsAromatic())
    arom_f  = sum(1 for b in fixed.GetBonds() if b.GetIsAromatic())
    sep     = "=" * 64

    print()
    print(sep)
    print("  VALIDATION REPORT")
    print(sep)
    print(f"  Template SMILES  : {t_canon}")
    print(f"  Fixed SDF SMILES : {f_canon}")
    result = "YES -- structure is correct" if match else "NO  -- inspect manually"
    print(f"  Bond orders match: {result}")
    print(f"  Aromatic bonds   : template={arom_t}  fixed={arom_f}")
    print(sep)
    print()


# =============================================================================
# 9. CLI
# =============================================================================

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="app.py",
        description="Fix bond orders in PDBQT-converted SDF files using RDKit.",
    )
    src = p.add_mutually_exclusive_group()
    src.add_argument("--smiles",       metavar="SMILES", help="SMILES with correct bonds")
    src.add_argument("--template-sdf", metavar="FILE",   help="Reference SDF with correct bonds")
    src.add_argument("--smiles-file",  metavar="FILE",   help="SMILES+name file (for --input-dir)")

    p.add_argument("--input",      metavar="FILE")
    p.add_argument("--output",     metavar="FILE")
    p.add_argument("--input-dir",  metavar="DIR")
    p.add_argument("--output-dir", metavar="DIR")
    p.add_argument("--pose-index", metavar="N", type=int, default=0,
                   help="0-based pose to fix (default 0 = best pose)")
    p.add_argument("--all-poses",  action="store_true", help="Fix ALL poses in SDF")
    p.add_argument("--validate",   action="store_true", help="Sanity-check after writing")
    return p


def main() -> None:
    args = _build_parser().parse_args()

    if args.input_dir:
        if not args.smiles_file:
            sys.exit("ERROR: --smiles-file required with --input-dir")
        if not args.output_dir:
            sys.exit("ERROR: --output-dir required with --input-dir")
        fix_bond_orders_dir(args.input_dir, args.output_dir, args.smiles_file)
        return

    if not args.input:
        sys.exit("ERROR: --input required")
    if not args.output:
        sys.exit("ERROR: --output required")
    if args.smiles is None and args.template_sdf is None:
        sys.exit("ERROR: provide --smiles or --template-sdf")

    if args.all_poses:
        fix_bond_orders_batch(
            input_sdf=args.input, output_sdf=args.output,
            smiles=args.smiles, template_sdf=args.template_sdf,
        )
    else:
        fix_bond_orders_single(
            input_sdf=args.input, output_sdf=args.output,
            smiles=args.smiles, template_sdf=args.template_sdf,
            pose_index=args.pose_index,
        )

    if args.validate and args.smiles:
        validate_fix(args.smiles, args.output)


if __name__ == "__main__":
    main()
