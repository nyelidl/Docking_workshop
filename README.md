# 🧬 Just Molecular Docking (AutoDock Vina1.2.7 on Google Colab)

This repository provides a **hands-on, beginner-friendly workflow** for molecular docking using **AutoDock Vina** in **Google Colab**, designed especially for **undergraduate workshops** and newcomers to computer-aided drug design.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1jShXQkN3-fCKQ5g92LgL_2UGgiYUv4T7?usp=sharing)

## 🖼 Workflow Overview

![Docking workflow](https://github.com/nyelidl/Docking_workshop/blob/main/WS_docking.png)

This figure summarizes the full pipeline:

**Ligand Prep → Receptor Prep → Docking → Pose Extraction → Score Analysis → Best Pose → (Optional MD) → Visualization**

Students can follow a complete pipeline, from raw structures to visualization:

1. **Ligand preparation**  
   Load small molecules from `.sdf / .mol2 / .pdb`, generate 3D conformers, assign charges, and convert to PDBQT.

2. **Receptor preparation**  
   Clean the protein structure (remove water/ligands), add hydrogens, and convert the receptor to PDBQT.

3. **Docking box setup**  
   Define the search box (center and size) around the binding pocket.

4. **Run AutoDock Vina**  
   Perform docking to generate multiple poses and compute Vina binding scores.

5. **Pose extraction**  
   Split the Vina `output.pdbqt` into individual PDB/SDF pose files for further analysis.

6. **Vina score analysis**  
   Parse `vina_score`, `rmsd_lb`, and `rmsd_ub` into a CSV file and visualize the scores directly in Colab (e.g., bar plots).

7. **Best pose selection**  
   Identify the most promising pose based on the lowest (most negative) Vina score.

8. **(Optional) Short MD relaxation**  
   Run a brief OpenMM simulation to relax the complex and check basic stability.

9. **Interactive visualization with Proteins.plus**  
   Upload the receptor and selected pose to **[Proteins.plus](https://proteins.plus/)** for 3D inspection and interaction analysis.

---

## 🎯 Why this tutorial?

- **Undergrad-friendly:** Step-by-step explanations with code, comments, and plots.
- **No local installation:** Everything runs in **Google Colab** using a web browser.
- **Teaching-ready:** Ideal for workshops, classroom demos, and self-study.
- **Extensible:** Can be extended later with MM/GBSA, longer MD simulations, or PaCS-MD workflows.

---

## 🚀 Getting Started

1. Open the Colab notebook:  
   👉 *[Insert your Colab link here]*

2. Follow the cells from top to bottom:
   - Upload your **receptor** (`rec.pdb`) and **ligand**.
   - Run docking, extract poses, and analyze Vina scores.
   - Download results (poses, scores, and receptor) as a ZIP.
   - Visualize the complex in **Proteins.plus**.

