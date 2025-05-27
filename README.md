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

---

### 1. **Load VEI Dataset**
```python
import vei
data_loader = vei.LOADDATA()
whelley_data = data_loader.whelley_2015(as_geodataframe=True)
```

---

### 2. **Parse Volcanic Ash Advisory (VAA) Reports from Tokyo VAAC**
```python
from vep_vaa_text import VEP_TVAAC_VAAText
scraper = VEP_TVAAC_VAAText(year=2020)
scraper.fetch_webpage()
tables = scraper.extract_all_tables()
```

---

### 3. **Filter Specific Volcano or Advisory Reports**
```python
search_results = scraper.search(query='SINABUNG', date_time=None, advisory_number='2020')
vaa_data, latest_report, latest_data = scraper.download_vaa_text(
    output_dir="./vaa_texts", filtered_results=search_results, csv=True, gdf=whelley_data
)
```

---

### 4. **Estimate ESP Parameters**

#### 4.1. **Estimate Total Eruption Mass (TEM) from VEI**
```python
from vei import VEI_BulkVolume_Mass
vei_model = VEI_BulkVolume_Mass(use_default_densities=False, num_samples=1_000_000)
vei_model.generate_probabilistic_volumes(sampling_method='exponential')
vei_model.calculate_mass()
```

#### 4.2. **Estimate Mass Eruption Rate (MER) from TEM**
```python
from mer_predict import MERPredictor
Aubrey = data_loader.load_Aubry()
tem_values = vei_model.data['Mass_50th_kg'].tolist()
mer_model = MERPredictor(Aubrey)
mer_results = mer_model.predict_mer(tem_values)
```

#### 4.3. **Estimate Plume Height from MER**
```python
from plume_rise_predict import PlumeHeightPredictor
Mastin = data_loader.load_Mastin()
predictor = PlumeHeightPredictor(Mastin)
heights = predictor.predict_height_with_uncertainty(mer_results['MERPercentile_50'].tolist())
```

#### 4.4. **Estimate MER from Observed Plume Height**
```python
from mer_from_height import MERPredictorFromHeight
Combined = data_loader.load_combined_dataset()
obs_heights = [5, 8]  # km
reverse_mer = MERPredictorFromHeight(Combined)
mer_from_height = reverse_mer.predict_MER_with_uncertainty(obs_heights)
```

#### 4.5. **Estimate Mass Fraction of Ash < 63 Microns**
```python
from ParticleSize_MER import Predict_ASH_BELOW_63_Micron
mastin_a = data_loader.load_Mastin_a(as_geodataframe=True)
psize_model = Predict_ASH_BELOW_63_Micron(mastin_a)
psize_model.set_xvar('MER_kg/s')
psize_model.set_yvar('MASS_FRACTION_ASH_BELOW_63_micron')
ash_predictions = psize_model.predict_with_uncertainty(mer_results['MERPercentile_95'].tolist())
```

---

### ✅ Output
- `Final_prediction_results.csv` contains:
  - VEI levels
  - Total Eruption Mass
  - Mass Eruption Rates (MER)
  - Estimated Plume Heights
  - Ash grain size distribution (fraction < 63 µm)
  - Eruption durations

---

### 🔹 Phase Two: Real-Time ESP Update from VONA Reports

Phase Two automates monitoring and updating of eruption parameters using real-time VONA messages.

#### 🧪 Usage via Notebook (`Phase_Two.ipynb`) or Script

1. **Live Monitoring Loop with ESP Updates:**
```python
"""
VONA Monitoring Script

This script continuously monitors the latest Volcanic Observatory Notice for Aviation (VONA) reports 
and detects changes in key volcanic activity parameters such as volcano name, ash cloud height above ground level (AGL),
and volcanic explosivity index (VEI) range. When changes are detected, the screen is cleared, and updated information is displayed.

Key Features:
- Fetches VONA reports from a specified data source (default: "MAGMA").
- Detects changes in volcano name, ash cloud height, and VEI range.
- Updates the display when changes occur.
- Uses the `ESP_INIT` function for eruption source parameter analysis when new data is available.
- Implements a progress bar to visualize the monitoring interval.

Dependencies:
- `vona_trigger`: Retrieves VONA reports.
- `re`: For text normalization.
- `esp_init.ESP_INIT`: Processes eruption source parameters.
- `time`: Introduces delays between monitoring cycles.
- `os`: Clears the terminal screen.
- `tqdm`: Provides a visual progress bar for monitoring intervals.

Contact: 
Dr. Mahmud Muhammad
Email: mahmud.muhammad@hotmail.com

"""


import vona_trigger
import re
from esp_init import ESP_INIT
import time
import os
from tqdm import tqdm  # For progress bar
from vona_trigger import PlumeHeightAnalyzer_FromInfrasound

### Plume Height from Infrasound
analyzer = PlumeHeightAnalyzer_FromInfrasound("./allPlumeHeights/")
dataset_name = "sparks"  # sparks or mastin

mono_mean = analyzer.get_mono_mean(dataset_name) # This represent min Plume Height
di_mean = analyzer.get_di_mean(dataset_name) # This represents max plume Height 

print(f"Mono Mean for {dataset_name}: {mono_mean}")
print(f"DI Mean for {dataset_name}: {di_mean}")

combined=mono_mean + di_mean
# Round numbers to two decimal places and remove duplicates
combined = list(set(int(round(num)) for num in combined))
# Sort the result (optional)
combined.sort()

Use_Infrasound_Height = combined if combined is not None else None
print(f"Combined Mono and di mean Plume Heights: {combined}")

########################################

# Initialize storage for previous variable values
previous_values = {
    "volcano_name": None,
    "AshCloudHeight_AGL": None,
    "vei_range": None
}

def clear_screen():
    """Clears the terminal screen for a fresh output."""
    os.system('cls' if os.name == 'nt' else 'clear')

def normalize_text(text):
    """Removes extra spaces and normalizes text for meaningful comparison."""
    if isinstance(text, str):
        return re.sub(r'\s+', ' ', text).strip()  # Replace multiple spaces with one and trim
    return text  # Return non-string values as-is

Use_Infrasound=False # Change this to True if you want to use observed Plume Height from Infrasound Team
while True:
    # Fetch the latest VONA data
    VONA_reports, VONA_latest_data, volcano_name, latitude, longitude, AshCloudHeight_AGL, vei_range = vona_trigger.VONA_Message(VONA_Source="MAGMA")
   
        
    
    # Store current values in a dictionary
    current_values = {
       
        "volcano_name": volcano_name,
        "AshCloudHeight_AGL": AshCloudHeight_AGL,
        "vei_range": vei_range
    }

   # Check for changes in each variable
    changes_detected = False
    for key in current_values:
        prev_value = normalize_text(previous_values[key]) if previous_values[key] is not None else None
        curr_value = normalize_text(current_values[key])
        
        if prev_value != curr_value:
            changes_detected = True
    
    # If changes are detected, clear screen and print new data
    
    if changes_detected:
        clear_screen()  # Clears previous prints and outputs
        print("🔔 **New VONA Data Detected:**\n")
        for key in current_values:
            prev_value = normalize_text(previous_values[key]) if previous_values[key] is not None else None
            curr_value = normalize_text(current_values[key])
            
            if prev_value != curr_value:
                print(f"🔹 **Change detected in {key}:**")
                print(f"   - **Previous:** {prev_value}")
                print(f"   - **New:** {curr_value}\n")
                previous_values[key] = current_values[key]  # Update stored value

        # Convert AshCloudHeight_AGL to km if it's not None
        if AshCloudHeight_AGL is not None or vei_range is  None:
            
            ESP_INIT(vei_levels=None, PlumeHeight=AshCloudHeight_AGL, show_plots=True)

        if vei_range is not None or AshCloudHeight_AGL is  None: 
            ESP_INIT(vei_levels=vei_range, PlumeHeight=None, show_plots=True)
        
        # if AshCloudHeight_AGL is not None and vei_range is not None:
        
        #     ESP_INIT(vei_levels=None, PlumeHeight=AshCloudHeight_AGL, show_plots=True)
        #     ESP_INIT(vei_levels=vei_range, PlumeHeight=None, show_plots=True)
        
        if AshCloudHeight_AGL is  None and vei_range is  None:
            ESP_INIT(vei_levels=None, PlumeHeight=None, show_plots=True)
   
        if Use_Infrasound_Height is not None:
            ESP_INIT(vei_levels=None, PlumeHeight=Use_Infrasound_Height, show_plots=True)
            analyzer.visualize_datasets()
    
    
    # Progress bar with dynamic status
    status_message = "🟢 Waiting for next VONA report..." if changes_detected else "🟡 No new data - Monitoring..."

    with tqdm(total=1800, desc=status_message, unit="s", bar_format="{l_bar}{bar} {remaining}") as pbar:
        for _ in range(1800):
            time.sleep(1)  # Sleep in 1-second intervals
            pbar.update(1)  # Update progress bar


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
