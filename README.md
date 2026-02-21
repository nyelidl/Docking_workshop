# 🧬 Just Molecular Docking (AutoDock Vina 1.2.7 on Google Colab)

This repository provides a **hands-on, beginner-friendly workflow** for molecular docking using **AutoDock Vina** in **Google Colab**.

Designed especially for:

- 🎓 Undergraduate workshops  
- 🧪 Beginners in computer-aided drug design (CADD)  
- 💻 Users who want zero local installation  

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1jShXQkN3-fCKQ5g92LgL_2UGgiYUv4T7?usp=sharing)

---

# 🖼 Workflow Overview

![Docking workflow](https://github.com/nyelidl/Docking_workshop/blob/main/WS_docking.png)

Pipeline:

**Ligand Prep → Receptor Prep → Docking → Pose Extraction → Score Analysis → Best Pose → (Optional MD) → Visualization**

This notebook walks students from raw structures to analyzed docking results.

---

# 🔬 What Is Molecular Docking?

Molecular docking is a computational method used to:

> Predict how a small molecule (ligand) binds to a protein.

It provides:

- 📌 A **binding pose** (geometry)
- 📊 A **binding score** (predicted strength, kcal/mol)

Docking is widely used in early-stage drug discovery to:

- Rank candidate molecules
- Understand protein–ligand interactions
- Support experimental design

⚠ Important: Docking predicts binding — it does not prove it.

---

# 🧪 What Determines Binding?

Docking scores are based on physical interactions between protein and ligand.

### Main interaction types:

- **Van der Waals interactions**  
  Shape complementarity and optimal atomic contact.

- **Electrostatic interactions**  
  Attraction between opposite charges.

- **Hydrogen bonds**  
  Strong dipole interactions (optimal distance ~2.5–3.2 Å).

- **π–π interactions**  
  Aromatic stacking (Phe, Tyr, Trp, His).

- **Halogen bonds (if present)**  
  Directional interaction from Cl, Br, I atoms.

These interactions together determine the predicted Vina score.

---

# ⚙️ Step-by-Step Tutorial Structure

## 1️⃣ Ligand Preparation

- Load `.sdf / .mol2 / .pdb`
- Generate 3D conformers
- Assign charges
- Convert to PDBQT

---

## 2️⃣ Receptor Preparation

- Remove water and unwanted ligands
- Add hydrogens
- Convert to PDBQT format

---

## 3️⃣ Docking Box Setup

Define:

- `center_x, center_y, center_z`
- `size_x, size_y, size_z`

The box must cover the binding pocket.

---

## 4️⃣ Run AutoDock Vina

Vina:

- Samples multiple poses
- Scores each pose
- Outputs ranked binding modes

Example:

```bash
vina --receptor receptor.pdbqt \
     --ligand ligand.pdbqt \
     --center_x 10 --center_y 15 --center_z 20 \
     --size_x 20 --size_y 20 --size_z 20 \
     --out output.pdbqt
```

---

## 5️⃣ Pose Extraction

- Split `output.pdbqt`
- Convert poses to PDB or SDF
- Save each pose separately

---

## 6️⃣ Vina Score Analysis

The notebook:

- Extracts `vina_score`
- Extracts `rmsd_lb` and `rmsd_ub`
- Saves results as CSV
- Generates bar plots inside Colab

Score interpretation (general guideline):

| Vina Score (kcal/mol) | Interpretation |
|------------------------|----------------|
| < -10 | Strong |
| -8 to -10 | Moderate |
| -6 to -8 | Weak |
| > -6 | Very weak |

Always compare scores **within the same system only**.

---

## 7️⃣ Best Pose Selection

- Choose the most negative score
- Inspect geometry
- Check hydrogen bonds and key residues

Lowest score ≠ automatically correct pose  
Always inspect visually.

---

## 8️⃣ (Optional) Short MD Relaxation

- Run a brief OpenMM simulation
- Relax steric clashes
- Observe short-term stability

This step helps check basic structural reasonableness.

---

## 9️⃣ Interactive Visualization

Upload:

- `rec.pdb`
- Selected docked pose

To:

👉 https://proteins.plus/

Use PoseView for:

- 2D interaction diagrams
- Hydrogen bond detection
- Residue mapping

Great for:
- Reports
- Class presentations
- Publications

---

# 🎯 Why This Tutorial?

- ✅ No installation required (runs entirely in browser)
- ✅ Fully commented Colab notebook
- ✅ Visual plots included
- ✅ Designed for teaching
- ✅ Easy to extend later

Interested in going beyond docking?

You can explore **enhanced sampling molecular dynamics (MD) simulations directly in the cloud** using **DFDD**:

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1FfTuVSykgsstjzN0nJN0ZQo1_tw0WXSe?usp=sharing)

---

# 🚀 Further Analysis

You can:

- Upload your own receptor
- Dock multiple ligands
- Download all outputs as ZIP
- Compare poses visually
- Perform batch docking

Batch version:

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1TBXO8Dp37CbXPqto3atvZVxsashXYP7Y?usp=sharing)

---

# 📌 Good Practice for Beginners

Always:

- Redock the crystal ligand first
- Check RMSD (< 2 Å is ideal)
- Use a consistent grid box
- Compare within the same protocol
- Do not overinterpret the score

---

# 👨‍🔬 Author

Kowit Hengphasatporn  
Center for Computational Sciences (CCS)  
University of Tsukuba

---

## **Citation**

If you use **DFDD** or **pKaNET Cloud** in your research, **please cite**:

**Hengphasatporn, K.; Duan, L.; Harada, R.; Shigeta, Y.**  
*DFDD: A Cloud-Ready Tool for Distance-Guided Fully Dynamic Docking in Host–Guest Complexation.*  
**Journal of Chemical Information and Modeling**, 2026.  
DOI: https://doi.org/10.1021/acs.jcim.5c02852

---

## **Happy Docking** 🚀
