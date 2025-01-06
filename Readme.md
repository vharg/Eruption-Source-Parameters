
# Volcanic Eruption Analysis Tools

This repository contains a collection of Python modules designed for the analysis and prediction of volcanic eruption parameters. Each module is tailored for a specific task, such as predicting eruption rates, analyzing plume heights, or modeling volcanic ash properties.

---

## Modules

### 1. VEP_TVAAC_VAAText

#### Description
The `VEP_TVAAC_VAAText` module scrapes, processes, and analyzes Volcanic Ash Advisory (VAA) data. It provides tools to extract tabular data, filter records, and download advisory text files.

#### Features
- Web scraping of volcanic ash advisory data.
- Data extraction into pandas DataFrames.
- Search functionality with multiple filters.
- File download and CSV export.

#### Usage
```python
from vep_vaa_text import VEP_TVAAC_VAAText

scraper = VEP_TVAAC_VAAText()
scraper.fetch_webpage()
tables = scraper.extract_all_tables()
results = scraper.search("eruption", date_time="2023")
scraper.download_vaa_text(output_dir="./vaa_texts", filtered_results=results)
```

---

### 2. MERPredictorFromHeight

#### Description
The `MERPredictorFromHeight` module predicts Mass Eruption Rates (MER) using plume heights with Bayesian regression.

#### Features
- Bayesian linear regression.
- Uncertainty and predictive interval calculation.
- Posterior sampling and percentile analysis.
- Data visualization tools.

#### Usage
```python
from mer_from_height import MERPredictorFromHeight

data = pd.DataFrame({'Height_km.a.v.l': [5, 10, 15], 'MER_kg/s': [1e5, 1e6, 1e7]})
predictor = MERPredictorFromHeight(data)
predictions = predictor.predictive_intervals([10, 20, 30])
```

---

### 3. MERPredictor

#### Description
The `MERPredictor` module uses Total Eruption Mass (TEM) to model Mass Eruption Rates (MER).

#### Features
- Bayesian regression for MER prediction.
- Uncertainty estimation for regression outputs.
- Percentile and predictive interval computation.

#### Usage
```python
from mer_predict import MERPredictor

data = pd.DataFrame({'TEM_kg': [1e9, 2e9, 3e9], 'MER_kg/s': [1e5, 1e6, 1e7]})
predictor = MERPredictor(data)
results = predictor.calculate_percentiles([1e9, 2e9, 3e9])
```

---

### 4. Predict_ASH_BELOW_63_Micron

#### Description
This module predicts the fraction of ash particles smaller than 63 microns based on MER and plume height.

#### Features
- Bayesian regression for ash fraction prediction.
- Predictive intervals and uncertainty estimates.
- User-configurable parameters.

#### Usage
```python
from ParticleSize_MER import Predict_ASH_BELOW_63_Micron

data = pd.DataFrame({'Height_km.a.v.l': [5, 10], 'MER_kg/s': [1e5, 1e6]})
predictor = Predict_ASH_BELOW_63_Micron(data)
predictions = predictor.calculate_percentiles([10, 15])
```

---

### 5. PlumeHeightPredictor

#### Description
The `PlumeHeightPredictor` module estimates plume heights using Mass Eruption Rates (MER).

#### Features
- Bayesian regression for plume height estimation.
- Predictive intervals and posterior sampling.
- Comprehensive uncertainty analysis.

#### Usage
```python
from plume_rise_predict import PlumeHeightPredictor

data = pd.DataFrame({'MER_kg/s': [1e5, 2e5], 'Height_km.a.v.l': [5, 10]})
predictor = PlumeHeightPredictor(data)
height_predictions = predictor.calculate_percentiles([1e5, 2e5])
```

---

### 6. VEI_BulkVolume_Mass

#### Description
The `VEI_BulkVolume_Mass` module calculates volcanic bulk volumes and masses based on the Volcanic Explosivity Index (VEI).

#### Features
- Monte Carlo simulations for probabilistic modeling.
- Bayesian updating for density estimation.
- Visualization tools for statistical analysis.

#### Usage
```python
from vei import VEI_BulkVolume_Mass

vei_model = VEI_BulkVolume_Mass()
vei_model.generate_probabilistic_volumes()
vei_model.calculate_mass()
```

---

## Dependencies
Ensure the following Python libraries are installed:
- `numpy`
- `pandas`
- `matplotlib`
- `scipy`
- `requests`
- `beautifulsoup4`

## Installation
Install the dependencies using pip:
```bash
pip install numpy pandas matplotlib scipy requests beautifulsoup4
```

---

## Contact
**Dr. Mahmud Muhammad**  
(PhD, MSc, BSc in Geology)  
Email: [mahmud.geology@hotmail.com](mailto:mahmud.geology@hotmail.com)  
Website: [mahmudm.com](http://mahmudm.com)

