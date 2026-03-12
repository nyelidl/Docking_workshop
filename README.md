# 🧬 AutoDock Vina 1.2.7 — Streamlit Interface

A cloud-ready molecular docking workflow converted from the original Google Colab notebook.

## Workflow (top to bottom)

| Step | What it does |
|------|-------------|
| **1 — Receptor** | Download PDB from RCSB (or upload), auto-detect co-crystal ligand, set docking box, prepare PDBQT via OpenBabel |
| **2 — Ligand** | Enter SMILES, predict pKa, adjust protonation at target pH, generate 3D conformer, prepare PDBQT via Meeko |
| **3 — Docking** | Run AutoDock Vina 1.2.7 with configurable exhaustiveness and pose count |
| **4 — Results** | Score table, affinity bar chart, animated pose viewer, interactive pose selector, download buttons |

## Notes

- The **Vina binary** is downloaded at startup from the official GitHub release (~8 MB)
- **OpenBabel** is installed as a system package via `packages.txt`
- All intermediate files live in a temporary directory scoped to your session
- `st.session_state` preserves results between widget interactions — no need to re-run steps

## Citations

**AutoDock Vina 1.2:**  
Eberhardt, J.; Santos-Martins, D.; Tillack, A. F.; Forli, S.  
*J. Chem. Inf. Model.* 2021, 61, 3891–3898. https://doi.org/10.1021/acs.jcim.1c00203

**Meeko:**  
https://github.com/forlilab/Meeko

**pKaPredict:**  
Hengphasatporn, K. et al. *J. Chem. Inf. Model.* 2026. https://doi.org/10.1021/acs.jcim.5c02852
