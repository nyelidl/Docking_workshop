Create a clear, student-friendly workflow diagram for an undergraduate workshop about basic molecular docking using AutoDock Vina and Google Colab. 
Make the diagram visually appealing and easy to understand, with icons, labels, and short explanations inside or under each box. 
Use a step-by-step sequence with arrows. 
Use a calm educational color palette (blue, green, light gray).

Include the following boxes in this exact order, each with a short explanation:

1. Ligand Preparation  
   Explanation: “Load ligand file (.sdf/.mol2/.pdb), generate 3D conformer, assign charges, and convert to PDBQT.”  
   Icon idea: small molecule icon.

2. Receptor Preparation  
   Explanation: “Clean the protein (remove water/ligands), add hydrogens, and convert protein to PDBQT.”  
   Icon idea: protein ribbon.

3. Define Docking Box  
   Explanation: “Specify search space (center and size) where ligand will explore binding.”  
   Icon idea: 3D box around a protein pocket.

4. Run AutoDock Vina  
   Explanation: “Perform docking to generate multiple poses and calculate binding affinities (Vina scores).”  
   Icon idea: gear or rocket (calculation running).

5. Extract Docked Poses  
   Explanation: “Split poses from output.pdbqt into individual PDB/SDF files for analysis.”  
   Icon idea: stack of files being separated.

6. Vina Score Analysis  
   Explanation: “Parse vina_score, rmsd_lb, rmsd_ub → save to CSV → visualize scores (bar plot).”  
   Icon idea: bar chart.

7. Select Best Pose  
   Explanation: “Choose lowest-energy pose (most negative Vina score).”  
   Icon idea: gold star or checkmark.

8. Optional: Short MD Simulation (OpenMM)  
   Explanation: “Run a brief relaxation or energy minimization to validate stability.”  
   Icon idea: molecular dynamics wave or atom icon.  
   (Mark this step as optional.)

9. Visualization with Proteins.plus  
   Explanation: “Upload receptor and best docked pose for interactive 3D visualization and interaction analysis.”  
   Icon idea: 3D molecular viewer.

Design instructions:
- Use clean rounded boxes.
- Connect steps with arrows in a vertical or horizontal flow.
- Add small text descriptions to help beginners understand each step.
- Style should look like a teaching tutorial figure used in a workshop.
- Ensure labels are clear and readable for undergraduates.
