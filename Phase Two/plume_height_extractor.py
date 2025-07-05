# """ 
# PlumeHeightExtractor Module
# ---------------------------

# This module defines the `PlumeHeightExtractor` class for extracting and organizing volcanic plume height data 
# from Excel files. The file is expected to contain eruption event metadata and segmented data for different 
# eruption dates and volcanoes.

# Features:
# - Parses eruption blocks based on "Eruption" markers.
# - Segments data by specific calendar dates like "17th April, 2024".
# - Cleans data by removing fully empty rows.
# - Stores each segment with keys formatted as: Volcano_EruptionPeriod/Date (with underscores).
# - Adds UTC datetime columns from base date and hour.
# - Filters out rows where a given column equals zero.
# - Displays formatted metadata.

# Dependencies:
# - pandas
# - re
# - datetime
# - tabulate
# """

# import pandas as pd
# import re
# from datetime import datetime, timedelta
# from tabulate import tabulate

# class PlumeHeightExtractor:
#     """
#     A class to extract and organize satellite plume height data by eruption and date
#     from structured Excel sheets.

#     Attributes
#     ----------
#     file_path : str
#         Path to the Excel file.
#     raw_df : pd.DataFrame
#         Raw DataFrame read from Excel.
#     eruption_blocks : dict
#         Dictionary mapping keys like 'Volcano_EruptionPeriod/Date' to DataFrames.
#     metadata : list of dict
#         List summarizing each eruption-date block.

#     Methods
#     -------
#     print_metadata():
#         Displays metadata summary in a formatted table.

#     get_dataframe(key: str) -> pd.DataFrame:
#         Returns a specific eruption-date DataFrame.

#     list_dataframes() -> list:
#         Returns all keys available in eruption_blocks.

#     show_preview(key: str, n: int = 5):
#         Prints the first `n` rows of a specific DataFrame.

#     add_datetime_column(key: str):
#         Adds 'datetime_utc' column to a DataFrame using its key and UTC hour.

#     drop_rows_where_zero(key: str, column_name: str):
#         Drops rows where the specified column equals 0.
#     """

#     def __init__(self, file_path):
#         self.file_path = file_path
#         self.raw_df = None
#         self.eruption_blocks = {}
#         self.metadata = []
#         self._load_and_process()

#     def _load_and_process(self):
#         self.raw_df = pd.read_excel(self.file_path, sheet_name=0, header=None)
#         eruption_start_indices = self.raw_df[self.raw_df[0].astype(str).str.contains("Eruption", na=False)].index.tolist()
#         eruption_start_indices.append(len(self.raw_df))

#         for i in range(len(eruption_start_indices) - 1):
#             start_idx = eruption_start_indices[i]
#             end_idx = eruption_start_indices[i + 1]
#             block = self.raw_df.iloc[start_idx:end_idx].reset_index(drop=True)

#             metadata_str = str(block.iloc[0, 0])
#             volcano_match = re.match(r'^(.*?)\s+[Ee]ruption', metadata_str)
#             volcano_name = volcano_match.group(1).strip() if volcano_match else "Unknown"

#             eruption_date_match = re.search(r'\(([^)]+)\)', metadata_str)
#             eruption_range = eruption_date_match.group(1).strip() if eruption_date_match else "Unknown"

#             eruption_cleaned = eruption_range.replace(",", "").replace(" ", "_").replace("-", "_")

#             date_rows = block[block[0].astype(str).str.contains(r'\d{1,2}[a-z]{2}\s+\w+,\s+\d{4}', case=False, na=False)].index.tolist()
#             date_rows.append(len(block))

#             for j in range(len(date_rows) - 1):
#                 date_row_idx = date_rows[j]
#                 next_date_idx = date_rows[j + 1]

#                 date_str = str(block.iloc[date_row_idx, 0]).strip()
#                 cleaned_date = date_str.replace(",", "").replace(" ", "_")

#                 header_row_idx = date_row_idx + 1
#                 while header_row_idx < next_date_idx and block.iloc[header_row_idx].notna().sum() < 4:
#                     header_row_idx += 1

#                 if header_row_idx >= next_date_idx:
#                     continue

#                 data_start_idx = header_row_idx + 1
#                 header = block.iloc[header_row_idx]
#                 data = block.iloc[data_start_idx:next_date_idx].dropna(how='all').reset_index(drop=True)
#                 data.columns = header

#                 df_key = f"{volcano_name}_{eruption_cleaned}/{cleaned_date}"
#                 self.eruption_blocks[df_key] = data

#                 self.metadata.append({
#                     "Key": df_key,
#                     "Volcano": volcano_name,
#                     "Eruption Period": eruption_range,
#                     "Date": date_str,
#                     "Rows": len(data),
#                     "Columns": len(data.columns)
#                 })

#     def print_metadata(self):
#         """
#         Display metadata as a formatted table, including whether each entry is metadata or actual DataFrame.
#         """
#         if not self.metadata:
#             print("No eruption data loaded.")
#             return

#         typed_metadata = []
#         for entry in self.metadata:
#             df_type = "dataframe" if isinstance(self.eruption_blocks.get(entry["Key"], None), pd.DataFrame) else "metadata"
#             typed_entry = {
#                 "Key": entry["Key"],
#                 "Volcano": entry["Volcano"],
#                 "Eruption Period": entry["Eruption Period"],
#                 "Date": entry["Date"],
#                 "Rows": entry["Rows"],
#                 "Columns": entry["Columns"],
#                 "Type": df_type
#             }
#             typed_metadata.append(typed_entry)

#         print(tabulate(typed_metadata, headers="keys", tablefmt="fancy_grid"))


#     def get_dataframe(self, key):
#         return self.eruption_blocks.get(key, None)

#     def list_dataframes(self):
#         return list(self.eruption_blocks.keys())

#     def show_preview(self, key, n=5):
#         df = self.get_dataframe(key)
#         if df is not None:
#             print(df.head(n))
#         else:
#             print(f"Data for '{key}' not found.")

#     def add_datetime_column(self, key):
#         df = self.get_dataframe(key)
#         if df is None:
#             print(f"DataFrame '{key}' not found.")
#             return None
#         try:
#             date_str = key.split("/")[-1].split("_")
#             date_str_cleaned = " ".join([re.sub(r'(st|nd|rd|th)', '', part) for part in date_str])
#             base_date = datetime.strptime(date_str_cleaned, "%d %B %Y")
#             time_col = "Time in hour (UTC)"
#             df = df[pd.to_numeric(df[time_col], errors='coerce').notna()]
#             df[time_col] = df[time_col].astype(int)
#             #df["datetime_utc"] = df[time_col].apply(lambda h: base_date + timedelta(hours=h))
#             df["datetime_utc"] = df[time_col].apply(lambda h: (base_date + timedelta(hours=h)).strftime("%Y%m%d/%H%MZ"))

#             self.eruption_blocks[key] = df
#             return df
#         except Exception as e:
#             print(f"Error processing datetime for '{key}': {e}")
#             return None

#     def drop_rows_where_zero(self, key, column_name):
#         df = self.get_dataframe(key)
#         if df is None:
#             print(f"DataFrame '{key}' not found.")
#             return None
#         if column_name not in df.columns:
#             print(f"Column '{column_name}' not found in DataFrame '{key}'.")
#             return None
#         filtered_df = df[df[column_name] != 0].reset_index(drop=True)
#         self.eruption_blocks[key] = filtered_df
#         return filtered_df

import pandas as pd
import re
from datetime import datetime, timedelta
from tabulate import tabulate

class PlumeHeightExtractor:
    """
    A class to extract and organize satellite plume height data by eruption and date
    from structured Excel sheets.

    Attributes
    ----------
    file_path : str
        Path to the Excel file.
    raw_df : pd.DataFrame
        Raw DataFrame read from Excel.
    eruption_blocks : dict
        Dictionary mapping keys like 'Volcano_EruptionPeriod/Date' to DataFrames.
    metadata : list of dict
        List summarizing each eruption-date block.

    Methods
    -------
    print_metadata():
        Displays metadata summary in a formatted table.

    get_dataframe(key: str) -> pd.DataFrame:
        Returns a specific eruption-date DataFrame.

    list_dataframes() -> list:
        Returns all keys available in eruption_blocks.

    show_preview(key: str, n: int = 5):
        Prints the first `n` rows of a specific DataFrame.

    add_datetime_column(key: str):
        Adds 'datetime_utc' column to a DataFrame using its key and UTC hour.

    drop_rows_where_zero(key: str, column_name: str):
        Drops rows where the specified column equals 0.
    """

    def __init__(self, file_path):
        self.file_path = file_path
        self.raw_df = None
        self.eruption_blocks = {}
        self.metadata = []
        self._load_and_process()

    def _load_and_process(self):
        self.raw_df = pd.read_excel(self.file_path, sheet_name=0, header=None)
        eruption_start_indices = self.raw_df[self.raw_df[0].astype(str).str.contains("Eruption", na=False)].index.tolist()
        eruption_start_indices.append(len(self.raw_df))

        for i in range(len(eruption_start_indices) - 1):
            start_idx = eruption_start_indices[i]
            end_idx = eruption_start_indices[i + 1]
            block = self.raw_df.iloc[start_idx:end_idx].reset_index(drop=True)

            metadata_row = block.iloc[0]

            # Extract volcano name
            metadata_str = str(metadata_row[0])
            volcano_match = re.match(r'^(.*?)\s+[Ee]ruption', metadata_str)
            volcano_name = volcano_match.group(1).strip() if volcano_match else "Unknown"

            # Extract eruption period
            eruption_date_match = re.search(r'\(([^)]+)\)', metadata_str)
            eruption_range = eruption_date_match.group(1).strip() if eruption_date_match else "Unknown"
            eruption_cleaned = eruption_range.replace(",", "").replace(" ", "_").replace("-", "_")

            # Extract Latitude, Longitude, and Summit_Elevation from structured header row
            latitude, longitude, summit_elev = None, None, None
            for i in range(len(metadata_row) - 1):
                label = str(metadata_row[i]).strip().lower()
                value = metadata_row[i + 1]
                if label == "latitude":
                    try:
                        latitude = float(value)
                    except:
                        pass
                elif label == "longitude":
                    try:
                        longitude = float(value)
                    except:
                        pass
                elif "summit_elevation" in label:
                    try:
                        summit_elev = float(value)
                    except:
                        pass

            # Find rows containing calendar dates
            date_rows = block[block[0].astype(str).str.contains(r'\d{1,2}[a-z]{2}\s+\w+,\s+\d{4}', case=False, na=False)].index.tolist()
            date_rows.append(len(block))

            for j in range(len(date_rows) - 1):
                date_row_idx = date_rows[j]
                next_date_idx = date_rows[j + 1]
                date_str = str(block.iloc[date_row_idx, 0]).strip()
                cleaned_date = date_str.replace(",", "").replace(" ", "_")

                header_row_idx = date_row_idx + 1
                while header_row_idx < next_date_idx and block.iloc[header_row_idx].notna().sum() < 4:
                    header_row_idx += 1
                if header_row_idx >= next_date_idx:
                    continue

                data_start_idx = header_row_idx + 1
                header = block.iloc[header_row_idx]
                data = block.iloc[data_start_idx:next_date_idx].dropna(how='all').reset_index(drop=True)
                data.columns = header

                df_key = f"{volcano_name}_{eruption_cleaned}/{cleaned_date}"
                self.eruption_blocks[df_key] = data

                self.metadata.append({
                    "Key": df_key,
                    "Volcano": volcano_name,
                    "Eruption Period": eruption_range,
                    "Date": date_str,
                    "Rows": len(data),
                    "Columns": len(data.columns),
                    "Latitude": latitude,
                    "Longitude": longitude,
                    "Summit_Elevation(m)": summit_elev
                })

    def print_metadata(self):
        if not self.metadata:
            print("No eruption data loaded.")
            return

        typed_metadata = []
        for entry in self.metadata:
            df_type = "dataframe" if isinstance(self.eruption_blocks.get(entry["Key"], None), pd.DataFrame) else "metadata"
            typed_entry = entry.copy()
            typed_entry["Type"] = df_type
            typed_metadata.append(typed_entry)

        print(tabulate(typed_metadata, headers="keys", tablefmt="fancy_grid"))

    def get_dataframe(self, key):
        return self.eruption_blocks.get(key, None)

    def list_dataframes(self):
        return list(self.eruption_blocks.keys())

    def show_preview(self, key, n=5):
        df = self.get_dataframe(key)
        if df is not None:
            print(df.head(n))
        else:
            print(f"Data for '{key}' not found.")

    def add_datetime_column(self, key):
        df = self.get_dataframe(key)
        if df is None:
            print(f"DataFrame '{key}' not found.")
            return None
        try:
            date_str = key.split("/")[-1].split("_")
            date_str_cleaned = " ".join([re.sub(r'(st|nd|rd|th)', '', part) for part in date_str])
            base_date = datetime.strptime(date_str_cleaned, "%d %B %Y")
            time_col = "Time in hour (UTC)"
            df = df[pd.to_numeric(df[time_col], errors='coerce').notna()]
            df[time_col] = df[time_col].astype(int)
            df["datetime_utc"] = df[time_col].apply(lambda h: (base_date + timedelta(hours=h)).strftime("%Y%m%d/%H%MZ"))
            self.eruption_blocks[key] = df
            return df
        except Exception as e:
            print(f"Error processing datetime for '{key}': {e}")
            return None

    def drop_rows_where_zero(self, key, column_name):
        df = self.get_dataframe(key)
        if df is None:
            print(f"DataFrame '{key}' not found.")
            return None
        if column_name not in df.columns:
            print(f"Column '{column_name}' not found in DataFrame '{key}'.")
            return None
        filtered_df = df[df[column_name] != 0].reset_index(drop=True)
        self.eruption_blocks[key] = filtered_df
        return filtered_df
