# 🌋 Volcanic Ash Dispersion Analysis & Visualization Suite

This suite of Python tools provides comprehensive capabilities for processing, analyzing, and visualizing outputs from the **NAME (Numerical Atmospheric-dispersion Modelling Environment)** software. It includes both command-line modules and an interactive web-based dashboard.

---

## 📚 Overview

- **Web Dashboard** – An interactive app built with Panel for visual exploration and export of NAME simulation results.
- **Probability Processor** – A backend module for computing and visualizing exceedance probability maps across multiple simulations.

---

## ✅ Requirements

- Python 3.7+
- Required packages:
  ```bash
  pip install panel xarray numpy matplotlib netCDF4 cartopy
  ```

---

## 🛰 About NAME

This software works with simulation outputs from the **Numerical Atmospheric-dispersion Modelling Environment (NAME)**, developed by the UK Met Office. NAME is widely used for modeling the dispersion of volcanic ash and other airborne pollutants.

---

## 🚀 How to Use

1. **Launch the Dashboard**  
   ```bash
   panel serve app.py --show --autoreload
   ```

2. **Upload a NAME ZIP file** containing `.txt` model outputs.

3. **Use dashboard tabs** to:
   - View 3D and 2D animations
   - Analyze threshold exceedance probabilities
   - Download media outputs

4. **Access the Help tab** for usage instructions.

---

## ✨ Features

- 📦 Upload and process `.zip` archives of NAME model outputs
- 🎞 Create visualizations:
  - 3D ash concentration at various altitude levels
  - Vertical profiles over time
  - 2D surface fields such as air concentration, dry and wet deposition
- 📊 Compute exceedance **probability maps** across simulation ensemble:
  - Probability that a field ≥ threshold at each grid point
- 📁 Integrated media viewer for browsing and downloading outputs
- 🪵 Session logs and error reporting

---

## ⚙️ Workflow

```
1. Upload ZIP
       │
       ▼
2. Convert to NetCDF
       │
       ▼
3. Visualize in 2D/3D or Analyze Probability
       │
       ▼
4. Download Results
```

---

## 🖥 Dashboard Tabs

- **3D Field** – Animate altitude layers, generate profiles, export JPG frames.
- **2D Field** – Animate air concentration, dry/wet deposition.
- **Probability Analysis** – Generate exceedance maps from multiple simulation folders.
- **Media Viewer** – Browse and download `.gif`, `.jpg`, `.nc`, etc.
- **Help** – User guide and ZIP structure reference.

---

## 📘 Probability Processor

The `ProbabilityProcessor` computes exceedance probability maps from an ensemble of NAME simulation outputs. It compares each simulation’s values against a defined threshold and aggregates results to determine the probability of exceedance.

### Key Capabilities

- Supports both 3D and horizontal 2D fields
- Accepts user-defined thresholds
- Generates NetCDF outputs and `.gif` animations
- Supports zoomed and full-map comparison panels

### Example Output

If 7 of 10 simulations exceed 0.02 g/m³ at a point, the probability = `0.7`.

### Output Directory

```
media/
├── Probability_3D/
│   └── ash_concentration_probability_0.02.gif
├── Probability_2D/
│   ├── air_concentration_probability_0.00001.gif
│   ├── dry_deposition_rate_probability_0.00001.gif
└── ...
```

---

## 🗂 Input Format

Upload a `.zip` archive with `.txt` files structured as:

```bash
Taal_273070_20200112_scenario_1.zip
├── AQOutput_3DField_*.txt
├── AQOutput_horizontal_*.txt
```

---

## 💾 Output Formats

- `.gif` animations (2D/3D/probability)
- `.jpg` image snapshots
- `.nc` NetCDF datasets
- `.log` files for diagnostics
- `project_path_map.json` for persistent folder navigation

---

## 📁 Example Directory Tree

```
media/
├── 3D/
│   └── Threshold_0.01/
│       └── ash_concentration_T4.gif
├── 2D/
│   └── Threshold_0.0001/
│       └── air_concentration.gif
├── Probability_3D/
│   └── Threshold_0.02/
│       └── ash_concentration_probability.gif
├── Probability_2D/
│   └── Threshold_0.00001/
│       └── air_concentration_probability.gif
├── all_exports.zip
├── app_errors.log
└── project_path_map.json
```
