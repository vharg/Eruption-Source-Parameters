import os
import re
import difflib
from datetime import datetime
import pandas as pd
import warnings


class SimulationParameterGenerator:
    def __init__(self, vona_input=None, plume_input=None, output_dir="output", VolcanoName=None, Longitude=None,
                 Latitude=None, Summit_Elevation=None, Issued_date=None, duration_hours=None):
        
        self.vona_input = vona_input
        self.plume_input = plume_input
        self.output_dir = output_dir
        self.vona_df = None
        self.plume_df = None
        self.base_params = {}
        self.issue_datetime = None
        
        self.duration_hours = duration_hours

        self.user_params = {
            "Volcano": VolcanoName,
            "Longitude": Longitude,
            "Latitude": Latitude,
            "Summit Elevation": Summit_Elevation,
            "Issued": Issued_date
        }

    @staticmethod
    def generate_output_folder(base_path, issued_datetime, volcano_name=""):
        suffix = issued_datetime.strftime("%Y_%m_%d_%H")
        return os.path.join(base_path, f"simulation_input_parameters_{suffix}_{volcano_name}")

    def load_data(self):
        if self.vona_input is None:
            missing = [k for k, v in self.user_params.items() if v is None]
            issued_str = self.user_params["Issued"] or datetime.utcnow().strftime("%Y%m%d/%H%MZ")
            if missing:
                warnings.warn(
                    f"VONA input is None and the following user parameters are also missing: {missing}. "
                    f"Please provide them manually."
                )
            self.vona_df = pd.DataFrame([{
                "Issued": issued_str,
                "Volcano": self.user_params["Volcano"] or "UnknownVolcano",
                "Longitude": self.user_params["Longitude"] or 0.0,
                "Latitude": self.user_params["Latitude"] or 0.0,
                "Summit Elevation": f"({self.user_params['Summit Elevation']} M)" if self.user_params["Summit Elevation"] else "(0 M)"
            }])
        elif isinstance(self.vona_input, pd.DataFrame):
            self.vona_df = self.vona_input.copy()
        elif isinstance(self.vona_input, str):
            self.vona_df = pd.read_csv(self.vona_input)
        else:
            raise TypeError("vona_input must be a file path, a pandas DataFrame, or None.")

        if isinstance(self.plume_input, pd.DataFrame):
            self.plume_df = self.plume_input.copy()
        elif isinstance(self.plume_input, str):
            self.plume_df = pd.read_csv(self.plume_input)
        else:
            raise TypeError("plume_input must be a file path or a pandas DataFrame.")

        if self.vona_df.empty or self.plume_df.empty:
            raise ValueError("One of the input data sources is empty.")

    def extract_base_parameters(self):
        entry = self.vona_df.iloc[0]
        self.issue_datetime = datetime.strptime(entry["Issued"], "%Y%m%d/%H%MZ")
        simulation_start = self.issue_datetime.strftime("%Y%m%d_%H%M")
        self.volcano_name = entry["Volcano"]

        summit_height_match = re.search(r'\(([\d,]+)\s*M\)', entry["Summit Elevation"])
        summit_height_m = int(summit_height_match.group(1).replace(",", "")) if summit_height_match else 0

        self.base_params = {
            "simulationStartDatetime": simulation_start,
            "simulationDurationInHour": 168,
            "volcanoName": re.sub(r"[^\w\-_.]", "_", entry["Volcano"]),
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

        self.output_dir = self.generate_output_folder(self.output_dir, self.issue_datetime, entry["Volcano"])

    def _smart_find_column(self, possible_names, columns):
        for name in possible_names:
            match = difflib.get_close_matches(name, columns, n=1, cutoff=0.8)
            if match:
                return match[0]
        return None

   
    # def generate_simulation_files(self):
    #     os.makedirs(self.output_dir, exist_ok=True)
    #     all_generated_paths = []

    #     columns = list(self.plume_df.columns)
    #     duration_cols = [col for col in columns if re.search(r"Duration.*Percentile", col)]
    #     height_col = self._smart_find_column(["Height_km.a.v.l", "Plume_Height_km", "Height_km", "Height_km.a.v.l_Percentile_5", "Height_km.a.v.l_Percentile_50", 
    #                                           "Height_km.a.v.l_Percentile_95"], columns)

    #     if not duration_cols:
    #         raise ValueError("No percentile duration columns found in plume data.")

    #     if not height_col:
    #         warnings.warn("No height column found. Using default summit elevation + 1000 m.")

    #     for col in duration_cols:
    #         match = re.search(r"Percentile_(\d+)", col)
    #         if not match:
    #             continue
    #         percentile = int(match.group(1))
    #         emission_sets = []
    #         set_index = 1

    #         for idx, row in self.plume_df.iterrows():
    #             if pd.isna(row[col]):
    #                 continue

    #             # Determine emission height
    #             if height_col and not pd.isna(row.get(height_col)):
    #                 height_m = int(round(row[height_col] * 1000))
    #             else:
    #                 height_m = self.base_params.get("summitHeightInMetre", 0) + 1000

    #             duration_hr = row[col]
    #             # duration_hr_int = int(duration_hr)
    #             # duration_min_int = int(round((duration_hr - duration_hr_int) * 60))
                
    #             ####################
    #             # Get the emission duration:
    #             if self.duration_hours is not None:
    #                 total_duration_hr = float(self.duration_hours)
    #             else:
    #                 total_duration_hr = float(row[col])  # from percentile column

    #             # Split into hours and minutes:
    #             duration_hr_int = int(total_duration_hr)
    #             duration_min_int = int((total_duration_hr - duration_hr_int) * 60)
                
    #             # Construct the emission string:
    #             emission_str = f"{height_m}_{duration_hr_int}_{duration_min_int}_{self.issue_datetime.strftime('%Y_%m_%d_%H_%M')}"
                
    #             ################
                
                
                
    #             #emission_str = f"{height_m}_{duration_hr_int}_{duration_min_int}_{self.issue_datetime.strftime('%Y_%m_%d_%H_%M')}"

    #             # Label VEI or Row
    #             if "VEI" in row and not pd.isna(row["VEI"]):
    #                 label = f"# VEI {int(row['VEI'])}"
    #             else:
    #                 label = f"# Row {idx}"

    #             emission_sets.append((set_index, label, emission_str))
    #             set_index += 1

    #         # Output to one file per percentile
    #         output_file = os.path.join(self.output_dir, f"simulation_parameters_P{percentile}_{self.volcano_name}.txt")
    #         with open(output_file, "w") as f:
    #             for key, value in self.base_params.items():
    #                 f.write(f"{key} {value}\n")

    #             for set_index, label, emission_str in emission_sets:
    #                 f.write(f"\n{label}\n")
    #                 f.write(f"emissionSourceParameterSet_{set_index} {emission_str}\n")

    #         all_generated_paths.append(output_file)

    #     return all_generated_paths

    def generate_simulation_files(self):
        os.makedirs(self.output_dir, exist_ok=True)
        all_generated_paths = []

        columns = list(self.plume_df.columns)
        duration_cols = [col for col in columns if re.search(r"Duration.*Percentile", col)]

        if not duration_cols:
            raise ValueError("No percentile duration columns found in plume data.")

        for duration_col in duration_cols:
            # Extract percentile number from duration column
            match = re.search(r"Percentile_(\d+)", duration_col)
            if not match:
                continue
            percentile = match.group(1)

            # Priority 1: Try to find the corresponding percentile height column
            possible_height_cols = [
                f"Height_km.a.v.l_Percentile_{percentile}",
                f"Height_km_Percentile_{percentile}",
                f"Plume_Height_km_Percentile_{percentile}"
            ]

            # Priority 2: If not found, fall back to generic height columns
            fallback_height_cols = [
                "Height_km.a.v.l",
                "Plume_Height_km",
                "Height_km"
            ]

            # Try to find the best height column
            height_col = self._smart_find_column(possible_height_cols, columns)

            if not height_col:
                # Try fallback options
                height_col = self._smart_find_column(fallback_height_cols, columns)

            emission_sets = []
            set_index = 1

            for idx, row in self.plume_df.iterrows():
                if pd.isna(row[duration_col]):
                    continue

                # Determine emission height
                if height_col and not pd.isna(row.get(height_col)):
                    height_m = int(round(row[height_col] * 1000))
                else:
                    warnings.warn(
                        f"No height data found for percentile {percentile} row {idx}. Using default summit elevation + 1000 m."
                    )
                    height_m = self.base_params.get("summitHeightInMetre", 0) + 1000

                # Get the emission duration
                if self.duration_hours is not None:
                    total_duration_hr = float(self.duration_hours)
                else:
                    total_duration_hr = float(row[duration_col])

                duration_hr_int = int(total_duration_hr)
                duration_min_int = int((total_duration_hr - duration_hr_int) * 60)

                emission_str = f"{height_m}_{duration_hr_int}_{duration_min_int}_{self.issue_datetime.strftime('%Y_%m_%d_%H_%M')}"

                if "VEI" in row and not pd.isna(row["VEI"]):
                    label = f"# VEI {int(row['VEI'])}"
                else:
                    label = f"# Row {idx}"

                emission_sets.append((set_index, label, emission_str))
                set_index += 1

            # Output file for this percentile
            output_file = os.path.join(
                self.output_dir,
                f"simulation_parameters_P{percentile}_{self.volcano_name}.txt"
            )
            with open(output_file, "w") as f:
                for key, value in self.base_params.items():
                    f.write(f"{key} {value}\n")

                for set_index, label, emission_str in emission_sets:
                    f.write(f"\n{label}\n")
                    f.write(f"emissionSourceParameterSet_{set_index} {emission_str}\n")

            all_generated_paths.append(output_file)

        return all_generated_paths

    def run(self):
        self.load_data()
        self.extract_base_parameters()
        return self.generate_simulation_files()


       