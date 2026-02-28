#!/usr/bin/env python3
"""
AutoDock Vina 1.2.7 — Streamlit Docking Interface
Tabs: Basic (single ligand) | Batch (multiple ligands)
"""

import streamlit as st
import os, sys, subprocess, tempfile, io, zipfile, re as _re
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


# ─── Theme — Light only ───────────────────────────────────────────────────────
import streamlit.components.v1 as _comps

def _chart_colors():
    """Return chart colors matching Streamlit's active theme (light or dark)."""
    try:
        dark = st.get_option("theme.base") == "dark"
    except Exception:
        dark = False
    if dark:
        return {
            "bg":        "#0d1117",
            "bg_sub":    "#161b22",
            "border":    "#30363d",
            "text":      "#c9d1d9",
            "muted":     "#8b949e",
            "legend_bg": "#21262d",
        }
    return {
        "bg":        "#FFFFFF",
        "bg_sub":    "#F6F8FA",
        "border":    "#D0D7DE",
        "text":      "#24292F",
        "muted":     "#57606A",
        "legend_bg": "#F6F8FA",
    }

def _viewer_bg():
    """Return py3Dmol background color matching active theme."""
    try:
        return "#0d1117" if st.get_option("theme.base") == "dark" else "#FFFFFF"
    except Exception:
        return "#FFFFFF"

# ─── Global CSS (Auto light/dark theme) ─────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

:root {
    --bg:          #FFFFFF;
    --bg-subtle:   #F6F8FA;
    --bg-card:     #f3f4f6;
    --bg-input:    #FFFFFF;
    --border:      #D0D7DE;
    --text:        #24292F;
    --text-muted:  #57606A;
    --accent:      #0969DA;
    --accent2:     #0550AE;
    --success:     #1A7F37;
    --warn:        #9A6700;
    --text-card-title:   #6b7280;
    --text-card-heading: #111827;
    --text-input:        #24292F;
    --border-input:      #D0D7DE;
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
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-left: 4px solid var(--accent);
    border-radius: 8px;
    padding: 20px 24px;
    margin-bottom: 24px;
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
.stButton > button[kind="secondary"] { background: var(--btn-sec-bg); border: 1px solid var(--border); color: var(--text); }
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

/* Dark gray for 3D Receptor + Docking Box expander label */
[data-testid="stExpander"]:has(summary:contains("3D")) summary p,
.st-expander-3d summary p { color: #6b7280 !important; }

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

# ─── Session State ─────────────────────────────────────────────────────────────
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
    output_pdbqt=None, output_sdf=None, dock_base=None,
    docking_done=False, docking_log="", score_df=None, pose_mols=None,
    # Batch — receptor  (b_ prefix keeps state separate)
    b_pdb_token=None, b_raw_pdb=None, b_receptor_fh=None, b_receptor_pdbqt=None,
    b_box_pdb=None, b_config_txt=None, b_cx=None, b_cy=None, b_cz=None,
    b_ligand_pdb_path=None, b_receptor_done=False, b_receptor_log="",
    # Batch — results
    b_batch_done=False, b_batch_results=None, b_batch_log="",
    b_redock_score=None, b_redock_result=None,
    # Confirmed reference score (set when user clicks "Use this pose as reference")
    b_confirmed_ref_score=None, b_confirmed_ref_pose=None, b_confirmed_ref_name=None,
    # PoseView — Basic tab
    pv_image_url=None, pv_image_png=None, pv_image_svg=None, pv_pose_key=None,
    # PoseView — Batch tab
    b_pv_image_url=None, b_pv_image_png=None, b_pv_image_svg=None, b_pv_pose_key=None,
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

# ─── Helpers ──────────────────────────────────────────────────────────────────
def show3d(view, height=480):
    """Render py3Dmol responsively — fills container on any screen width."""
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


# ─── PoseView Helper ───────────────────────────────────────────────────────────
def _call_poseview(receptor_pdb: str, pose_sdf: str):
    """Submit to proteins.plus PoseView API. Returns (image_url, error)."""
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
    for _ in range(30):                          # poll up to 60 s
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
    """Convert SVG bytes → PNG bytes via cairosvg, white background. Returns None on failure."""
    try:
        import cairosvg
        return cairosvg.svg2png(bytestring=svg_bytes, scale=2, background_color="white")
    except Exception:
        return None


# ─── PoseView legend (base64-embedded) ───────────────────────────────────────
_POSEVIEW_LEGEND_B64 = "/9j/4AAQSkZJRgABAQAAAQABAAD/4gHYSUNDX1BST0ZJTEUAAQEAAAHIAAAAAAQwAABtbnRyUkdCIFhZWiAH4AABAAEAAAAAAABhY3NwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAA9tYAAQAAAADTLQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAlkZXNjAAAA8AAAACRyWFlaAAABFAAAABRnWFlaAAABKAAAABRiWFlaAAABPAAAABR3dHB0AAABUAAAABRyVFJDAAABZAAAAChnVFJDAAABZAAAAChiVFJDAAABZAAAAChjcHJ0AAABjAAAADxtbHVjAAAAAAAAAAEAAAAMZW5VUwAAAAgAAAAcAHMAUgBHAEJYWVogAAAAAAAAb6IAADj1AAADkFhZWiAAAAAAAABimQAAt4UAABjaWFlaIAAAAAAAACSgAAAPhAAAts9YWVogAAAAAAAA9tYAAQAAAADTLXBhcmEAAAAAAAQAAAACZmYAAPKnAAANWQAAE9AAAApbAAAAAAAAAABtbHVjAAAAAAAAAAEAAAAMZW5VUwAAACAAAAAcAEcAbwBvAGcAbABlACAASQBuAGMALgAgADIAMAAxADb/2wBDAAUDBAQEAwUEBAQFBQUGBwwIBwcHBw8LCwkMEQ8SEhEPERETFhwXExQaFRERGCEYGh0dHx8fExciJCIeJBweHx7/2wBDAQUFBQcGBw4ICA4eFBEUHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh7/wAARCAB+BpQDASIAAhEBAxEB/8QAHQABAAEFAQEBAAAAAAAAAAAAAAECBQYHCAQDCf/EAGIQAAEDAwIEAgMJCQkMBQsFAQEAAgMEBREGBwgSITETQSJRYRQXMlVxgZGh0QkVFiM3UnaxtDNCU1RikpPS4jhyc3R1lKOksrPB4SQ1NoLwGCUnNDlDZIOiwvEoRGNmw9P/xAAbAQEAAwEBAQEAAAAAAAAAAAAAAgMEAQUGB//EADQRAQACAQIDBgMHAwUAAAAAAAABAgMEERITUQUUIVJxkTFTYQYVIjJBgaGiweEjM1Ry0f/aAAwDAQACEQMRAD8A6X2L/IhoP9G7d+zRrNFhexP5ENB/o3bv2aNZogIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiAiIgIiICIiDgD7o5+W+zfo3B+01KJ90c/LfZv0bg/aalEHZmxP5ENB/o3bv2aNZmsM2J/IhoP9G7d+zRrM0BERAREQEREBERAREQEREBERAREQEREBFo7ib3e1DtldtKUljorbUsvFW6Cc1bHuLWgsGW8rh19I98rdNsnfU26nqJA0Okja48vbJCD0IiICIiAioqHFkEjx3a0n6lovhh3i1HufX3iC+UNtpm0TnNjNLG9pOOTvzOP5xQb3REQEREBERAREQEREBERARFpLio3a1BtXR6elsNFbqp9zrTBN7sY9wa3Gct5XN6oN2ovPbJ3VVup6h4AdJGHEDtkhehAREQEREBERAReO+VT6Kz1lZG1rnwQvkaHdiQM9VqHhd3Yv+6J1X9/KK3Uws9ZHBT+5GPbzNcZM83M45PoDthBupERAREQEREBERAREQEREBERAREQEREBERAREQEREBERAREQEREBERAREQEREBERAREQEREBERARFDjytLj5DKCUWqNBbzWzWW7180JbaGeP7zwvdNPK0APe2QMIbg9uvqW10BEXnuM7qahmnaAXMYXAFB6EWkuFTdvUO6tpvFXfqK20z6KtdBGKNj2gtDWnJ5nHr6RW7UBFpvUm4uuqDfi3aNo7JQy6eqHxiWrex3itDizODz4/fHy8luRARFRUStggfM/4LGlx+QIK0WsNot3KDcXWGqrNbqKaCCwzspy+UAGRxLw4jBPTLD6ls9AREQEREBERAREQEWs9/t27btVYKatq6SarqaydsFPHGARk5OXZI6YaVedzNTXmxbWXLUtgoYau5wUvjU8EwJY53ToQCD9aDM0WDbG6o1BrDbugv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P0bt37NGsyQTlMqMplBOUUZTKCcplRlMoJymVGUygnKZUZTKCcplRlMoJymVGUygnKZUZTKCcplRlMoJymVGUygnKZUZTKCcplRlMoJymVGUygnKZUZTKCcplRlMoJymVGUygnKZUZTKCcplRlMoJymVGUygnKZUZTKCcplRlMoJymVGUygnKZUZTKCcplRlMoJymVGUygnKZUZTKCcplRlMoJymVGUygnKZUZTKCcplRlMoJymVGUygnKZUZTKCcplRlMoJymVGUygnKZUZTKCcplRlMoJymVGUygnKZUZTKCcplRlMoJymVGUygnKZUZTKCcplRlMoJymVGUygnKZUZTKCcplRlMoJymVGUygnKZUZTKCcplRlMoJymVGUygnKZUZTKCcplRlMoJysC3w21oN09IxaduNY6khjqmVIkawuOWhwxgEfnetZ3lTlBbtL2mKw6forRC8yR0kTYmuIxkAYyrllU5TKCpQoymUEooymUEooymUEooymUEooymUEooymUEooymUEooymUEooymUEooymUFWUyoymUE5TKjKZQTlMqMplBOUyoymUE5TKjKZQTlMqMplBOUyoymUE5TKjKZQTlMqMplBOUyoymUE5TKjKZQTlMqMplBOUyoymUE5TKjKZQTlMqMplBOUyoymUE5TKjKZQTlMqMplBOUyoymUE5Wmt8Ni4tz9R0t1n1VWWyCKFsM1JE1zmTNBJ64e0efqW5MqM+xBj23Oj7JoXS1Np6xUzIaaEDmIHWR3KAXH1k4CyNU59inKCcplRlMoJymVGUygnKZUZTKDAN89r7futpimsVxrXUkcFW2pD2sLiSGubjo4fnLM7Fb47TaKa3RPL2QMDA7GMr2ZTKCcplRlMoJymVGUygnKZUZTKCcplRlMoJymVGUygnKZUZTKCcplRlMoJz7EyoymUE5TKjKjKCrKZVOUygqymVTlMoKsplU5TKCrKZVOUygqymVTlMoKsplU5TKCrKEqnKZQcC/dGvy3Wb9G4P2mpRR90Z/LdZv0bg/aalEHZOxf5EtCfo3b/ANmjWZLCtiz/AOhPQg//AK3b/wBmjWZ9UE5CZVOUygqymVTlMoKsplU5TKCrKZVOUygqymVTlMoKsplU5TKCrKZVOUygqymVTlMoKsplU5TKCrKZVOUygqymVTlMoKsplU5TKCrKZVOUygqymVTlMoKsplU5TKCrKZVOUygqymVTlMoKsplU5TKCrKZVOUygqymVTlMoKsplU5TKCrKZVOUygqymVTlMoKsplU5TKCrKZVOUygqymVTlMoKsplU5TKCrKZVOUygqymVTlMoKsplU5TKCrKZVOUygrRUZ9iZ9iCtFRn2Jn2IK0VGfYmfYgqymVSiCrKZVKIKsplUogqymVSiCrKZVKIKsplUogqymVSiCrKZVKIKsplUogqymVSiCrKZVKIKsplUogqymVSiCrKZVKIKsplUogqymVSiCrKZVKIKsplUogqymVSiCrKZVKIKsplUogqymVSiCrKZVKIKsplUogqymVSiCrKZVKIKsplUogqymVSiCrKZVKIK0VGfYmfYgqymVSiCrKZVKIKsplUogqymVSiCrKZVKIKsplUogqymVSiCrKZVKIKsplUogqymVSiCrKZVKIKsplUogqymVSiCrKZVKIKsplUogqymVSiCrKZVKIKsplUogqymVSiCrKZVKIKsplUogqymVSiCrKZVKIKsplUogqymVSiCrKZVKIKsplUogqymVSiCrKZVKIKsplUogqymVSiCtFRn2Jn2IK0VGfYmfYgqymVTn2Jn2IKsplU59iZ9iCrKZUIgnKZUIgnKZUIgnKZUIgnKEqEQcDfdGPy22b9G4P2mpRU/dFTneyz/o5B+01KIP/9k="

def _show_poseview_image(png_data, url, caption):
    """Display PoseView image on white card, with interaction-type legend below."""
    import base64 as _b64

    # ── Choose image source ───────────────────────────────────────────────────
    if png_data:
        img_src = f"data:image/png;base64,{_b64.b64encode(png_data).decode()}"
    else:
        img_src = url

    # ── Main diagram on white card ────────────────────────────────────────────
    st.markdown(
        f'''<div style="background:#ffffff;border-radius:8px;padding:12px;
                       border:1px solid #D0D7DE;margin:8px 0;">
            <img src="{img_src}" style="width:100%;height:auto;display:block;" />
            <div style="text-align:center;font-size:0.78rem;color:#57606A;
                        margin-top:6px;">{caption}</div>
        </div>''',
        unsafe_allow_html=True,
    )

    # ── Interaction-type legend below diagram ─────────────────────────────────
    st.markdown(
        f'''<div style="background:#ffffff;border-radius:8px;padding:8px 16px;
                       border:1px solid #D0D7DE;margin:2px 0 10px 0;">
            <img src="data:image/png;base64,{_POSEVIEW_LEGEND_B64}"
                 style="width:100%;max-width:820px;height:auto;
                        display:block;margin:auto;" />
        </div>''',
        unsafe_allow_html=True,
    )

def _rdkit_six_patch():
    """Compatibility shim for older Meeko versions that import rdkit.six."""
    try:
        from rdkit import six  # noqa
    except ImportError:
        from io import StringIO as _SIO
        from types import ModuleType as _MT
        import rdkit as _rdkit
        _m = _MT("six"); _m.StringIO = _SIO; _m.PY3 = True
        _rdkit.six = _m; sys.modules["rdkit.six"] = _m

def _meeko_to_pdbqt(mol, out_path):
    """Prepare a mol to PDBQT using Meeko — supports both v0.4 and v0.5 API."""
    from meeko import MoleculePreparation
    prep = MoleculePreparation()
    try:
        # Meeko >= 0.5
        from meeko import PDBQTWriterLegacy
        setups = prep.prepare(mol)
        pdbqt_str, _, _ = PDBQTWriterLegacy.write_string(setups[0])
    except (ImportError, AttributeError):
        # Meeko 0.4 fallback
        prep.prepare(mol)
        pdbqt_str = prep.write_pdbqt_string()
    with open(out_path, "w") as f:
        f.write(pdbqt_str)

# ─── Vina Binary (cached) ─────────────────────────────────────────────────────
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

# ─── Ligand exclusion lists ────────────────────────────────────────────────────
_EXCLUDE_IONS   = set("HOH,WAT,DOD,SOL,NA,CL,K,CA,MG,ZN,MN,FE,CU,CO,NI,CD,HG".split(","))
_GLYCAN_NAMES   = {"NAG","BMA","MAN","FUC","GAL","GLC","SIA","NGA","FUL","GLA","BGC"}
_COFACTOR_NAMES = {"ATP","ADP","AMP","GTP","GDP","FAD","FMN","HEM","GOL","PEG","EDO","SO4","PO4"}


# ══════════════════════════════════════════════════════════════════════════════
#  SHARED: Receptor Preparation
#  pfx=""   → basic tab   (state keys: "receptor_done", "cx", …)
#  pfx="b_" → batch tab   (state keys: "b_receptor_done", "b_cx", …)
# ══════════════════════════════════════════════════════════════════════════════
def _receptor_section(pfx: str, wdir: Path, step_label: str):
    import py3Dmol
    done     = st.session_state.get(pfx + "receptor_done", False)
    card_cls = "step-card done" if done else "step-card"

    st.markdown(f'<div class="{card_cls}"><div class="step-title">{step_label}</div><div class="step-heading" style="color:var(--text-card-heading);">📦 Receptor Preparation</div>', unsafe_allow_html=True)

    col_a, col_b = st.columns([1.2, 1])
    with col_a:
        src = st.radio("PDB source", ["Download from RCSB", "Upload PDB file"],
                       horizontal=True, key=pfx+"src_mode")
        if src == "Download from RCSB":
            pdb_id      = st.text_input("PDB ID", value="1M17", max_chars=4, key=pfx+"pdb_id")
            upload_pdb  = None
        else:
            upload_pdb  = st.file_uploader("Upload .pdb", type=["pdb"], key=pfx+"pdb_upload")
            pdb_id      = None

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

            # Load PDB
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

            # Co-crystal ligand
            ligand_pdb_path = None
            cx = cy = cz = 0.0
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

            # Receptor atoms
            sel_str  = (f"not ({ligand_sel_str}) and not water"
                        if ligand_sel_str else "not water")
            rec_sel  = atoms.select(sel_str)
            rec_raw  = str(wdir / "receptor_atoms.pdb")
            writePDB(rec_raw, rec_sel)
            log.append(f"✓ Receptor: {rec_sel.numAtoms()} atoms")

            # OpenBabel → PDBQT
            rec_fh    = str(wdir / "rec.pdb")
            rec_pdbqt = str(wdir / "rec.pdbqt")
            run_cmd(f'obabel "{rec_raw}" -O "{rec_fh}" -h 2>/dev/null')
            if os.path.getsize(rec_fh) < 100:
                raise ValueError("OpenBabel H-addition produced empty file")
            run_cmd(f'obabel "{rec_fh}" -O "{rec_pdbqt}" -xr --partialcharge gasteiger 2>/dev/null')
            if os.path.getsize(rec_pdbqt) < 100:
                raise ValueError("PDBQT conversion produced empty file")
            log.append("✓ Receptor PDBQT ready")

            # Box PDB wireframe
            box_pdb  = str(wdir / "rec.box.pdb")
            cfg_path = str(wdir / "rec.box.txt")
            hx, hy, hz = sx/2, sy/2, sz/2
            corners = [(cx+dx, cy+dy, cz+dz)
                       for dx in (-hx, hx) for dy in (-hy, hy) for dz in (-hz, hz)]
            with open(box_pdb, "w") as f:
                for i, (x, y, z) in enumerate(corners, 1):
                    f.write(f"HETATM{i:5d}  C   BOX A   1    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C\n")
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

    # ── Show result if done ────────────────────────────────────────────────────
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
            st.markdown("""<script>
            (function(){
                var els = window.parent.document.querySelectorAll('[data-testid="stExpander"] summary p');
                els.forEach(function(el){ if(el.innerText.includes('3D: Receptor')) el.style.color='#6b7280'; });
            })();
            </script>""", unsafe_allow_html=True)
            v3 = py3Dmol.view(width="100%", height=480)
            v3.setBackgroundColor(_viewer_bg())
            mi = 0
            for path, style in [
                (st.session_state.get(pfx+"receptor_fh"),
                 {"cartoon": {"color": "spectrum", "opacity": 0.65}}),
                (st.session_state.get(pfx+"box_pdb"),
                 {"stick": {"radius":0.2, "color": "gray"}}),
            ]:
                if path and os.path.exists(path):
                    v3.addModel(open(path).read(), "pdb")
                    v3.setStyle({"model": mi}, style); mi += 1
            lig_p = st.session_state.get(pfx+"ligand_pdb_path")
            if lig_p and os.path.exists(lig_p):
                v3.addModel(open(lig_p).read(), "pdb")
                v3.setStyle({"model": mi},
                             {"stick": {"colorscheme": "magentaCarbon", "radius": 0.25}})
            v3.zoomTo(); v3.zoom(0.85)
            show3d(v3, height=480)

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<hr class="step-divider">', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("# 🧬 Anyone can dock, everyone can do!")
st.markdown(
    "Molecular docking powered by **AutoDock Vina 1.2.7**, **RDKit**, **Meeko**, and **OpenBabel**. "
    "**Basic** — single ligand. **Batch** — multiple ligands."
)
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
#  TAB 1 — BASIC DOCKING
# ╚════════════════════════════════════════════════════════════════════════════╝
with tab_basic:

    # ── Step 1: Receptor ──────────────────────────────────────────────────────
    _receptor_section(pfx="", wdir=WORKDIR, step_label="Step 1 of 4")

    # ── Step 2: Ligand ────────────────────────────────────────────────────────
    card_cls = "step-card done" if st.session_state.ligand_done else "step-card"
    st.markdown(f'<div class="{card_cls}"><div class="step-title">Step 2 of 4</div><div class="step-heading" style="color:var(--text-card-heading);">⚗️ Ligand Preparation</div>', unsafe_allow_html=True)

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

    # ── Step 3: Docking ───────────────────────────────────────────────────────
    card_cls = "step-card done" if st.session_state.docking_done else "step-card"
    st.markdown(f'<div class="{card_cls}"><div class="step-title">Step 3 of 4</div><div class="step-heading">🚀 Run Docking</div>', unsafe_allow_html=True)

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
        with st.spinner(f"Running Vina (exhaustiveness={exh})… this may take a few minutes ⏳"):
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
                # Parse scores
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
                    output_pdbqt=out_pdbqt, output_sdf=out_sdf, dock_base=base,
                    docking_done=True, docking_log=vlog, score_df=df, pose_mols=mols))

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

    # ── Step 4: Results ───────────────────────────────────────────────────────
    card_cls = "step-card done" if st.session_state.docking_done else "step-card"
    st.markdown(f'<div class="{card_cls}"><div class="step-title">Step 4 of 4</div><div class="step-heading">📊 Results & Visualization</div>', unsafe_allow_html=True)

    if not st.session_state.docking_done:
        st.info("Complete Step 3 to see results here.")
    else:
        import py3Dmol
        from rdkit import Chem
        df   = st.session_state.score_df
        mols = st.session_state.pose_mols or []

        # Score table + bar chart
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

        # Animated viewer
        st.markdown("**🎬 Animated Pose Viewer**")
        anim_spd = st.slider("Interval (ms)", 500, 3000, 1500, 250, key="anim_spd")
        if st.session_state.output_sdf and os.path.exists(st.session_state.output_sdf):
            sdf_txt = open(st.session_state.output_sdf).read()
            va = py3Dmol.view(width="100%", height=440); va.setBackgroundColor(_viewer_bg())
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
            va.zoomTo(); va.zoom(0.85); va.rotate(30)
            show3d(va, height=440)

        st.markdown("---")

        # Interactive pose selector
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
                    v2 = py3Dmol.view(width="100%", height=400); v2.setBackgroundColor(_viewer_bg())
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
                    v2.zoomTo(); show3d(v2, height=400)
                except Exception as e:
                    st.info(f"Viewer error: {e}")
            with cdl:
                st.markdown("**Download**")
                sp = str(WORKDIR / f"pose_{pose_idx+1}.sdf")
                with Chem.SDWriter(sp) as w: w.write(sel_mol)
                st.download_button(f"⬇ Pose {pose_idx+1} (.sdf)", open(sp, "rb"),
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

            # ── PoseView 2D Interaction ───────────────────────────────────────
            st.markdown("---")
            st.markdown("**🧬 2D Interaction Diagram — PoseView**")

            # Track which pose the diagram was generated for
            _pose_key = f"{st.session_state.get('ligand_name','lig')}_pose{pose_idx+1}"
            _pv_stale = st.session_state.get("pv_pose_key") != _pose_key

            _c_pv_info, _c_pv_btn = st.columns([3, 1])
            with _c_pv_info:
                if _pv_stale and st.session_state.get("pv_image_url"):
                    st.caption("⚠️ Pose changed — click **Generate** to update the diagram.")
                else:
                    st.caption(
                        "Sends the selected pose to [proteins.plus PoseView](https://proteins.plus/) "
                        "and renders a 2D protein-ligand interaction map."
                    )
            with _c_pv_btn:
                _run_pv = st.button("🔬 Generate 2D Diagram", key="btn_pv_basic", type="primary")

            if _run_pv:
                _rec = st.session_state.get("receptor_fh", "")
                if not _rec or not os.path.exists(_rec):
                    st.error("Receptor PDB not found — complete Step 1 first.")
                elif not os.path.exists(sp):
                    st.error("Pose SDF not found — select a pose above first.")
                else:
                    with st.spinner("Submitting to PoseView API… (10–30 s)"):
                        _url, _err = _call_poseview(_rec, sp)
                    if _err:
                        st.error(f"❌ PoseView error: {_err}")
                    else:
                        import requests as _rq
                        _raw = _rq.get(_url, timeout=20).content
                        _png = _svg_to_png(_raw)
                        st.session_state["pv_image_url"]  = _url
                        st.session_state["pv_image_png"]  = _png
                        st.session_state["pv_image_svg"]  = _raw
                        st.session_state["pv_pose_key"]   = _pose_key

            # Display stored image + download buttons
            if st.session_state.get("pv_image_url") and not _pv_stale:
                _png_data = st.session_state.get("pv_image_png")
                _svg_data = st.session_state.get("pv_image_svg")
                _lig_nm   = st.session_state.get("ligand_name", "ligand")
                _fname    = f"{_lig_nm}_pose{pose_idx+1}_poseview"

                # Show PNG on white background
                _show_poseview_image(
                    _png_data,
                    st.session_state["pv_image_url"],
                    f"PoseView — {_lig_nm} pose {pose_idx+1}",
                )

                # Download buttons — PNG + SVG side by side
                _dl_c1, _dl_c2, _dl_c3 = st.columns([1, 1, 2])
                with _dl_c1:
                    if _png_data:
                        st.download_button(
                            "⬇ Save PNG",
                            data=_png_data,
                            file_name=f"{_fname}.png",
                            mime="image/png",
                            key="dl_pv_png_basic",
                            use_container_width=True,
                        )
                with _dl_c2:
                    if _svg_data:
                        st.download_button(
                            "⬇ Save SVG",
                            data=_svg_data,
                            file_name=f"{_fname}.svg",
                            mime="image/svg+xml",
                            key="dl_pv_svg_basic",
                            use_container_width=True,
                        )
                with _dl_c3:
                    st.caption("💡 SVG is vector — scalable for publications. PNG for quick use.")

    st.markdown('</div>', unsafe_allow_html=True)


# ╔════════════════════════════════════════════════════════════════════════════╗
#  TAB 2 — BATCH DOCKING
# ╚════════════════════════════════════════════════════════════════════════════╝
with tab_batch:

    # Step B1: Receptor
    _receptor_section(pfx="b_", wdir=BATCH_WORKDIR, step_label="Step B1 of B3")

    # ── Step B2: Ligand Input + Run ───────────────────────────────────────────
    b_rec_done   = st.session_state.get("b_receptor_done", False)
    b_batch_done = st.session_state.get("b_batch_done", False)
    card_cls = "step-card done" if b_batch_done else "step-card"
    st.markdown(f'<div class="{card_cls}"><div class="step-title">Step B2 of B3</div><div class="step-heading">⚗️ Batch Ligand Input & Docking</div>', unsafe_allow_html=True)

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
                       "CC1=C(C=C(C=C1)NC2=NC=NC3=C2C=CC=C3)OC Imatinib"
                      ),
                height=300, key="b_smiles_text")
        elif b_input_mode == "Upload .smi file":
            st.file_uploader("Upload .smi file", type=["smi", "txt"], key="b_smi_file")
        else:
            st.file_uploader("Upload structure file", type=["sdf", "mol2", "pdb"],
                             key="b_struct_file")
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

        # ── Parse SMILES ───────────────────────────────────────────────────
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
                fobj = st.session_state.get("b_struct_file")
                if fobj is None: raise ValueError("No structure file uploaded")
                ext = Path(fobj.name).suffix.lower()
                tmp = str(BATCH_WORKDIR / f"input{ext}")
                with open(tmp, "wb") as f: f.write(fobj.read())
                if ext == ".sdf":
                    for i, mol in enumerate(Chem.SDMolSupplier(tmp, sanitize=True)):
                        if mol is None: continue
                        nm = (mol.GetProp("_Name") if mol.HasProp("_Name")
                              else f"lig_{i+1}").replace(" ", "_")
                        smiles_pairs.append((Chem.MolToSmiles(mol), nm))
                else:
                    run_cmd(f'obabel "{tmp}" -O "{tmp}.smi" --gen2D 2>/dev/null')
                    for line in open(f"{tmp}.smi"):
                        pts = line.strip().split(None, 1)
                        if pts:
                            smiles_pairs.append((
                                pts[0],
                                pts[1].replace(" ", "_") if len(pts) > 1
                                else f"lig_{len(smiles_pairs)+1}"
                            ))
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
                isomers = list(EnumerateStereoisomers(
                    mol, options=StereoEnumerationOptions(unique=True, maxIsomers=2)))
                expanded.append((Chem.MolToSmiles(isomers[0]) if isomers else smi, nm))
            smiles_pairs = expanded

        # ── Ligand prep helper ─────────────────────────────────────────────
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

        # ── Docking helper ─────────────────────────────────────────────────
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
            # Parse ALL per-pose scores (one REMARK VINA RESULT per MODEL)
            pose_scores = []
            for line in open(out_pdbqt):
                if line.strip().startswith("REMARK VINA RESULT:"):
                    try: pose_scores.append(float(line.split()[3]))
                    except: pass
            top = pose_scores[0] if pose_scores else None
            return out_pdbqt, out_sdf, log, top, pose_scores

        # ── Redocking ──────────────────────────────────────────────────────
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
                        # Count poses
                        rd_n_poses = 0
                        if rd_out_sdf and os.path.exists(rd_out_sdf):
                            rd_n_poses = sum(
                                1 for m in Chem.SDMolSupplier(rd_out_sdf, sanitize=False) if m)
                        # Store as a browsable result entry (flagged with is_redock=True)
                        redock_result = {
                            "Name":        f"⭐ {rd_nm} (co-crystal ref)",
                            "SMILES":      rd_smi,
                            "Top Score":   rd_top,
                            "pose_scores": rd_pose_scores,
                            "Poses":       rd_n_poses,
                            "out_pdbqt":   rd_out_pdbqt,
                            "out_sdf":     rd_out_sdf,
                            "Status":      "OK",
                            "is_redock":   True,
                        }
                        st.success(f"✓ Reference score: **{redock_score:.2f} kcal/mol** ({rd_nm})")
                    else:
                        st.warning("⚠ Redocking failed — no score returned")
                else:
                    st.warning(f"⚠ Reference ligand prep failed: {rd_err}")

        # ── Main batch loop ────────────────────────────────────────────────
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
                all_logs.append(f"[{name}] PREP ERROR: {prep_err}")
                continue
            out_pdbqt, out_sdf, dock_log, top, pose_scores = _dock_one(
                pdbqt_in, name, b_exh, b_nm, b_er)
            all_logs.append(f"[{name}] score={top} | {dock_log[:120]}")
            log_slot.markdown(
                f'<div class="log-box">{"".join(all_logs[-5:])}</div>',
                unsafe_allow_html=True)
            if top is None:
                results.append({"Name": name, "SMILES": smi, "Top Score": None,
                                 "Poses": 0, "Status": "DOCK FAILED"})
                continue
            n_poses = 0
            if out_sdf and os.path.exists(out_sdf):
                n_poses = sum(1 for m in Chem.SDMolSupplier(out_sdf, sanitize=False) if m)
            results.append({"Name": name, "SMILES": smi, "Top Score": top,
                             "pose_scores": pose_scores,
                             "Poses": n_poses, "out_pdbqt": out_pdbqt,
                             "out_sdf": out_sdf, "Status": "OK"})

        n_ok_final = sum(1 for r in results if r["Status"] == "OK")
        prog.progress(1.0, text=f"✓ Done — {n_ok_final}/{n} ligands docked successfully")
        log_slot.empty()
        st.session_state.update({
            "b_batch_done":           True,
            "b_batch_results":        results,
            "b_batch_log":            "\n".join(all_logs),
            "b_redock_score":         redock_score,
            "b_redock_result":        redock_result,
            # Reset confirmed ref — user must re-confirm after each new run
            "b_confirmed_ref_score":  None,
            "b_confirmed_ref_pose":   None,
            "b_confirmed_ref_name":   None,
        })

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<hr class="step-divider">', unsafe_allow_html=True)

    # ── Step B3: Results ──────────────────────────────────────────────────────
    b_batch_done = st.session_state.get("b_batch_done", False)
    card_cls = "step-card done" if b_batch_done else "step-card"
    st.markdown(f'<div class="{card_cls}"><div class="step-title">Step B3 of B3</div><div class="step-heading">📊 Batch Results</div>', unsafe_allow_html=True)

    if not b_batch_done:
        st.info("Complete Step B2 to see batch results here.")
    else:
        import py3Dmol
        from rdkit import Chem
        results              = st.session_state.get("b_batch_results", [])
        redock_score         = st.session_state.get("b_redock_score")
        redock_result        = st.session_state.get("b_redock_result")
        confirmed_ref_score  = st.session_state.get("b_confirmed_ref_score")
        confirmed_ref_pose   = st.session_state.get("b_confirmed_ref_pose")
        confirmed_ref_name   = st.session_state.get("b_confirmed_ref_name")
        # The active reference line value: confirmed pose score > fallback to top redock score
        active_ref_score = confirmed_ref_score if confirmed_ref_score is not None else redock_score

        n_ok   = sum(1 for r in results if r["Status"] == "OK")
        n_fail = len(results) - n_ok
        st.markdown(
            f"{_pill(f'{n_ok} ligands docked ✓', 'success')} "
            f"{_pill('AutoDock Vina 1.2.7')}"
            + (f" {_pill(f'{n_fail} failed', 'warn')}" if n_fail else ""),
            unsafe_allow_html=True)

        # ── Pose Browser ──────────────────────────────────────────────────────
        st.markdown("**🔎 Pose Browser**")

        # Collect all successfully docked batch ligands
        ok_results = [r for r in results
                      if r["Status"] == "OK"
                      and r.get("out_sdf") and os.path.exists(r["out_sdf"])]

        # Prepend co-crystal reference at the top of the dropdown (if available)
        if redock_result and redock_result.get("out_sdf") and os.path.exists(redock_result["out_sdf"]):
            browsable = [redock_result] + ok_results
        else:
            browsable = ok_results

        if browsable:
            sel_nm = st.selectbox(
                "Select ligand",
                [r["Name"] for r in browsable],
                index=0,
                key="b_lig_sel",
            )
            sel_res = next(r for r in browsable if r["Name"] == sel_nm)
            is_redock_sel = sel_res.get("is_redock", False)

            # ── Per-ligand pose scores (from stored list or fallback to top) ──
            pose_scores_list = sel_res.get("pose_scores", [])

            b_mols = [m for m in Chem.SDMolSupplier(sel_res["out_sdf"], sanitize=False) if m]
            if b_mols:
                # Pose slider
                b_pose_i = st.slider("Pose", 1, len(b_mols), 1, key="b_pose_sel") - 1

                # Resolve score for this specific pose
                if pose_scores_list and b_pose_i < len(pose_scores_list):
                    this_pose_score = pose_scores_list[b_pose_i]
                else:
                    this_pose_score = sel_res["Top Score"]

                score_kind = "success" if (this_pose_score is not None and this_pose_score < -8) else "warn"

                # Score display row
                row_pills = (
                    f'{_pill(f"Pose {b_pose_i+1} / {len(b_mols)}")}'
                    f'{_pill(f"Score: {this_pose_score:.2f} kcal/mol", score_kind) if this_pose_score is not None else ""}'
                )
                # Add delta vs best pose for non-best poses
                if pose_scores_list and b_pose_i > 0 and len(pose_scores_list) > 1:
                    delta = this_pose_score - pose_scores_list[0]
                    row_pills += f' {_pill(f"Δ {delta:+.2f} vs pose 1")}'

                # If this is the co-crystal ref, show confirmed state
                if is_redock_sel:
                    st.markdown(f'<div style="margin-bottom:6px">{_pill("⭐ Co-crystal reference ligand", "warn")}</div>',
                                unsafe_allow_html=True)
                    # Show current confirmed ref status
                    if confirmed_ref_score is not None:
                        st.markdown(
                            f'<div style="background:#23863622;border:1px solid #238636;border-radius:8px;'
                            f'padding:10px 16px;margin-bottom:10px;font-family:\'IBM Plex Mono\',monospace;">'
                            f'<span style="color:#3fb950;font-size:0.85rem;">✅ Reference locked:</span> '
                            f'<b style="color:#3fb950">{confirmed_ref_score:.2f} kcal/mol</b>'
                            f'<span style="color:#8b949e;font-size:0.8rem;"> — pose {confirmed_ref_pose} of {confirmed_ref_name}</span>'
                            f'</div>',
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
                                         {"stick": {"colorscheme": "magentaCarbon", "radius": 0.2}}); bmi += 1
                        vb.addModel(Chem.MolToMolBlock(b_mols[b_pose_i]), "mol")
                        vb.setStyle({"model": bmi},
                                     {"stick": {"colorscheme": "cyanCarbon", "radius": 0.28}})
                        vb.zoomTo(); show3d(vb, height=420)
                    except Exception as e:
                        st.info(f"Viewer error: {e}")

                with cbd:
                    st.markdown("**Actions**")

                    # ── Confirm reference button (co-crystal only) ─────────────
                    if is_redock_sel and this_pose_score is not None:
                        already_confirmed = (
                            confirmed_ref_score == this_pose_score
                            and confirmed_ref_pose == b_pose_i + 1
                        )
                        btn_label = (
                            f"✅ Confirmed (pose {b_pose_i+1})"
                            if already_confirmed
                            else f"📌 Use pose {b_pose_i+1} as reference"
                        )
                        if st.button(
                            btn_label,
                            key="b_confirm_ref_btn",
                            type="primary" if not already_confirmed else "secondary",
                            use_container_width=True,
                        ):
                            st.session_state["b_confirmed_ref_score"] = this_pose_score
                            st.session_state["b_confirmed_ref_pose"]  = b_pose_i + 1
                            st.session_state["b_confirmed_ref_name"]  = sel_nm
                            st.rerun()

                        if confirmed_ref_score is not None and not already_confirmed:
                            if st.button(
                                "🔄 Reset reference",
                                key="b_reset_ref_btn",
                                use_container_width=True,
                            ):
                                st.session_state["b_confirmed_ref_score"] = None
                                st.session_state["b_confirmed_ref_pose"]  = None
                                st.session_state["b_confirmed_ref_name"]  = None
                                st.rerun()

                    st.markdown("**Download**")
                    safe_sel_nm = sel_nm.replace("⭐ ", "").replace(" (co-crystal ref)", "")
                    sp3 = str(BATCH_WORKDIR / f"{safe_sel_nm}_pose{b_pose_i+1}.sdf")
                    with Chem.SDWriter(sp3) as w: w.write(b_mols[b_pose_i])
                    st.download_button(f"⬇ Pose {b_pose_i+1} (.sdf)", open(sp3, "rb"),
                        file_name=f"{safe_sel_nm}_pose{b_pose_i+1}.sdf", key="b_dl_pose")
                    if sel_res.get("out_pdbqt") and os.path.exists(sel_res["out_pdbqt"]):
                        st.download_button("⬇ All poses (.pdbqt)",
                            open(sel_res["out_pdbqt"], "rb"),
                            file_name=f"{safe_sel_nm}_out.pdbqt", key="b_dl_pdbqt")

                # ── PoseView 2D Interaction ───────────────────────────────────
                st.markdown("---")
                st.markdown("**🧬 2D Interaction Diagram — PoseView**")

                _b_pose_key = f"{sel_nm}_pose{b_pose_i+1}"
                _b_pv_stale = st.session_state.get("b_pv_pose_key") != _b_pose_key

                _bc_info, _bc_btn = st.columns([3, 1])
                with _bc_info:
                    if _b_pv_stale and st.session_state.get("b_pv_image_url"):
                        st.caption("⚠️ Pose changed — click **Generate** to update the diagram.")
                    else:
                        st.caption(
                            "Sends the selected pose to [proteins.plus PoseView](https://proteins.plus/) "
                            "and renders a 2D protein-ligand interaction map."
                        )
                with _bc_btn:
                    _b_run_pv = st.button("🔬 Generate 2D Diagram", key="btn_pv_batch", type="primary")

                if _b_run_pv:
                    _b_rec = st.session_state.get("b_receptor_fh", "")
                    if not _b_rec or not os.path.exists(_b_rec):
                        st.error("Receptor PDB not found — complete Step B1 first.")
                    elif not os.path.exists(sp3):
                        st.error("Pose SDF not found.")
                    else:
                        with st.spinner("Submitting to PoseView API… (10–30 s)"):
                            _b_url, _b_err = _call_poseview(_b_rec, sp3)
                        if _b_err:
                            st.error(f"❌ PoseView error: {_b_err}")
                        else:
                            import requests as _rq
                            _b_raw = _rq.get(_b_url, timeout=20).content
                            _b_png = _svg_to_png(_b_raw)
                            st.session_state["b_pv_image_url"]  = _b_url
                            st.session_state["b_pv_image_png"]  = _b_png
                            st.session_state["b_pv_image_svg"]  = _b_raw
                            st.session_state["b_pv_pose_key"]   = _b_pose_key

                # Display stored image + download buttons
                if st.session_state.get("b_pv_image_url") and not _b_pv_stale:
                    _b_png_data = st.session_state.get("b_pv_image_png")
                    _b_svg_data = st.session_state.get("b_pv_image_svg")
                    _b_fname    = f"{sel_nm}_pose{b_pose_i+1}_poseview"

                    # Show PNG on white background
                    _show_poseview_image(
                        _b_png_data,
                        st.session_state["b_pv_image_url"],
                        f"PoseView — {sel_nm} pose {b_pose_i+1}",
                    )

                    # Download buttons — PNG + SVG side by side
                    _b_dl_c1, _b_dl_c2, _b_dl_c3 = st.columns([1, 1, 2])
                    with _b_dl_c1:
                        if _b_png_data:
                            st.download_button(
                                "⬇ Save PNG",
                                data=_b_png_data,
                                file_name=f"{_b_fname}.png",
                                mime="image/png",
                                key="dl_pv_png_batch",
                                use_container_width=True,
                            )
                    with _b_dl_c2:
                        if _b_svg_data:
                            st.download_button(
                                "⬇ Save SVG",
                                data=_b_svg_data,
                                file_name=f"{_b_fname}.svg",
                                mime="image/svg+xml",
                                key="dl_pv_svg_batch",
                                use_container_width=True,
                            )
                    with _b_dl_c3:
                        st.caption("💡 SVG is vector — scalable for publications. PNG for quick use.")

        st.markdown("---")

        # ── Full docking log + Score Table + Plot ─────────────────────────────
        with st.expander("📋 Full docking log", expanded=False):
            st.markdown(
                f'<div class="log-box">{st.session_state.get("b_batch_log","")}</div>',
                unsafe_allow_html=True)

        # Score table + dot plot
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
                ax.set_xlabel("Ligand", color=_cc["muted"], fontsize=9)
                ax.tick_params(colors=_cc["muted"], labelsize=7)
                plt.xticks(rotation=40, ha="right")
                for sp in ax.spines.values(): sp.set_edgecolor(_cc["border"])
                ax.grid(axis="y", color=_cc["bg_sub"], linewidth=0.5)
                fig.tight_layout()
                st.pyplot(fig, use_container_width=True); plt.close(fig)

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
            # Include co-crystal ref in the zip
            zip_results = ([redock_result] if redock_result else []) + ok_results
            with zipfile.ZipFile(zb, "w", zipfile.ZIP_DEFLATED) as zf:
                for r in zip_results:
                    safe_name = r["Name"].replace("⭐ ", "").replace(" (co-crystal ref)", "")
                    if r.get("out_sdf") and os.path.exists(r["out_sdf"]):
                        zf.write(r["out_sdf"], f"poses/{safe_name}_out.sdf")
                    if r.get("out_pdbqt") and os.path.exists(r["out_pdbqt"]):
                        zf.write(r["out_pdbqt"], f"pdbqt/{safe_name}_out.pdbqt")
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
