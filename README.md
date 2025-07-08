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


### 📹 Video Demonstrations

The following videos provide a walkthrough of the functionalities across all three phases:

- 🔸 [Phase 1: Probabilistic ESP sampling and VEI modeling](./Phase1.mp4)
- 🔸 [Phase 2: Real-time automation using VONA, infrasound, satellite](./Phase2.mp4)
- 🔸 [Phase 3: Visualization and probabilistic analysis of NAME outputs](./Phase3.mp4)

> 💡 Click the links to download and view the demonstrations locally.



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
VONA ESP Processing Loop

This script continuously monitors for new VONA messages using the `vona_trigger` module.
When a new VONA alert is detected (based on changes in volcano name, ash cloud height, or VEI),
it initializes eruption source parameter (ESP) forecasting using the `ESPInitializer` class.
The output is then passed to `SimulationParameterGenerator` to create NAME model simulation input files.

Dependencies:
- vona_trigger
- re
- os
- esp_init (ESPInitializer class)
- nameModel_file_generator (SimulationParameterGenerator class)
"""
import vona_trigger
import re
from esp_init import ESPInitializer
import os
import time
from tqdm import tqdm
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from nameModel_file_generator import SimulationParameterGenerator

# Initialize rich console
console = Console()

# Initialize storage for previous values
previous_values = {
    "volcano_name": None,
    "AshCloudHeight_AGL": None,
    "vei_range": None
}

def clear_screen():
    """Clears the terminal screen for a clean output."""
    os.system('cls' if os.name == 'nt' else 'clear')

def normalize_text(text):
    """Normalizes text by removing excess whitespace."""
    if isinstance(text, str):
        return re.sub(r'\s+', ' ', text).strip()
    return text

def fancy_status_panel(status: str, emoji="🔔", style="bold green"):
    """Display a highlighted status message."""
    console.print(Panel(Text(status, justify="center", style=style), title=emoji + " STATUS", style="bold blue", expand=False))

def display_change_table(prev_dict, curr_dict):
    """Pretty table showing changes."""
    table = Table(title="Change Summary", box=box.DOUBLE_EDGE, title_style="bold magenta")
    table.add_column("Field", style="cyan", justify="left")
    table.add_column("Previous", style="red")
    table.add_column("Current", style="green")

    for key in curr_dict:
        prev = normalize_text(prev_dict[key]) if prev_dict[key] is not None else "-"
        curr = normalize_text(curr_dict[key])
        if prev != curr:
            table.add_row(key, str(prev), str(curr))

    console.print(table)


# Main loop
while True:
    VONA_reports, VONA_latest_data, volcano_name, latitude, longitude, AshCloudHeight_AGL, vei_range = vona_trigger.VONA_Message(VONA_Source="MAGMA")
    VONA_latest_data.reset_index(drop=True, inplace=True)
    row = VONA_latest_data.iloc[0]
    issue_date = row.get("Issued", "_")

    current_values = {
        "volcano_name": volcano_name,
        "AshCloudHeight_AGL": AshCloudHeight_AGL,
        "vei_range": vei_range
    }

    changes_detected = False
    for key in current_values:
        prev_value = normalize_text(previous_values[key]) if previous_values[key] is not None else None
        curr_value = normalize_text(current_values[key])
        if prev_value != curr_value:
            changes_detected = True

    if changes_detected:
        clear_screen()
        fancy_status_panel("New VONA Data Detected", emoji="🌋")

        display_change_table(previous_values, current_values)
        previous_values.update(current_values)

        # Forecast using plume height (when VEI is absent)
        if AshCloudHeight_AGL is not None or vei_range is None:
            console.print("\n[bold blue]Running ESP Forecast (Plume Height)...[/bold blue]")
            esp = ESPInitializer(vei_levels=None, plume_height=AshCloudHeight_AGL, show_plots=True,
                                 base_directory=f'{volcano_name}/{issue_date}/VONA')
            esp.run_all_forecasts(percentiles=[5,50,95])
            heights = esp.get_results_dataframe()

            if heights is not None:
                generator = SimulationParameterGenerator(
                    vona_input=VONA_latest_data,
                    plume_input=heights,
                    output_dir=f'{volcano_name}_{issue_date}/VONA/Name_inputFiles'
                )
                created_files = generator.run()
                console.print("[green]✓ NAME input files created for Plume Height run.[/green]")

        # Forecast using VEI (when both inputs are present)
        if vei_range is not None : # and AshCloudHeight_AGL is not None
            console.print("\n[bold blue]Running ESP Forecast (VEI)...[/bold blue]")
            esp = ESPInitializer(vei_levels=vei_range, plume_height=None, show_plots=True,
                                 base_directory=f'{volcano_name}/{issue_date}/init')
            esp.run_all_forecasts(percentiles=[5,50,95])
            heights = esp.get_results_dataframe()

            if heights is not None:
                generator = SimulationParameterGenerator(
                    vona_input=VONA_latest_data,
                    plume_input=heights,
                    output_dir=f'{volcano_name}/{issue_date}/init/Name_inputFiles', duration_hours=1.0)
                created_files = generator.run()
                console.print("[green]✓ NAME input files created for VEI run.[/green]")

    # Wait loop with progress bar
    status_msg = "🟢 Waiting for next VONA report..." if changes_detected else "🟡 No new data - Monitoring..."
    console.print(Panel(status_msg, title="⏱ Status", expand=False, style="bold yellow" if not changes_detected else "bold green"))

    with tqdm(total=1800, desc="⏳ Refreshing in", unit="s", bar_format="{l_bar}{bar} | ETA: {remaining}") as pbar:
        for _ in range(1800):
            time.sleep(1)
            pbar.update(1)

```
------------------------------------------------------------------------------------------------

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
