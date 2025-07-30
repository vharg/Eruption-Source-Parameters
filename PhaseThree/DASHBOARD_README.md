
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

An interactive dashboard for uploading, processing, analyzing, and visualizing volcanic ash dispersion model outputs from the **NAME** software. Built with **Panel**, **Xarray**, and **Matplotlib**, this tool supports processing 2D and 3D data processing, statistical  probability maps, and downloadable outputs.

---

## 🚀 How to Use

1. **Launch the Dashboard**

   1. **Open the Anaconda Command Prompt**  
      Navigate to the `Phase Three` folder.

   2. **Start the Application**  
      Type the command below. A new web page containing the web application will open.

      ```bash
      panel serve app.py --show --autoreload
      ```

   3. **Access Help**  
      Click the **Help** tab to read the instructions on how to use the software.

2. **Upload a NAME ZIP file.**

3. **Use the 2D/3D tabs to customize and generate visualizations.**

4. **Explore results in the Media Viewer.**

5. **Download animations, images, or logs.**


---

## ✨ Features

- 📦 Upload and process ZIP archives containing NAME model outputs
- 🎞 Generate animated visualizations:
  - 3D ash concentration at various altitude levels
  - Vertical profiles over time
  - 2D surface fields like air concentration and deposition rates
- 📊  probability maps for  2D and 3D field data
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

## 🧮 Core Components

### File Processing

- `NAMEDataProcessor.batch_process_zip()` reads raw `.txt` files and generates NetCDF:
  - `ash_output/3D/*.nc`
  - `ash_output/horizontal/*.nc`

### Visualization

- `Plot_3DField_Data`: Renders 3D altitude slices and profiles.
- `Plot_Horizontal_Data`: Animates 2D horizontal surface fields.
- Widgets allow threshold adjustment, zoom, and colormap selection.



---

## 🖥 Dashboard Tabs

---

## 🧭 Right Sidebar Info Cards

The dashboard includes contextual help on the right side of the interface. These sidebar cards provide quick-reference guides for each main tab:

### 🌋 3D Field Help
Visualize ash concentration at various altitudes using 3D model outputs.

**Features:**
- Generate animations for specific altitude layers
- Create vertical ash profiles over time
- Animate all z-levels

**Controls:**
- Altitude layer (Define Ash Altitude Level)
- Threshold filtering to exclude low-concentration ash
- FPS, Colormap, Basemap controls

**Output:**
- `.gif` animations saved under `media/3D/Threshold_x/`

---

### 🌍 2D Field Help
Explore ground-level ash behavior using horizontal fields (surface concentration and deposition).

**Features:**
- Animate Air Concentration
- Animate Dry/Wet Deposition Rates

**Controls:**
- 2D threshold slider
- Zoom level, FPS, and Basemap selection

**Output:**
- `.gif` animations saved under `media/2D/`

---

### 📘 Probability Help
The `ProbabilityProcessor` generates probabilistic maps from multiple simulations.

**How It Works:**
- Computes probability that a variable (e.g., ash) ≥ threshold
- Aggregates binary masks from all runs
- Normalizes into probability field

**Example:**
If 7 of 10 simulations exceed `0.02 g/m³`, probability = `0.7`.

**Output:**
- NetCDF datasets + `.gif` animations in:
  - `media/Probability_3D/`
  - `media/Probability_2D/`

---

### 🖼 Media Viewer Help
The Media Viewer allows easy preview and download of all generated outputs.

**Features:**
- Browse folders by type and threshold
- Search files by name
- Preview and download `.gif`, `.jpg`, `.txt`, etc.

**Tips:**
- Use the 🔄 “Load Files” button inside each folder
- Filter and preview outputs directly from the interface

- **3D Field** – Animate altitude layers, generate profiles, export JPG frames.
- **2D Field** – Animate air concentration, dry/wet deposition.
- **Probability Analysis** – Create exceedance contour maps by variable and level.
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
├── 2D/
│ ├── Threshold_0.005/
│ │ ├── air_concentration.gif
│ │ └── dry_deposition_rate.gif
│ ├── Threshold_0.010/
│ │ └── wet_deposition_rate.gif
│
├── 3D/
│
│ │ └── ash_altitude10km.gif
│ ├── Threshold_0.05/
│ │ └── T4_profile.gif
│
├── Probability_2D/
│ ├── Threshold_0.00001/
│ │ ├── air_concentration_probability.gif
│ │ └── dry_deposition_probability.gif
│
├── Probability_3D/
│ ├── Threshold_0.002/
│ │ └── ash_concentration_probability_T4.gif
│
├── all_exports.zip
├── app_errors.log
└── project_path_map.json
```


