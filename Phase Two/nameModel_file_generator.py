# import os
# import re
# from datetime import datetime
# import pandas as pd


# class SimulationParameterGenerator:
#     def __init__(self, vona_csv_path, plume_csv_path, output_dir):
#         """
#         Initialize the simulation parameter generator with input files and output directory.

#         Parameters:
#         - vona_csv_path (str): Path to the VONA data CSV file.
#         - plume_csv_path (str): Path to the plume height and duration data CSV file.
#         - output_dir (str): Path to save the generated simulation parameter files.
#         """
#         self.vona_csv_path = vona_csv_path
#         self.plume_csv_path = plume_csv_path
#         self.output_dir = output_dir
#         self.vona_df = None
#         self.plume_df = None
#         self.base_params = {}
#         self.issue_datetime = None

#     def load_data(self):
#         """Loads VONA and plume data CSV files into DataFrames."""
#         self.vona_df = pd.read_csv(self.vona_csv_path)
#         self.plume_df = pd.read_csv(self.plume_csv_path)

#         if self.vona_df.empty or self.plume_df.empty:
#             raise ValueError("One of the input files is empty.")

#     def extract_base_parameters(self):
#         """Extracts base simulation parameters using the first VONA record."""
#         entry = self.vona_df.iloc[0]

#         # Parse the Issued datetime and use it to define simulation start time
#         self.issue_datetime = datetime.strptime(entry["Issued"], "%Y%m%d/%H%MZ")
#         simulation_start = self.issue_datetime.strftime("%Y%m%d_%H%M")

#         # Extract summit height in meters using regex
#         summit_height_match = re.search(r'\((\d+)\s*M\)', entry["Summit Elevation"])
#         summit_height_m = int(summit_height_match.group(1)) if summit_height_match else 0

#         self.base_params = {
#             "simulationStartDatetime": simulation_start,
#             "simulationDurationInHour": 168,
#             "volcanoName": entry["Volcano"].replace(' ', '_').replace('(', '_').replace(')', ''),
#             "volcanoX": entry["Longitude"],
#             "volcanoY": entry["Latitude"],
#             "summitHeightInMetre": summit_height_m,
#             "simulationDomain_xMin": 90.0,
#             "simulationDomain_xMax": 160.0,
#             "simulationDomain_yMin": -15.0,
#             "simulationDomain_yMax": 40.0,
#             "outputGridSize_dX": 0.25,
#             "outputGridSize_dY": 0.25,
#             "emissionSourceParameterSet": "TO_BE_UPDATED"
#         }

#     def generate_simulation_files(self):
#         """
#         Creates simulation parameter files for plume height/duration percentiles.

#         Returns:
#         - List[str]: Paths to the created simulation parameter files.
#         """
#         os.makedirs(self.output_dir, exist_ok=True)

#         percentiles = [5, 25, 50, 75, 95]
#         file_paths = []

#         for p in percentiles:
#             height_col = f"Height_km.a.v.l_Percentile_{p}"
#             duration_col = f"Duration_hr_P{p}"

#             height_m = int(round(self.plume_df[height_col].iloc[0] * 1000))
#             duration_hr = self.plume_df[duration_col].iloc[0]
#             duration_hr_int = int(duration_hr)
#             duration_min_int = int(round((duration_hr - duration_hr_int) * 60))

#             emission_str = f"{height_m}_{duration_hr_int}_{duration_min_int}_{self.issue_datetime.strftime('%Y_%m_%d_%H_%M')}"
#             self.base_params["emissionSourceParameterSet"] = emission_str

#             output_file = os.path.join(self.output_dir, f"simulation_parameters_height_percentile_{p}.txt")
#             with open(output_file, "w") as f:
#                 for key, value in self.base_params.items():
#                     f.write(f"{key} {value}\n")

#             file_paths.append(output_file)

#         return file_paths

#     def run(self):
#         """Executes the full simulation parameter generation workflow."""
#         self.load_data()
#         self.extract_base_parameters()
#         return self.generate_simulation_files()

import os
import re
from datetime import datetime
import pandas as pd


class SimulationParameterGenerator:
    def __init__(self, vona_input, plume_input, output_dir):
        """
        Initialize the simulation parameter generator with input data and output directory.

        Parameters:
        - vona_input (str or pd.DataFrame): Path to the VONA CSV file or a pandas DataFrame.
        - plume_input (str or pd.DataFrame): Path to the plume height CSV file or a pandas DataFrame.
        - output_dir (str): Base path to save the generated simulation parameter files.
        """
        self.vona_input = vona_input
        self.plume_input = plume_input
        self.output_dir = output_dir
        self.vona_df = None
        self.plume_df = None
        self.base_params = {}
        self.issue_datetime = None

    @staticmethod
    def generate_output_folder(base_path, issued_datetime, volcano_name=""):
        """
        Generate an output folder path by appending a datetime suffix (yyyy_mm_dd_hh)
        to the given base path.

        Parameters:
        - base_path (str): Base directory path.
        - issued_datetime (datetime): Issue datetime object.

        Returns:
        - str: Full path with datetime suffix.
        """
        suffix = issued_datetime.strftime("%Y_%m_%d_%H")
        
        return os.path.join(base_path, f"simulation_input_parameters_{suffix}_{volcano_name}")

    def load_data(self):
        """Loads VONA and plume data from CSV path or DataFrame."""
        if isinstance(self.vona_input, pd.DataFrame):
            self.vona_df = self.vona_input.copy()
        elif isinstance(self.vona_input, str):
            self.vona_df = pd.read_csv(self.vona_input)
        else:
            raise TypeError("vona_input must be a file path or a pandas DataFrame.")

        if isinstance(self.plume_input, pd.DataFrame):
            self.plume_df = self.plume_input.copy()
        elif isinstance(self.plume_input, str):
            self.plume_df = pd.read_csv(self.plume_input)
        else:
            raise TypeError("plume_input must be a file path or a pandas DataFrame.")

        if self.vona_df.empty or self.plume_df.empty:
            raise ValueError("One of the input data sources is empty.")

    def extract_base_parameters(self):
        """Extracts base simulation parameters using the first VONA record."""
        entry = self.vona_df.iloc[0]

        # Parse the Issued datetime and use it to define simulation start time
        self.issue_datetime = datetime.strptime(entry["Issued"], "%Y%m%d/%H%MZ")
        simulation_start = self.issue_datetime.strftime("%Y%m%d_%H%M")

        # Extract summit height in meters using regex
        summit_height_match = re.search(r'\((\d+)\s*M\)', entry["Summit Elevation"])
        summit_height_m = int(summit_height_match.group(1)) if summit_height_match else 0

        self.base_params = {
            "simulationStartDatetime": simulation_start,
            "simulationDurationInHour": 168,
            "volcanoName": entry["Volcano"].replace(' ', '_').replace('(', '_').replace(')', ''),
            "volcanoX": entry["Longitude"],
            "volcanoY": entry["Latitude"],
            "summitHeightInMetre": summit_height_m,
            "simulationDomain_xMin": 90.0,
            "simulationDomain_xMax": 160.0,
            "simulationDomain_yMin": -15.0,
            "simulationDomain_yMax": 40.0,
            "outputGridSize_dX": 0.25,
            "outputGridSize_dY": 0.25,
            "emissionSourceParameterSet": "TO_BE_UPDATED"
        }

        # Update output directory using datetime suffix
        self.output_dir = self.generate_output_folder(self.output_dir, self.issue_datetime, entry["Volcano"])

    def generate_simulation_files(self):
        """
        Creates simulation parameter files for plume height/duration percentiles.

        Returns:
        - List[str]: Paths to the created simulation parameter files.
        """
        os.makedirs(self.output_dir, exist_ok=True)

        percentiles = [5, 25, 50, 75, 95]
        file_paths = []

        for p in percentiles:
            height_col = f"Height_km.a.v.l_Percentile_{p}"
            duration_col = f"Duration_hr_P{p}"

            height_m = int(round(self.plume_df[height_col].iloc[0] * 1000))
            duration_hr = self.plume_df[duration_col].iloc[0]
            duration_hr_int = int(duration_hr)
            duration_min_int = int(round((duration_hr - duration_hr_int) * 60))

            emission_str = f"{height_m}_{duration_hr_int}_{duration_min_int}_{self.issue_datetime.strftime('%Y_%m_%d_%H_%M')}"
            self.base_params["emissionSourceParameterSet"] = emission_str

            output_file = os.path.join(self.output_dir, f"simulation_parameters_height_percentile_{p}.txt")
            with open(output_file, "w") as f:
                for key, value in self.base_params.items():
                    f.write(f"{key} {value}\n")

            file_paths.append(output_file)

        return file_paths

    def run(self):
        """Executes the full simulation parameter generation workflow."""
        self.load_data()
        self.extract_base_parameters()
        return self.generate_simulation_files()
