#!/usr/bin/env python3
"""
AutoDock Vina 1.2.7 — Streamlit Docking Interface
Tabs: Basic (single ligand) | Batch (multiple ligands)
Bond-order correction applied automatically before PoseView submission.
"""

import streamlit as st
import os, sys, subprocess, tempfile, io, zipfile, re as _re
import shutil
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import streamlit.components.v1 as components

# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Anyone can dock, Everyone can do!",
    page_icon="🧩",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Theme Helper ─────────────────────────────────────────────────────────────
import streamlit.components.v1 as _comps

def _chart_colors():
    theme = st.get_option("theme.base") if hasattr(st, "get_option") else "light"
    dark  = (theme == "dark")
    return {
        "bg":        "#0d1117" if dark else "#FFFFFF",
        "bg_sub":    "#161b22" if dark else "#F6F8FA",
        "border":    "#30363d" if dark else "#D0D7DE",
        "text":      "#c9d1d9" if dark else "#24292F",
        "muted":     "#8b949e" if dark else "#57606A",
        "legend_bg": "#21262d" if dark else "#F6F8FA",
    }

def _viewer_bg():
    return _chart_colors()["bg"]


# ══════════════════════════════════════════════════════════════════════════════
#  PDB / MOL2 / SDF → canonical SMILES via obabel
#  Used in both the live upload preview and the batch docking parser.
# ══════════════════════════════════════════════════════════════════════════════

def pdb_to_canonical_smiles(file_bytes: bytes, filename: str) -> tuple:
    """
    Convert any structure file (PDB, MOL2, SDF) to a list of
    (smiles, name) pairs using Open Babel:

        obabel input.ext -O output.smi --canonical

    Parameters
    ----------
    file_bytes : raw bytes of the uploaded file
    filename   : original filename (used to preserve the extension so
                 obabel can auto-detect the format)

    Returns
    -------
    (pairs, error_message)
        pairs         – list of (smiles_str, name_str), empty on failure
        error_message – None on success, descriptive string on failure
    """
    if shutil.which("obabel") is None:
        return [], (
            "Open Babel (obabel) not found in PATH. "
            "Install via: conda install -c conda-forge openbabel"
        )
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp      = Path(tmp_dir)
            stem     = Path(filename).stem
            ext      = Path(filename).suffix.lower()          # e.g. ".pdb"
            in_file  = tmp / f"input{ext}"
            smi_file = tmp / "output.smi"

            in_file.write_bytes(file_bytes)

            result = subprocess.run(
                ["obabel", str(in_file), "-O", str(smi_file), "--canonical"],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if not smi_file.exists() or smi_file.stat().st_size == 0:
                stderr = result.stderr.strip()
                return [], (
                    f"obabel produced no output. "
                    f"stderr: {stderr or '(none)'}"
                )

            # obabel .smi format: "<SMILES>\t<name>" per molecule
            pairs = []
            for i, line in enumerate(
                smi_file.read_text(encoding="utf-8", errors="replace").splitlines()
            ):
                line = line.strip()
                if not line:
                    continue
                parts = line.split(None, 1)
                smi   = parts[0].strip()
                name  = (
                    parts[1].strip().replace(" ", "_")
                    if len(parts) > 1 and parts[1].strip()
                    else f"{stem}_{i+1:03d}"
                )
                if smi:
                    pairs.append((smi, name))

            if not pairs:
                return [], "obabel ran but produced no SMILES lines."

            return pairs, None

    except subprocess.TimeoutExpired:
        return [], "obabel conversion timed out (>60 s)."
    except Exception as exc:
        return [], f"Unexpected error during structure→SMILES conversion: {exc}"


# ─── Global CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

:root {
    --bg:          #FFFFFF;
    --bg-subtle:   #F6F8FA;
    --bg-card:     #3a3f47;
    --bg-input:    #2d3139;
    --border:      #D0D7DE;
    --text:        #24292F;
    --text-muted:  #57606A;
    --accent:      #0969DA;
    --accent2:     #0550AE;
    --success:     #1A7F37;
    --warn:        #9A6700;
    --text-card-title:   #9ca3af;
    --text-card-heading: #e5e7eb;
    --text-input:        #e5e7eb;
    --border-input:      #4b5563;
    --pill-border: #54AEFF;
    --pill-text:   #0550AE;
    --ok-bg:       #DAFBE1;
    --ok-border:   #1A7F37;
    --wn-bg:       #FFF8C5;
    --wn-border:   #9A6700;
    --btn-sec-bg:  #F6F8FA;
}
@media (prefers-color-scheme: dark) {
    :root {
        --bg:          #0d1117;
        --bg-subtle:   #161b22;
        --bg-card:     #161b22;
        --bg-input:    #21262d;
        --border:      #30363d;
        --text:        #c9d1d9;
        --text-muted:  #8b949e;
        --accent:      #58a6ff;
        --accent2:     #79c0ff;
        --success:     #3fb950;
        --warn:        #d29922;
        --text-card-title:   #8b949e;
        --text-card-heading: #e6edf3;
        --text-input:        #c9d1d9;
        --border-input:      #30363d;
        --pill-border: #1f6feb;
        --pill-text:   #79c0ff;
        --ok-bg:       #23863622;
        --ok-border:   #238636;
        --wn-bg:       #9e680322;
        --wn-border:   #9e6803;
        --btn-sec-bg:  #21262d;
    }
}

html, body, [data-testid="stAppViewContainer"] {
    background-color: var(--bg) !important;
    color: var(--text);
    font-family: 'IBM Plex Sans', sans-serif;
}
[data-testid="stSidebar"] { background: var(--bg-subtle) !important; }
[data-testid="stHeader"]  { background: transparent !important; }
h1 { font-family: 'IBM Plex Mono', monospace; color: var(--accent); letter-spacing: -1px; }
h2, h3 { font-family: 'IBM Plex Mono', monospace; color: var(--accent2); }
.step-card {
    background: var(--bg-card); border: 1px solid var(--border);
    border-left: 4px solid var(--accent); border-radius: 8px;
    padding: 20px 24px; margin-bottom: 24px;
}
.step-card.done    { border-left-color: var(--success); }
.step-card.running { border-left-color: var(--warn); }
.step-title {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.85rem; color: var(--text-card-title);
    text-transform: uppercase; letter-spacing: 2px; margin-bottom: 4px;
}
.step-heading {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 1.3rem; color: var(--text-card-heading); margin-bottom: 16px;
}
.result-pill {
    display: inline-block;
    background: var(--pill-bg); border: 1px solid var(--pill-border); color: var(--pill-text);
    border-radius: 20px; padding: 2px 12px;
    font-family: 'IBM Plex Mono', monospace; font-size: 0.8rem; margin: 2px;
}
.success-pill {
    display: inline-block;
    background: var(--ok-bg); border: 1px solid var(--ok-border); color: var(--success);
    border-radius: 20px; padding: 4px 14px;
    font-family: 'IBM Plex Mono', monospace; font-size: 0.85rem;
}
.warn-pill {
    display: inline-block;
    background: var(--wn-bg); border: 1px solid var(--wn-border); color: var(--warn);
    border-radius: 20px; padding: 4px 14px;
    font-family: 'IBM Plex Mono', monospace; font-size: 0.85rem;
}
.log-box {
    background: var(--bg-subtle); border: 1px solid var(--border); border-radius: 6px;
    padding: 12px 16px;
    font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem; color: var(--text-muted);
    max-height: 220px; overflow-y: auto; white-space: pre-wrap;
}
.score-best { font-family: 'IBM Plex Mono', monospace; font-size: 2.4rem; color: var(--success); font-weight: 600; }
.score-unit { font-size: 1rem; color: var(--text-muted); }
.stButton > button {
    background: var(--success); color: white; border: none; border-radius: 6px;
    font-family: 'IBM Plex Mono', monospace; font-size: 0.88rem;
    padding: 8px 20px; transition: background 0.2s;
}
.stButton > button:hover { filter: brightness(1.15); }
.stButton > button[kind="secondary"] {
    background: var(--btn-sec-bg); border: 1px solid var(--border); color: var(--text);
}
.stButton > button[kind="secondary"]:hover { filter: brightness(0.95); }
.stTextInput > div > div > input,
.stSelectbox > div > div,
.stNumberInput > div > div > input {
    background: var(--bg-input) !important; border: 1px solid var(--border-input) !important;
    color: var(--text-input) !important; border-radius: 6px !important;
    font-family: 'IBM Plex Mono', monospace !important;
}
.stSlider > div { color: var(--text); }
[data-baseweb="slider"] { accent-color: var(--accent); }
.stDataFrame { border: 1px solid var(--border); border-radius: 6px; }
hr { border-color: var(--border); }
.step-divider { border: none; border-top: 1px dashed var(--border); margin: 32px 0; }
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: var(--bg-subtle); border-bottom: 1px solid var(--border); gap: 4px;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    font-family: 'IBM Plex Mono', monospace; font-size: 0.9rem;
    color: var(--text-muted); background: transparent; border-radius: 6px 6px 0 0;
    padding: 10px 20px;
}
[data-testid="stTabs"] [aria-selected="true"] {
    color: var(--accent) !important; background: var(--bg) !important;
    border-bottom: 2px solid var(--accent) !important;
}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
_DEFAULTS = dict(
    workdir=None,
    # Basic — receptor
    pdb_token=None, raw_pdb=None, receptor_fh=None, receptor_pdbqt=None,
    box_pdb=None, config_txt=None, cx=None, cy=None, cz=None,
    ligand_pdb_path=None, receptor_done=False, receptor_log="",
    # Basic — ligand
    ligand_pdbqt=None, ligand_sdf=None, ligand_name="ELR",
    prot_smiles=None, ligand_done=False, ligand_log="",
    # Basic — docking
    output_pdbqt=None, output_sdf=None, output_pv_sdf=None, dock_base=None,
    docking_done=False, docking_log="", score_df=None, pose_mols=None,
    # Basic — PoseView
    pv_image_url=None, pv_image_png=None, pv_image_svg=None, pv_pose_key=None,
    # Batch — receptor
    b_pdb_token=None, b_raw_pdb=None, b_receptor_fh=None, b_receptor_pdbqt=None,
    b_box_pdb=None, b_config_txt=None, b_cx=None, b_cy=None, b_cz=None,
    b_ligand_pdb_path=None, b_receptor_done=False, b_receptor_log="",
    # Batch — results
    b_batch_done=False, b_batch_results=None, b_batch_log="",
    b_redock_score=None, b_redock_result=None,
    b_confirmed_ref_score=None, b_confirmed_ref_pose=None, b_confirmed_ref_name=None,
    # Batch — PoseView
    b_pv_image_url=None, b_pv_image_png=None, b_pv_image_svg=None, b_pv_pose_key=None,
    # Batch — uploaded structure preview
    b_struct_smiles_pairs=None, b_struct_filename=None,
    # Batch — downloadable assets
    b_plot_png=None,
)
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── Working Directories ──────────────────────────────────────────────────────
if st.session_state.workdir is None:
    st.session_state.workdir = tempfile.mkdtemp(prefix="vina_")
WORKDIR       = Path(st.session_state.workdir)
BATCH_WORKDIR = WORKDIR / "batch"
BATCH_WORKDIR.mkdir(exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
#  GENERAL HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def show3d(view, height=480):
    try:
        from stmol import showmol
        showmol(view, height=height)
    except ImportError:
        raw  = view._make_html()
        resp = _re.sub(r'(width\s*[:=]\s*)["\']?\d+px?["\']?', r'\g<1>100%', raw)
        components.html(f'<div style="width:100%;overflow:hidden">{resp}</div>',
                        height=height, scrolling=False)

def _pill(text, kind="info"):
    cls = {"info": "result-pill", "success": "success-pill", "warn": "warn-pill"}.get(kind, "result-pill")
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

def _meeko_to_pdbqt(mol, out_path):
    from meeko import MoleculePreparation
    prep = MoleculePreparation()
    try:
        from meeko import PDBQTWriterLegacy
        setups = prep.prepare(mol)
        pdbqt_str, _, _ = PDBQTWriterLegacy.write_string(setups[0])
    except (ImportError, AttributeError):
        prep.prepare(mol)
        pdbqt_str = prep.write_pdbqt_string()
    with open(out_path, "w") as f:
        f.write(pdbqt_str)


# ══════════════════════════════════════════════════════════════════════════════
#  BOND ORDER CORRECTION
# ══════════════════════════════════════════════════════════════════════════════
def _bo_template(smiles: str):
    from rdkit import Chem
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"Cannot parse SMILES: {smiles!r}")
    Chem.Kekulize(mol, clearAromaticFlags=True)
    return mol


def _bo_fix_mol(probe, template):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    probe_noH = Chem.RemoveHs(probe, sanitize=False)
    try:
        fixed = AllChem.AssignBondOrdersFromTemplate(template, probe_noH)
    except ValueError as exc:
        raise RuntimeError(
            f"AssignBondOrdersFromTemplate failed (atom/connectivity mismatch): {exc}"
        ) from exc
    Chem.SanitizeMol(fixed)
    for prop in probe.GetPropsAsDict():
        fixed.SetProp(prop, probe.GetProp(prop))
    return fixed


def _fix_sdf_bond_orders(raw_sdf: str, smiles: str, fixed_sdf: str) -> list[str]:
    from rdkit import Chem
    log = []
    try:
        template = _bo_template(smiles)
    except Exception as e:
        log.append(f"⚠ Could not build template: {e} — skipping fix")
        import shutil as _sh
        _sh.copy(raw_sdf, fixed_sdf)
        return log

    supplier  = Chem.SDMolSupplier(raw_sdf, sanitize=False, removeHs=False)
    writer    = Chem.SDWriter(fixed_sdf)
    n_ok = n_fail = 0

    for i, mol in enumerate(supplier):
        if mol is None:
            log.append(f"  pose {i+1}: unreadable — skipped"); n_fail += 1; continue
        try:
            fixed = _bo_fix_mol(mol, template)
            writer.write(fixed); n_ok += 1
        except Exception as e:
            log.append(f"  pose {i+1}: fix failed ({e}) — writing raw"); n_fail += 1
            writer.write(Chem.RemoveHs(mol, sanitize=False))
    writer.close()
    log.insert(0, f"✓ Bond-order fix: {n_ok} OK, {n_fail} fallback")
    return log


def _load_pv_mols(pv_sdf: str):
    from rdkit import Chem
    return [m for m in Chem.SDMolSupplier(pv_sdf, sanitize=True, removeHs=False) if m]


def _write_single_pose(mol, path: str) -> None:
    from rdkit import Chem
    with Chem.SDWriter(path) as w:
        w.write(mol)


# ══════════════════════════════════════════════════════════════════════════════
#  POSEVIEW HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def _call_poseview(receptor_pdb: str, pose_sdf: str):
    import requests, time
    _BASE   = "https://proteins.plus/api/v2/"
    _SUBMIT = _BASE + "poseview/"
    _JOBS   = _BASE + "poseview/jobs/"
    try:
        with open(receptor_pdb) as rf, open(pose_sdf) as lf:
            r = requests.post(_SUBMIT, files={"protein_file": rf, "ligand_file": lf}, timeout=30)
        r.raise_for_status()
        job_id = r.json()["job_id"]
    except Exception as e:
        return None, f"Submission failed: {e}"
    for _ in range(30):
        try:
            job    = requests.get(_JOBS + job_id + "/", timeout=10).json()
            status = job.get("status", "")
            if status in ("done", "success"):
                img = job.get("image") or job.get("result") or job.get("image_url")
                return (img, None) if img else (None, "Job finished but no image URL returned.")
            if status not in ("pending", "running"):
                return None, f"Job ended with status '{status}'"
        except Exception as e:
            return None, f"Polling error: {e}"
        time.sleep(2)
    return None, "Timed out waiting for PoseView (60 s)."


def _svg_to_png(svg_bytes: bytes):
    try:
        import cairosvg
        return cairosvg.svg2png(bytestring=svg_bytes, scale=2, background_color="white")
    except Exception:
        return None


def _show_poseview_image(png_data, url, caption):
    import base64 as _b64
    img_src = (f"data:image/png;base64,{_b64.b64encode(png_data).decode()}"
               if png_data else url)
    st.markdown(
        f'''<div style="background:#ffffff;border-radius:8px;padding:12px;
                       border:1px solid #D0D7DE;margin:8px 0;">
            <img src="{img_src}" style="width:100%;height:auto;display:block;" />
            <div style="text-align:center;font-size:0.78rem;color:#57606A;
                        margin-top:6px;">{caption}</div>
        </div>''',
        unsafe_allow_html=True,
    )


def _poseview_ui(
    rec_key, raw_sdf_key, pv_sdf_key, smiles_key,
    pose_idx, pose_sdf_path,
    img_url_key, img_png_key, img_svg_key, pose_key_key,
    btn_key, dl_png_key, dl_svg_key, label_suffix="",
):
    _pose_key = f"{st.session_state.get(smiles_key, 'lig')}_pose{pose_idx+1}{label_suffix}"
    _pv_stale = st.session_state.get(pose_key_key) != _pose_key

    st.markdown("---")
    st.markdown("**🧬 2D Interaction Diagram — PoseView**")

    _ci, _cb = st.columns([3, 1])
    with _ci:
        if _pv_stale and st.session_state.get(img_url_key):
            st.caption("⚠️ Pose changed — click **Generate** to update the diagram.")
        else:
            st.caption(
                "Sends the selected pose to [proteins.plus PoseView](https://proteins.plus/) "
                "and renders a 2D protein–ligand interaction map. Bond orders are "
                "automatically corrected before submission."
            )
    with _cb:
        _run_pv = st.button("🔬 Generate 2D Diagram", key=btn_key, type="primary")

    if _run_pv:
        _rec = st.session_state.get(rec_key, "")
        if not _rec or not os.path.exists(_rec):
            st.error("Receptor PDB not found — complete receptor preparation first.")
        elif not os.path.exists(pose_sdf_path):
            st.error("Pose SDF not found.")
        else:
            with st.spinner("Submitting to PoseView API… (10–60 s)"):
                _url, _err = _call_poseview(_rec, pose_sdf_path)
            if _err:
                st.error(f"❌ PoseView error: {_err}")
            else:
                import requests as _rq
                _raw = _rq.get(_url, timeout=20).content
                _png = _svg_to_png(_raw)
                st.session_state[img_url_key]  = _url
                st.session_state[img_png_key]  = _png
                st.session_state[img_svg_key]  = _raw
                st.session_state[pose_key_key] = _pose_key
                st.rerun()

    if st.session_state.get(img_url_key) and not _pv_stale:
        _png_data = st.session_state.get(img_png_key)
        _svg_data = st.session_state.get(img_svg_key)
        lig_label = st.session_state.get(smiles_key, "ligand")[:20]
        _show_poseview_image(
            _png_data,
            st.session_state[img_url_key],
            f"PoseView — {lig_label} pose {pose_idx+1}",
        )
        _dc1, _dc2, _dc3 = st.columns([1, 1, 2])
        with _dc1:
            if _png_data:
                st.download_button("⬇ Save PNG", data=_png_data,
                    file_name=f"poseview_pose{pose_idx+1}.png", mime="image/png",
                    key=dl_png_key, use_container_width=True)
        with _dc2:
            if _svg_data:
                st.download_button("⬇ Save SVG", data=_svg_data,
                    file_name=f"poseview_pose{pose_idx+1}.svg", mime="image/svg+xml",
                    key=dl_svg_key, use_container_width=True)
        with _dc3:
            st.caption("💡 SVG is vector — scalable for publications. PNG for quick use.")

        st.markdown("---")
        st.markdown(
            f"""### 🤖 AI Prompt for PoseView Interpretation

Copy and paste the prompt below into any AI tool (GPT, Claude, Gemini, DeepSeek, etc.) together with the PoseView figure.

**Task:**  
Analyze the attached **Proteins.Plus PoseView interaction diagram** for **PDB ID [____]**, docked ligand **[____]**, generated using **AutoDock Vina v1.2.7** with predicted binding energy **[____ kcal/mol]**, and compare with the **co-crystallized reference ligand [____]** in the same binding pocket.

1. Identify key ligand–protein interactions (hydrogen bonds, hydrophobic contacts, π–π interactions, salt bridges, etc.).
2. List the main interacting residues and describe their roles in stabilizing the ligand.
3. Compare the docking pose with the reference ligand in the same pocket.
4. Highlight similarities or differences in binding orientation and interaction patterns.
5. Evaluate whether the interaction profile supports the predicted binding energy.

Provide a **concise structural interpretation of the binding mode**.
"""
        )


# ══════════════════════════════════════════════════════════════════════════════
#  VINA BINARY + pKa MODEL
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_resource(show_spinner="⬇ Downloading AutoDock Vina 1.2.7…")
def _get_vina():
    path = "/tmp/vina_1.2.7"
    if not os.path.exists(path) or os.path.getsize(path) < 100_000:
        rc, out = run_cmd(["wget", "-q",
            "https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/"
            "v1.2.7/vina_1.2.7_linux_x86_64", "-O", path])
        if rc != 0:
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

VINA_PATH, _vina_err = _get_vina()
PKA_MODEL             = _get_pka_model()

_EXCLUDE_IONS   = set("HOH,WAT,DOD,SOL,NA,CL,K,CA,MG,ZN,MN,FE,CU,CO,NI,CD,HG".split(","))
_GLYCAN_NAMES   = {"NAG","BMA","MAN","FUC","GAL","GLC","SIA","NGA","FUL","GLA","BGC"}
_COFACTOR_NAMES = {"ATP","ADP","AMP","GTP","GDP","FAD","FMN","HEM","GOL","PEG","EDO","SO4","PO4"}


# ══════════════════════════════════════════════════════════════════════════════
#  SHARED: RECEPTOR PREPARATION
# ══════════════════════════════════════════════════════════════════════════════
def _receptor_section(pfx: str, wdir: Path, step_label: str):
    import py3Dmol
    done     = st.session_state.get(pfx + "receptor_done", False)
    card_cls = "step-card done" if done else "step-card"

    st.markdown(
        f'<div class="{card_cls}"><div class="step-title">{step_label}</div>'
        f'<div class="step-heading" style="color:#FFFFFF;">📦 Receptor Preparation</div>',
        unsafe_allow_html=True)

    col_a, col_b = st.columns([1.2, 1])
    with col_a:
        src = st.radio("PDB source", ["Download from RCSB", "Upload PDB file"],
                       horizontal=True, key=pfx+"src_mode")
        if src == "Download from RCSB":
            pdb_id     = st.text_input("PDB ID", value="1M17", max_chars=4, key=pfx+"pdb_id")
            upload_pdb = None
        else:
            upload_pdb = st.file_uploader("Upload .pdb", type=["pdb"], key=pfx+"pdb_upload")
            pdb_id     = None

        center_mode = st.radio("Grid center",
            ["Auto-detect co-crystal ligand", "Enter XYZ manually"],
            horizontal=True, key=pfx+"center_mode")
        if center_mode == "Enter XYZ manually":
            c1, c2, c3 = st.columns(3)
            mx = c1.number_input("X", value=0.0, key=pfx+"mx")
            my = c2.number_input("Y", value=0.0, key=pfx+"my")
            mz = c3.number_input("Z", value=0.0, key=pfx+"mz")

    with col_b:
        st.markdown("**Search box size (Å)**")
        sx = st.slider("X size", 10, 40, 16, 2, key=pfx+"sx")
        sy = st.slider("Y size", 10, 40, 16, 2, key=pfx+"sy")
        sz = st.slider("Z size", 10, 40, 16, 2, key=pfx+"sz")
        st.markdown(f"Box volume: **{sx*sy*sz:,} Å³**")

    if st.button("▶ Prepare Receptor", key=pfx+"btn_receptor", type="primary"):
        from prody import parsePDB, calcCenter, writePDB
        log = []
        try:
            raw_path = str(wdir / "raw.pdb")

            if src == "Download from RCSB":
                token = pdb_id.strip().upper()
                rc, _ = run_cmd(["curl", "-sf",
                    f"https://files.rcsb.org/download/{token}.pdb", "-o", raw_path])
                if rc != 0 or not os.path.exists(raw_path) or os.path.getsize(raw_path) < 200:
                    raise ValueError(f"Download failed for {token}")
                st.session_state[pfx+"pdb_token"] = token
                log.append(f"⬇ Downloaded {token}")
            else:
                if upload_pdb is None:
                    st.error("Please upload a PDB file first."); st.stop()
                with open(raw_path, "wb") as f:
                    f.write(upload_pdb.read())
                st.session_state[pfx+"pdb_token"] = Path(upload_pdb.name).stem
                log.append(f"📂 Loaded: {upload_pdb.name}")

            atoms = parsePDB(raw_path)
            log.append(f"✓ Parsed {atoms.numAtoms()} atoms")

            ligand_pdb_path = None
            cx = cy = cz   = 0.0
            ligand_sel_str  = None

            if center_mode == "Auto-detect co-crystal ligand":
                het = atoms.select("hetero and not water")
                if het is not None:
                    excl  = _EXCLUDE_IONS | _GLYCAN_NAMES | _COFACTOR_NAMES
                    cands = [r for r in het.getHierView().iterResidues()
                             if (r.getResname() or "").strip() not in excl]
                    if cands:
                        cands.sort(key=lambda r: (-r.numAtoms(), r.getChid() != "A"))
                        chosen = cands[0]
                        rn, ch, ri = chosen.getResname(), chosen.getChid(), chosen.getResnum()
                        ligand_sel_str  = f"resname {rn} and resid {ri} and chain {ch}"
                        lig_atoms       = atoms.select(ligand_sel_str)
                        ligand_pdb_path = str(wdir / "LIG.pdb")
                        writePDB(ligand_pdb_path, lig_atoms)
                        cx, cy, cz = (float(v) for v in calcCenter(lig_atoms))
                        log.append(f"✓ Ligand: {rn} chain {ch} ({lig_atoms.numAtoms()} atoms)")
                        log.append(f"📍 Center: ({cx:.3f}, {cy:.3f}, {cz:.3f})")
                    else:
                        log.append("⚠ No co-crystal ligand found after filtering")
            else:
                cx, cy, cz = mx, my, mz
                log.append(f"🛠 Manual center: ({cx:.3f}, {cy:.3f}, {cz:.3f})")

            sel_str = (f"not ({ligand_sel_str}) and not water"
                       if ligand_sel_str else "not water")
            rec_sel  = atoms.select(sel_str)
            rec_raw  = str(wdir / "receptor_atoms.pdb")
            writePDB(rec_raw, rec_sel)
            log.append(f"✓ Receptor: {rec_sel.numAtoms()} atoms")

            rec_fh    = str(wdir / "rec.pdb")
            rec_pdbqt = str(wdir / "rec.pdbqt")
            run_cmd(f'obabel "{rec_raw}" -O "{rec_fh}" -h 2>/dev/null')
            if os.path.getsize(rec_fh) < 100:
                raise ValueError("OpenBabel H-addition produced empty file")
            run_cmd(f'obabel "{rec_fh}" -O "{rec_pdbqt}" -xr --partialcharge gasteiger 2>/dev/null')
            if os.path.getsize(rec_pdbqt) < 100:
                raise ValueError("PDBQT conversion produced empty file")
            log.append("✓ Receptor PDBQT ready")

            box_pdb  = str(wdir / "rec.box.pdb")
            cfg_path = str(wdir / "rec.box.txt")
            hx, hy, hz = sx/2, sy/2, sz/2
            corners = [(cx+dx, cy+dy, cz+dz)
                       for dx in (-hx, hx) for dy in (-hy, hy) for dz in (-hz, hz)]
            with open(box_pdb, "w") as f:
                for i, (x, y, z) in enumerate(corners, 1):
                    f.write(f"HETATM{i:5d}  C   BOX A   1    {x:8.3f}{y:8.3f}{z:8.3f}"
                            f"  1.00  0.00           C\n")
                f.write("CONECT    1    2    3    5\nCONECT    2    1    4    6\n"
                        "CONECT    3    1    4    7\nCONECT    4    2    3    8\n"
                        "CONECT    5    1    6    7\nCONECT    6    2    5    8\n"
                        "CONECT    7    3    5    8\nCONECT    8    4    6    7\n")
            with open(cfg_path, "w") as f:
                f.write(f"center_x = {cx:.4f}\ncenter_y = {cy:.4f}\ncenter_z = {cz:.4f}\n"
                        f"size_x = {sx}\nsize_y = {sy}\nsize_z = {sz}\n")
            log.append("✓ Box + config written")

            st.session_state.update({
                pfx+"raw_pdb": raw_path,         pfx+"receptor_fh": rec_fh,
                pfx+"receptor_pdbqt": rec_pdbqt, pfx+"box_pdb": box_pdb,
                pfx+"config_txt": cfg_path,      pfx+"cx": cx,
                pfx+"cy": cy,                    pfx+"cz": cz,
                pfx+"ligand_pdb_path": ligand_pdb_path,
                pfx+"receptor_done": True,       pfx+"receptor_log": "\n".join(log),
            })
        except Exception as e:
            st.error(f"❌ Receptor preparation failed: {e}")
            st.session_state[pfx+"receptor_done"] = False
            st.session_state[pfx+"receptor_log"]  = "\n".join(log) + f"\nERROR: {e}"

    if st.session_state.get(pfx+"receptor_done"):
        token = st.session_state.get(pfx+"pdb_token", "")
        cx_v  = st.session_state.get(pfx+"cx", 0)
        cy_v  = st.session_state.get(pfx+"cy", 0)
        cz_v  = st.session_state.get(pfx+"cz", 0)
        _sx   = st.session_state.get(pfx+"sx", 16)
        _sy   = st.session_state.get(pfx+"sy", 16)
        _sz   = st.session_state.get(pfx+"sz", 16)
        st.markdown(
            f"{_pill('Receptor ready ✓', 'success')} {_pill(token)} "
            f"{_pill(f'Center ({cx_v:.2f}, {cy_v:.2f}, {cz_v:.2f})')} "
            f"{_pill(f'Box {_sx}×{_sy}×{_sz} Å')}",
            unsafe_allow_html=True)
        with st.expander("📋 Preparation log", expanded=False):
            st.markdown(
                f'<div class="log-box">{st.session_state.get(pfx+"receptor_log","")}</div>',
                unsafe_allow_html=True)
        with st.expander("🔭 3D: Receptor + Docking Box", expanded=True):
            v3 = py3Dmol.view(width="100%", height=480)
            v3.setBackgroundColor(_viewer_bg())
            mi = 0
            for path, style in [
                (st.session_state.get(pfx+"receptor_fh"),
                 {"cartoon": {"color": "spectrum", "opacity": 0.65}}),
                (st.session_state.get(pfx+"box_pdb"),
                 {"stick": {"radius": 0.2, "color": "gray"}}),
            ]:
                if path and os.path.exists(path):
                    v3.addModel(open(path).read(), "pdb")
                    v3.setStyle({"model": mi}, style); mi += 1
            lig_p = st.session_state.get(pfx+"ligand_pdb_path")
            if lig_p and os.path.exists(lig_p):
                v3.addModel(open(lig_p).read(), "pdb")
                v3.setStyle({"model": mi},
                             {"stick": {"colorscheme": "magentaCarbon", "radius": 0.25}})
            v3.zoomTo()
            if lig_p and os.path.exists(lig_p):
                v3.center({"model": mi})
            show3d(v3, height=480)

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<hr class="step-divider">', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("# 🧩 AutoDock Vina 1.2.7")
st.markdown("Molecular docking powered by **AutoDock Vina 1.2.7**, **pKaNET Cloud**, and **PoseView 2D interaction**")
st.markdown("**Basic** — single ligand.  **Batch** — multiple ligands.")
if VINA_PATH is None:
    st.error(f"❌ Could not download Vina binary: {_vina_err}")
    st.stop()

st.markdown(_pill("Vina 1.2.7 ready ✓", "success"), unsafe_allow_html=True)
st.markdown('<hr class="step-divider">', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  TABS
# ══════════════════════════════════════════════════════════════════════════════
tab_basic, tab_batch = st.tabs([
    "🧪  Basic — single ligand",
    "🔬  Batch — multiple ligands",
])


# ╔════════════════════════════════════════════════════════════════════════════╗
#  TAB 1 — BASIC DOCKING  (unchanged)
# ╚════════════════════════════════════════════════════════════════════════════╝
with tab_basic:

    _receptor_section(pfx="", wdir=WORKDIR, step_label="Step 1 of 4")

    card_cls = "step-card done" if st.session_state.ligand_done else "step-card"
    st.markdown(
        f'<div class="{card_cls}"><div class="step-title">Step 2 of 4</div>'
        f'<div class="step-heading" style="color:#FFFFFF;">⚗️ Ligand Preparation</div>',
        unsafe_allow_html=True)

    cl1, cl2 = st.columns([1.5, 1])
    with cl1:
        smiles_in   = st.text_input("SMILES string",
            value="COCCOC1=C(C=C2C(=C1)C(=NC=N2)NC3=CC=CC(=C3)C#C)OCCOC",
            key="smiles_in")
        lig_name_in = st.text_input("Output name", value="ELR", key="lig_name_in")
        ph_in       = st.number_input("Target pH", 0.0, 14.0, 7.4, 0.1, key="ph_in")
    with cl2:
        st.markdown("**pKa prediction**")
        if PKA_MODEL and smiles_in:
            try:
                from pkapredict import smiles_to_rdkit_descriptors, predict_pKa
                pka_v   = float(predict_pKa(PKA_MODEL,
                                            smiles_to_rdkit_descriptors([smiles_in]))[0])
                charged = "deprotonated (−1)" if pka_v < ph_in else "neutral (0)"
                st.markdown(
                    f'<div style="background:#1f6feb15;border:1px solid #1f6feb;'
                    f'border-radius:8px;padding:16px;">'
                    f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:1.8rem;'
                    f'color:#58a6ff">pKa = {pka_v:.2f}</div>'
                    f'<div style="color:#8b949e;font-size:0.85rem">at pH {ph_in:.1f}: '
                    f'likely <b style="color:#79c0ff">{charged}</b></div>'
                    f'</div>', unsafe_allow_html=True)
            except Exception:
                st.info("pKa unavailable for this SMILES.")

    if not st.session_state.receptor_done:
        st.caption("⚠ Complete Step 1 first.")
    if st.button("▶ Prepare Ligand", key="btn_ligand", type="primary",
                 disabled=not st.session_state.receptor_done):
        _rdkit_six_patch()
        from rdkit import Chem
        from rdkit.Chem import AllChem, Draw
        log      = []
        lig_name = lig_name_in.strip() or "LIG"
        out_pdbqt = str(WORKDIR / f"{lig_name}.pdbqt")
        out_sdf   = str(WORKDIR / f"{lig_name}_3d.sdf")
        with st.spinner("Preparing ligand…"):
            try:
                prot = smiles_in.strip()
                try:
                    from dimorphite_dl import protonate_smiles
                    vs = protonate_smiles(prot, ph_min=ph_in, ph_max=ph_in, max_variants=1)
                    if vs: prot = vs[0]; log.append(f"✓ Dimorphite-DL pH {ph_in}")
                except Exception as e:
                    log.append(f"⚠ Dimorphite-DL skipped: {e}")

                mol = Chem.MolFromSmiles(prot)
                if mol is None: raise ValueError("RDKit could not parse SMILES")
                log.append(f"✓ Formal charge: {Chem.GetFormalCharge(mol):+d}")
                mol = Chem.AddHs(mol)
                try:    params = AllChem.ETKDGv3()
                except: params = AllChem.ETKDG()
                params.randomSeed = 42
                if AllChem.EmbedMolecule(mol, params) == -1:
                    AllChem.EmbedMolecule(mol, useRandomCoords=True, randomSeed=42)
                if AllChem.MMFFHasAllMoleculeParams(mol):
                    AllChem.MMFFOptimizeMolecule(mol, maxIters=500)
                else:
                    AllChem.UFFOptimizeMolecule(mol, maxIters=500)
                log.append("✓ 3D conformer generated")
                with Chem.SDWriter(out_sdf) as w: w.write(mol)
                _meeko_to_pdbqt(mol, out_pdbqt)
                log.append("✓ PDBQT written")
                st.session_state.update(dict(
                    ligand_pdbqt=out_pdbqt, ligand_sdf=out_sdf,
                    ligand_name=lig_name, prot_smiles=prot,
                    ligand_done=True, ligand_log="\n".join(log)))
            except Exception as e:
                st.error(f"❌ Ligand preparation failed: {e}")
                st.session_state.ligand_done = False
                st.session_state.ligand_log  = "\n".join(log) + f"\nERROR: {e}"

    if st.session_state.ligand_done:
        import py3Dmol
        from rdkit import Chem
        from rdkit.Chem import AllChem, Draw
        st.markdown(
            f"{_pill('Ligand ready ✓', 'success')} {_pill(st.session_state.ligand_name)}",
            unsafe_allow_html=True)
        with st.expander("📋 Preparation log", expanded=False):
            st.markdown(f'<div class="log-box">{st.session_state.ligand_log}</div>',
                        unsafe_allow_html=True)
        c2d, c3d = st.columns(2)
        with c2d:
            st.markdown("**2D Structure**")
            try:
                m2 = Chem.MolFromSmiles(st.session_state.prot_smiles)
                AllChem.Compute2DCoords(m2)
                buf = io.BytesIO()
                Draw.MolToImage(m2, size=(320, 260)).save(buf, format="PNG")
                st.image(buf.getvalue(), width=320)
            except Exception as e:
                st.info(f"2D unavailable: {e}")
        with c3d:
            st.markdown("**3D Conformer**")
            try:
                vl = py3Dmol.view(width="100%", height=280)
                vl.setBackgroundColor(_viewer_bg())
                vl.addModel(open(st.session_state.ligand_sdf).read(), "sdf")
                vl.setStyle({}, {"stick": {"colorscheme": "yellowCarbon", "radius": 0.2}})
                vl.zoomTo(); show3d(vl, height=280)
            except Exception as e:
                st.info(f"3D viewer unavailable: {e}")

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<hr class="step-divider">', unsafe_allow_html=True)

    card_cls = "step-card done" if st.session_state.docking_done else "step-card"
    st.markdown(
        f'<div class="{card_cls}"><div class="step-title">Step 3 of 4</div>'
        f'<div class="step-heading">🚀 Run Docking</div>',
        unsafe_allow_html=True)

    cd1, cd2 = st.columns([1.5, 1])
    with cd1:
        exh = st.slider("Exhaustiveness", 4, 64, 16, 2, key="exh_slider")
        nm  = st.slider("Number of poses", 5, 20, 10, 1, key="n_modes")
        er  = st.slider("Energy range (kcal/mol)", 1, 5, 3, 1, key="e_range")
    with cd2:
        est = max(1, exh // 8)
        st.markdown(
            f'<div style="background:#F6F8FA;border:1px solid #D0D7DE;'
            f'border-radius:8px;padding:16px;">'
            f'<div style="color:#8b949e;font-size:0.8rem">ESTIMATED TIME</div>'
            f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:2rem;color:#d29922">'
            f'~{est}–{est*3} min</div>'
            f'<div style="color:#8b949e;font-size:0.8rem">exhaustiveness = {exh}</div>'
            f'</div>', unsafe_allow_html=True)

    if not st.session_state.ligand_done:
        st.caption("⚠ Complete Steps 1 & 2 first.")
    if st.button("▶ Run Docking", key="btn_dock", type="primary",
                 disabled=not st.session_state.ligand_done):
        base      = st.session_state.ligand_name
        out_pdbqt = str(WORKDIR / f"{base}_out.pdbqt")
        out_sdf   = str(WORKDIR / f"{base}_out.sdf")
        pv_sdf    = str(WORKDIR / f"{base}_pv_ready.sdf")
        with st.spinner(f"Running Vina (exhaustiveness={exh})… ⏳"):
            rc, vlog = run_cmd(
                f'"{VINA_PATH}" '
                f'--receptor "{st.session_state.receptor_pdbqt}" '
                f'--ligand "{st.session_state.ligand_pdbqt}" '
                f'--config "{st.session_state.config_txt}" '
                f'--exhaustiveness {exh} --num_modes {nm} '
                f'--energy_range {er} --out "{out_pdbqt}"',
                cwd=str(WORKDIR))
            if rc != 0 or not os.path.exists(out_pdbqt):
                st.error(f"❌ Vina failed (exit {rc})\n{vlog[:500]}")
                st.session_state.docking_done = False
            else:
                run_cmd(f'obabel "{out_pdbqt}" -O "{out_sdf}" 2>/dev/null')
                pv_log = _fix_sdf_bond_orders(
                    out_sdf, st.session_state.prot_smiles, pv_sdf)
                vlog += "\n\n── Bond-order fix ──\n" + "\n".join(pv_log)
                if not os.path.exists(pv_sdf) or os.path.getsize(pv_sdf) < 10:
                    pv_sdf = out_sdf

                data = []; cur = None
                for line in open(out_pdbqt):
                    ln = line.strip()
                    if ln.startswith("MODEL"):
                        try: cur = int(ln.split()[1])
                        except: pass
                    elif ln.startswith("REMARK VINA RESULT:"):
                        try:
                            p = ln.split()
                            data.append({"Pose": cur,
                                         "Affinity (kcal/mol)": float(p[3]),
                                         "RMSD lb": float(p[4]),
                                         "RMSD ub": float(p[5])})
                        except: pass
                df = (pd.DataFrame(data)
                      .sort_values("Affinity (kcal/mol)")
                      .reset_index(drop=True)) if data else None

                from rdkit import Chem
                mols = ([m for m in Chem.SDMolSupplier(out_sdf, sanitize=False) if m]
                        if os.path.exists(out_sdf) else [])

                st.session_state.update(dict(
                    output_pdbqt=out_pdbqt, output_sdf=out_sdf,
                    output_pv_sdf=pv_sdf,   dock_base=base,
                    docking_done=True,       docking_log=vlog,
                    score_df=df,             pose_mols=mols,
                    pv_image_url=None, pv_image_png=None,
                    pv_image_svg=None, pv_pose_key=None,
                ))

    if st.session_state.docking_done:
        st.markdown(_pill("Docking complete ✓", "success"), unsafe_allow_html=True)
        with st.expander("📋 Vina output log", expanded=False):
            st.markdown(f'<div class="log-box">{st.session_state.docking_log}</div>',
                        unsafe_allow_html=True)
        if st.session_state.score_df is not None:
            best = st.session_state.score_df["Affinity (kcal/mol)"].min()
            cls  = ("Very strong" if best < -11 else "Strong" if best < -9
                    else "Moderate" if best < -7 else "Weak")
            st.markdown(
                f'<div class="score-best">{best:.2f} '
                f'<span class="score-unit">kcal/mol</span></div>'
                f'<div style="color:#8b949e;font-size:0.9rem;margin-bottom:12px">'
                f'Best pose — {cls} predicted binding</div>',
                unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<hr class="step-divider">', unsafe_allow_html=True)

    card_cls = "step-card done" if st.session_state.docking_done else "step-card"
    st.markdown(
        f'<div class="{card_cls}"><div class="step-title">Step 4 of 4</div>'
        f'<div class="step-heading">📊 Results & Visualization</div>',
        unsafe_allow_html=True)

    if not st.session_state.docking_done:
        st.info("Complete Step 3 to see results here.")
    else:
        import py3Dmol
        from rdkit import Chem
        df   = st.session_state.score_df
        mols = st.session_state.pose_mols or []

        ct, cc = st.columns([1, 1.4])
        with ct:
            st.markdown("**Score Table**")
            if df is not None:
                st.dataframe(
                    df.style.background_gradient(
                        cmap="RdYlGn", subset=["Affinity (kcal/mol)"],
                        gmap=-df["Affinity (kcal/mol)"]),
                    hide_index=True, use_container_width=True)
        with cc:
            st.markdown("**Affinity by Pose**")
            if df is not None:
                fig, ax = plt.subplots(figsize=(6, 3.5))
                _cc = _chart_colors()
                fig.patch.set_facecolor(_cc["bg"]); ax.set_facecolor(_cc["bg_sub"])
                cols = ["#3fb950" if v == df["Affinity (kcal/mol)"].min() else "#58a6ff"
                        for v in df["Affinity (kcal/mol)"]]
                ax.bar(df["Pose"].astype(str), df["Affinity (kcal/mol)"],
                       color=cols, edgecolor=_cc["border"], linewidth=0.6)
                ax.invert_yaxis()
                ax.set_xlabel("Pose", color=_cc["muted"], fontsize=9)
                ax.set_ylabel("Affinity (kcal/mol)", color=_cc["muted"], fontsize=9)
                ax.tick_params(colors=_cc["muted"], labelsize=8)
                for sp in ax.spines.values(): sp.set_edgecolor(_cc["border"])
                fig.tight_layout()
                st.pyplot(fig, use_container_width=True); plt.close(fig)

        st.markdown("---")
        st.markdown("**🎬 Animated Pose Viewer**")
        anim_spd = st.slider("Interval (ms)", 500, 3000, 1500, 250, key="anim_spd")
        if st.session_state.output_sdf and os.path.exists(st.session_state.output_sdf):
            sdf_txt = open(st.session_state.output_sdf).read()
            va = py3Dmol.view(width="100%", height=440)
            va.setBackgroundColor(_viewer_bg())
            mai = 0
            if st.session_state.receptor_fh and os.path.exists(st.session_state.receptor_fh):
                va.addModel(open(st.session_state.receptor_fh).read(), "pdb")
                va.setStyle({"model": mai},
                             {"cartoon": {"color": "spectrum", "opacity": 0.7},
                              "stick":   {"radius": 0.1, "opacity": 0.2}}); mai += 1
            if st.session_state.ligand_pdb_path and os.path.exists(st.session_state.ligand_pdb_path):
                va.addModel(open(st.session_state.ligand_pdb_path).read(), "pdb")
                va.setStyle({"model": mai},
                             {"stick": {"colorscheme": "magentaCarbon", "radius": 0.22}}); mai += 1
            va.addModelsAsFrames(sdf_txt)
            va.setStyle({"model": mai}, {"stick": {"colorscheme": "greenCarbon", "radius": 0.25}})
            va.animate({"interval": anim_spd, "loop": "forward"})
            va.addSurface("SES", {"opacity": 0.18, "color": "lightblue"},
                          {"model": 0}, {"model": mai})
            va.zoomTo(); va.center({"model": mai}); va.rotate(30)
            show3d(va, height=440)

        st.markdown("---")
        st.markdown("**🔎 Interactive Pose Selector**")
        if mols:
            pose_idx = st.slider("Select pose", 1, len(mols), 1, key="pose_sel") - 1
            sel_mol  = mols[pose_idx]
            if df is not None:
                row = df[df["Pose"] == pose_idx + 1]
                if len(row):
                    aff = row.iloc[0]["Affinity (kcal/mol)"]
                    st.markdown(
                        f'{_pill(f"Pose {pose_idx+1}/{len(mols)}")} '
                        f'{_pill(f"Affinity: {aff:.2f} kcal/mol", "success" if aff < -8 else "warn")}',
                        unsafe_allow_html=True)

            cpv, cdl = st.columns([3, 1])
            with cpv:
                try:
                    v2 = py3Dmol.view(width="100%", height=400)
                    v2.setBackgroundColor(_viewer_bg())
                    mi2 = 0
                    if st.session_state.receptor_fh and os.path.exists(st.session_state.receptor_fh):
                        v2.addModel(open(st.session_state.receptor_fh).read(), "pdb")
                        v2.setStyle({"model": mi2},
                                     {"cartoon": {"color": "spectrum", "opacity": 0.5},
                                      "stick":   {"radius": 0.08, "opacity": 0.15}}); mi2 += 1
                    if st.session_state.ligand_pdb_path and os.path.exists(st.session_state.ligand_pdb_path):
                        v2.addModel(open(st.session_state.ligand_pdb_path).read(), "pdb")
                        v2.setStyle({"model": mi2},
                                     {"stick": {"colorscheme": "magentaCarbon", "radius": 0.2}}); mi2 += 1
                    v2.addModel(Chem.MolToMolBlock(sel_mol), "mol")
                    v2.setStyle({"model": mi2},
                                 {"stick": {"colorscheme": "cyanCarbon", "radius": 0.28}})
                    v2.addSurface("SES", {"opacity": 0.2, "color": "lightblue"},
                                  {"model": 0}, {"model": mi2})
                    v2.zoomTo(); v2.center({"model": mi2})
                    show3d(v2, height=400)
                except Exception as e:
                    st.info(f"Viewer error: {e}")

            with cdl:
                st.markdown("**Download**")
                sp_raw = str(WORKDIR / f"pose_{pose_idx+1}_raw.sdf")
                _write_single_pose(sel_mol, sp_raw)
                st.download_button(f"⬇ Pose {pose_idx+1} (.sdf)", open(sp_raw, "rb"),
                    file_name=f"pose_{pose_idx+1}.sdf", key=f"dl_p_{pose_idx}")
                st.download_button("⬇ All poses (.pdbqt)",
                    open(st.session_state.output_pdbqt, "rb"),
                    file_name=f"{st.session_state.dock_base}_out.pdbqt", key="dl_pdbqt")
                if df is not None:
                    st.download_button("⬇ Scores (.csv)",
                        df.to_csv(index=False).encode(),
                        file_name=f"{st.session_state.dock_base}_scores.csv",
                        mime="text/csv", key="dl_csv")
                if st.session_state.receptor_fh and os.path.exists(st.session_state.receptor_fh):
                    st.download_button("⬇ Receptor (.pdb)",
                        open(st.session_state.receptor_fh, "rb"),
                        file_name="receptor.pdb", key="dl_rec")

            pv_sdf_all = st.session_state.get("output_pv_sdf", "")
            sp_pv      = str(WORKDIR / f"pose_{pose_idx+1}_pv_ready.sdf")
            if pv_sdf_all and os.path.exists(pv_sdf_all):
                pv_mols_all = _load_pv_mols(pv_sdf_all)
                if pv_mols_all and pose_idx < len(pv_mols_all):
                    _write_single_pose(pv_mols_all[pose_idx], sp_pv)
                else:
                    _write_single_pose(sel_mol, sp_pv)
            else:
                _write_single_pose(sel_mol, sp_pv)

            _poseview_ui(
                rec_key="receptor_fh", raw_sdf_key="output_sdf",
                pv_sdf_key="output_pv_sdf", smiles_key="ligand_name",
                pose_idx=pose_idx, pose_sdf_path=sp_pv,
                img_url_key="pv_image_url", img_png_key="pv_image_png",
                img_svg_key="pv_image_svg", pose_key_key="pv_pose_key",
                btn_key="btn_pv_basic", dl_png_key="dl_pv_png_basic",
                dl_svg_key="dl_pv_svg_basic", label_suffix="_basic",
            )

    st.markdown('</div>', unsafe_allow_html=True)


# ╔════════════════════════════════════════════════════════════════════════════╗
#  TAB 2 — BATCH DOCKING
# ╚════════════════════════════════════════════════════════════════════════════╝
with tab_batch:

    _receptor_section(pfx="b_", wdir=BATCH_WORKDIR, step_label="Step B1 of B3")

    b_rec_done   = st.session_state.get("b_receptor_done", False)
    b_batch_done = st.session_state.get("b_batch_done", False)
    card_cls = "step-card done" if b_batch_done else "step-card"
    st.markdown(
        f'<div class="{card_cls}"><div class="step-title">Step B2 of B3</div>'
        f'<div class="step-heading">⚗️ Batch Ligand Input & Docking</div>',
        unsafe_allow_html=True)

    col_b1, col_b2 = st.columns([1.6, 1])
    with col_b1:
        b_input_mode = st.radio("Input mode",
            ["SMILES list (text)", "Upload .smi file", "Upload structure (.sdf/.mol2/.pdb)"],
            key="b_input_mode")

        if b_input_mode == "SMILES list (text)":
            st.text_area("One `SMILES [name]` per line",
                value=("C1=CC(=CC=C1C2=CC(=O)C3=C(C=C(C=C3O2)O)O)O Apigenin\n"
                       "C1=CC=C(C=C1)C2=CC(=O)C3=C(O2)C=C(C(=C3O)O)O Baicalein\n"
                       "CC1=CC=C(C=C1)NC2=NC=NC3=C2C=C(C=C3)O Osimertinib\n"
                       "C1=CC=C(C=C1)C2=CC(=O)C3=C(O2)C=C(C(=C3O)O)O Luteolin\n"
                       "CC(C)OC1=C(C=C2C(=C1)N=CN2)NC3=CC=CC(=C3)C#C Gefitinib\n"
                       "C1=CC=C(C=C1)C2=CC(=O)C3=C(O2)C=C(C(=C3O)O)OC Kaempferol\n"
                       "CCOC1=CC=C(C=C1)NC2=NC=NC3=C2C=C(C=C3)F Lapatinib\n"
                       "CC1=CC=C(C=C1)NC2=NC=NC3=C2C=C(C=C3)Cl Afatinib\n"
                       "C1=CC=C(C=C1)C2=CC(=O)C3=C(O2)C=C(C(=C3O)OC)O Galangin\n"
                       "CC1=C(C=C(C=C1)NC2=NC=NC3=C2C=CC=C3)OC Imatinib"),
                height=300, key="b_smiles_text")

        elif b_input_mode == "Upload .smi file":
            st.file_uploader("Upload .smi file", type=["smi", "txt"], key="b_smi_file")

        else:
            # ── Upload structure: PDB / MOL2 / SDF ───────────────────────────
            # Uses obabel --canonical for reliable SMILES extraction.
            # Live preview is shown as soon as a file is uploaded.
            b_struct_fobj = st.file_uploader(
                "Upload structure file (.pdb, .mol2, .sdf)",
                type=["pdb", "mol2", "sdf"],
                key="b_struct_file",
                help="Each molecule in the file becomes one docking ligand.",
            )

            if b_struct_fobj is not None:
                # Re-run conversion only when a new file is uploaded
                if st.session_state.get("b_struct_filename") != b_struct_fobj.name:
                    file_bytes = b_struct_fobj.read()
                    with st.spinner(f"Converting {b_struct_fobj.name} → canonical SMILES via obabel…"):
                        pairs, conv_err = pdb_to_canonical_smiles(file_bytes, b_struct_fobj.name)
                    if conv_err:
                        st.error(f"❌ Structure conversion failed: {conv_err}")
                        st.session_state["b_struct_smiles_pairs"] = None
                    else:
                        st.session_state["b_struct_smiles_pairs"] = pairs
                    st.session_state["b_struct_filename"] = b_struct_fobj.name

                # Show preview if conversion succeeded
                cached_pairs = st.session_state.get("b_struct_smiles_pairs")
                if cached_pairs:
                    n_mols = len(cached_pairs)
                    st.success(
                        f"✅ Converted **{n_mols} molecule{'s' if n_mols > 1 else ''}** "
                        f"from `{b_struct_fobj.name}` to canonical SMILES"
                    )

                    # Expandable table of extracted SMILES
                    with st.expander(
                        f"🔍 Preview extracted SMILES ({n_mols} molecule{'s' if n_mols > 1 else ''})",
                        expanded=(n_mols <= 10),
                    ):
                        preview_df = pd.DataFrame(
                            cached_pairs, columns=["SMILES", "Name"]
                        )
                        st.dataframe(preview_df, hide_index=True, use_container_width=True)

                        # Optional: 2D thumbnails for small sets
                        if n_mols <= 6:
                            try:
                                from rdkit import Chem
                                from rdkit.Chem import AllChem, Draw
                                thumb_cols = st.columns(min(n_mols, 3))
                                for col_i, (smi, nm) in enumerate(cached_pairs[:6]):
                                    m = Chem.MolFromSmiles(smi)
                                    if m:
                                        AllChem.Compute2DCoords(m)
                                        buf = io.BytesIO()
                                        Draw.MolToImage(m, size=(240, 180)).save(buf, format="PNG")
                                        with thumb_cols[col_i % 3]:
                                            st.image(buf.getvalue(), caption=nm, use_container_width=True)
                            except Exception:
                                pass  # 2D preview is cosmetic only

        b_ph     = st.number_input("Target pH", 0.0, 14.0, 7.4, 0.1, key="b_ph")
        b_stereo = st.checkbox("Enumerate stereocenters (use first isomer)", key="b_stereo")

    with col_b2:
        st.markdown("**Redocking validation**")
        b_do_redock = st.checkbox("Dock co-crystal ligand first as reference",
                                  value=True, key="b_do_redock")
        if b_do_redock:
            st.text_input("Co-crystal SMILES [name]",
                value="COCCOC1=C(C=C2C(=C1)C(=NC=N2)NC3=CC=CC(=C3)C#C)OCCOC Erlotinib",
                key="b_redock_smiles")
            st.caption("Score shown as dashed reference line in plot.")

        st.markdown("**Docking parameters**")
        b_exh = st.slider("Exhaustiveness", 4, 32, 8, 2, key="b_exh")
        b_nm  = st.slider("Poses per ligand", 5, 20, 10, 1, key="b_nm")
        b_er  = st.slider("Energy range (kcal/mol)", 1, 5, 3, 1, key="b_er")

    if not b_rec_done:
        st.caption("⚠ Complete Step B1 first.")
    if st.button("▶ Run Batch Docking", key="b_btn_dock", type="primary",
                 disabled=not b_rec_done):
        _rdkit_six_patch()
        from rdkit import Chem
        from rdkit.Chem import AllChem

        rec_pdbqt = st.session_state.get("b_receptor_pdbqt")
        config    = st.session_state.get("b_config_txt")
        b_ph_val  = st.session_state.get("b_ph", 7.4)

        # ── Parse ligand inputs ───────────────────────────────────────────────
        smiles_pairs = []
        try:
            mode = st.session_state.get("b_input_mode", "SMILES list (text)")

            if mode == "SMILES list (text)":
                for line in st.session_state.get("b_smiles_text", "").strip().splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"): continue
                    pts = line.split(None, 1)
                    smiles_pairs.append((
                        pts[0],
                        pts[1].replace(" ", "_") if len(pts) > 1 else f"lig_{len(smiles_pairs)+1}"
                    ))

            elif mode == "Upload .smi file":
                fobj = st.session_state.get("b_smi_file")
                if fobj is None: raise ValueError("No .smi file uploaded")
                for line in fobj.read().decode().splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"): continue
                    pts = line.split(None, 1)
                    smiles_pairs.append((
                        pts[0],
                        pts[1].replace(" ", "_") if len(pts) > 1 else f"lig_{len(smiles_pairs)+1}"
                    ))

            else:
                # ── Use cached obabel conversion result ───────────────────────
                # The preview block above already ran pdb_to_canonical_smiles()
                # and stored the pairs in session state.
                cached_pairs = st.session_state.get("b_struct_smiles_pairs")
                if not cached_pairs:
                    raise ValueError(
                        "No structure file converted yet — please upload a PDB/MOL2/SDF file "
                        "and wait for the SMILES preview before running docking."
                    )
                smiles_pairs = list(cached_pairs)

            if not smiles_pairs:
                raise ValueError("No valid SMILES found in the input.")

        except Exception as e:
            st.error(f"❌ Input parsing failed: {e}"); st.stop()

        if st.session_state.get("b_stereo", False):
            from rdkit.Chem.EnumerateStereoisomers import (
                EnumerateStereoisomers, StereoEnumerationOptions)
            expanded = []
            for smi, nm in smiles_pairs:
                mol = Chem.MolFromSmiles(smi)
                if mol is None: expanded.append((smi, nm)); continue
                isomers = list(EnumerateStereoisomers(
                    mol, options=StereoEnumerationOptions(unique=True, maxIsomers=2)))
                expanded.append((Chem.MolToSmiles(isomers[0]) if isomers else smi, nm))
            smiles_pairs = expanded

        # ── Ligand prep helper ────────────────────────────────────────────────
        def _prep_one(smi, name, ph, wdir):
            pdbqt_path = str(wdir / f"{name}.pdbqt")
            try:
                prot = smi
                try:
                    from dimorphite_dl import protonate_smiles
                    vs = protonate_smiles(prot, ph_min=ph, ph_max=ph, max_variants=1)
                    if vs: prot = vs[0]
                except Exception: pass
                mol = Chem.MolFromSmiles(prot)
                if mol is None: raise ValueError(f"Cannot parse SMILES: {smi[:50]}")
                mol = Chem.AddHs(mol)
                try:    params = AllChem.ETKDGv3()
                except: params = AllChem.ETKDG()
                params.randomSeed = 42
                if AllChem.EmbedMolecule(mol, params) == -1:
                    AllChem.EmbedMolecule(mol, useRandomCoords=True, randomSeed=42)
                if AllChem.MMFFHasAllMoleculeParams(mol):
                    AllChem.MMFFOptimizeMolecule(mol, maxIters=500)
                else:
                    AllChem.UFFOptimizeMolecule(mol, maxIters=500)
                _meeko_to_pdbqt(mol, pdbqt_path)
                return pdbqt_path, None
            except Exception as e:
                return None, str(e)

        # ── Docking helper ────────────────────────────────────────────────────
        def _dock_one(pdbqt_in, name, exh, nm, er):
            out_pdbqt = str(BATCH_WORKDIR / f"{name}_out.pdbqt")
            out_sdf   = str(BATCH_WORKDIR / f"{name}_out.sdf")
            rc, log   = run_cmd(
                f'"{VINA_PATH}" --receptor "{rec_pdbqt}" --ligand "{pdbqt_in}" '
                f'--config "{config}" --exhaustiveness {exh} --num_modes {nm} '
                f'--energy_range {er} --out "{out_pdbqt}"',
                cwd=str(BATCH_WORKDIR))
            if rc != 0 or not os.path.exists(out_pdbqt):
                return None, None, log, None, []
            run_cmd(f'obabel "{out_pdbqt}" -O "{out_sdf}" 2>/dev/null')
            pose_scores = []
            for line in open(out_pdbqt):
                if line.strip().startswith("REMARK VINA RESULT:"):
                    try: pose_scores.append(float(line.split()[3]))
                    except: pass
            top = pose_scores[0] if pose_scores else None
            return out_pdbqt, out_sdf, log, top, pose_scores

        # ── Redocking ─────────────────────────────────────────────────────────
        redock_score  = None
        redock_result = None
        if st.session_state.get("b_do_redock", False):
            raw_rd = st.session_state.get("b_redock_smiles", "").strip()
            pts    = raw_rd.split(None, 1)
            rd_smi = pts[0]
            rd_nm  = (pts[1].replace(" ", "_") if len(pts) > 1 else "redock")
            with st.spinner(f"Docking reference ligand ({rd_nm})…"):
                rd_pdbqt, rd_err = _prep_one(rd_smi, "redock_" + rd_nm, b_ph_val, BATCH_WORKDIR)
                if rd_pdbqt:
                    rd_out_pdbqt, rd_out_sdf, _, rd_top, rd_pose_scores = _dock_one(
                        rd_pdbqt, "redock_" + rd_nm, b_exh, b_nm, b_er)
                    if rd_top is not None:
                        redock_score = rd_top
                        rd_pv_sdf = str(BATCH_WORKDIR / f"redock_{rd_nm}_pv_ready.sdf")
                        _fix_sdf_bond_orders(rd_out_sdf, rd_smi, rd_pv_sdf)
                        if not os.path.exists(rd_pv_sdf) or os.path.getsize(rd_pv_sdf) < 10:
                            rd_pv_sdf = rd_out_sdf
                        rd_n_poses = 0
                        if rd_out_sdf and os.path.exists(rd_out_sdf):
                            rd_n_poses = sum(
                                1 for m in Chem.SDMolSupplier(rd_out_sdf, sanitize=False) if m)
                        redock_result = {
                            "Name":        f"⭐ {rd_nm} (co-crystal ref)",
                            "SMILES":      rd_smi,
                            "Top Score":   rd_top,
                            "pose_scores": rd_pose_scores,
                            "Poses":       rd_n_poses,
                            "out_pdbqt":   rd_out_pdbqt,
                            "out_sdf":     rd_out_sdf,
                            "pv_sdf":      rd_pv_sdf,
                            "Status":      "OK",
                            "is_redock":   True,
                        }
                        st.success(f"✓ Reference score: **{redock_score:.2f} kcal/mol** ({rd_nm})")
                    else:
                        st.warning("⚠ Redocking failed — no score returned")
                else:
                    st.warning(f"⚠ Reference ligand prep failed: {rd_err}")

        # ── Main batch loop ───────────────────────────────────────────────────
        results  = []
        n        = len(smiles_pairs)
        prog     = st.progress(0, text=f"Docking 0/{n}…")
        log_slot = st.empty()
        all_logs = []

        for i, (smi, name) in enumerate(smiles_pairs):
            prog.progress(i / n, text=f"Docking {name} ({i+1}/{n})…")
            pdbqt_in, prep_err = _prep_one(smi, name, b_ph_val, BATCH_WORKDIR)
            if pdbqt_in is None:
                results.append({"Name": name, "SMILES": smi, "Top Score": None,
                                 "Poses": 0, "Status": f"PREP FAILED: {prep_err}"})
                all_logs.append(f"[{name}] PREP ERROR: {prep_err}"); continue

            out_pdbqt, out_sdf, dock_log, top, pose_scores = _dock_one(
                pdbqt_in, name, b_exh, b_nm, b_er)
            all_logs.append(f"[{name}] score={top} | {dock_log[:120]}")
            log_slot.markdown(
                f'<div class="log-box">{"".join(all_logs[-5:])}</div>',
                unsafe_allow_html=True)

            if top is None:
                results.append({"Name": name, "SMILES": smi, "Top Score": None,
                                 "Poses": 0, "Status": "DOCK FAILED"}); continue

            pv_sdf = str(BATCH_WORKDIR / f"{name}_pv_ready.sdf")
            _fix_sdf_bond_orders(out_sdf, smi, pv_sdf)
            if not os.path.exists(pv_sdf) or os.path.getsize(pv_sdf) < 10:
                pv_sdf = out_sdf

            n_poses = 0
            if out_sdf and os.path.exists(out_sdf):
                n_poses = sum(1 for m in Chem.SDMolSupplier(out_sdf, sanitize=False) if m)
            results.append({
                "Name": name, "SMILES": smi, "Top Score": top,
                "pose_scores": pose_scores, "Poses": n_poses,
                "out_pdbqt": out_pdbqt, "out_sdf": out_sdf,
                "pv_sdf": pv_sdf, "Status": "OK",
            })

        n_ok_final = sum(1 for r in results if r["Status"] == "OK")
        prog.progress(1.0, text=f"✓ Done — {n_ok_final}/{n} ligands docked successfully")
        log_slot.empty()
        st.session_state.update({
            "b_batch_done":          True,
            "b_batch_results":       results,
            "b_batch_log":           "\n".join(all_logs),
            "b_redock_score":        redock_score,
            "b_redock_result":       redock_result,
            "b_confirmed_ref_score": None,
            "b_confirmed_ref_pose":  None,
            "b_confirmed_ref_name":  None,
            "b_pv_image_url": None, "b_pv_image_png": None,
            "b_pv_image_svg": None, "b_pv_pose_key":  None,
            "b_plot_png":     None,
        })

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<hr class="step-divider">', unsafe_allow_html=True)

    # ── Step B3: Results ──────────────────────────────────────────────────────
    b_batch_done = st.session_state.get("b_batch_done", False)
    card_cls = "step-card done" if b_batch_done else "step-card"
    st.markdown(
        f'<div class="{card_cls}"><div class="step-title">Step B3 of B3</div>'
        f'<div class="step-heading">📊 Batch Results</div>',
        unsafe_allow_html=True)

    if not b_batch_done:
        st.info("Complete Step B2 to see batch results here.")
    else:
        import py3Dmol
        from rdkit import Chem
        results             = st.session_state.get("b_batch_results", [])
        redock_score        = st.session_state.get("b_redock_score")
        redock_result       = st.session_state.get("b_redock_result")
        confirmed_ref_score = st.session_state.get("b_confirmed_ref_score")
        confirmed_ref_pose  = st.session_state.get("b_confirmed_ref_pose")
        confirmed_ref_name  = st.session_state.get("b_confirmed_ref_name")
        active_ref_score    = (confirmed_ref_score if confirmed_ref_score is not None
                               else redock_score)

        n_ok   = sum(1 for r in results if r["Status"] == "OK")
        n_fail = len(results) - n_ok
        st.markdown(
            f"{_pill(f'{n_ok} ligands docked ✓', 'success')} "
            f"{_pill('AutoDock Vina 1.2.7')}"
            + (f" {_pill(f'{n_fail} failed', 'warn')}" if n_fail else ""),
            unsafe_allow_html=True)

        st.markdown("**🔎 Pose Browser**")
        ok_results = [r for r in results
                      if r["Status"] == "OK"
                      and r.get("out_sdf") and os.path.exists(r["out_sdf"])]
        if redock_result and redock_result.get("out_sdf") and os.path.exists(redock_result["out_sdf"]):
            browsable = [redock_result] + ok_results
        else:
            browsable = ok_results

        if browsable:
            sel_nm = st.selectbox(
                "Select ligand", [r["Name"] for r in browsable], index=0, key="b_lig_sel")
            sel_res       = next(r for r in browsable if r["Name"] == sel_nm)
            is_redock_sel = sel_res.get("is_redock", False)
            pose_scores_list = sel_res.get("pose_scores", [])

            b_mols = [m for m in Chem.SDMolSupplier(sel_res["out_sdf"], sanitize=False) if m]
            if b_mols:
                b_pose_i = st.slider("Pose", 1, len(b_mols), 1, key="b_pose_sel") - 1
                this_pose_score = (pose_scores_list[b_pose_i]
                                   if pose_scores_list and b_pose_i < len(pose_scores_list)
                                   else sel_res["Top Score"])
                score_kind = ("success" if (this_pose_score is not None
                                            and this_pose_score < -8) else "warn")

                row_pills = (
                    f'{_pill(f"Pose {b_pose_i+1} / {len(b_mols)}")}'
                    f'{_pill(f"Score: {this_pose_score:.2f} kcal/mol", score_kind) if this_pose_score is not None else ""}'
                )
                if pose_scores_list and b_pose_i > 0 and len(pose_scores_list) > 1:
                    delta = this_pose_score - pose_scores_list[0]
                    row_pills += f' {_pill(f"Δ {delta:+.2f} vs pose 1")}'

                if is_redock_sel:
                    st.markdown(
                        f'<div style="margin-bottom:6px">'
                        f'{_pill("⭐ Co-crystal reference ligand", "warn")}</div>',
                        unsafe_allow_html=True)
                    if confirmed_ref_score is not None:
                        st.markdown(
                            f'<div style="background:#23863622;border:1px solid #238636;'
                            f'border-radius:8px;padding:10px 16px;margin-bottom:10px;'
                            f'font-family:\'IBM Plex Mono\',monospace;">'
                            f'<span style="color:#3fb950;font-size:0.85rem;">✅ Reference locked:</span> '
                            f'<b style="color:#3fb950">{confirmed_ref_score:.2f} kcal/mol</b>'
                            f'<span style="color:#8b949e;font-size:0.8rem;"> — pose '
                            f'{confirmed_ref_pose} of {confirmed_ref_name}</span></div>',
                            unsafe_allow_html=True)

                st.markdown(row_pills, unsafe_allow_html=True)

                cbv, cbd = st.columns([3, 1])
                with cbv:
                    try:
                        vb = py3Dmol.view(width="100%", height=420)
                        vb.setBackgroundColor(_viewer_bg()); bmi = 0
                        rec_fh = st.session_state.get("b_receptor_fh")
                        if rec_fh and os.path.exists(rec_fh):
                            vb.addModel(open(rec_fh).read(), "pdb")
                            vb.setStyle({"model": bmi},
                                         {"cartoon": {"color": "spectrum", "opacity": 0.7},
                                          "stick":   {"radius": 0.08, "opacity": 0.15}}); bmi += 1
                        lig_p = st.session_state.get("b_ligand_pdb_path")
                        if lig_p and os.path.exists(lig_p):
                            vb.addModel(open(lig_p).read(), "pdb")
                            vb.setStyle({"model": bmi},
                                         {"stick": {"colorscheme": "magentaCarbon",
                                                    "radius": 0.2}}); bmi += 1
                        vb.addModel(Chem.MolToMolBlock(b_mols[b_pose_i]), "mol")
                        vb.setStyle({"model": bmi},
                                     {"stick": {"colorscheme": "cyanCarbon", "radius": 0.28}})
                        vb.addSurface("SES", {"opacity": 0.2, "color": "lightblue"},
                                      {"model": 0}, {"model": bmi})
                        vb.zoomTo(); vb.center({"model": bmi})
                        show3d(vb, height=420)
                    except Exception as e:
                        st.info(f"Viewer error: {e}")

                with cbd:
                    st.markdown("**Actions**")

                    if is_redock_sel and this_pose_score is not None:
                        already_confirmed = (
                            confirmed_ref_score == this_pose_score
                            and confirmed_ref_pose == b_pose_i + 1
                        )
                        btn_label = (f"✅ Confirmed (pose {b_pose_i+1})"
                                     if already_confirmed
                                     else f"📌 Use pose {b_pose_i+1} as reference")
                        if st.button(btn_label, key="b_confirm_ref_btn",
                                     type="primary" if not already_confirmed else "secondary",
                                     use_container_width=True):
                            st.session_state["b_confirmed_ref_score"] = this_pose_score
                            st.session_state["b_confirmed_ref_pose"]  = b_pose_i + 1
                            st.session_state["b_confirmed_ref_name"]  = sel_nm
                            st.rerun()
                        if confirmed_ref_score is not None and not already_confirmed:
                            if st.button("🔄 Reset reference", key="b_reset_ref_btn",
                                         use_container_width=True):
                                st.session_state["b_confirmed_ref_score"] = None
                                st.session_state["b_confirmed_ref_pose"]  = None
                                st.session_state["b_confirmed_ref_name"]  = None
                                st.rerun()

                    st.markdown("**Download**")
                    safe_sel_nm = sel_nm.replace("⭐ ", "").replace(" (co-crystal ref)", "")
                    sp3 = str(BATCH_WORKDIR / f"{safe_sel_nm}_pose{b_pose_i+1}.sdf")
                    _write_single_pose(b_mols[b_pose_i], sp3)
                    st.download_button(f"⬇ Pose {b_pose_i+1} (.sdf)", open(sp3, "rb"),
                        file_name=f"{safe_sel_nm}_pose{b_pose_i+1}.sdf", key="b_dl_pose")
                    if sel_res.get("out_pdbqt") and os.path.exists(sel_res["out_pdbqt"]):
                        st.download_button("⬇ All poses (.pdbqt)",
                            open(sel_res["out_pdbqt"], "rb"),
                            file_name=f"{safe_sel_nm}_out.pdbqt", key="b_dl_pdbqt")

                pv_sdf_all = sel_res.get("pv_sdf", "")
                sp3_pv     = str(BATCH_WORKDIR / f"{safe_sel_nm}_pose{b_pose_i+1}_pv_ready.sdf")
                if pv_sdf_all and os.path.exists(pv_sdf_all):
                    pv_mols_all = _load_pv_mols(pv_sdf_all)
                    if pv_mols_all and b_pose_i < len(pv_mols_all):
                        _write_single_pose(pv_mols_all[b_pose_i], sp3_pv)
                    else:
                        _write_single_pose(b_mols[b_pose_i], sp3_pv)
                else:
                    _write_single_pose(b_mols[b_pose_i], sp3_pv)

                st.session_state["_b_cur_smiles"] = sel_res.get("SMILES", sel_nm)

                _poseview_ui(
                    rec_key="b_receptor_fh", raw_sdf_key="b_cur_out_sdf",
                    pv_sdf_key="b_cur_pv_sdf", smiles_key="_b_cur_smiles",
                    pose_idx=b_pose_i, pose_sdf_path=sp3_pv,
                    img_url_key="b_pv_image_url", img_png_key="b_pv_image_png",
                    img_svg_key="b_pv_image_svg", pose_key_key="b_pv_pose_key",
                    btn_key="btn_pv_batch", dl_png_key="dl_pv_png_batch",
                    dl_svg_key="dl_pv_svg_batch", label_suffix=f"_{safe_sel_nm}",
                )

        st.markdown("---")
        with st.expander("📋 Full docking log", expanded=False):
            st.markdown(
                f'<div class="log-box">{st.session_state.get("b_batch_log","")}</div>',
                unsafe_allow_html=True)

        df_res = pd.DataFrame([
            {"Name": r["Name"], "Top Score (kcal/mol)": r["Top Score"],
             "Poses": r["Poses"], "Status": r["Status"]}
            for r in results
        ])
        ok_df = (df_res[df_res["Status"] == "OK"]
                 .sort_values("Top Score (kcal/mol)")
                 .reset_index(drop=True))

        ct2, cp2 = st.columns([1, 1.6])
        with ct2:
            st.markdown("**Score Table**")
            st.dataframe(df_res, hide_index=True, use_container_width=True)
        with cp2:
            st.markdown("**Top Score per Ligand**")
            if not ok_df.empty:
                fig, ax = plt.subplots(figsize=(max(5, len(ok_df)*0.6 + 1.5), 4))
                _cc = _chart_colors()
                fig.patch.set_facecolor(_cc["bg"]); ax.set_facecolor(_cc["bg_sub"])
                scores = ok_df["Top Score (kcal/mol)"].values
                names  = ok_df["Name"].values
                best_i = int(np.argmin(scores))
                colors = ["#3fb950" if i == best_i else "#58a6ff" for i in range(len(scores))]
                ax.scatter(names, scores, color=colors, s=90, zorder=3,
                           edgecolors=_cc["border"], linewidths=0.5)
                ax.plot(names, scores, color=_cc["border"], linewidth=0.8, zorder=2)
                if active_ref_score is not None:
                    ref_label = (
                        f"✓ Confirmed ref (pose {confirmed_ref_pose}): {active_ref_score:.2f} kcal/mol"
                        if confirmed_ref_score is not None
                        else f"Co-crystal ref (top pose): {active_ref_score:.2f} kcal/mol"
                    )
                    ax.axhline(active_ref_score, color="#f85149", linewidth=1.8,
                               linestyle="--", label=ref_label)
                    ax.legend(facecolor=_cc["legend_bg"], edgecolor=_cc["border"],
                              labelcolor=_cc["text"], fontsize=8)
                ax.set_ylabel("Vina score (kcal/mol)", color=_cc["muted"], fontsize=9)
                ax.set_xlabel("Ligand",               color=_cc["muted"], fontsize=9)
                ax.tick_params(colors=_cc["muted"], labelsize=7)
                plt.xticks(rotation=40, ha="right")
                for sp in ax.spines.values(): sp.set_edgecolor(_cc["border"])
                ax.grid(axis="y", color=_cc["bg_sub"], linewidth=0.5)
                fig.tight_layout()
                # Save plot bytes to session state BEFORE closing
                _plot_buf = io.BytesIO()
                fig.savefig(_plot_buf, format="png", dpi=150, bbox_inches="tight",
                            facecolor=fig.get_facecolor())
                _plot_buf.seek(0)
                st.session_state["b_plot_png"] = _plot_buf.getvalue()
                st.pyplot(fig, use_container_width=True); plt.close(fig)

        st.markdown("---")
        st.markdown("**⬇ Download All Results**")

        # ── Row 1: CSV + Plot + PoseView ──────────────────────────────────────
        dl_c1, dl_c2, dl_c3 = st.columns(3)

        with dl_c1:
            if not ok_df.empty:
                st.download_button(
                    "📊 Top scores (.csv)",
                    ok_df.to_csv(index=False).encode(),
                    file_name="batch_scores.csv",
                    mime="text/csv",
                    key="b_dl_csv",
                    use_container_width=True,
                )

        with dl_c2:
            _plot_bytes = st.session_state.get("b_plot_png")
            if _plot_bytes:
                st.download_button(
                    "📈 Score plot (.png)",
                    data=_plot_bytes,
                    file_name="batch_score_plot.png",
                    mime="image/png",
                    key="b_dl_plot_png",
                    use_container_width=True,
                )
            else:
                st.caption("Run docking to generate the score plot.")

        with dl_c3:
            _pv_png  = st.session_state.get("b_pv_image_png")
            _pv_svg  = st.session_state.get("b_pv_image_svg")
            _pv_url  = st.session_state.get("b_pv_image_url")
            _cur_lig = st.session_state.get("_b_cur_smiles", "ligand")[:20]

            if _pv_png:
                st.download_button(
                    "🧬 2D interaction (.png)",
                    data=_pv_png,
                    file_name="poseview_2d_interaction.png",
                    mime="image/png",
                    key="b_dl_pv_png_bulk",
                    use_container_width=True,
                )
            elif _pv_svg:
                st.download_button(
                    "🧬 2D interaction (.svg)",
                    data=_pv_svg,
                    file_name="poseview_2d_interaction.svg",
                    mime="image/svg+xml",
                    key="b_dl_pv_svg_bulk",
                    use_container_width=True,
                )
            else:
                st.caption("Generate a 2D diagram above to enable this download.")

        # If both PNG and SVG are available, show SVG button too
        if _pv_png and _pv_svg:
            st.download_button(
                "🧬 2D interaction (.svg — vector, for publications)",
                data=_pv_svg,
                file_name="poseview_2d_interaction.svg",
                mime="image/svg+xml",
                key="b_dl_pv_svg_bulk2",
                use_container_width=True,
            )

        st.markdown("---")

        # ── Row 2: Full ZIP ───────────────────────────────────────────────────
        zb = io.BytesIO()
        zip_results = ([redock_result] if redock_result else []) + ok_results
        with zipfile.ZipFile(zb, "w", zipfile.ZIP_DEFLATED) as zf:
            for r in zip_results:
                sn = r["Name"].replace("⭐ ", "").replace(" (co-crystal ref)", "")
                if r.get("out_sdf") and os.path.exists(r["out_sdf"]):
                    zf.write(r["out_sdf"], f"poses/{sn}_out.sdf")
                if r.get("pv_sdf") and os.path.exists(r["pv_sdf"]):
                    zf.write(r["pv_sdf"], f"poses_pv_ready/{sn}_pv_ready.sdf")
                if r.get("out_pdbqt") and os.path.exists(r["out_pdbqt"]):
                    zf.write(r["out_pdbqt"], f"pdbqt/{sn}_out.pdbqt")
            if not ok_df.empty:
                zf.writestr("batch_scores.csv", ok_df.to_csv(index=False))
            # Include plot PNG in ZIP
            _plot_bytes_zip = st.session_state.get("b_plot_png")
            if _plot_bytes_zip:
                zf.writestr("batch_score_plot.png", _plot_bytes_zip)
            # Include PoseView images in ZIP
            _pv_png_zip = st.session_state.get("b_pv_image_png")
            _pv_svg_zip = st.session_state.get("b_pv_image_svg")
            if _pv_png_zip:
                zf.writestr("poseview/2d_interaction.png", _pv_png_zip)
            if _pv_svg_zip:
                zf.writestr("poseview/2d_interaction.svg", bytes(_pv_svg_zip))
            rec_fh = st.session_state.get("b_receptor_fh")
            if rec_fh and os.path.exists(rec_fh):
                zf.write(rec_fh, "receptor.pdb")
        zb.seek(0)
        st.download_button(
            "📦 Download ALL results (.zip) — structures + plot + 2D diagram",
            zb,
            file_name="batch_docking_results.zip",
            mime="application/zip",
            key="b_dl_zip",
            use_container_width=True,
        )

    st.markdown('</div>', unsafe_allow_html=True)


# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown('<hr class="step-divider">', unsafe_allow_html=True)
st.markdown(
    '<div style="text-align:center;color:#57606A;font-size:0.78rem;'
    'font-family:\'IBM Plex Mono\',monospace;">'
    'AutoDock Vina 1.2.7 · Meeko · RDKit · OpenBabel · py3Dmol<br>'
    'Eberhardt et al. J. Chem. Inf. Model. 2021, 61, 3891–3898 &nbsp;·&nbsp; '
    '<a href="https://pubs.acs.org/doi/10.1021/acs.jcim.5c02852" target="_blank" '
    'style="color:#58a6ff;text-decoration:none;">'
    'DFDD — Hengphasatporn et al. J. Chem. Inf. Model. 2026</a>'
    '</div>',
    unsafe_allow_html=True,
)
