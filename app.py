#!/usr/bin/env python3
"""
AutoDock Vina 1.2.7 — Streamlit Docking Interface
Single-page, top-to-bottom molecular docking workflow.
"""

import streamlit as st
import os, sys, subprocess, tempfile, shutil, io
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from pathlib import Path
import streamlit.components.v1 as components

# ─── Page Config (must be first Streamlit call) ────────────────────────────────
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
[data-testid="stHeader"] { background: transparent; }

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
.step-card.done { border-left-color: #3fb950; }
.step-card.running { border-left-color: #d29922; }

.step-title {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.85rem;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-bottom: 4px;
}
.step-heading {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 1.3rem;
    color: #e6edf3;
    margin-bottom: 16px;
}

.result-pill {
    display: inline-block;
    background: #1f6feb22;
    border: 1px solid #1f6feb;
    color: #79c0ff;
    border-radius: 20px;
    padding: 2px 12px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.8rem;
    margin: 2px;
}
.success-pill {
    display: inline-block;
    background: #23863622;
    border: 1px solid #238636;
    color: #3fb950;
    border-radius: 20px;
    padding: 4px 14px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.85rem;
}
.warn-pill {
    display: inline-block;
    background: #9e680322;
    border: 1px solid #9e6803;
    color: #d29922;
    border-radius: 20px;
    padding: 4px 14px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.85rem;
}

.log-box {
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 12px 16px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.78rem;
    color: #8b949e;
    max-height: 220px;
    overflow-y: auto;
    white-space: pre-wrap;
}

.score-best {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 2.4rem;
    color: #3fb950;
    font-weight: 600;
}
.score-unit {
    font-size: 1rem;
    color: #8b949e;
}

/* Streamlit widget overrides */
.stButton > button {
    background: #238636;
    color: white;
    border: none;
    border-radius: 6px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.88rem;
    padding: 8px 20px;
    transition: background 0.2s;
}
.stButton > button:hover { background: #2ea043; }
.stButton > button[kind="secondary"] { background: #21262d; border: 1px solid #30363d; }
.stButton > button[kind="secondary"]:hover { background: #30363d; }

.stTextInput > div > div > input,
.stSelectbox > div > div,
.stNumberInput > div > div > input {
    background: #21262d !important;
    border: 1px solid #30363d !important;
    color: #c9d1d9 !important;
    border-radius: 6px !important;
    font-family: 'IBM Plex Mono', monospace !important;
}
.stSlider > div { color: #c9d1d9; }
[data-baseweb="slider"] { accent-color: #58a6ff; }

.stDataFrame { border: 1px solid #30363d; border-radius: 6px; }
hr { border-color: #30363d; }

/* Divider between steps */
.step-divider {
    border: none;
    border-top: 1px dashed #30363d;
    margin: 32px 0;
}
</style>
""", unsafe_allow_html=True)

# ─── Session State ─────────────────────────────────────────────────────────────
_DEFAULTS = dict(
    workdir=None,
    # Receptor
    pdb_token=None, raw_pdb=None, receptor_fh=None, receptor_pdbqt=None,
    box_pdb=None, config_txt=None,
    cx=None, cy=None, cz=None,
    ligand_pdb_path=None, receptor_done=False, receptor_log="",
    # Ligand
    ligand_pdbqt=None, ligand_sdf=None, ligand_name="ELR",
    prot_smiles=None, pka_est=None, ligand_done=False, ligand_log="",
    # Docking
    output_pdbqt=None, output_sdf=None, dock_base=None,
    docking_done=False, docking_log="",
    # Results
    score_df=None, pose_mols=None, pose_dir=None,
)
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── Working Directory ─────────────────────────────────────────────────────────
if st.session_state.workdir is None:
    st.session_state.workdir = tempfile.mkdtemp(prefix="vina_")
WORKDIR = Path(st.session_state.workdir)

# ─── Helpers ──────────────────────────────────────────────────────────────────
def show3d(view, height=520):
    """Render a py3Dmol view inside Streamlit."""
    try:
        from stmol import showmol
        showmol(view, height=height)
    except ImportError:
        components.html(view._make_html(), height=height, scrolling=False)

def _pill(text, kind="info"):
    cls = {"info": "result-pill", "success": "success-pill", "warn": "warn-pill"}.get(kind, "result-pill")
    return f'<span class="{cls}">{text}</span>'

def run_cmd(cmd, cwd=None, log=True):
    r = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, cwd=cwd)
    out = (r.stdout + r.stderr).strip()
    return r.returncode, out

# ─── Cached Resources ──────────────────────────────────────────────────────────
@st.cache_resource(show_spinner="⬇ Downloading Vina 1.2.7 binary…")
def _get_vina():
    path = "/tmp/vina_1.2.7"
    if not os.path.exists(path) or os.path.getsize(path) < 100_000:
        url = ("https://github.com/ccsb-scripps/AutoDock-Vina/releases/"
               "download/v1.2.7/vina_1.2.7_linux_x86_64")
        rc, out = run_cmd(["wget", "-q", url, "-O", path])
        if rc != 0 or not os.path.exists(path):
            return None, out
    os.chmod(path, 0o755)
    return path, "ok"

@st.cache_resource(show_spinner="Loading pKa model…")
def _get_pka_model():
    try:
        from pkapredict import load_model
        return load_model()
    except Exception:
        return None

VINA_PATH, vina_err = _get_vina()
PKA_MODEL = _get_pka_model()

# ─── Header ───────────────────────────────────────────────────────────────────
st.markdown("# 🧬 AutoDock Vina 1.2.7")
st.markdown(
    "Cloud molecular docking powered by **AutoDock Vina**, **RDKit**, **Meeko**, and **OpenBabel**. "
    "Complete each step in order — results persist as you scroll down."
)

st.markdown(
    "🧬 Assembled code for Molecular Docking using AutoDock Vina 1.2.7 &nbsp;|&nbsp; "
    "For questions: [kowith@ccs.tsukuba.ac.jp](mailto:kowith@ccs.tsukuba.ac.jp)  \n"
    "This is part of the **DFDD Project**.",
    unsafe_allow_html=True,
)

if VINA_PATH is None:
    st.error(f"❌ Vina binary could not be downloaded. Error: {vina_err}")
    st.stop()

st.markdown(f"<div style='margin-bottom:8px'>{_pill('Vina 1.2.7 ✓', 'success')} {_pill(f'Workdir: {WORKDIR}', 'info')}</div>", unsafe_allow_html=True)
st.markdown('<hr class="step-divider">', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 1 — RECEPTOR PREPARATION
# ══════════════════════════════════════════════════════════════════════════════
card_class = "step-card done" if st.session_state.receptor_done else "step-card"
st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)
st.markdown('<div class="step-title">Step 1 of 4</div>', unsafe_allow_html=True)
st.markdown('<div class="step-heading">📦 Receptor Preparation</div>', unsafe_allow_html=True)

col_r1, col_r2 = st.columns([1.2, 1])

with col_r1:
    source_mode = st.radio("PDB source", ["Download from RCSB", "Upload PDB file"], horizontal=True, key="src_mode")
    if source_mode == "Download from RCSB":
        pdb_id_input = st.text_input("PDB ID (4 characters)", value="1M17", max_chars=4, key="pdb_id")
        uploaded_pdb = None
    else:
        uploaded_pdb = st.file_uploader("Upload .pdb file", type=["pdb"], key="pdb_upload")
        pdb_id_input = None

    center_mode = st.radio(
        "Grid center",
        ["Auto-detect co-crystal ligand", "Enter XYZ manually"],
        horizontal=True, key="center_mode",
    )
    if center_mode == "Enter XYZ manually":
        m1, m2, m3 = st.columns(3)
        mx = m1.number_input("X", value=0.0, key="mx")
        my = m2.number_input("Y", value=0.0, key="my")
        mz = m3.number_input("Z", value=0.0, key="mz")

with col_r2:
    st.markdown("**Search box size (Å)**")
    sx = st.slider("X size", 10, 40, 16, 2, key="sx")
    sy = st.slider("Y size", 10, 40, 16, 2, key="sy")
    sz = st.slider("Z size", 10, 40, 16, 2, key="sz")
    st.markdown(f"Box volume: **{sx * sy * sz} Å³**")

run_receptor_btn = st.button("▶ Prepare Receptor", key="btn_receptor", type="primary")

if run_receptor_btn:
    import py3Dmol
    from prody import parsePDB, calcCenter, writePDB

    EXCLUDE_IONS = set("HOH,WAT,DOD,SOL,NA,CL,K,CA,MG,ZN,MN,FE,CU,CO,NI,CD,HG".split(","))
    GLYCANS = {"NAG","BMA","MAN","FUC","GAL","GLC","SIA","NGA","FUL","GLA","BGC"}
    COFACTORS = {"ATP","ADP","AMP","GTP","GDP","FAD","FMN","HEM","GOL","PEG","EDO","SO4","PO4"}

    log_lines = []

    with st.spinner("Preparing receptor… this may take 1–2 minutes"):
        try:
            # ── 1. Load PDB ────────────────────────────────────────────────
            raw_pdb_path = str(WORKDIR / "raw.pdb")
            if source_mode == "Download from RCSB":
                token = pdb_id_input.strip().upper()
                rc, out = run_cmd(["curl", "-sf",
                    f"https://files.rcsb.org/download/{token}.pdb", "-o", raw_pdb_path])
                log_lines.append(f"⬇ Downloaded {token}: exit {rc}")
                if rc != 0 or not os.path.exists(raw_pdb_path) or os.path.getsize(raw_pdb_path) < 200:
                    raise ValueError(f"Download failed for {token}")
                st.session_state.pdb_token = token
            else:
                if uploaded_pdb is None:
                    st.error("Please upload a PDB file first.")
                    st.stop()
                with open(raw_pdb_path, "wb") as f:
                    f.write(uploaded_pdb.read())
                st.session_state.pdb_token = Path(uploaded_pdb.name).stem
                log_lines.append(f"📂 Loaded uploaded file: {uploaded_pdb.name}")

            atoms = parsePDB(raw_pdb_path)
            log_lines.append(f"✓ Parsed PDB: {atoms.numAtoms()} atoms")

            # ── 2. Co-crystal ligand detection ─────────────────────────────
            het = atoms.select("hetero and not water")
            ligand_pdb_path = None
            cx, cy, cz = 0.0, 0.0, 0.0

            if het is not None and center_mode == "Auto-detect co-crystal ligand":
                exclude_all = EXCLUDE_IONS | GLYCANS | COFACTORS
                candidates = []
                for res in het.getHierView().iterResidues():
                    rn = (res.getResname() or "").strip()
                    if rn not in exclude_all:
                        candidates.append(res)

                if candidates:
                    # pick largest candidate (most atoms), prefer chain A
                    candidates.sort(key=lambda r: (-r.numAtoms(), r.getChid() != "A"))
                    chosen = candidates[0]
                    lig_sel = atoms.select(
                        f"resname {chosen.getResname()} and resid {chosen.getResnum()} "
                        f"and chain {chosen.getChid()}"
                    )
                    ligand_pdb_path = str(WORKDIR / "LIG.pdb")
                    writePDB(ligand_pdb_path, lig_sel)
                    cx, cy, cz = (float(v) for v in calcCenter(lig_sel))
                    log_lines.append(f"✓ Auto-selected ligand: {chosen.getResname()} "
                                     f"chain {chosen.getChid()} resid {chosen.getResnum()} "
                                     f"({lig_sel.numAtoms()} atoms)")
                    log_lines.append(f"📍 Grid center: ({cx:.3f}, {cy:.3f}, {cz:.3f})")
                    ligand_sel_str = (f"resname {chosen.getResname()} and resid {chosen.getResnum()} "
                                      f"and chain {chosen.getChid()}")
                else:
                    log_lines.append("⚠ No co-crystal ligand found after filtering")
                    ligand_sel_str = None
            else:
                ligand_sel_str = None
                if center_mode == "Enter XYZ manually":
                    cx, cy, cz = mx, my, mz
                    log_lines.append(f"🛠 Manual grid center: ({cx:.3f}, {cy:.3f}, {cz:.3f})")

            # ── 3. Receptor atom selection ──────────────────────────────────
            if ligand_sel_str:
                rec_sel_str = f"not ({ligand_sel_str}) and not water"
            else:
                rec_sel_str = "not water"
            rec_atoms = atoms.select(rec_sel_str)
            receptor_pdb_path = str(WORKDIR / "receptor_atoms.pdb")
            writePDB(receptor_pdb_path, rec_atoms)
            log_lines.append(f"✓ Receptor: {rec_atoms.numAtoms()} atoms written")

            # ── 4. OpenBabel: add H → PDBQT ────────────────────────────────
            rec_fh = str(WORKDIR / "rec.pdb")
            rec_pdbqt = str(WORKDIR / "rec.pdbqt")
            rc1, o1 = run_cmd(f'obabel "{receptor_pdb_path}" -O "{rec_fh}" -h 2>/dev/null')
            log_lines.append(f"obabel -h exit {rc1}")
            if rc1 != 0 or os.path.getsize(rec_fh) < 100:
                raise ValueError("OpenBabel H-addition failed")

            rc2, o2 = run_cmd(
                f'obabel "{rec_fh}" -O "{rec_pdbqt}" -xr --partialcharge gasteiger 2>/dev/null'
            )
            log_lines.append(f"obabel PDBQT exit {rc2}")
            if rc2 != 0 or os.path.getsize(rec_pdbqt) < 100:
                raise ValueError("OpenBabel PDBQT conversion failed")
            log_lines.append(f"✓ Receptor PDBQT: {rec_pdbqt}")

            # ── 5. Box PDB + Vina config ────────────────────────────────────
            box_pdb_path = str(WORKDIR / "rec.box.pdb")
            config_path  = str(WORKDIR / "rec.box.txt")

            hx, hy, hz = sx / 2, sy / 2, sz / 2
            corners = [
                (cx-hx, cy-hy, cz-hz), (cx+hx, cy-hy, cz-hz),
                (cx-hx, cy+hy, cz-hz), (cx+hx, cy+hy, cz-hz),
                (cx-hx, cy-hy, cz+hz), (cx+hx, cy-hy, cz+hz),
                (cx-hx, cy+hy, cz+hz), (cx+hx, cy+hy, cz+hz),
            ]
            with open(box_pdb_path, "w") as f:
                for i, (x, y, z) in enumerate(corners, 1):
                    f.write(f"HETATM{i:5d}  C   BOX A   1    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C\n")
                f.write("CONECT    1    2    3    5\nCONECT    2    1    4    6\n"
                        "CONECT    3    1    4    7\nCONECT    4    2    3    8\n"
                        "CONECT    5    1    6    7\nCONECT    6    2    5    8\n"
                        "CONECT    7    3    5    8\nCONECT    8    4    6    7\n")

            with open(config_path, "w") as f:
                f.write(f"center_x = {cx:.4f}\ncenter_y = {cy:.4f}\ncenter_z = {cz:.4f}\n"
                        f"size_x = {sx}\nsize_y = {sy}\nsize_z = {sz}\n")
            log_lines.append(f"✓ Config written: {config_path}")

            # ── Save to session ────────────────────────────────────────────
            st.session_state.update(dict(
                raw_pdb=raw_pdb_path, receptor_fh=rec_fh, receptor_pdbqt=rec_pdbqt,
                box_pdb=box_pdb_path, config_txt=config_path,
                cx=cx, cy=cy, cz=cz,
                ligand_pdb_path=ligand_pdb_path,
                receptor_done=True, receptor_log="\n".join(log_lines),
            ))

        except Exception as e:
            st.error(f"❌ Receptor preparation failed: {e}")
            st.session_state.receptor_done = False
            st.session_state.receptor_log = "\n".join(log_lines) + f"\n\nERROR: {e}"

# ── Receptor Results ───────────────────────────────────────────────────────────
if st.session_state.receptor_done:
    import py3Dmol
    st.markdown(
        f"{_pill('Receptor ready ✓', 'success')} "
        f"{_pill(st.session_state.pdb_token)} "
        f"{_pill(f'Center: ({st.session_state.cx:.2f}, {st.session_state.cy:.2f}, {st.session_state.cz:.2f})')} "
        f"{_pill(f'Box: {st.session_state.sx}×{st.session_state.sy}×{st.session_state.sz} Å')}",
        unsafe_allow_html=True,
    )
    with st.expander("📋 Preparation log", expanded=False):
        st.markdown(f'<div class="log-box">{st.session_state.receptor_log}</div>', unsafe_allow_html=True)

    # 3D viewer
    with st.expander("🔭 3D: Receptor + Docking Box", expanded=True):
        view = py3Dmol.view(width=820, height=500)
        view.setBackgroundColor("#0d1117")
        idx = 0
        for path, style in [
            (st.session_state.receptor_fh, {"cartoon": {"color": "spectrum", "opacity": 0.65}}),
            (st.session_state.box_pdb,     {"line": {"color": "cyan"}}),
        ]:
            if path and os.path.exists(path):
                view.addModel(open(path).read(), "pdb")
                view.setStyle({"model": idx}, style)
                idx += 1
        if st.session_state.ligand_pdb_path and os.path.exists(st.session_state.ligand_pdb_path):
            view.addModel(open(st.session_state.ligand_pdb_path).read(), "pdb")
            view.setStyle({"model": idx}, {"stick": {"colorscheme": "magentaCarbon", "radius": 0.25}})
        view.zoomTo({"model": 1})
        view.zoom(0.7)
        show3d(view, height=500)

st.markdown('</div>', unsafe_allow_html=True)
st.markdown('<hr class="step-divider">', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 2 — LIGAND PREPARATION
# ══════════════════════════════════════════════════════════════════════════════
card_class = "step-card done" if st.session_state.ligand_done else "step-card"
st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)
st.markdown('<div class="step-title">Step 2 of 4</div>', unsafe_allow_html=True)
st.markdown('<div class="step-heading">⚗️ Ligand Preparation</div>', unsafe_allow_html=True)

col_l1, col_l2 = st.columns([1.5, 1])
with col_l1:
    smiles_input = st.text_input(
        "SMILES string",
        value="COCCOC1=C(C=C2C(=C1)C(=NC=N2)NC3=CC=CC(=C3)C#C)OCCOC",
        help="Enter the canonical SMILES for your ligand",
        key="smiles_in",
    )
    ligand_name_input = st.text_input("Output name (no extension)", value="ELR", key="lig_name_in")
    ph_input = st.number_input("Target pH for protonation", min_value=0.0, max_value=14.0, value=7.4, step=0.1, key="ph_in")

with col_l2:
    st.markdown("**pKa prediction**")
    if PKA_MODEL is not None and smiles_input:
        try:
            from pkapredict import smiles_to_rdkit_descriptors, predict_pKa
            desc = smiles_to_rdkit_descriptors([smiles_input])
            pka_live = float(predict_pKa(PKA_MODEL, desc)[0])
            charged = "deprotonated (−1)" if pka_live < ph_input else "neutral (0)"
            st.markdown(
                f'<div style="background:#1f6feb15;border:1px solid #1f6feb;border-radius:8px;padding:16px;">'
                f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:1.8rem;color:#58a6ff">'
                f'pKa = {pka_live:.2f}</div>'
                f'<div style="color:#8b949e;font-size:0.85rem">at pH {ph_input:.1f}: likely <b style="color:#79c0ff">{charged}</b></div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        except Exception:
            st.info("pKa model unavailable for this SMILES.")
    else:
        st.info("Enter a SMILES to see live pKa estimate.")

run_ligand_btn = st.button("▶ Prepare Ligand", key="btn_ligand", type="primary",
                           disabled=not st.session_state.receptor_done)
if not st.session_state.receptor_done:
    st.caption("⚠ Complete Step 1 first.")

if run_ligand_btn:
    from rdkit import Chem
    from rdkit.Chem import AllChem, Draw
    import io as _io

    log_lines = []

    # rdkit.six compatibility patch for Meeko
    try:
        from rdkit import six as _rdkit_six
    except ImportError:
        from io import StringIO as _SIO
        from types import ModuleType as _MT
        import rdkit as _rdkit
        _m = _MT("six")
        _m.StringIO = _SIO
        _m.PY3 = True
        _rdkit.six = _m
        sys.modules["rdkit.six"] = _m
        log_lines.append("✓ Applied rdkit.six compatibility patch")

    from meeko import MoleculePreparation

    lig_name = ligand_name_input.strip() or "LIG"
    lig_pdbqt = str(WORKDIR / f"{lig_name}.pdbqt")
    lig_sdf   = str(WORKDIR / f"{lig_name}_scrubbed.sdf")

    with st.spinner("Preparing ligand…"):
        try:
            # Protonation
            prot_smiles = smiles_input.strip()
            try:
                from dimorphite_dl import protonate_smiles
                variants = protonate_smiles(prot_smiles, ph_min=ph_input, ph_max=ph_input, max_variants=1)
                if variants:
                    prot_smiles = variants[0]
                    log_lines.append(f"✓ Dimorphite-DL protonation at pH {ph_input}")
                else:
                    log_lines.append("⚠ Dimorphite-DL returned no variants; using input SMILES")
            except Exception as e:
                log_lines.append(f"⚠ Dimorphite-DL unavailable ({e}); using input SMILES")

            mol = Chem.MolFromSmiles(prot_smiles)
            if mol is None:
                raise ValueError("RDKit could not parse SMILES")
            formal_charge = Chem.GetFormalCharge(mol)
            log_lines.append(f"✓ Formal charge at pH {ph_input}: {formal_charge:+d}")

            # 3D conformer
            mol = Chem.AddHs(mol)
            try:
                params = AllChem.ETKDGv3()
            except AttributeError:
                params = AllChem.ETKDG()
            params.randomSeed = 42
            res = AllChem.EmbedMolecule(mol, params)
            if res == -1:
                res = AllChem.EmbedMolecule(mol, useRandomCoords=True, randomSeed=42)
            if res == -1:
                raise ValueError("3D embedding failed")

            if AllChem.MMFFHasAllMoleculeParams(mol):
                AllChem.MMFFOptimizeMolecule(mol, maxIters=500)
                log_lines.append("✓ MMFF geometry optimized")
            else:
                AllChem.UFFOptimizeMolecule(mol, maxIters=500)
                log_lines.append("✓ UFF geometry optimized (MMFF unavailable)")

            with Chem.SDWriter(lig_sdf) as w:
                w.write(mol)
            log_lines.append(f"✓ SDF written: {lig_sdf}")

            # Meeko PDBQT
            prep = MoleculePreparation()
            prep.prepare(mol)
            pdbqt_str = prep.write_pdbqt_string()
            with open(lig_pdbqt, "w") as f:
                f.write(pdbqt_str)
            log_lines.append(f"✓ PDBQT written: {lig_pdbqt}")

            st.session_state.update(dict(
                ligand_pdbqt=lig_pdbqt, ligand_sdf=lig_sdf,
                ligand_name=lig_name, prot_smiles=prot_smiles,
                ligand_done=True, ligand_log="\n".join(log_lines),
            ))

        except Exception as e:
            st.error(f"❌ Ligand preparation failed: {e}")
            st.session_state.ligand_done = False
            st.session_state.ligand_log = "\n".join(log_lines) + f"\n\nERROR: {e}"

# ── Ligand Results ─────────────────────────────────────────────────────────────
if st.session_state.ligand_done:
    from rdkit import Chem
    from rdkit.Chem import AllChem, Draw
    import py3Dmol

    st.markdown(
        f"{_pill('Ligand ready ✓', 'success')} "
        f"{_pill(st.session_state.ligand_name)} "
        f"{_pill(f'PDBQT: {Path(st.session_state.ligand_pdbqt).name}')}",
        unsafe_allow_html=True,
    )
    with st.expander("📋 Preparation log", expanded=False):
        st.markdown(f'<div class="log-box">{st.session_state.ligand_log}</div>', unsafe_allow_html=True)

    col_2d, col_3d = st.columns(2)
    with col_2d:
        st.markdown("**2D Structure**")
        try:
            mol2d = Chem.MolFromSmiles(st.session_state.prot_smiles)
            if mol2d:
                AllChem.Compute2DCoords(mol2d)
                img = Draw.MolToImage(mol2d, size=(320, 260))
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                st.image(buf.getvalue(), use_container_width=False, width=320)
        except Exception as e:
            st.info(f"2D rendering unavailable: {e}")

    with col_3d:
        st.markdown("**3D Conformer**")
        try:
            sdf_content = open(st.session_state.ligand_sdf).read()
            v = py3Dmol.view(width=380, height=280)
            v.setBackgroundColor("#0d1117")
            v.addModel(sdf_content, "sdf")
            v.setStyle({}, {"stick": {"colorscheme": "yellowCarbon", "radius": 0.2}})
            v.zoomTo()
            show3d(v, height=280)
        except Exception as e:
            st.info(f"3D viewer unavailable: {e}")

st.markdown('</div>', unsafe_allow_html=True)
st.markdown('<hr class="step-divider">', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 3 — DOCKING
# ══════════════════════════════════════════════════════════════════════════════
card_class = "step-card done" if st.session_state.docking_done else "step-card"
st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)
st.markdown('<div class="step-title">Step 3 of 4</div>', unsafe_allow_html=True)
st.markdown('<div class="step-heading">🚀 Docking with AutoDock Vina</div>', unsafe_allow_html=True)

col_d1, col_d2 = st.columns([1.5, 1])
with col_d1:
    exhaustiveness = st.slider(
        "Exhaustiveness", min_value=4, max_value=64, value=16, step=2, key="exh_slider",
        help="Higher = more thorough but slower. 8 = fast, 16 = balanced, 32+ = thorough.",
    )
    num_modes = st.slider("Number of poses", 5, 20, 10, 1, key="n_modes")
    energy_range = st.slider("Energy range (kcal/mol)", 1, 5, 3, 1, key="e_range")

with col_d2:
    est_min = max(1, exhaustiveness // 8)
    st.markdown(
        f'<div style="background:#21262d;border:1px solid #30363d;border-radius:8px;padding:16px;">'
        f'<div style="color:#8b949e;font-size:0.8rem">ESTIMATED TIME</div>'
        f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:2rem;color:#d29922">~{est_min}–{est_min*3} min</div>'
        f'<div style="color:#8b949e;font-size:0.8rem">exhaustiveness = {exhaustiveness}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

run_dock_btn = st.button("▶ Run Docking", key="btn_dock", type="primary",
                         disabled=not st.session_state.ligand_done)
if not st.session_state.ligand_done:
    st.caption("⚠ Complete Steps 1 & 2 first.")

if run_dock_btn:
    dock_base = st.session_state.ligand_name
    out_pdbqt = str(WORKDIR / f"{dock_base}_out.pdbqt")
    out_sdf   = str(WORKDIR / f"{dock_base}_out.sdf")

    with st.spinner(f"Running Vina (exhaustiveness={exhaustiveness})… please wait ⏳"):
        cmd = (
            f'"{VINA_PATH}" '
            f'--receptor "{st.session_state.receptor_pdbqt}" '
            f'--ligand "{st.session_state.ligand_pdbqt}" '
            f'--config "{st.session_state.config_txt}" '
            f'--exhaustiveness {exhaustiveness} '
            f'--num_modes {num_modes} '
            f'--energy_range {energy_range} '
            f'--out "{out_pdbqt}"'
        )
        rc, vina_log = run_cmd(cmd, cwd=str(WORKDIR))

        if rc != 0 or not os.path.exists(out_pdbqt):
            st.error(f"❌ Vina failed (exit {rc}):\n{vina_log}")
            st.session_state.docking_done = False
        else:
            # Convert to SDF via obabel
            rc2, _ = run_cmd(f'obabel "{out_pdbqt}" -O "{out_sdf}" 2>/dev/null')
            st.session_state.update(dict(
                output_pdbqt=out_pdbqt, output_sdf=out_sdf, dock_base=dock_base,
                docking_done=True, docking_log=vina_log,
            ))

            # Parse scores
            data = []
            cur_model = None
            for line in open(out_pdbqt):
                line = line.strip()
                if line.startswith("MODEL"):
                    try: cur_model = int(line.split()[1])
                    except: pass
                elif line.startswith("REMARK VINA RESULT:"):
                    parts = line.split()
                    try:
                        data.append({
                            "Pose": cur_model,
                            "Affinity (kcal/mol)": float(parts[3]),
                            "RMSD lb": float(parts[4]),
                            "RMSD ub": float(parts[5]),
                        })
                    except: pass
            if data:
                df = pd.DataFrame(data).sort_values("Affinity (kcal/mol)").reset_index(drop=True)
                st.session_state.score_df = df

            # Load pose molecules
            from rdkit import Chem
            if os.path.exists(out_sdf):
                sup = Chem.SDMolSupplier(out_sdf, sanitize=False)
                st.session_state.pose_mols = [m for m in sup if m is not None]

# ── Docking Results Preview ────────────────────────────────────────────────────
if st.session_state.docking_done:
    st.markdown(f"{_pill('Docking complete ✓', 'success')}", unsafe_allow_html=True)
    with st.expander("📋 Vina output log", expanded=False):
        st.markdown(f'<div class="log-box">{st.session_state.docking_log}</div>', unsafe_allow_html=True)

    if st.session_state.score_df is not None and len(st.session_state.score_df) > 0:
        best = st.session_state.score_df["Affinity (kcal/mol)"].min()
        binding_class = (
            "Very strong" if best < -11 else
            "Strong" if best < -9 else
            "Moderate" if best < -7 else "Weak"
        )
        st.markdown(
            f'<div class="score-best">{best:.2f} '
            f'<span class="score-unit">kcal/mol</span></div>'
            f'<div style="color:#8b949e;font-size:0.9rem;margin-bottom:12px">'
            f'Best pose affinity — {binding_class} predicted binding</div>',
            unsafe_allow_html=True,
        )

st.markdown('</div>', unsafe_allow_html=True)
st.markdown('<hr class="step-divider">', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 4 — RESULTS
# ══════════════════════════════════════════════════════════════════════════════
card_class = "step-card done" if st.session_state.docking_done else "step-card"
st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)
st.markdown('<div class="step-title">Step 4 of 4</div>', unsafe_allow_html=True)
st.markdown('<div class="step-heading">📊 Results & Visualization</div>', unsafe_allow_html=True)

if not st.session_state.docking_done:
    st.info("Complete Step 3 (docking) to see results here.")
else:
    import py3Dmol
    df = st.session_state.score_df
    mols = st.session_state.pose_mols or []
    from rdkit import Chem

    # ── Score table + bar chart ────────────────────────────────────────────
    col_tbl, col_chart = st.columns([1, 1.4])
    with col_tbl:
        st.markdown("**Vina Score Table**")
        if df is not None:
            st.dataframe(
                df.style.background_gradient(cmap="RdYlGn", subset=["Affinity (kcal/mol)"], gmap=-df["Affinity (kcal/mol)"]),
                use_container_width=True, hide_index=True,
            )

    with col_chart:
        st.markdown("**Affinity by Pose**")
        if df is not None:
            fig, ax = plt.subplots(figsize=(6, 3.5))
            fig.patch.set_facecolor("#161b22")
            ax.set_facecolor("#0d1117")

            colors = ["#3fb950" if v == df["Affinity (kcal/mol)"].min() else "#58a6ff"
                      for v in df["Affinity (kcal/mol)"]]
            bars = ax.bar(df["Pose"].astype(str), df["Affinity (kcal/mol)"], color=colors,
                          edgecolor="#30363d", linewidth=0.6)
            ax.invert_yaxis()
            ax.set_xlabel("Pose", color="#8b949e", fontsize=9)
            ax.set_ylabel("Affinity (kcal/mol)", color="#8b949e", fontsize=9)
            ax.tick_params(colors="#8b949e", labelsize=8)
            for spine in ax.spines.values():
                spine.set_edgecolor("#30363d")
            ax.axhline(y=0, color="#30363d", linewidth=0.5)
            fig.tight_layout()
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)

    st.markdown("---")

    # ── Animated pose viewer ───────────────────────────────────────────────
    st.markdown("**🎬 Animated Pose Viewer** — all poses cycling through")
    anim_speed = st.slider("Animation interval (ms)", 500, 3000, 1500, 250, key="anim_spd")

    if os.path.exists(st.session_state.output_sdf):
        sdf_text = open(st.session_state.output_sdf).read()
        v = py3Dmol.view(width=860, height=540)
        v.setBackgroundColor("#0d1117")
        midx = 0
        # Receptor
        if st.session_state.receptor_fh and os.path.exists(st.session_state.receptor_fh):
            v.addModel(open(st.session_state.receptor_fh).read(), "pdb")
            v.setStyle({"model": midx}, {"cartoon": {"color": "spectrum", "opacity": 0.55},
                                          "stick": {"radius": 0.1, "opacity": 0.2}})
            midx += 1
        # Reference ligand
        if st.session_state.ligand_pdb_path and os.path.exists(st.session_state.ligand_pdb_path):
            v.addModel(open(st.session_state.ligand_pdb_path).read(), "pdb")
            v.setStyle({"model": midx}, {"stick": {"colorscheme": "magentaCarbon", "radius": 0.22}})
            midx += 1
        # Docked poses (animated)
        v.addModelsAsFrames(sdf_text)
        v.setStyle({"model": midx}, {"stick": {"colorscheme": "greenCarbon", "radius": 0.25}})
        v.animate({"interval": anim_speed, "loop": "forward"})
        v.zoomTo({"model": 0})
        v.rotate(30)
        show3d(v, height=540)

    st.markdown("---")

    # ── Interactive pose selector ──────────────────────────────────────────
    st.markdown("**🔎 Interactive Pose Selector**")
    if mols:
        pose_idx = st.slider("Select pose", 1, len(mols), 1, key="pose_sel") - 1
        selected_mol = mols[pose_idx]

        # Score for this pose
        if df is not None and pose_idx < len(df):
            row = df.iloc[pose_idx] if "Pose" not in df.columns else df[df["Pose"] == pose_idx + 1]
            if not isinstance(row, pd.Series):
                row = row.iloc[0] if len(row) else None
            if row is not None:
                aff = row["Affinity (kcal/mol)"] if isinstance(row, pd.Series) else None
                if aff is not None:
                    st.markdown(
                        f'{_pill(f"Pose {pose_idx+1}/{len(mols)}")} '
                        f'{_pill(f"Affinity: {aff:.2f} kcal/mol", "success" if aff < -8 else "warn")}',
                        unsafe_allow_html=True,
                    )

        col_pv, col_dl = st.columns([3, 1])
        with col_pv:
            # Render selected pose with receptor
            from rdkit.Chem import AllChem
            try:
                sdf_one = Chem.MolToMolBlock(selected_mol)
                v2 = py3Dmol.view(width=620, height=400)
                v2.setBackgroundColor("#0d1117")
                midx2 = 0
                if st.session_state.receptor_fh and os.path.exists(st.session_state.receptor_fh):
                    v2.addModel(open(st.session_state.receptor_fh).read(), "pdb")
                    v2.setStyle({"model": midx2}, {"cartoon": {"color": "spectrum", "opacity": 0.5},
                                                    "stick": {"radius": 0.08, "opacity": 0.15}})
                    midx2 += 1
                if st.session_state.ligand_pdb_path and os.path.exists(st.session_state.ligand_pdb_path):
                    v2.addModel(open(st.session_state.ligand_pdb_path).read(), "pdb")
                    v2.setStyle({"model": midx2}, {"stick": {"colorscheme": "magentaCarbon", "radius": 0.2}})
                    midx2 += 1
                v2.addModel(sdf_one, "mol")
                v2.setStyle({"model": midx2}, {"stick": {"colorscheme": "cyanCarbon", "radius": 0.28}})
                v2.zoomTo({"model": midx2})
                show3d(v2, height=400)
            except Exception as e:
                st.info(f"Pose viewer error: {e}")

        with col_dl:
            st.markdown("**Download**")
            # Selected pose SDF
            sel_sdf_path = str(WORKDIR / f"pose_{pose_idx+1}.sdf")
            with Chem.SDWriter(sel_sdf_path) as w:
                w.write(selected_mol)
            with open(sel_sdf_path, "rb") as f:
                st.download_button(
                    f"⬇ Pose {pose_idx+1} (.sdf)",
                    f, file_name=f"pose_{pose_idx+1}.sdf", key=f"dl_pose_{pose_idx}",
                )
            # Full output PDBQT
            with open(st.session_state.output_pdbqt, "rb") as f:
                st.download_button(
                    "⬇ All poses (.pdbqt)",
                    f, file_name=f"{st.session_state.dock_base}_out.pdbqt", key="dl_pdbqt",
                )
            # Score CSV
            if df is not None:
                csv_buf = df.to_csv(index=False).encode()
                st.download_button(
                    "⬇ Scores (.csv)",
                    csv_buf, file_name=f"{st.session_state.dock_base}_scores.csv",
                    mime="text/csv", key="dl_csv",
                )
            # Receptor PDB
            if st.session_state.receptor_fh and os.path.exists(st.session_state.receptor_fh):
                with open(st.session_state.receptor_fh, "rb") as f:
                    st.download_button(
                        "⬇ Receptor (.pdb)",
                        f, file_name="receptor.pdb", key="dl_rec",
                    )

st.markdown('</div>', unsafe_allow_html=True)

# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown('<hr class="step-divider">', unsafe_allow_html=True)
st.markdown(
    '<div style="text-align:center;color:#484f58;font-size:0.78rem;font-family:\'IBM Plex Mono\',monospace;">'
    'AutoDock Vina 1.2.7 · Meeko · RDKit · OpenBabel · py3Dmol<br>'
    'Eberhardt et al. J. Chem. Inf. Model. 2021, 61, 3891–3898 &nbsp;·&nbsp; '
    '<a href="https://pubs.acs.org/doi/10.1021/acs.jcim.5c02852" target="_blank" '
    'style="color:#58a6ff;text-decoration:none;">DFDD — Hengphasatporn et al. J. Chem. Inf. Model. 2026</a>'
    '</div>',
    unsafe_allow_html=True,
)
