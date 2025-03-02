# **VONA Monitoring System**  
*A software solution for real-time volcanic activity analysis using VONA (Volcano Observatory Notice for Aviation) reports.*

## **Project Overview**
This project is part of the **OSTIn** initiative, aimed at developing an automated system to extract and analyze VONA reports. The system integrates **infrasound** and **satellite imagery** analyses based on real-time VONA alerts, predicting key eruption parameters.

## **Key Features**
- **Real-time VONA parsing**: Extracts eruption time and location from **MAGMA** and **TVAAC** VONA reports.
- **Volcanic activity monitoring**: Detects changes in key parameters such as:
  - Volcano name  
  - Ash cloud height (AGL)  
  - Volcanic Explosivity Index (VEI) using Whelley et.al, 2015 database  
- **Forecasting eruption parameters**: Uses Bayesian statistics to estimate:
  - Mass Eruption Rate  
  - Total Erupted Mass  
  - Eruption Duration  
  - Percentage of fine ash particles  
- **Graphical updates**: Displays detected changes dynamically.
- **Progress bar visualization**: Provides real-time monitoring status updates.

## **Data Sources**
- **MAGMA VONA Reports**: [MAGMA VONA](https://magma.esdm.go.id/v1/vona)  
- **TVAAC VONA Reports**: [TVAAC VONA](https://www.data.jma.go.jp/svd/vaac/data/vaac_list.html)  

## **Dependencies**

```sh
pip install tqdm re time os
```
- `vona_trigger`: Fetches VONA reports.
- `re`: Text normalization.
- `esp_init.ESP_INIT`: Processes eruption source parameters.
- `time`: Implements monitoring cycle delays.
- `os`: Clears the terminal screen.
- `tqdm`: Provides a progress bar for tracking monitoring status.



## **Contact**
For any inquiries, please contact:  
📧 **Dr. Mahmud Muhammad**  
✉️ mahmud.muhammad@hotmail.com  
