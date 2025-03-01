import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import re

class VEP_TVAAC_VAAText:
    
    """
    Class VEP_TVAAC_VAAText
    ------------------------

    This class is designed to scrape and process volcanic ash advisory (VAA) data from a specified webpage. 
    It includes methods for fetching the webpage, extracting tables, searching the data, and downloading advisory text files.

    Attributes
    ----------
    url : str
        The URL of the webpage to scrape.
    soup : BeautifulSoup or None
        Parsed HTML content of the webpage.
    dataframes : list of pd.DataFrame
        List of DataFrames containing table data from the webpage.

    Methods
    -------
    __init__(url="https://www.data.jma.go.jp/svd/vaac/data/Archives/2020_vaac_list.html")
        Initializes the scraper with the provided URL.

    set_url(url)
        Updates the URL for the scraper.

    fetch_webpage()
        Fetches and parses the webpage content.

    extract_all_tables()
        Extracts all HTML tables from the webpage and converts them into pandas DataFrames.

    search(query, date_time=None, advisory_number=None)
        Searches the extracted DataFrames for rows matching a query string, with optional filters.

    download_vaa_text(output_dir=".", filtered_results=None, csv=True)
        Downloads VAA text files from the links in the "VAA Text" column and optionally saves the data as a CSV.

    Examples
    --------
    # Initialize the scraper
    scraper = VEP_TVAAC_VAAText()

    # Fetch webpage content
    scraper.fetch_webpage()

    # Extract all tables
    tables = scraper.extract_all_tables()

    # Search for entries containing "Taal" in any column, filtered by date
    search_results = scraper.search(query="Taal", date_time="02 Feb. 2020")

    # Download VAA text files and save as a CSV
    scraper.download_vaa_text(output_dir="./vaa_texts", filtered_results=search_results, csv=True)
    """
    
    
    
    def __init__(self, url="https://www.data.jma.go.jp/svd/vaac/data/Archives/2020_vaac_list.html", year=None):
        """
        Initializes the scraper with the provided URL.
        :param url: URL of the webpage to scrape.
        
        # Example Usage
         
        url = "https://www.data.jma.go.jp/svd/vaac/data/Archives/2020_vaac_list.html" 
        
        change url to https://www.data.jma.go.jp/svd/vaac/data/vaac_list.html to search for latest  data
        
        scraper = VEP_TVAAC_VAAText()
        
        scraper.fetch_webpage()
        
        tables = scraper.extract_all_tables()
        
        # Perform a search
        
        search_results = scraper.search("taal", date_time='02 Feb. 2020')  # Replace with your query string

        search_results = scraper.search("TAAL", date_time='2020')  # Replace with your query string
        
        scraper.download_vaa_text(output_dir="./vaa_texts", filtered_results=search_results, csv=True)
        
        search_results.head(5)
        
        
        """
        
        self.Header_content = """\
        ============================================================
                        Tokyo VAAC | Volcanic Ash Advisory
        ============================================================

        ### 📌 Overview:
        This document is a **Volcanic Ash Advisory (VAA)** issued by the **Tokyo Volcanic Ash Advisory Center (VAAC).**
        VAAs provide critical information on volcanic ash emissions that may affect **aviation safety, air traffic management, and public awareness.**

        ### 🏢 Issuing Organization:
        **Tokyo VAAC** is responsible for monitoring volcanic activity and issuing advisories for its designated airspace.
        It relies on **satellite imagery, pilot reports, ground observations, and meteorological data** to assess volcanic ash dispersion.

        ### 🔎 Key Components of the Advisory:
        - **📍 VAAC:** The issuing Volcanic Ash Advisory Center.
        - **🌋 Volcano Information:** Name, coordinates, and elevation.
        - **🌋 Eruption Details:** Reports on volcanic ash emissions, including altitude and movement.
        - **🛰 Observed Volcanic Ash Cloud:** Height, direction, and speed.
        - **🔮 Forecasted Ash Movement:** Predictions for ash dispersion over the next **6, 12, and 18 hours.**
        - **ℹ️ Remarks:** Additional observations or notes.
        - **🕘 Next Advisory:** Scheduled time for the next update.

        🔴 **Importance:** This advisory is crucial for **aviation safety** as volcanic ash can **damage aircraft engines, reduce visibility, and impact flight routes.**

        ------------------------------------------------------------

        📄 **Volcanic Ash Advisory Text**
        ------------------------------------------------------------

        {original_content}

        ------------------------------------------------------------

        ### 🛠 Explanation of Codes Used in the Advisory:

        🔹 **Header Information:**
        - **FVFE01 RJTD 121800**: 
        - **FVFE01** → WMO (World Meteorological Organization) identifier for volcanic ash advisories.
        - **RJTD** → Tokyo VAAC identifier.
        - **121800** → Issued on **January 12, 2020, at 18:00 UTC**.

        - **DTG (Date-Time Group):** `20200112/1800Z`
        - Indicates **date and time** of advisory issuance.

        - **VAAC (Volcanic Ash Advisory Center):** `TOKYO`
        - Identifies the **Tokyo VAAC** as the issuing authority.

        🔹 **Volcano Information:**
        - **VOLCANO:** `TAAL 273070`
        - **Taal Volcano**, Philippines.
        - **273070** → Standard WMO identifier.

        - **PSN (Position):** `N1400 E12100`
        - Geographic coordinates: **14°00’N, 121°00’E**.

        - **AREA:** `PHILIPPINES`
        - Country where the volcano is located.

        - **SUMMIT ELEVATION:** `311M`
        - Height of the volcano summit (**311 meters above sea level**).

        🔹 **Advisory Details:**
        - **ADVISORY NR:** `2020/6`
        - **6th advisory issued in 2020** for this volcano.

        - **INFO SOURCE:** `HIMAWARI-8`
        - **Himawari-8 satellite** was used for observation.

        - **AVIATION COLOUR CODE:** `NIL`
        - No aviation color code assigned.
        - 🟢 **Green:** Normal activity.
        - 🟡 **Yellow:** Increased activity.
        - 🟠 **Orange:** Possible significant ash emission.
        - 🔴 **Red:** Ongoing or imminent significant eruption.

        🔹 **Eruption & Ash Cloud Details:**
        - **ERUPTION DETAILS:** `VA EMISSIONS CONTINUING`
        - Volcanic ash (VA) emissions **still occurring**.

        - **OBS VA DTG (Observed Ash Cloud Time):** `12/1720Z`
        - **Last observed:** **January 12, 2020, at 17:20 UTC**.

        - **OBS VA CLD (Observed Volcanic Ash Cloud):**  
        - **SFC/FL550** → Surface to **Flight Level 550** (**55,000 feet**).
        - Ash cloud moving **northeast (NE) at 75 knots (~139 km/h)**.

        🔹 **Forecasted Volcanic Ash Movement:**
        - **+6 HR, +12 HR, +18 HR:** Predicts where the **ash cloud will move in the next 6, 12, and 18 hours.**

        🔹 **Remarks (RMK):** `NIL`
        - No additional remarks.

        🔹 **Next Advisory:** `20200112/2100Z`
        - Next scheduled advisory at **21:00 UTC on January 12, 2020**.

        ============================================================
        """
        
        if year is not None:
                year= str(year)
                url=f"https://www.data.jma.go.jp/svd/vaac/data/Archives/{year}_vaac_list.html"
        else:
            url="https://www.data.jma.go.jp/svd/vaac/data/vaac_list.html"
            
        
        self.url =url
        self.soup = None
        self.dataframes = []
        self.dataframes_outputs=[]
        self.cache = {}  # Stores { (lat, lon): elevation }

        

    def set_url(self, url):
        """
        Updates the URL for the scraper.
        :param url: New URL to set.
        """
        self.url = url
        
    def fetch_webpage(self):
        """
        Fetches the webpage content and initializes the BeautifulSoup object.
        Raises an exception if the request fails.
        """
        try:
            response = requests.get(self.url, timeout=10)
            response.raise_for_status()
            self.soup = BeautifulSoup(response.content, 'html.parser')
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Failed to fetch the webpage: {e}")

    def extract_all_tables(self):
        """
        Extracts all tables from the webpage and converts them to DataFrames.
        Handles special cases for columns with links.
        :return: List of DataFrames representing all tables on the webpage.
        """
        if not self.soup:
            raise ValueError("Webpage content not fetched. Please call fetch_webpage() first.")

        tables = self.soup.find_all("table")
        self.dataframes = []  # Clear any existing DataFrames

        for idx, table in enumerate(tables):
            headers = [th.get_text(strip=True) for th in table.find("tr").find_all("th")] if table.find("tr") else []
            rows = table.find_all("tr")[1:]  # Skip the header row

            table_data = []
            for row in rows:
                cells = row.find_all("td")[1:]
                row_data = {}
                for header, cell in zip(headers or range(len(cells)), cells):
                    if isinstance(header, str) and header in {"VAA Text", "VA Graphic", "VA Initial", "VA Forecast"}:
                        link = cell.find("a", href=True)
                        row_data[header] = requests.compat.urljoin(self.url, link['href']) if link else cell.get_text(strip=True)
                    else:
                        link = cell.find("a", href=True)
                        cell_value = cell.get_text(strip=True)
                        row_data[header if isinstance(header, str) else f"Column {header}"] = (
                            f"{cell_value} ({requests.compat.urljoin(self.url, link['href'])})" if link else cell_value
                        )
                table_data.append(row_data)

            df = pd.DataFrame(table_data)
            if not df.empty:
                self.dataframes.append(df)

        return self.dataframes

    def search(self, query, date_time=None, advisory_number=None):
        """
        Searches all DataFrames for a specific query string.
        :param query: The string to search for.
        :param date_time: Optional filter for the "Date Time" column.
        :param advisory_number: Optional filter for the "Advisory Number" column.
        :return: DataFrame containing matching rows across all tables.
        
        
        """
        if not self.dataframes:
            raise ValueError("No DataFrames available. Please call extract_all_tables() first.")

        
        if query is None:
            # Combine all DataFrames into one without filtering by query
            matches = pd.concat(self.dataframes, ignore_index=True)
        else:
        
            matches = pd.concat([
                df[df.apply(lambda row: row.astype(str).str.contains(query, case=False, na=False).any(), axis=1)]
                for df in self.dataframes
            ], ignore_index=True)
            
        
         # Apply additional filters if provided
        if date_time:
            matches = matches[matches['Date Time'].str.contains(date_time, case=False, na=False)]
        if advisory_number:
            matches = matches[matches['Advisory Number'].str.contains(advisory_number, case=False, na=False)]

        return matches
    
    
    


    def add_header_to_file(self, file_path):
        """
        Adds a structured header to a VAA text file.
        """
        try:
            # Read existing content
            with open(file_path, "r", encoding="utf-8") as file:
                original_content = file.read()

            # Add header
            updated_content = self.Header_content.format(original_content=original_content)

            # Write back to file
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(updated_content)

            #print(f"✅ Header added to: {file_path}")

        except Exception as e:
            print(f"❌ Error adding header to {file_path}: {e}")

    
    def download_vaa_text(self, output_dir=".", filtered_results=None, csv=True, gdf=None, get_latest_date_data_option=True):
        """
        Downloads text files linked in the "VAA Text" column for filtered results.
        Creates the output directory if it does not exist.
        :param output_dir: Directory to save the downloaded files.
        :param filtered_results: DataFrame containing filtered rows to download.
        :param gdf: GeoDataFrame contianing coordinate bounds to only return VAA reports relevant to Area of Interest
        """
        latest_date_data = None
        
        def search_and_convert_flight_level_and_coordinates(df, column='OBS VA CLD', flight_pattern="SFC/FL\\d{3}", coord_pattern="N\\d{4} E\\d{5}"):
            """
            Search a DataFrame for a specified flight level pattern and coordinates pattern in a given column,
            convert the altitude to meters, extract latitude and longitude, and update the DataFrame.

            Parameters:
            df (pd.DataFrame): Input DataFrame containing the data to search.
            column (str): The name of the column to search for the flight level and coordinate patterns.
            flight_pattern (str): Regex pattern to identify flight levels (default is 'SFC/FL\\d{3}').
            coord_pattern (str): Regex pattern to identify coordinates (default is 'N\\d{4} E\\d{5}').

            Returns:
            pd.DataFrame: DataFrame with original rows and additional columns for altitude, latitude, and longitude.
            """
            def extract_altitude(text):
                if pd.isnull(text):  # Handle None or NaN values
                    return None
                match = re.search(flight_pattern, str(text))
                if match:
                    # Extract the flight level number and convert to meters (1 FL = 100 feet, 1 foot = 0.3048 meters)
                    flight_level = int(match.group(0).split("/FL")[-1])  # Extract flight level
                    return flight_level * 100 * 0.3048  # Convert to meters
                return None

            def extract_coordinates(text):
                if pd.isnull(text):  # Handle None or NaN values
                    return []
                matches = re.findall(coord_pattern, str(text))
                coordinates = []
                for match in matches:
                    lat, lon = match.split(" ")
                    lat = float(lat[1:]) / 100  # Convert N#### to decimal degrees
                    lon = float(lon[1:]) / 1000  # Convert E##### to decimal degrees
                    coordinates.append((lat, lon))
                return coordinates
            
            

            # Apply functions to identify matches
            df["height_asl_meter"] = df[column].apply(extract_altitude)
            
            df["Coordinates"] = df[column].apply(extract_coordinates)

            # Check if any matches were found
            if df["height_asl_meter"].isnull().all() and df["Coordinates"].apply(len).sum() == 0:
                #If no matches, drop temporary columns and return original DataFrame
                df = df.drop(columns=["height_asl_meter", "Coordinates"])
                return df

           

            
            # convert Height above sea level to height above ground level(vent level)
           
            df=compute_height_agl(df, "Latitude", "Longitude", "height_asl_meter")
                
            
            ######################################################
            
            # Drop intermediate 'Coordinates' column
            df = df.drop(columns=["Coordinates"])
            
            return df

        
        def parse_coordinates(coord):
            """
            Converts a coordinate string in the format 'N1400 E12100' to decimal degrees.
            """
            lat_raw, lon_raw = coord.split()
            
            # Parse latitude
            lat_dir = lat_raw[0]
            lat_deg = int(lat_raw[1:3])
            lat_min = int(lat_raw[3:])
            lat = lat_deg + (lat_min / 60.0)
            if lat_dir == 'S':
                lat = -lat
            
            # Parse longitude
            lon_dir = lon_raw[0]
            lon_deg = int(lon_raw[1:4])
            lon_min = int(lon_raw[4:])
            lon = lon_deg + (lon_min / 60.0)
            if lon_dir == 'W':
                lon = -lon
            
            return lat, lon
        
        if filtered_results is None or filtered_results.empty:
            raise ValueError("No filtered results provided or the DataFrame is empty.")

        os.makedirs(output_dir, exist_ok=True)  # Create directory if it doesn't exist
        raw_dir=output_dir + '/raw_text_dir'
        os.makedirs(raw_dir, exist_ok=True)

        
        predefined_columns = [
            "DTG", "VAAC", "VOLCANO", "VOLCANO CODE", "PSN", "AREA", "SUMMIT ELEV", "ADVISORY NR", "INFO SOURCE",
            "AVIATION COLOUR CODE", "ERUPTION DETAILS", "OBS VA DTG", "OBS VA CLD", "FCST VA CLD +6 HR",
            "FCST VA CLD +12 HR", "FCST VA CLD +18 HR", "RMK", "NXT ADVISORY"
        ]

        data = []
        

        if "VAA Text" in filtered_results.columns:
            for idx, link in filtered_results["VAA Text"].items():
                if link.startswith("http"):
                    try:
                        response = requests.get(link, timeout=10)
                        response.raise_for_status()

                        # Parse HTML content to extract text
                        soup = BeautifulSoup(response.content, 'html.parser')
                        text_content = soup.get_text(separator="\n").strip()

                        # Save text content to file
                        file_name = link.split("/")[-1]
                        if not file_name.endswith(".txt"):
                            file_name += ".txt"
                        with open(f"{raw_dir}/{file_name}", "w", encoding="utf-8") as file:
                            
                            file.write(text_content)
                        #print(f"Downloaded and saved: {file_name}")
                        
                         # Add header
                        self.add_header_to_file(f"{raw_dir}/{file_name}")

                        # If csv=True, parse text into a structured format
                        if csv:
                            row = {}
                            for line in text_content.split("\n"):
                                if ":" in line:
                                    key, value = line.split(":", 1)
                                    key = key.strip().upper()
                                    value = value.strip()
                                    if key in predefined_columns:
                                        row[key] = value
                            
                            # Split VOLCANO into VOLCANO and VOLCANO CODE
                            if "VOLCANO" in row and row["VOLCANO"]:
                                volcano_parts = row["VOLCANO"].split()
                                row["VOLCANO"] = " ".join([p for p in volcano_parts if not p.isdigit()])
                                row["VOLCANO CODE"] = " ".join([p for p in volcano_parts if p.isdigit()])

                            data.append(row)

                    except requests.exceptions.RequestException as e:
                        print(f"Failed to download {link}: {e}")

        if csv and data:
            df = pd.DataFrame(data, columns=predefined_columns )
            
            # Apply the function to extract latitude and longitude
            df[['Latitude', 'Longitude']] = df['PSN'].apply(
                lambda x: pd.Series(parse_coordinates(x))
            )
            
            if gdf is not None and not gdf.empty:
                # Get the bounding box of the GeoDataFrame
                minx, miny, maxx, maxy = gdf.total_bounds  # min Longitude, min Latitude, max Longitude, max Latitude

                # Filter the DataFrame based on the bounding box
                df = df[
                    (df['Longitude'] >= minx) & (df['Longitude'] <= maxx) &
                    (df['Latitude'] >= miny) & (df['Latitude'] <= maxy)
                ]
                
            
            
            #################
            # Split 'ADVISORY NR' to extract the year and report number
            df[['ADVISORY_YEAR', 'REPORT_NUMBER']] = df['ADVISORY NR'].str.split('/', expand=True)

            # Convert 'REPORT_NUMBER' to integer for comparison
            df['REPORT_NUMBER'] = df['REPORT_NUMBER'].astype(int)

            # Find the latest advisory report for each volcano by year and report number
            latest_VAA_report = df.loc[df.groupby('VOLCANO')['REPORT_NUMBER'].idxmax()]

            # Drop helper columns if not needed
            latest_VAA_report = latest_VAA_report.drop(columns=['ADVISORY_YEAR', 'REPORT_NUMBER'])
            
            ########
            
            #####################
            
           
            import time
            import logging

            # Initialize cache globally to avoid repeated API calls
            elevation_cache = {}

            # Configure logging
            logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


            def get_elevation(lat: float, lon: float, retries: int = 2, delay: int = 5) -> float:
                """
                Fetch elevation from multiple online sources with caching and automatic fallback.

                :param lat: Latitude (float)
                :param lon: Longitude (float)
                :param retries: Number of retries per API before switching (default: 2)
                :param delay: Initial retry delay in seconds (default: 5)
                :return: Elevation in meters (float) or NaN if all APIs fail.
                """
                
                # Check if elevation is already cached
                if (lat, lon) in elevation_cache:
                    #logging.info(f"Using cached elevation for ({lat}, {lon})")
                    return elevation_cache[(lat, lon)]

                # API priority list
                API_SERVERS = [
                    {"name": "SRTM", "url": "https://api.opentopodata.org/v1/srtm30m", "params": {"locations": f"{lat},{lon}"}},
                    {"name": "MapZone", "url": "https://api.mapzone.io/v1/elevation", "params": {"lat": lat, "lon": lon}},
                    {"name": "Open-Elevation", "url": "https://api.open-elevation.com/api/v1/lookup", "params": {"locations": f"{lat},{lon}"}},
                    {"name": "USGS", "url": "https://nationalmap.gov/epqs/pqs.php",
                    "params": {"x": lon, "y": lat, "units": "Meters", "output": "json"}},
                    {"name": "Elevation-API.io", "url": "https://api.elevationapi.io/api/Elevation",
                    "params": {"points": f"[{{'latitude': {lat}, 'longitude': {lon}}}]"}}
                ]

                with requests.Session() as session:  # Efficiently reuses connections
                    for api in API_SERVERS:
                        for attempt in range(retries):
                            try:
                                response = session.get(api["url"], params=api["params"], timeout=10)
                                if response.status_code == 200:
                                    data = response.json()

                                    # Validate response format
                                    if not data:
                                        logging.warning(f"{api['name']} returned empty response.")
                                        continue

                                    # Extract elevation
                                    elevation = _extract_elevation(api["name"], data)
                                    if elevation is not None:
                                        elevation_cache[(lat, lon)] = elevation  # Store in cache
                                        return elevation

                                logging.warning(f"{api['name']} API error {response.status_code}. Retrying in {delay} seconds...")
                                time.sleep(delay)
                                delay = min(delay * 2, 30)  # Cap maximum delay

                            except requests.exceptions.RequestException as e:
                                logging.error(f"{api['name']} API request failed: {e}. Retrying...")

                        logging.warning(f"{api['name']} API failed. Moving to next source...")

                # If all APIs fail, return NaN and cache it to prevent redundant retries
                logging.error("All elevation APIs failed. Returning NaN.")
                elevation_cache[(lat, lon)] = float("nan")
                return float("nan")


            def _extract_elevation(api_name: str, data: dict) -> float:
                """
                Extract elevation data from API response.

                :param api_name: Name of the API
                :param data: Response JSON
                :return: Elevation in meters (float) or NaN if extraction fails.
                """
                try:
                    if api_name == "SRTM":
                        return data["results"][0]["elevation"]
                    elif api_name == "MapZone":
                        return data["elevation"]
                    elif api_name == "Open-Elevation":
                        return data["results"][0]["elevation"]
                    elif api_name == "USGS":
                        return data["value"]
                    elif api_name == "Elevation-API.io":
                        return data["elevations"][0]["elevation"]
                except (KeyError, IndexError, TypeError):
                    logging.error(f"Failed to extract elevation from {api_name} response.")

                return float("nan")


            def compute_height_agl(df: pd.DataFrame, lat_col: str, lon_col: str, height_asl_col: str) -> pd.DataFrame:
                """
                Compute height above ground level (AGL) for a DataFrame.
                
                If the height_asl_col does not exist in the DataFrame, return the original DataFrame unchanged.

                Parameters:
                    df (pd.DataFrame): DataFrame containing latitude, longitude, and height above sea level.
                    lat_col (str): Column name for latitude.
                    lon_col (str): Column name for longitude.
                    height_asl_col (str): Column name for height above sea level (ASL) in meters.

                Returns:
                    pd.DataFrame: Original DataFrame with an added 'height_agl' column, or unchanged if ASL column is missing.
                """
                # Check if required columns exist
                missing_cols = [col for col in [lat_col, lon_col, height_asl_col] if col not in df.columns]
                if missing_cols:
                    logging.warning(f"Missing required columns: {', '.join(missing_cols)}. Returning original DataFrame.")
                    return df

                # Compute ground elevation using vectorized apply
                df["ground_elevation"] = df[[lat_col, lon_col]].apply(lambda row: get_elevation(*row), axis=1)

                # Compute AGL (Height Above Ground Level) and round to 2 decimal places
                df["height_agl"] = (df[height_asl_col] - df["ground_elevation"]).round(2)

                return df


            

                        
            #######################
            
            def get_latest_date_data(df, dtg_column='DTG', volcano_column='VOLCANO'):
                """
                Process the DataFrame to find and return rows corresponding to the latest advisory date.

                Parameters:
                df (pd.DataFrame): Input DataFrame containing the advisory data.
                dtg_column (str): Column name for DTG values in '%Y%m%d/%H%MZ' format.
                volcano_column (str): Column name for volcano identifiers.

                Returns:
                pd.DataFrame: Filtered DataFrame with rows matching the latest advisory date.
                """
                # Convert the 'DTG' column to a datetime object for sorting
                df['DTG_DATETIME'] = pd.to_datetime(df[dtg_column], format='%Y%m%d/%H%MZ', errors='coerce')

                # Group by 'VOLCANO' and find the row with the latest advisory by 'DTG_DATETIME'
                latest_advisories = df.loc[
                    df.groupby(volcano_column)['DTG_DATETIME'].idxmax()
                ]

                # Find the latest date in the 'DTG_DATETIME' column
                latest_date = latest_advisories['DTG_DATETIME'].max()

                # Filter the DataFrame for rows that match the latest date
                latest_date_data = latest_advisories[latest_advisories['DTG_DATETIME'] == latest_date]

                return latest_date_data
            
            if get_latest_date_data_option is True and latest_date_data is None:
                # Ensure the `get_latest_date_data` is a callable function
                if callable(get_latest_date_data):
                    # Call the function to retrieve the latest date data
                    latest_date_data = get_latest_date_data(df)
                    
                    # Ensure that the function's output is not None or empty
                    if latest_date_data is not None and not latest_date_data.empty:
                        # Process the retrieved data with the search_and_convert function
                        latest_date_data_flight = search_and_convert_flight_level_and_coordinates(latest_date_data, column="OBS VA CLD")
                        latest_date_data=latest_date_data_flight
                    else:
                        print("Warning: No data found for the latest date.")
                else:
                    raise TypeError("get_latest_date_data is not callable. Ensure it's a function.")
                
            
            csv_file = os.path.join(output_dir, "vaa_texts.csv")
            df=search_and_convert_flight_level_and_coordinates(df, column="OBS VA CLD")
            df.to_csv(csv_file, index=False)
            print(f"CSV file created: {csv_file}")
            
            self.dataframes_outputs=self.dataframes_outputs.append([df , latest_VAA_report, latest_date_data])
            
            return df , latest_VAA_report, latest_date_data

    def get_data(self, processed=False):
        """
        Returns stored DataFrames.
        
        :param processed: If True, returns processed outputs (filtered results or downloaded data).
                          If False, returns raw extracted tables.
        :return: List of DataFrames
        """
        if processed:
            return self.dataframes_outputs if self.dataframes_outputs else None
        else:
            return self.dataframes if self.dataframes else None
#####################################################################################################################

    










#############################################################################################################################


import os
import time
import random
import requests
import pandas as pd
import dask
import dask.dataframe as dd
from dask import delayed
from bs4 import BeautifulSoup
from difflib import get_close_matches
from datetime import datetime
from tqdm import tqdm
from shapely.geometry import Point
import geopandas as gpd

class MAGMA_VONA_PARSER:
    """
    A scraper designed for extracting, processing, and storing VONA (Volcano Observatory Notice for Aviation) 
    reports from the MAGMA website. This parser optimizes request handling to prevent server overload and 
    supports parallel data extraction using Dask.

    Features:
    - Retrieves VONA reports for all volcanoes or a specified volcano.
    - Implements automatic retry logic with exponential backoff for network requests.
    - Supports real-time and historical data retrieval.
    - Saves VONA reports in CSV and formatted text files for easy analysis.

    Attributes:
    -----------
    volcanoes : dict
        A dictionary mapping volcano names to their corresponding VONA report URLs.

    HEADERS : dict
        HTTP headers for web requests, including a user-agent string.

    BASE_FOLDER : str
        Directory where VONA reports are stored.

    DETAILED_FOLDER : str
        Directory for storing detailed VONA report text files.

    reports : list
        A list to store extracted report metadata (date, URL).

    session : requests.Session
        A persistent HTTP session for handling requests efficiently.
    """

    
    
    # Volcano dictionary
    volcanoes = {
    "All Volcanoes": "https://magma.esdm.go.id/v1/vona?page=",
    "Agung": "https://magma.esdm.go.id/v1/vona?code=AGU&page=",
    "Anak Krakatau": "https://magma.esdm.go.id/v1/vona?code=KRA&page=",
    "Awu": "https://magma.esdm.go.id/v1/vona?code=AWU&page=",
    "Batutara": "https://magma.esdm.go.id/v1/vona?code=TAR&page=",
    "Bromo": "https://magma.esdm.go.id/v1/vona?code=BRO&page=",
    "Dempo": "https://magma.esdm.go.id/v1/vona?code=DEM&page=",
    "Dukono": "https://magma.esdm.go.id/v1/vona?code=DUK&page=",
    "Gamalama": "https://magma.esdm.go.id/v1/vona?code=GML&page=",
    "Ibu": "https://magma.esdm.go.id/v1/vona?code=IBU&page=",
    "Ili Lewotolok": "https://magma.esdm.go.id/v1/vona?code=LEW&page=",
    "Karangetang": "https://magma.esdm.go.id/v1/vona?code=KAR&page=",
    "Kerinci": "https://magma.esdm.go.id/v1/vona?code=KER&page=",
    "Lewotobi Laki-laki": "https://magma.esdm.go.id/v1/vona?code=LWK&page=",
    "Lokon": "https://magma.esdm.go.id/v1/vona?code=LOK&page=",
    "Marapi": "https://magma.esdm.go.id/v1/vona?code=MAR&page=",
    "Merapi": "https://magma.esdm.go.id/v1/vona?code=MER&page=",
    "Raung": "https://magma.esdm.go.id/v1/vona?code=RAU&page=",
    "Rinjani": "https://magma.esdm.go.id/v1/vona?code=RIN&page=",
    "Ruang": "https://magma.esdm.go.id/v1/vona?code=RUA&page=",
    "Sangeangapi": "https://magma.esdm.go.id/v1/vona?code=SAN&page=",
    "Semeru": "https://magma.esdm.go.id/v1/vona?code=SMR&page=",
    "Sinabung": "https://magma.esdm.go.id/v1/vona?code=SIN&page=",
    "Sirung": "https://magma.esdm.go.id/v1/vona?code=SIR&page=",
    "Slamet": "https://magma.esdm.go.id/v1/vona?code=SLA&page=",
    "Soputan": "https://magma.esdm.go.id/v1/vona?code=SOP&page=",
    "Sorikmarapi": "https://magma.esdm.go.id/v1/vona?code=SOR&page=",
    "Tandikat": "https://magma.esdm.go.id/v1/vona?code=TAN&page=",
    "Tangkuban Parahu": "https://magma.esdm.go.id/v1/vona?code=TPR&page="
}

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36"
    }

    def __init__(self, volcano_name="All Volcanoes", BASE_FOLDER=None):
        """
        Initializes the scraper with the specified volcano name and sets up storage directories.

        Parameters:
        -----------
        volcano_name : str, optional
            The name of the volcano to retrieve reports for (default is "All Volcanoes").
        
        BASE_FOLDER : str, optional
            The base directory for saving extracted reports (default is "MAGMA_VONA_REPORTS").

        Raises:
        -------
        OSError
            If directory creation fails.
        """
        self.volcano_name = volcano_name
        self.base_url = self.search_volcano(volcano_name)
        self.reports = []
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

        self.BASE_FOLDER = BASE_FOLDER if BASE_FOLDER is not None else "MAGMA_VONA_REPORTS"
        self.DETAILED_FOLDER = os.path.join(self.BASE_FOLDER, "detailed_reports")
        os.makedirs(self.BASE_FOLDER, exist_ok=True)
        os.makedirs(self.DETAILED_FOLDER, exist_ok=True)

    def search_volcano(self, name):
        """
        Searches for the closest matching volcano name and retrieves its corresponding URL.

        Parameters:
        -----------
        name : str
            The volcano name input by the user.

        Returns:
        --------
        str
            The URL of the volcano's VONA report page.
        """
        name = name.strip().title()
        volcano_names = list(self.volcanoes.keys())

        # Exact match
        if name in volcano_names:
            return self.volcanoes[name]

        # Fuzzy match
        matches = get_close_matches(name, volcano_names, n=1, cutoff=0.3)
        best_match = matches[0] if matches else "All Volcanoes"

        return self.volcanoes[best_match]

    def make_request(self, url, max_retries=3):
        """
        Sends an HTTP request to the given URL with exponential backoff on failure.

        Parameters:
        -----------
        url : str
            The URL to fetch data from.
        
        max_retries : int, optional
            The maximum number of retry attempts in case of failures (default is 3).

        Returns:
        --------
        requests.Response or None
            The response object if the request is successful; otherwise, None.
        """
        retries = 0
        while retries < max_retries:
            try:
                response = self.session.get(url, timeout=10)
                if response.status_code == 200:
                    return response
                elif response.status_code == 429:  # Too many requests
                    wait_time = 2 ** retries + random.uniform(0, 1)
                    print(f"Rate limited. Retrying in {wait_time:.2f} seconds...")
                    time.sleep(wait_time)
                else:
                    print(f"Request failed with status {response.status_code}. Skipping...")
                    return None
            except requests.exceptions.RequestException as e:
                print(f"Error: {e}. Retrying...")
                time.sleep(2 ** retries)
            retries += 1
        return None

    
    
    
    
    def get_total_pages(self):
        """
        Determines the total number of pages available for VONA reports.

        Returns:
        --------
        int
            The total number of pages detected.
        """
        response = self.make_request(self.base_url + "1")  # Fetch the first page
        if not response:
            print("Failed to retrieve data. Defaulting to 1 page.")
            return 1  # Assume at least 1 page exists

        soup = BeautifulSoup(response.text, "html.parser")
        pagination_links = soup.select("div.ui.pagination.menu a")
        page_numbers = []

        for link in pagination_links:
            try:
                num = int(link.text.strip())
                page_numbers.append(num)
            except ValueError:
                continue  # Ignore non-numeric values like "..."

        if page_numbers:
            total_pages = max(page_numbers)
            print(f"Total pages detected: {total_pages}")
            return total_pages
        else:
            print("Error extracting total page count. Falling back to manual limit.")
            return 1

    def sanitize_filename(self, filename):
        """Cleans the filename by removing or replacing invalid characters."""
        return filename.replace(" ", "_").replace(":", "-").replace("/", "-").strip()

    
    def _progress_bar(self, iterable, description, unit):
        """
        Creates and manages a tqdm progress bar.

        Parameters:
        -----------
        iterable : iterable
            The iterable object to track progress.
        
        description : str
            The description to display on the progress bar.
        
        unit : str
            The unit label for each iteration (e.g., "page", "report").

        Returns:
        --------
        tqdm iterator
            A tqdm-wrapped iterator for tracking progress.
        """
        return tqdm(iterable, desc=description, unit=unit, dynamic_ncols=True)
    
    
    def scrape_all_reports(self, max_pages=None):
        """
        Scrapes VONA reports and extracts their URLs.

        Parameters:
        -----------
        max_pages : int, optional
            The maximum number of pages to scrape (default is None, auto-detected).

        Returns:
        --------
        pd.DataFrame
            A DataFrame containing scraped report URLs and dates.
        
        int
            The total number of pages scraped.
        """
        
        if max_pages is None:
            max_pages = self.get_total_pages()
            print(f"Auto-detected total pages: {max_pages}")

        print(f"Scraping up to {max_pages} pages for {self.volcano_name}...")

        # for page in range(1, max_pages + 1):
        #     print(f"Scraping page {page}...")
        #     response = self.make_request(self.base_url + str(page))
        #     if not response:
        #         print(f"Skipping page {page} due to request failure.")
        #         continue
        for page in self._progress_bar(range(1, max_pages + 1), "🔄 Scraping Pages", "page"):
            response = self.make_request(self.base_url + str(page))
            if not response:
                tqdm.write(f"⚠️ Skipping page {page} due to request failure.")
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            for item in soup.select(".timeline-item"):
                time_element = item.select_one(".timeline-time small")
                date = time_element.text.strip() if time_element else None

                link_element = item.select_one(".card-link")
                if link_element and "href" in link_element.attrs:
                    report_url = link_element["href"]
                    if not report_url.startswith("http"):
                        report_url = f"https://magma.esdm.go.id{report_url}"

                    self.reports.append((date, report_url))

            time.sleep(random.uniform(3, 7))

        df = pd.DataFrame(self.reports, columns=["Date", "VONA URL"])
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.sort_values(by="Date", ascending=False).reset_index(drop=True)

        csv_path = os.path.join(self.BASE_FOLDER, "vona_reports_sorted.csv")
        df.to_csv(csv_path, index=False)
        print(f"Scraping completed. Data saved at {csv_path}")

        return df, max_pages

    @delayed
    def process_single_report(self, url):
        """Process a single report using Dask for parallel processing."""
        response = self.make_request(url)
        if not response:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        data = {"Source_URL": url}
        fileName_prefix, filename_suffix = None, None

        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 4:
                field = cells[1].get_text(strip=True)
                value = cells[3].get_text(strip=True)
                data[field] = value

                if field == "Issued":
                    fileName_prefix = self.sanitize_filename(value)
                if field == "Volcano":
                    filename_suffix = self.sanitize_filename(value)

        file_name = "Unknown_Report"
        if fileName_prefix and filename_suffix:
            file_name = f"{fileName_prefix}_{filename_suffix}"

        return data, file_name

    
    def extract_heights(self, text):
        """
        Extracts ASL and AGL heights from the Volcanic Cloud Height text.

        Parameters:
        -----------
        text : str
            The textual description of the ash cloud height.

        Returns:
        --------
        pd.Series
            A Pandas Series containing AshCloudHeight_ASL and AshCloudHeight_AGL.
        """
        match = re.search(r"(\d{3,5})\sFT\s\((\d{3,5})\sM\).*?(\d{3,5})\sFT\s\((\d{3,5})\sM\)", text)
        if match:
            return pd.Series({"AshCloudHeight_ASL": int(match.group(2)), "AshCloudHeight_AGL": int(match.group(4))})
        return pd.Series({"AshCloudHeight_ASL": None, "AshCloudHeight_AGL": None})
    
    
    def extract_vona_reports(self):
        """
        Extracts detailed data from VONA reports using parallel processing with Dask.

        Returns:
        --------
        pd.DataFrame or None
            A DataFrame containing detailed report information or None if extraction fails.
        """
        urls = [url for _, url in self.reports]
        print(f"Extracting details from {len(urls)} reports...")

        tasks = [self.process_single_report(url) for url in urls]
        
        # Using tqdm with Dask computations
        with self._progress_bar(range(len(tasks)), "📝 Extracting Reports", "report") as progress_bar:
            results = dask.compute(*tasks)

            extracted_data = []
            for res in results:
                if res is not None:
                    extracted_data.append(res)
                progress_bar.update(1)  # Update progress bar

        if not extracted_data:
            print("⚠️ No valid data extracted.")
            return None

       
        
        print("\n💾 Saving extracted reports...")

        all_data = []
        for data, file_name in self._progress_bar(extracted_data, "📁 Saving Reports", "file"):
            df = pd.DataFrame([data])
            
            # Check if "Volcano Location" exists and convert to decimal
            if "Volcano Location" in df.columns:
                df[["Latitude", "Longitude"]] = df["Volcano Location"].apply(lambda x: pd.Series(self.dms_to_decimal(x) if isinstance(x, str) else {"Latitude": None, "Longitude": None}))

            
            # Process Ash Cloud Height if the column exists
            if "Volcanic Cloud Height" in df.columns:
                df[["AshCloudHeight_ASL", "AshCloudHeight_AGL"]] = df["Volcanic Cloud Height"].apply(
                    lambda x: self.extract_heights(x) if isinstance(x, str) else pd.Series({"AshCloudHeight_ASL": None, "AshCloudHeight_AGL": None})
                )
            
            
            all_data.append(df)

            csv_file_path = os.path.join(self.DETAILED_FOLDER, f"VONA_Report_{file_name}.txt")

            self.save_detailed_reports_to_txt(df)
            tqdm.write(f"✅ Data saved: {csv_file_path}")  # Use tqdm.write to avoid conflicts with progress bar output


        combined_df = pd.concat(all_data, ignore_index=True)
        
        
            # Convert to GeoDataFrame if Latitude and Longitude exist
        if "Latitude" in combined_df.columns and "Longitude" in combined_df.columns:
            combined_df = combined_df.dropna(subset=['Latitude', 'Longitude'])  # Remove missing coordinates
            combined_df['geometry'] = combined_df.apply(lambda row: Point(row['Longitude'], row['Latitude']), axis=1)
            combined_gdf = gpd.GeoDataFrame(combined_df, geometry='geometry', crs="EPSG:4326")
        else:
            print("⚠️ No Latitude/Longitude data found. Returning a regular DataFrame.")
            combined_gdf = combined_df

        
        
        combined_report_path = os.path.join(self.BASE_FOLDER, "MAGMA_VONA_Reports.csv")
        combined_df.to_csv(combined_report_path, index=False)
        print("Detailed reports extracted successfully!")
        
        
        
        return combined_df
    
    def save_detailed_reports_to_txt(self, df):
        """Saves each detailed VONA report as a professionally formatted .txt file."""
        for _, row in df.iterrows():
            # Generate clean file name with prefix & suffix
            issued_date = row.get("Issued", "Unknown").replace(" ", "_")
            volcano_name = row.get("Volcano", "Unknown").replace(" ", "_")
            file_name = self.sanitize_filename(f"VONA_Report_{issued_date}_{volcano_name}.txt")
            txt_path = os.path.join(self.DETAILED_FOLDER, file_name)

            with open(txt_path, "w", encoding="utf-8") as file:
                # 🌍 Professional Header
                file.write("=" * 80 + "\n")
                file.write(" 🌋 VOLCANO OBSERVATORY NOTICE FOR AVIATION (VONA) REPORT 🌋 \n")
                file.write("=" * 80 + "\n")
                file.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
                file.write("Retrieved using Python automation | Real-time data extraction\n")
                file.write("For more information, contact: Dr. Mahmud Muhammad (mahmud.muhammad@hotmail.com)\n")
                file.write("=" * 80 + "\n")
                file.write(f"🔗 Source URL: {row['Source_URL']}\n")
                file.write("=" * 80 + "\n\n")

                # 📜 Report Details (Formatted for Readability)
                for column, value in row.items():
                    if column != "Source_URL":
                        file.write(f"{column:<20}: {value}\n")

                # 🌟 Elegant Footer
                file.write("\n" + "=" * 80 + "\n")
                file.write("📌 This is an automated report. Please verify with official sources.\n")
                file.write("=" * 80 + "\n")

        
        
    #print(f"✅ Detailed report saved: {txt_path}")
    # Function to convert DMS to decimal degrees
    def dms_to_decimal(self, dms_str):
        matches = re.findall(r'([NSWE])\s(\d+)\sdeg\s(\d+)\smin\s(\d+)\ssec', dms_str)
        decimal_coords = {}
        
        for match in matches:
            direction, deg, minutes, sec = match
            decimal_value = int(deg) + int(minutes)/60 + int(sec)/3600
            if direction in ['S', 'W']:  # South and West are negative
                decimal_value *= -1
            
            if direction in ['N', 'S']:
                decimal_coords['Latitude'] = decimal_value
            else:
                decimal_coords['Longitude'] = decimal_value
        
        return decimal_coords
    
    def filter_gdf_by_extent(self, gdf_vona, gdf_whelley):
        """
        Filters VONA GeoDataFrame based on the geographic extent of another GeoDataFrame.

        Parameters:
        -----------
        gdf_vona (GeoDataFrame): The VONA GeoDataFrame to be filtered.
        gdf_whelley (GeoDataFrame): The GeoDataFrame providing the bounding box.

        Returns:
        --------
        gpd.GeoDataFrame: Filtered GeoDataFrame.
        """
        if gdf_whelley is not None and not gdf_whelley.empty:
            # Get bounding box of gdf_whelley
            minx, miny, maxx, maxy = gdf_whelley.total_bounds  # min Longitude, min Latitude, max Longitude, max Latitude

            # Correct filtering by using `.apply()` on the geometry column
            gdf_vona = gdf_vona[
                gdf_vona.geometry.apply(lambda geom: minx <= geom.x <= maxx and miny <= geom.y <= maxy)
            ]

        return gdf_vona