# 🌋 Eruption Source Parameter Estimation and Ash Dispersion Analysis

This GitHub repository contains all scripts and tools developed as part of the OSTIn initiative led by Prof. Susanna Jenkins. The suite is designed to support real-time forecasting and analysis of volcanic ash hazards using a combination of eruption source parameter sampling, VONA report parsing, satellite/infrasound analysis, and visualization of NAME model outputs.

---

## 📦 Repository Structure

```
📁 PhaseOne/        # Probabilistic ESP sampling and VEI modeling
📁 PhaseTwo/        # Real-time automation using VONA, infrasound, satellite
📁 PhaseThree/      # Visualization and probabilistic analysis of NAME outputs
📄 requirements.txt # Installation dependencies

```

---

## 🛠 Installation Instructions

Ensure Python 3.7 or later is installed. Then install the required packages using:

```bash
pip install -r requirements.txt
```

If you wish to work with individual phases manually, use:

### PhaseOne:
```bash
pip install numpy pandas matplotlib
```

### PhaseTwo:
```bash
pip install beautifulsoup4 requests gdal tqdm
```

### PhaseThree:
```bash
pip install panel xarray netCDF4 cartopy matplotlib dask
```

---

## 🚀 Usage Examples

This repository is organized into three phases, each with standalone scripts and Jupyter notebooks for batch or interactive analysis. Below is a summary of how to use each phase.

---

### 🔹 Phase One: Probabilistic Eruption Source Parameter (ESP) Sampling

This phase generates eruption source parameters using VEI-based probability distributions, built on the dataset by Whelley et al. (2015), which includes >750 volcanoes in Southeast Asia.

#### 🧪 Usage via Notebook (`phase1.ipynb`)

1. **Load VEI Dataset:**
```python
import vei
data_loader = vei.LOADDATA()
whelley_data = data_loader.whelley_2015(as_geodataframe=True)
```

2. **Parse Volcanic Ash Advisory (VAA) Reports from Tokyo VAAC:**
```python
from vep_vaa_text import VEP_TVAAC_VAAText
scraper = VEP_TVAAC_VAAText(year=2020)
scraper.fetch_webpage()
tables = scraper.extract_all_tables()
```

3. **Filter Specific Volcano or Advisory Reports:**
```python
search_results = scraper.search(query='SINABUNG', date_time=None, advisory_number='2020')
```

4. **Estimate ESP Parameters:**
Generate mass eruption rate (MER), total mass, plume height, and grain size. Outputs can be saved for use in NAME.

---

### 🔹 Phase Two: Real-Time ESP Update from VONA Reports

Phase Two automates monitoring and updating of eruption parameters using real-time VONA messages.

#### 🧪 Usage via Notebook (`Phase_Two.ipynb`) or Script

1. **Live Monitoring Loop with ESP Updates:**
```python
from esp_init import ESP_INIT
from vona_trigger import fetch_latest_vona
import time, os
from tqdm import tqdm

while True:
    vona_data = fetch_latest_vona()
    esp = ESP_INIT(vona_data)
    print(esp.summarize())
    for _ in tqdm(range(60)):
        time.sleep(1)
    os.system('cls' if os.name == 'nt' else 'clear')
```

2. **Functional Highlights:**
   - Parses VONA XML/HTML feeds
   - Detects changes in plume height, VEI, or volcano name
   - Triggers `ESP_INIT` to recalculate NAME input values

---

### 🔹 Phase Three: Visualization and Probabilistic Analysis via Panel Dashboard

This phase provides a web-based interactive application for processing and visualizing outputs from NAME model simulations.

#### 🖥 Usage via `app.py` Dashboard

1. **Start the Dashboard:**
```bash
panel serve app.py --autoreload --show
```

2. **Workflow Inside the App:**
- **Step 1 (Optional):** Upload a `.zip` containing `AQOutput_3DField_*.txt` and `AQOutput_horizontal_*.txt`
- **Step 2 (Required):** Click `Process ZIP`
- **Step 3 (Optional):** Download plots, animations, or sample ZIPs

3. **Tabs Available:**
- **3D Field Tab:** Animate and export maps by altitude and time
- **2D Field Tab:** Visualize air concentration, dry and wet deposition
- **Bayesian Analysis Tab:** Run exceedance probability analysis using posterior sampling
- **Media Viewer Tab:** Browse and download `.gif`, `.jpg`, and `.zip` products



## 🗂 Input Format

Example input ZIP for dashboard:

```
Taal_273070_20200112_scenario_1.zip
├── AQOutput_3DField_*.txt
├── AQOutput_horizontal_*.txt
```

---

## 💾 Output Examples

```bash
media/
├── 3D/
│   └── ash_altitude10km_runTimes.gif
├── 2D/
│   └── air_concentration.gif
├── Exceedance_3D/
│   └── average_exceedance.png
├── Exceedance_2D/
│   └── air_concentration_exceedance.png
└── app_errors.log
```

---

## 📘 Documentation

Each script includes detailed docstrings explaining:
- Inputs and outputs
- Data sources used (e.g., Whelley et al., VAAC)
- Bayesian methods and regression logic


---

## 📬 Contact

**Dr. Mahmud Muhammad**  
📧 [mahmud.muhammad@hotmail.com](mailto:mahmud.muhammad@hotmail.com)  
🔗 [mahmudm.com](http://mahmudm.com)
