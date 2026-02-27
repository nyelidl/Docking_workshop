#!/usr/bin/env python3
"""
AutoDock Vina 1.2.7 — Streamlit Docking Interface
Tabs: Basic (single ligand) | Batch (multi-ligand, Vina)
"""

import streamlit as st
import os, sys, subprocess, tempfile, shutil, io, zipfile, re as _re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import streamlit.components.v1 as components

# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AutoDock Vina 1.2.7",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Global CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

html, body, [data-testid="stAppViewContainer"] {
    background-color: #0d1117;
    color: #c9d1d9;
    font-family: 'IBM Plex Sans', sans-serif;
}
[data-testid="stSidebar"] { background: #161b22; }
[data-testid="stHeader"]  { background: transparent; }

h1 { font-family: 'IBM Plex Mono', monospace; color: #58a6ff; letter-spacing: -1px; }
h2, h3 { font-family: 'IBM Plex Mono', monospace; color: #79c0ff; }

.step-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-left: 4px solid #58a6ff;
    border-radius: 8px;
    padding: 20px 24px;
    margin-bottom: 24px;
}
.step-card.done    { border-left-color: #3fb950; }
.step-card.running { border-left-color: #d29922; }

.step-title {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.85rem; color: #8b949e;
    text-transform: uppercase; letter-spacing: 2px; margin-bottom: 4px;
}
.step-heading {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 1.3rem; color: #e6edf3; margin-bottom: 16px;
}
.result-pill {
    display: inline-block;
    background: #1f6feb22; border: 1px solid #1f6feb; color: #79c0ff;
    border-radius: 20px; padding: 2px 12px;
    font-family: 'IBM Plex Mono', monospace; font-size: 0.8rem; margin: 2px;
}
.success-pill {
    display: inline-block;
    background: #23863622; border: 1px solid #238636; color: #3fb950;
    border-radius: 20px; padding: 4px 14px;
    font-family: 'IBM Plex Mono', monospace; font-size: 0.85rem;
}
.warn-pill {
    display: inline-block;
    background: #9e680322; border: 1px solid #9e6803; color: #d29922;
    border-radius: 20px; padding: 4px 14px;
    font-family: 'IBM Plex Mono', monospace; font-size: 0.85rem;
}
.log-box {
    background: #0d1117; border: 1px solid #30363d; border-radius: 6px;
    padding: 12px 16px;
    font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem; color: #8b949e;
    max-height: 220px; overflow-y: auto; white-space: pre-wrap;
}
.score-best  { font-family: 'IBM Plex Mono', monospace; font-size: 2.4rem; color: #3fb950; font-weight: 600; }
.score-unit  { font-size: 1rem; color: #8b949e; }
.stButton > button {
    background: #238636; color: white; border: none; border-radius: 6px;
    font-family: 'IBM Plex Mono', monospace; font-size: 0.88rem;
    padding: 8px 20px; transition: background 0.2s;
}
.stButton > button:hover { background: #2ea043; }
.stButton > button[kind="secondary"] { background: #21262d; border: 1px solid #30363d; }
.stButton > button[kind="secondary"]:hover { background: #30363d; }
.stTextInput > div > div > input,
.stSelectbox > div > div,
.stNumberInput > div > div > input {
    background: #21262d !important; border: 1px solid #30363d !important;
    color: #c9d1d9 !important; border-radius: 6px !important;
    font-family: 'IBM Plex Mono', monospace !important;
}
.stSlider > div { color: #c9d1d9; }
[data-baseweb="slider"] { accent-color: #58a6ff; }
.stDataFrame { border: 1px solid #30363d; border-radius: 6px; }
hr { border-color: #30363d; }
.step-divider { border: none; border-top: 1px dashed #30363d; margin: 32px 0; }
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: #161b22; border-bottom: 1px solid #30363d; gap: 4px;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    font-family: 'IBM Plex Mono', monospace; font-size: 0.9rem;
    color: #8b949e; background: transparent; border-radius: 6px 6px 0 0;
    padding: 10px 20px;
}
[data-testid="stTabs"] [aria-selected="true"] {
    color: #58a6ff !important; background: #0d1117 !important;
    border-bottom: 2px solid #58a6ff !important;
}
</style>
""", unsafe_allow_html=True)

# ─── Session State ─────────────────────────────────────────────────────────────
_DEFAULTS = dict(
    workdir=None,
    # Basic tab: receptor
    pdb_token=None, raw_pdb=None, receptor_fh=None, receptor_pdbqt=None,
    box_pdb=None, config_txt=None, cx=None, cy=None, cz=None,
    ligand_pdb_path=None, receptor_done=False, receptor_log="",
    # Basic tab: ligand
    ligand_pdbqt=None, ligand_sdf=None, ligand_name="ELR",
    prot_smiles=None, pka_est=None, ligand_done=False, ligand_log="",
    # Basic tab: docking
    output_pdbqt=None, output_sdf=None, dock_base=None,
    docking_done=False, docking_log="",
    score_df=None, pose_mols=None, pose_dir=None,
    # Batch tab: receptor (b_ prefix)
    b_pdb_token=None, b_raw_pdb=None, b_receptor_fh=None, b_receptor_pdbqt=None,
    b_box_pdb=None, b_config_txt=None, b_cx=None, b_cy=None, b_cz=None,
    b_ligand_pdb_path=None, b_receptor_done=False, b_receptor_log="",
    # Batch tab: docking
    b_batch_done=False, b_batch_results=None, b_batch_log="",
    b_redock_score=None, b_redock_sdf=None, b_batch_engine="VINA",
)
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── Working Directories ───────────────────────────────────────────────────────
if st.session_state.workdir is None:
    st.session_state.workdir = tempfile.mkdtemp(prefix="vina_")
WORKDIR       = Path(st.session_state.workdir)
BATCH_WORKDIR = WORKDIR / "batch"
BATCH_WORKDIR.mkdir(exist_ok=True)

# ─── Shared Helpers ────────────────────────────────────────────────────────────
def show3d(view, height=480):
    """Render py3Dmol view responsively inside Streamlit."""
    try:
        from stmol import showmol
        showmol(view, height=height)
    except ImportError:
        raw  = view._make_html()
        resp = _re.sub(r'(width\s*[:=]\s*)["\']?\d+px?["\']?', r'\g<1>100%', raw)
        components.html(f'<div style="width:100%;overflow:hidden">{resp}</div>',
                        height=height, scrolling=False)

def _pill(text, kind="info"):
    cls = {"info":"result-pill","success":"success-pill","warn":"warn-pill"}.get(kind,"result-pill")
    return f'<span class="{cls}">{text}</span>'

def run_cmd(cmd, cwd=None):
    r = subprocess.run(cmd, shell=isinstance(cmd, str),
                       capture_output=True, text=True, cwd=cwd)
    return r.returncode, (r.stdout + r.stderr).strip()

def _rdkit_six_patch():
    try:
        from rdkit import six  # noqa
    except ImportError:
        from io import StringIO as _SIO
        from types import ModuleType as _MT
        import rdkit as _rdkit
        _m = _MT("six"); _m.StringIO = _SIO; _m.PY3 = True
        _rdkit.six = _m; sys.modules["rdkit.six"] = _m

# ─── Cached Resources ──────────────────────────────────────────────────────────
@st.cache_resource(show_spinner="⬇ Downloading Vina 1.2.7…")
def _get_vina():
    path = "/tmp/vina_1.2.7"
    if not os.path.exists(path) or os.path.getsize(path) < 100_000:
        rc, out = run_cmd(["wget", "-q",
            "https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/"
            "v1.2.7/vina_1.2.7_linux_x86_64", "-O", path])
        if rc != 0: return None, out
    os.chmod(path, 0o755)
    return path, "ok"

@st.cache_resource(show_spinner="Loading pKa model…")
def _get_pka_model():
    try:
        from pkapredict import load_model
        return load_model()
    except Exception:
        return None

VINA_PATH, _vina_err = _get_vina()
PKA_MODEL             = _get_pka_model()

# ─── Shared receptor prep exclusion lists ─────────────────────────────────────
_EXCLUDE_IONS   = set("HOH,WAT,DOD,SOL,NA,CL,K,CA,MG,ZN,MN,FE,CU,CO,NI,CD,HG".split(","))
_GLYCAN_NAMES   = {"NAG","BMA","MAN","FUC","GAL","GLC","SIA","NGA","FUL","GLA","BGC"}
_COFACTOR_NAMES = {"ATP","ADP","AMP","GTP","GDP","FAD","FMN","HEM","GOL","PEG","EDO","SO4","PO4"}


# ──────────────────────────────────────────────────────────────────────────────
#  _receptor_section(pfx, wdir, step_label)
#  Shared UI function for receptor preparation.
#  pfx=""   → basic tab  (widget/state keys like "src_mode", "receptor_done" …)
#  pfx="b_" → batch tab  (widget/state keys like "b_src_mode", "b_receptor_done" …)
# ──────────────────────────────────────────────────────────────────────────────
def _receptor_section(pfx: str, wdir: Path, step_label: str = "Step 1"):
    import py3Dmol
    done     = st.session_state.get(pfx + "receptor_done", False)
    card_cls = "step-card done" if done else "step-card"

    st.markdown(f'<div class="{card_cls}">', unsafe_allow_html=True)
    st.markdown(f'<div class="step-title">{step_label}</div>', unsafe_allow_html=True)
    st.markdown('<div class="step-heading">📦 Receptor Preparation</div>', unsafe_allow_html=True)

    col_r1, col_r2 = st.columns([1.2, 1])
    with col_r1:
        source_mode = st.radio("PDB source",
            ["Download from RCSB", "Upload PDB file"],
            horizontal=True, key=pfx+"src_mode")
        if source_mode == "Download from RCSB":
            pdb_id_input = st.text_input("PDB ID", value="1M17", max_chars=4, key=pfx+"pdb_id")
            uploaded_pdb = None
        else:
            uploaded_pdb = st.file_uploader("Upload .pdb file", type=["pdb"], key=pfx+"pdb_upload")
            pdb_id_input = None

        center_mode = st.radio("Grid center",
            ["Auto-detect co-crystal ligand", "Enter XYZ manually"],
            horizontal=True, key=pfx+"center_mode")
        if center_mode == "Enter XYZ manually":
            m1, m2, m3 = st.columns(3)
            mx = m1.number_input("X", value=0.0, key=pfx+"mx")
            my = m2.number_input("Y", value=0.0, key=pfx+"my")
            mz = m3.number_input("Z", value=0.0, key=pfx+"mz")

    with col_r2:

        b_exh = st.slider("Exhaustiveness", 4, 32, 8, 2, key="b_exh")
        b_nm  = st.slider("Poses per ligand", 5, 20, 10, 1, key="b_nm")
        b_er  = st.slider("Energy range (kcal/mol)", 1, 5, 3, 1, key="b_er")

    run_batch_btn = st.button("▶ Run Batch Docking", key="b_btn_dock", type="primary",
                              disabled=not b_rec_done)
    if not b_rec_done:
        st.caption("⚠ Complete Step B1 first.")

    # ── Batch run ─────────────────────────────────────────────────────────────
    if run_batch_btn:
        _rdkit_six_patch()
        from rdkit import Chem; from rdkit.Chem import AllChem
        from meeko import MoleculePreparation

        b_ph_val      = st.session_state.get("b_ph", 7.4)
        actual_engine = "VINA"
        rec_pdbqt     = st.session_state.get("b_receptor_pdbqt")
        config        = st.session_state.get("b_config_txt")

        # ── Parse SMILES input ─────────────────────────────────────────────
        smiles_pairs = []
        try:
            mode = st.session_state.get("b_input_mode", "SMILES list (text)")
            if mode == "SMILES list (text)":
                for line in st.session_state.get("b_smiles_text","").strip().splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"): continue
                    pts  = line.split(None, 1)
                    smiles_pairs.append((pts[0],
                        pts[1].replace(" ","_") if len(pts)>1 else f"lig_{len(smiles_pairs)+1}"))
            elif mode == "Upload .smi file":
                fobj = st.session_state.get("b_smi_file")
                if fobj is None: raise ValueError("No .smi file uploaded")
                for line in fobj.read().decode().splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"): continue
                    pts  = line.split(None, 1)
                    smiles_pairs.append((pts[0],
                        pts[1].replace(" ","_") if len(pts)>1 else f"lig_{len(smiles_pairs)+1}"))
            else:
                fobj = st.session_state.get("b_struct_file")
                if fobj is None: raise ValueError("No structure file uploaded")
                ext  = Path(fobj.name).suffix.lower()
                tmp  = str(BATCH_WORKDIR / f"input{ext}")
                with open(tmp,"wb") as f: f.write(fobj.read())
                if ext == ".sdf":
                    for i, mol in enumerate(Chem.SDMolSupplier(tmp, sanitize=True)):
                        if mol is None: continue
                        nm = mol.GetProp("_Name") if mol.HasProp("_Name") else f"lig_{i+1}"
                        smiles_pairs.append((Chem.MolToSmiles(mol), nm.replace(" ","_")))
                else:
                    run_cmd(f'obabel "{tmp}" -O "{tmp}.smi" --gen2D 2>/dev/null')
                    for line in open(f"{tmp}.smi"):
                        pts = line.strip().split(None, 1)
                        if pts: smiles_pairs.append((pts[0],
                            pts[1].replace(" ","_") if len(pts)>1 else f"lig_{len(smiles_pairs)+1}"))
            if not smiles_pairs: raise ValueError("No valid SMILES found")
        except Exception as e:
            st.error(f"❌ Input parsing failed: {e}"); st.stop()

        # Stereo enumeration
        if st.session_state.get("b_stereo", False):
            from rdkit.Chem.EnumerateStereoisomers import (
                EnumerateStereoisomers, StereoEnumerationOptions)
            expanded = []
            for smi, nm in smiles_pairs:
                mol = Chem.MolFromSmiles(smi)
                if mol is None: expanded.append((smi, nm)); continue
                isomers = list(EnumerateStereoisomers(mol,
                    options=StereoEnumerationOptions(unique=True, maxIsomers=2)))
                expanded.append((Chem.MolToSmiles(isomers[0]) if isomers else smi, nm))
            smiles_pairs = expanded

        # ── Inner helpers ──────────────────────────────────────────────────
        def _prep_one(smi, name, ph, wdir):
            try:
                prot = smi
                try:
                    from dimorphite_dl import protonate_smiles
                    vs = protonate_smiles(prot, ph_min=ph, ph_max=ph, max_variants=1)
                    if vs: prot = vs[0]
                except Exception: pass
                mol = Chem.MolFromSmiles(prot)
                if mol is None: raise ValueError(f"Cannot parse: {smi[:50]}")
                mol = Chem.AddHs(mol)
                try:    params = AllChem.ETKDGv3()
                except: params = AllChem.ETKDG()
                params.randomSeed = 42
                if AllChem.EmbedMolecule(mol, params) == -1:
                    AllChem.EmbedMolecule(mol, useRandomCoords=True, randomSeed=42)
                if AllChem.MMFFHasAllMoleculeParams(mol): AllChem.MMFFOptimizeMolecule(mol, maxIters=500)
                else:                                     AllChem.UFFOptimizeMolecule(mol, maxIters=500)
                sdf_path   = str(wdir / f"{name}.sdf")
                pdbqt_path = str(wdir / f"{name}.pdbqt")
                with Chem.SDWriter(sdf_path) as w: w.write(mol)
                prep = MoleculePreparation()
                from meeko import PDBQTWriterLegacy
                mol_setups = prep.prepare(mol)
                pdbqt_str, _, _ = PDBQTWriterLegacy.write_string(mol_setups[0])
                with open(pdbqt_path, "w") as f: f.write(pdbqt_str)
                return pdbqt_path, None
            except Exception as e:
                return None, str(e)

        def _dock_one(pdbqt_in, name, engine, exh, nm, er):
            bin_p     = VINA_PATH
            out_pdbqt = str(BATCH_WORKDIR / f"{name}_out.pdbqt")
            out_sdf   = str(BATCH_WORKDIR / f"{name}_out.sdf")
            rc, log   = run_cmd(
                f'"{bin_p}" --receptor "{rec_pdbqt}" --ligand "{pdbqt_in}" '
                f'--config "{config}" --exhaustiveness {exh} --num_modes {nm} '
                f'--energy_range {er} --out "{out_pdbqt}"',
                cwd=str(BATCH_WORKDIR))
            if rc != 0 or not os.path.exists(out_pdbqt):
                return None, None, log, None
            run_cmd(f'obabel "{out_pdbqt}" -O "{out_sdf}" 2>/dev/null')
            top = None
            for line in open(out_pdbqt):
                ln = line.strip()
                if ln.startswith("REMARK VINA RESULT:"):
                    try: top = float(ln.split()[3]); break
                    except: pass
            return out_pdbqt, out_sdf, log, top

        # ── Redocking ─────────────────────────────────────────────────────
        redock_score = None; redock_sdf = None
        if st.session_state.get("b_do_redock", False):
            raw_rd = st.session_state.get("b_redock_smiles","").strip()
            pts    = raw_rd.split(None, 1)
            rd_smi = pts[0]
            rd_nm  = pts[1].replace(" ","_") if len(pts)>1 else "redock"
            with st.spinner(f"Redocking reference ligand ({rd_nm})…"):
                rd_pdbqt, rd_err = _prep_one(rd_smi, "redock_"+rd_nm, b_ph_val, BATCH_WORKDIR)
                if rd_pdbqt:
                    _, rd_sdf_out, rd_log, rd_top = _dock_one(
                        rd_pdbqt, "redock_"+rd_nm, actual_engine, b_exh, b_nm, b_er)
                    if rd_top is not None:
                        redock_score = rd_top; redock_sdf = rd_sdf_out
                        st.success(f"✓ Redock reference: **{redock_score:.2f} kcal/mol** ({rd_nm})")
                    else:
                        st.warning(f"⚠ Redocking failed. {rd_log[:200]}")
                else:
                    st.warning(f"⚠ Redock prep failed: {rd_err}")

        # ── Main batch loop ────────────────────────────────────────────────
        results  = []
        n        = len(smiles_pairs)
        prog     = st.progress(0, text=f"Docking 0/{n}…")
        log_slot = st.empty()
        all_logs = []

        for i, (smi, name) in enumerate(smiles_pairs):
            prog.progress(i/n, text=f"Docking {name} ({i+1}/{n})…")
            pdbqt_in, prep_err = _prep_one(smi, name, b_ph_val, BATCH_WORKDIR)
            if pdbqt_in is None:
                results.append({"Name":name,"SMILES":smi,"Top Score":None,
                                 "Poses":0,"Status":f"PREP FAILED: {prep_err}"})
                all_logs.append(f"[{name}] PREP ERROR: {prep_err}"); continue
            out_pdbqt, out_sdf, dock_log, top = _dock_one(
                pdbqt_in, name, actual_engine, b_exh, b_nm, b_er)
            all_logs.append(f"[{name}] score={top} | {dock_log[:120]}")
            log_slot.markdown(
                f'<div class="log-box">{"".join(all_logs[-5:])}</div>',
                unsafe_allow_html=True)
            if top is None:
                results.append({"Name":name,"SMILES":smi,"Top Score":None,
                                 "Poses":0,"Status":"DOCK FAILED"}); continue
            n_poses = 0
            if out_sdf and os.path.exists(out_sdf):
                n_poses = sum(1 for m in Chem.SDMolSupplier(out_sdf, sanitize=False) if m)
            results.append({"Name":name,"SMILES":smi,"Top Score":top,"Poses":n_poses,
                             "out_pdbqt":out_pdbqt,"out_sdf":out_sdf,"Status":"OK"})

        prog.progress(1.0, text=f"✓ Complete — {n} ligands docked")
        log_slot.empty()
        st.session_state.update({
            "b_batch_done": True, "b_batch_results": results,
            "b_batch_log": "\n".join(all_logs),
            "b_redock_score": redock_score, "b_redock_sdf": redock_sdf,
            "b_batch_engine": actual_engine,
        })

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<hr class="step-divider">', unsafe_allow_html=True)

    # ── Step B3: Results ──────────────────────────────────────────────────────
    b_batch_done = st.session_state.get("b_batch_done", False)
    card_cls = "step-card done" if b_batch_done else "step-card"
    st.markdown(f'<div class="{card_cls}">', unsafe_allow_html=True)
    st.markdown('<div class="step-title">Step B3 of B4</div>', unsafe_allow_html=True)
    st.markdown('<div class="step-heading">📊 Batch Results</div>', unsafe_allow_html=True)

    if not b_batch_done:
        st.info("Complete Step B2 to see batch results here.")
    else:
        import py3Dmol
        from rdkit import Chem
        results      = st.session_state.get("b_batch_results", [])
        redock_score = st.session_state.get("b_redock_score")
        engine_used  = st.session_state.get("b_batch_engine", "VINA")

        n_ok = sum(1 for r in results if r["Status"]=="OK")
        n_fail = len(results) - n_ok
        st.markdown(
            f"{_pill(f'{n_ok} ligands docked ✓','success')} {_pill(f'Engine: {engine_used}')}"
            + (f" {_pill(f'{n_fail} failed','warn')}" if n_fail else ""),
            unsafe_allow_html=True)
        with st.expander("📋 Full docking log", expanded=False):
            st.markdown(f'<div class="log-box">{st.session_state.get("b_batch_log","")}</div>',
                        unsafe_allow_html=True)

        # Score table + dot plot
        df_res = pd.DataFrame([{"Name":r["Name"],"Top Score (kcal/mol)":r["Top Score"],
                                  "Poses":r["Poses"],"Status":r["Status"]} for r in results])
        ok_df  = (df_res[df_res["Status"]=="OK"]
                  .sort_values("Top Score (kcal/mol)").reset_index(drop=True))

        ct2, cp2 = st.columns([1, 1.6])
        with ct2:
            st.markdown("**Score Table**")
            st.dataframe(df_res, width='stretch', hide_index=True)
        with cp2:
            st.markdown(f"**Top Score per Ligand** — {engine_used}")
            if not ok_df.empty:
                fig, ax = plt.subplots(figsize=(max(5, len(ok_df)*0.6+1.5), 4))
                fig.patch.set_facecolor("#161b22"); ax.set_facecolor("#0d1117")
                scores = ok_df["Top Score (kcal/mol)"].values
                names  = ok_df["Name"].values
                best_i = int(np.argmin(scores))
                colors = ["#3fb950" if i==best_i else "#58a6ff" for i in range(len(scores))]
                ax.scatter(names, scores, color=colors, s=90, zorder=3,
                           edgecolors="#30363d", linewidths=0.5)
                ax.plot(names, scores, color="#30363d", linewidth=0.8, zorder=2)
                if redock_score is not None:
                    ax.axhline(redock_score, color="#f85149", linewidth=1.5,
                               linestyle="--", label=f"Co-crystal ref: {redock_score:.2f}")
                    ax.legend(facecolor="#21262d", edgecolor="#30363d",
                              labelcolor="#c9d1d9", fontsize=8)
                ax.invert_yaxis()
                ax.set_ylabel(f"{engine_used} score (kcal/mol)", color="#8b949e", fontsize=9)
                ax.set_xlabel("Ligand", color="#8b949e", fontsize=9)
                ax.tick_params(colors="#8b949e", labelsize=7)
                plt.xticks(rotation=40, ha="right")
                for sp in ax.spines.values(): sp.set_edgecolor("#30363d")
                ax.grid(axis="y", color="#21262d", linewidth=0.5)
                fig.tight_layout()
                st.pyplot(fig, width='stretch'); plt.close(fig)

        st.markdown("---")

        # Pose browser
        st.markdown("**🔎 Pose Browser**")
        ok_results = [r for r in results
                      if r["Status"]=="OK" and r.get("out_sdf") and os.path.exists(r["out_sdf"])]
        if ok_results:
            sel_nm  = st.selectbox("Select ligand", [r["Name"] for r in ok_results], key="b_lig_sel")
            sel_res = next(r for r in ok_results if r["Name"]==sel_nm)
            b_mols  = [m for m in Chem.SDMolSupplier(sel_res["out_sdf"], sanitize=False) if m]
            if b_mols:
                b_pose_i = st.slider("Pose", 1, len(b_mols), 1, key="b_pose_sel") - 1
                top_s    = sel_res["Top Score"]
                st.markdown(
                    f'{_pill(f"Pose {b_pose_i+1}/{len(b_mols)}")} '
                    f'{_pill(f"Top: {top_s:.2f} kcal/mol","success" if top_s<-8 else "warn")}',
                    unsafe_allow_html=True)
                cbv, cbd = st.columns([3, 1])
                with cbv:
                    try:
                        vb = py3Dmol.view(width="100%", height=420)
                        vb.setBackgroundColor("#0d1117"); bmi = 0
                        rec_fh = st.session_state.get("b_receptor_fh")
                        if rec_fh and os.path.exists(rec_fh):
                            vb.addModel(open(rec_fh).read(), "pdb")
                            vb.setStyle({"model":bmi}, {"cartoon":{"color":"spectrum","opacity":0.55},
                                                         "stick":{"radius":0.08,"opacity":0.15}}); bmi+=1
                        lig_p = st.session_state.get("b_ligand_pdb_path")
                        if lig_p and os.path.exists(lig_p):
                            vb.addModel(open(lig_p).read(), "pdb")
                            vb.setStyle({"model":bmi}, {"stick":{"colorscheme":"magentaCarbon","radius":0.2}}); bmi+=1
                        vb.addModel(Chem.MolToMolBlock(b_mols[b_pose_i]), "mol")
                        vb.setStyle({"model":bmi}, {"stick":{"colorscheme":"cyanCarbon","radius":0.28}})
                        vb.zoomTo(); show3d(vb, height=420)
                    except Exception as e: st.info(f"Viewer error: {e}")
                with cbd:
                    st.markdown("**Download**")
                    sp3 = str(BATCH_WORKDIR / f"{sel_nm}_pose{b_pose_i+1}.sdf")
                    with Chem.SDWriter(sp3) as w: w.write(b_mols[b_pose_i])
                    st.download_button(f"⬇ Pose {b_pose_i+1} (.sdf)", open(sp3,"rb"),
                        file_name=f"{sel_nm}_pose{b_pose_i+1}.sdf", key="b_dl_pose")
                    st.download_button("⬇ All poses (.pdbqt)",
                        open(sel_res["out_pdbqt"],"rb"),
                        file_name=f"{sel_nm}_out.pdbqt", key="b_dl_pdbqt")

        st.markdown("---")

        # Bulk downloads
        st.markdown("**⬇ Download All Results**")
        c_csv, c_zip = st.columns(2)
        with c_csv:
            if not ok_df.empty:
                st.download_button("⬇ Top scores (.csv)",
                    ok_df.to_csv(index=False).encode(),
                    file_name="batch_scores.csv", mime="text/csv", key="b_dl_csv")
        with c_zip:
            zb = io.BytesIO()
            with zipfile.ZipFile(zb, "w", zipfile.ZIP_DEFLATED) as zf:
                for r in ok_results:
                    if r.get("out_sdf") and os.path.exists(r["out_sdf"]):
                        zf.write(r["out_sdf"], f"poses/{r['Name']}_out.sdf")
                    if r.get("out_pdbqt") and os.path.exists(r["out_pdbqt"]):
                        zf.write(r["out_pdbqt"], f"pdbqt/{r['Name']}_out.pdbqt")
                if not ok_df.empty:
                    zf.writestr("batch_scores.csv", ok_df.to_csv(index=False))
                rec_fh = st.session_state.get("b_receptor_fh")
                if rec_fh and os.path.exists(rec_fh):
                    zf.write(rec_fh, "receptor.pdb")
            zb.seek(0)
            st.download_button("⬇ All results (.zip)", zb,
                file_name="batch_docking_results.zip",
                mime="application/zip", key="b_dl_zip")

    st.markdown('</div>', unsafe_allow_html=True)


# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown('<hr class="step-divider">', unsafe_allow_html=True)
st.markdown(
    '<div style="text-align:center;color:#484f58;font-size:0.78rem;'
    'font-family:\'IBM Plex Mono\',monospace;">'
    'AutoDock Vina 1.2.7 · Meeko · RDKit · OpenBabel · py3Dmol<br>'
    'Eberhardt et al. J. Chem. Inf. Model. 2021, 61, 3891–3898 &nbsp;·&nbsp; '
    '<a href="https://pubs.acs.org/doi/10.1021/acs.jcim.5c02852" target="_blank" '
    'style="color:#58a6ff;text-decoration:none;">'
    'DFDD — Hengphasatporn et al. J. Chem. Inf. Model. 2026</a>'
    '</div>',
    unsafe_allow_html=True,
)
