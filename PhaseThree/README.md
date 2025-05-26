
# 🌋 Volcanic Ash Dispersion Analysis & Visualization Suite

This suite of Python tools provides comprehensive capabilities for processing, analyzing, and visualizing outputs from the **NAME (Numerical Atmospheric-dispersion Modelling Environment)** software. It includes both command-line modules and an interactive web-based dashboard.

---

## 📚 Overview

- **Web Dashboard** – An interactive app built with Panel for visual exploration and export of NAME simulation results.

---


# Volcanic Ash Dispersion Visualization and Analysis Toolkit

This Python-based toolkit is designed for the visualization, interpolation, and analysis of **volcanic ash dispersion simulations** produced by the **NAME** (Numerical Atmospheric-dispersion Modelling Environment) software. It includes modules for rendering 2D and 3D animations, creating vertical and horizontal cross-sections, exporting results, and conducting scientific analyses on ash concentration fields.

---


## ✅ Requirements

- Python 3.7+
- Required packages:
  - `matplotlib`
  - `numpy`
  - `scipy`
  - `cartopy` or `basemap`
  - `netCDF4`

Install dependencies with:
```bash
pip install -r requirements.txt
```



## 🛰 About NAME

This software works with simulation outputs from the **Numerical Atmospheric-dispersion Modelling Environment (NAME)**, developed by the UK Met Office. NAME is widely used for modeling the dispersion of volcanic ash and other airborne pollutants.



---


# 🌋 NAME Ash Dispersion Visualizer Dashboard

An interactive dashboard for uploading, processing, analyzing, and visualizing volcanic ash dispersion model outputs from the **NAME** software. Built with **Panel**, **Xarray**, and **Matplotlib**, this tool supports processing 2D and 3D data processing, statistical Bayesian exceedance probability maps, and downloadable outputs.

---

## 🚀 How to Use

1. Launch the dashboard:
   ```bash
   panel serve app.py --show
   ```
2. Upload a NAME ZIP file.
3. Use the 2D/3D tabs to customize and generate visualizations.
4. Explore results in the Media Viewer.
5. Download animations, images, or logs.

---

## ✨ Features

- 📦 Upload and process ZIP archives containing NAME model outputs
- 🎞 Generate animated visualizations:
  - 3D ash concentration at various altitude levels
  - Vertical profiles over time
  - 2D surface fields like air concentration and deposition rates
- 📊 Bayesian exceedance probability maps for  2D and 3D field data
- 📁 Media viewer with previews and download options
- 🪵 Error logging and session restoration

---

## 🗂 Input Format

Upload a ZIP file containing **raw NAME output `.txt` files**, such as:

```bash
Taal_273070_20200112_scenario_1.zip
├── AQOutput_3DField_*.txt
├── AQOutput_horizontal_*.txt
```

---

## ⚙️ Workflow

```
1. Upload ZIP
       │
       ▼
2. Process into NetCDF
       │
       ▼
3. Visualize in 2D/3D or Analyze Exceedance
       │
       ▼
4. Export and Download Results
```

---

## 🚀 How to Use

1. Launch the dashboard:
   ```bash
   panel serve app.py --show
   ```
2. Upload a NAME ZIP file.
3. Use the 2D/3D tabs to customize and generate visualizations.
4. Explore results in the Media Viewer.
5. Download animations, images, or logs.

---

## 🧮 Core Components

### File Processing

- `NAMEDataProcessor.batch_process_zip()` reads raw `.txt` files and generates NetCDF:
  - `ash_output/3D/*.nc`
  - `ash_output/horizontal/*.nc`

### Visualization

- `Plot_3DField_Data`: Renders 3D altitude slices and profiles.
- `Plot_Horizontal_Data`: Animates 2D horizontal surface fields.
- Widgets allow threshold adjustment, zoom, and colormap selection.

### Statistical Analysis

- `AshExceedanceAnalyzer_3D`: Computes Bayesian exceedance maps for 3D fields.
- `MultiFieldExceedanceAnalyzer_2D`: Similar maps for 2D surface fields.

---

## 🖥 Dashboard Tabs

- **3D Field** – Animate altitude layers, generate profiles, export JPG frames.
- **2D Field** – Animate air concentration, dry/wet deposition.
- **Bayesian Analysis** – Create exceedance contour maps by variable and level.
- **Media Viewer** – View and download all outputs.
- **Help** – User guide and ZIP structure reference.

---

## ✅ Requirements

- Python 3.7+
- Dependencies:
  ```bash
  pip install panel xarray numpy matplotlib netCDF4 cartopy
  ```

---

## 💾 Output Formats

- `.gif` animations
- `.jpg` image frames
- `.zip` export of all generated media
- `.log` file for errors

---

## 📁 Example Directory Structure

```
media/
├── 3D/
│   └── ash_altitude10km_runTimes.gif
├── 2D/
│   └── air_concentration.gif
├── Exceedance_3D/
│   └── average_exceedance.png
├── Exceedance_2D/
│   └── air_concentration_exceedance.png
├── app_errors.log
└── all_exports.zip
```


