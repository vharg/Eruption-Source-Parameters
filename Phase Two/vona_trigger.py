def VONA_Message(VONA_Source="TOKYO"):
    
    """
    Retrieves and processes Volcanic Observatory Notice for Aviation (VONA) messages from 
    the Tokyo Volcanic Ash Advisory Center (TVAAC) and MAGMA VONA Center. 

    The function downloads, extracts, and analyzes volcanic ash advisory reports, 
    filtering them based on the Whelley 2015 Volcano Database.

    Parameters:
    -----------
    VONA_Source : str, optional (default: "TOKYO")
        * Specifies the source of the VONA message.
        - "TOKYO" : Retrieves VONA reports from the Tokyo VAAC.
            Source: https://www.data.jma.go.jp/vaac/data/vaac_list.html
        
        - "MAGMA" : Retrieves VONA reports from the MAGMA VONA Center.
            Source: https://magma.esdm.go.id/v1/vona

    Returns:
    --------
    - If `VONA_Source="TOKYO"`:
        Tuple: (downloaded_VAA_report, latest_date_data, volcano_name, latitude, 
                longitude, observed_ash_altitude_meter, vei_range)
        
        * downloaded_VAA_report (str): The latest downloaded volcanic ash advisory report.
        * latest_date_data (pd.DataFrame): Dataframe containing details of the most recent advisory.
        * volcano_name (str): Name of the volcano associated with the latest VONA report.
        * latitude (float): Latitude of the volcanic activity.
        * longitude (float): Longitude of the volcanic activity.
        * observed_ash_altitude_meter (float): Height of volcanic ash cloud above ground level (AGL).
        * vei_range (list): Possible Volcanic Explosivity Index (VEI) levels based on Whelley 2015.

    - If `VONA_Source="MAGMA"`:
        Tuple: (gdf_vona_magma, gdf_vona_magma_latest_data, volcano_name_magma, 
                latitude_magma, longitude_magma, AshCloudHeight_AGL, vei_range_Magma)
        
        * gdf_vona_magma (pd.DataFrame): Dataframe containing detailed MAGMA VONA reports.
        * gdf_vona_magma_latest_data (pd.DataFrame): Most recent filtered MAGMA VONA report.
        * volcano_name_magma (str): Name of the volcano from MAGMA VONA report.
        * latitude_magma (float): Latitude of the volcano (MAGMA).
        * longitude_magma (float): Longitude of the volcano (MAGMA).
        * AshCloudHeight_AGL (float): Ash cloud height above ground level (AGL).
        * vei_range_Magma (list): Possible VEI levels based on Whelley 2015.

    Notes:
    ------
    - Requires an active internet connection to fetch the latest reports.
    - Utilizes the `vei` and `vep_vaa_text` modules for data extraction and parsing.
    - Displays extracted information using `rich` library tables.
    - Filters volcanic reports using the Whelley 2015 database.

    Example Usage:
    --------------
    >>> VONA_Message(VONA_Source="TOKYO")
    >>> VONA_Message(VONA_Source="MAGMA")
    """
    # Download VONA Messages from TVAAC and extract time, location and ash column height

    # first we load Whelley 2015 Volcano Database later will be use to filter Volcanish Ash Advisory reports from Tokyo Volcanic Ash Advisory Center in realtime (computer need internet connection to parse VAA reports)

    import vei 

    data_loader=vei.LOADDATA()
    whelley_data=data_loader.whelley_2015(as_geodataframe=True)
    import vep_vaa_text
    from vep_vaa_text import VEP_TVAAC_VAAText
    #url = "https://www.data.jma.go.jp/svd/vaac/data/Archives/2020_vaac_list.html"
    scraper = VEP_TVAAC_VAAText(year=None)
    scraper.fetch_webpage()
    tables = scraper.extract_all_tables()
    tables
    # Perform a search Note: for realtime operation set all parameters to None to retrive the latest report VAA report
    search_results = scraper.search(query=None, date_time=None, advisory_number=None)  # Replace with your query string, set all parameters to None to retrive latest report dates: Note takes longer processing time
    downloaded_VAA_report, latest_VAA_report , latest_date_data=scraper.download_vaa_text(output_dir="./TVAAC_Tokyo", filtered_results=search_results, csv=True, gdf=whelley_data, get_latest_date_data_option=True)

    # Parse VONA from MAGAMA VONA Center

    from vep_vaa_text import MAGMA_VONA_PARSER

    parser = MAGMA_VONA_PARSER("All Volcanoes", BASE_FOLDER='Magma_VONA')

    # Scrape all reports and extract URLs
    parser.scrape_all_reports(max_pages=1) # set max_pages=1 to onlu download most recent 15 VONA reports

    # Extract detailed VONA reports from scraped URLs
    gdf_vona_magma =parser.extract_vona_reports()


    gdf_vona_magma_latest_data =  parser.filter_gdf_by_extent(gdf_vona_magma, whelley_data)

    ###################################

    import pandas as pd
    from rich.console import Console
    from rich.table import Table

    # Initialize the console once
    console = Console()

    # -----------------------------------------------
    # VONA Message Attributes from TVAAC VONA Center
    # -----------------------------------------------
    table_tvaac = Table(title="Message Attributes from TVAAC Center", show_lines=True, title_style="bold blue")

    # Define table columns
    table_tvaac.add_column("Parameter", style="bold black", width=40)
    table_tvaac.add_column("Value", style="bold red", justify="center")

    # Ensure latest_date_data exists and is not empty
    if 'latest_date_data' in locals() and isinstance(latest_date_data, pd.DataFrame) and not latest_date_data.empty:
        latest_date_data.reset_index(drop=True, inplace=True)  # Ensure proper indexing
        row = latest_date_data.iloc[0]  # Extract first row safely

        # Extract values
        volcano_name = row.get('VOLCANO', None)
        observed_ash_altitude_meter = row.get('height_agl', None)
        latitude = row.get('Latitude', None)
        longitude = row.get('Longitude', None)

        # Add extracted values to the table
        if volcano_name:
            table_tvaac.add_row("Site of Volcanic Activity", str(volcano_name))
        if observed_ash_altitude_meter is not None:
            table_tvaac.add_row("Observed Ash Altitude (meter AGL)", str(observed_ash_altitude_meter))
        if latitude is not None:
            table_tvaac.add_row("Latitude", str(latitude))
        if longitude is not None:
            table_tvaac.add_row("Longitude", str(longitude))
    else:
        console.print("[bold red]Error:[/] No valid data found in latest_date_data.")
        exit()

    # Call the search_whelley_2015 method with error handling
    vei_range=None
    try:
        search_results, vei_range = data_loader.search_whelley_2015(Volcano=volcano_name, max_vei_returns=None)
        if vei_range:
            #table_tvaac.add_row(f"Possible VEI Levels for Volcano {volcano_name} (Whelley et al. 2015)", str(vei_range))
            
            # search_results is your DataFrame already defined
            vei_cols = [f"VEI {v}" for v in vei_range if f"VEI {v}" in search_results.columns]
            vei_df = search_results[vei_cols]
            # Add each row from the filtered dataframe
            for idx, row in vei_df.iterrows():
                row_str = ", ".join(f"{col}: {row[col]}" for col in vei_cols)
                table_tvaac.add_row(f"Probability VEI Levels {vei_range} from (Whelley et al. 2015)", row_str)
                table_tvaac.add_row(
                            "Contact Information for Software Developer",
                            "Dr. Mahmud Muhammad\n"
                            "[blue underline]Email:[/] [link=mailto:mahmud.muhammad@hotmail.com]mahmud.muhammad@hotmail.com[/link]\n"
                            "[blue underline]Website:[/] [link=https://mahmudm.com/]https://mahmudm.com/[/link]"
                        )

                    
        else:
            table_tvaac.add_row("Probability VEI Levels", "No data available")
    except Exception as e:
        console.print(f"[bold red]Error fetching VEI levels:[/] {e}")
        search_results = pd.DataFrame()

    # Render the first table
    console.print(table_tvaac)

    # -----------------------------------------------
    # VONA Message Attributes from MAGMA VONA Center
    # -----------------------------------------------
    table_magma = Table(title="VONA Message Attributes from MAGMA VONA Center", show_lines=True, title_style="bold blue")

    # Define table columns
    table_magma.add_column("Parameter", style="bold black", width=40)
    table_magma.add_column("Value", style="bold red", justify="center")

    # Ensure gdf_filtered exists and is not empty
    if 'gdf_vona_magma_latest_data' in locals() and isinstance(gdf_vona_magma_latest_data, pd.DataFrame) and not gdf_vona_magma_latest_data.empty:
        gdf_vona_magma_latest_data.reset_index(drop=True, inplace=True)  # Ensure proper indexing
        row = gdf_vona_magma_latest_data.iloc[0]  # Select the latest VONA message

        # Add extracted fields to the table
        table_magma.add_row("Source URL", row.get("Source_URL", "N/A"))
        table_magma.add_row("Issued Date", row.get("Issued", "N/A"))
        table_magma.add_row("Volcano", row.get("Volcano", "N/A"))
        table_magma.add_row("Current Aviation Colour Code", row.get("Current Aviation Colour Code", "N/A"))
        table_magma.add_row("Previous Aviation Colour Code", row.get("Previous Aviation Colour Code", "N/A"))
        table_magma.add_row("Observing Source", row.get("Source", "N/A"))
        table_magma.add_row("Notice Number", row.get("Notice Number", "N/A"))
        table_magma.add_row("Volcano Location", row.get("Volcano Location", "N/A"))
        table_magma.add_row("Area", row.get("Area", "N/A"))
        table_magma.add_row("Summit Elevation", row.get("Summit Elevation", "N/A"))
        table_magma.add_row("Volcanic Activity Summary", row.get("Volcanic Activity Summary", "N/A"))
        table_magma.add_row("Volcanic Cloud Height", row.get("Volcanic Cloud Height", "N/A"))
        table_magma.add_row("Other Volcanic Cloud Information", row.get("Other Volcanic Cloud Information", "N/A"))
        table_magma.add_row("Remarks", row.get("Remarks", "N/A"))
        table_magma.add_row("Contacts", row.get("Contacts", "N/A"))
        table_magma.add_row("Next Notice", row.get("Next Notice", "N/A"))
        latitude_magma=table_magma.add_row("Latitude", str(row.get("Latitude", "N/A")))
        longitude_magma=table_magma.add_row("Longitude", str(row.get("Longitude", "N/A")))
        AshCloudHeight_ASL=table_magma.add_row("Ash Cloud Height (ASL)", f"{row.get('AshCloudHeight_ASL', 'N/A')} meters")
        AshCloudHeight_AGL=table_magma.add_row("Ash Cloud Height (AGL)", f"{row.get('AshCloudHeight_AGL', 'N/A')} meters")
        AshCloudHeight_AGL = row.get('AshCloudHeight_AGL', None)
        longitude_magma= row.get("Longitude", None)
        latitude_magma= row.get("Latitude", None)

        # Call the search_whelley_2015 method with error handling
        vei_range_Magma=None
        
        try:
            volcano_name_magma= gdf_vona_magma_latest_data['Volcano'].to_list()[0].split(" (")[0]
            search_results, vei_range_Magma = data_loader.search_whelley_2015(Volcano=volcano_name_magma, max_vei_returns=None)
            if vei_range_Magma:
                #table_magma.add_row(f"Possible VEI Levels for Volcano {volcano_name_magma} (Whelley et al. 2015)", str(vei_range_Magma))
                # search_results is your DataFrame already defined
                vei_cols = [f"VEI {v}" for v in vei_range_Magma if f"VEI {v}" in search_results.columns]
                vei_df = search_results[vei_cols]
                # Add each row from the filtered dataframe
                for idx, row in vei_df.iterrows():
                    row_str = ", ".join(f"{col}: {row[col]}" for col in vei_cols)
                    table_magma.add_row(f"Probability VEI Levels {vei_range_Magma} from (Whelley et al. 2015)", row_str)
                    table_magma.add_row(
                            "Contact Information for Software Developer",
                            "Dr. Mahmud Muhammad\n"
                            "[blue underline]Email:[/] [link=mailto:mahmud.muhammad@hotmail.com]mahmud.muhammad@hotmail.com[/link]\n"
                            "[blue underline]Website:[/] [link=https://mahmudm.com/]https://mahmudm.com/[/link]"
                        )

            else:
                table_magma.add_row("Probability VEI Levels", "No data available")
        except Exception as e:
            console.print(f"[bold red]Error fetching VEI levels:[/] {e}")
            search_results = pd.DataFrame()
        
        # Display the table
        console.print(table_magma)
    else:
        console.print("[bold red]Error:[/] No valid VONA data available.")


     # -----------------------------------------------
    # Returning Data Based on Source
    # -----------------------------------------------
    if AshCloudHeight_AGL is not None:
       AshCloudHeight_AGL= int(AshCloudHeight_AGL)/1000
        
    if observed_ash_altitude_meter is not None:
        observed_ash_altitude_meter=int(observed_ash_altitude_meter)/1000
        
    if VONA_Source == "TOKYO":
        return downloaded_VAA_report, latest_date_data, volcano_name, latitude, longitude, observed_ash_altitude_meter, vei_range
    elif VONA_Source == "MAGMA":
        return gdf_vona_magma, gdf_vona_magma_latest_data, volcano_name_magma, latitude_magma, longitude_magma, AshCloudHeight_AGL, vei_range_Magma

# Example How to USE
#VONA_reports, VONA_latest_data, volcano_name, latitude, longitude, AshCloudHeight_AGL, vei_range=VONA_Message(VONA_Source="TOKYO")


import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import matplotlib.gridspec as gridspec
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import matplotlib.dates as mdates


class PlumeHeightAnalyzer_FromInfrasound:
   
    
    def __init__(self, folder_path, InfraSound_DateTime_Txt_input=None,
             window_minutes_before=None, window_minutes_after=None,
             output_duration_format=None,
             output_csv_dir=None, sim_output_dir=None):
        
        """
       
        A class to analyze plume height datasets stored in text files within a specified folder.
        It calculates mean values for two categories ('Mono' and 'DI') and visualizes the data.

        Attributes:
            folder_path (str): The directory containing text files with plume height data.
            datasets (list): A list of NumPy arrays, each representing a dataset.
            valid_file_paths (list): A list of file paths corresponding to valid datasets.
            dataset_prefixes (set): A set of unique dataset prefixes derived from filenames.
            mean_values (dict): A dictionary storing computed mean values for 'Mono' and 'DI' categories.

        Methods:
            load_datasets(): Loads valid .txt files from the folder and stores them as NumPy arrays.
            calculate_mean_values(): Computes and stores mean values for 'Mono' and 'DI' datasets.
            get_mono_means(): Returns a dictionary of Mono mean values for all datasets.
            get_di_means(): Returns a dictionary of DI mean values for all datasets.
            get_mono_mean(dataset_name): Returns the Mono mean values for a specific dataset.
            get_di_mean(dataset_name): Returns the DI mean values for a specific dataset.
            visualize_datasets(): Generates scatter plots with median trend lines for all datasets.
    
        """
        
      
        os.makedirs(output_csv_dir, exist_ok=True)
        os.makedirs(sim_output_dir, exist_ok=True)
        
        self.InfraSound_DateTime_Txt_input = InfraSound_DateTime_Txt_input
        self.window_minutes_before = window_minutes_before
        self.window_minutes_after = window_minutes_after
        self.output_duration_format = output_duration_format
        self.output_csv_dir = Path(output_csv_dir) if output_csv_dir else None
        self.sim_output_dir = Path(sim_output_dir) if sim_output_dir else None

        self.folder_path = folder_path
        self.datasets = []
        self.valid_file_paths = []
        self.dataset_prefixes = set()
        self.mean_values = {}

        self.load_datasets()
        self.calculate_mean_values()
        self.Infrasound_datatime_dataframe=None
        self.plume_height_percentile_dataframe = None  
        
        
        

    def load_datasets(self):
        """
        Loads all valid .txt datasets from the specified folder.
        """
        file_paths = [os.path.join(self.folder_path, file) for file in os.listdir(self.folder_path) if file.endswith(".txt")]

        for file in file_paths:
            try:
                data = np.loadtxt(file)
                if data.size > 0:
                    self.datasets.append(data)
                    self.valid_file_paths.append(file)
            except Exception as e:
                print(f"Error loading {file}: {e}")

        if not self.datasets:
            print("No valid datasets found. Please check the folder path and file contents.")

        # Extract unique dataset prefixes
        self.dataset_prefixes = set(os.path.splitext(file)[0].split("_")[0] for file in os.listdir(self.folder_path) if file.endswith(".txt"))

    def calculate_mean_values(self):
        """
        Calculates and stores mean values separately for 'Mono' and 'DI' datasets.
        """
        mean_values = {}

        for dataset_prefix in sorted(self.dataset_prefixes):
            dataset_files = [file for file in self.valid_file_paths if os.path.basename(file).startswith(dataset_prefix)]
            dataset_data = [data for file, data in zip(self.valid_file_paths, self.datasets) if os.path.basename(file).startswith(dataset_prefix)]
            
            mono_means = []
            di_means = []

            for file_path, data in zip(dataset_files, dataset_data):
                if data.size > 0:  # Ensure dataset is not empty
                    file_name = os.path.basename(file_path)
                    if 'di' in file_name.lower():
                        di_means.append(np.mean(data))
                    else:
                        mono_means.append(np.mean(data))

            mean_values[dataset_prefix] = {
                "Mono": mono_means,
                "DI": di_means
            }

        self.mean_values = mean_values  # Store computed means for later use

    def get_mono_means(self):
        """
        Returns a dictionary where keys are dataset names, and values are lists of Mono means.
        """
        return {key: value["Mono"] for key, value in self.mean_values.items()}

    def get_di_means(self):
        """
        Returns a dictionary where keys are dataset names, and values are lists of DI means.
        """
        return {key: value["DI"] for key, value in self.mean_values.items()}

    def get_mono_mean(self, dataset_name):
        """
        Returns the Mono means for a specific dataset.
        """
        if dataset_name in self.mean_values:
            return self.mean_values[dataset_name]["Mono"]
        else:
            print(f"Dataset '{dataset_name}' not found.")
            return None

    def get_di_mean(self, dataset_name):
        """
        Returns the DI means for a specific dataset.
        """
        if dataset_name in self.mean_values:
            return self.mean_values[dataset_name]["DI"]
        else:
            print(f"Dataset '{dataset_name}' not found.")
            return None

   
        
    def visualize_datasets(self, eruption_df=None, save_path=None):
        """
        Generates scatter plots and median trend lines for the datasets.
        If eruption_df is provided (output of eruptiontime_processer), uses its Datetime values on the x-axis.
        """
        if not self.datasets:
            print("No datasets to visualize.")
            return

        num_datasets = len(self.dataset_prefixes)

        fig = plt.figure(figsize=(14, 6 * num_datasets))
        gs = gridspec.GridSpec(num_datasets, 1, figure=fig, hspace=0.4)

        # Define colormap
        cmap = cm.coolwarm
        norm = mcolors.Normalize(
            vmin=min(np.nanmin(np.nanmedian(data, axis=0)) for data in self.datasets),
            vmax=max(np.nanmax(np.nanmedian(data, axis=0)) for data in self.datasets)
        )

        # Build x-axis labels if eruption_df is provided
        x_datetime_labels = None
        if eruption_df is not None:
            # Sort eruption_df by Datetime to ensure order
            eruption_df_sorted = eruption_df.sort_values("Datetime").reset_index(drop=True)
            x_datetime_labels = eruption_df_sorted["Datetime"].tolist()

        # Process each dataset separately
        for idx, dataset_prefix in enumerate(sorted(self.dataset_prefixes)):
            ax = fig.add_subplot(gs[idx]) if num_datasets > 1 else plt.gca()
            
            dataset_files = [file for file in self.valid_file_paths if os.path.basename(file).startswith(dataset_prefix)]
            dataset_data = [data for file, data in zip(self.valid_file_paths, self.datasets) if os.path.basename(file).startswith(dataset_prefix)]

            for file_path, data in zip(dataset_files, dataset_data):
                file_name = os.path.basename(file_path)

                linestyle = 'dashed' if 'di' in file_name.lower() else 'solid'

                # Compute medians
                medians = np.nanmedian(data, axis=0)

                # Normalize transparency
                median_min, median_max = np.nanmin(medians), np.nanmax(medians)
                if median_max - median_min < 1e-6:
                    normalized_alphas = np.ones(len(medians)) * 0.7
                else:
                    normalized_alphas = (medians - median_min) / (median_max - median_min + 1e-6) * 0.7 + 0.3

                # Determine x values
                if x_datetime_labels is not None and len(x_datetime_labels) >= data.shape[1]:
                    x_values = x_datetime_labels[:data.shape[1]]
                else:
                    x_values = np.arange(data.shape[1])  # fallback

                # Plot scatter points
                scatter_colors = cmap(norm(data.flatten()))
                ax.scatter(
                    np.tile(x_values, data.shape[0]),
                    data.flatten(),
                    color=scatter_colors,
                    s=2,
                    alpha=0.4
                )

                # Plot median line
                for i in range(len(medians) - 1):
                    color = cmap(norm(medians[i]))
                    x0 = x_values[i]
                    x1 = x_values[i + 1]
                    ax.plot([x0, x1], [medians[i], medians[i + 1]], color=color, alpha=normalized_alphas[i], linestyle=linestyle, linewidth=2)

            # Format x-axis
            if x_datetime_labels is not None:
                ax.set_xlabel("Datetime", fontsize=12)
                #ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%Y-%m-%d\n%H:%M'))
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d\n%H:%M'))

                fig.autofmt_xdate()  # rotate dates for readability
            else:
                ax.set_xlabel("Column Index", fontsize=12)

            ax.set_ylabel("Plume Heights", fontsize=12)
            ax.set_title(f"Scatter Plot for {dataset_prefix} Data", fontsize=14)
            ax.grid(True, linestyle='--', alpha=0.6)

            # Legend
            ax.plot([], [], color='black', linestyle='dashed', label="DI")
            ax.plot([], [], color='black', linestyle='solid', label="Mono")
            ax.legend(loc="upper right", fontsize=10, frameon=True)

        # Add colorbar
        cbar_ax = fig.add_axes([0.92, 0.15, 0.02, 0.7])
        cbar = plt.colorbar(cm.ScalarMappable(norm=norm, cmap=cmap), cax=cbar_ax)
        cbar.set_label("Median Value", fontsize=12)

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')

        plt.show()

   

    def eruptiontime_processer(
        self,
        InfraSound_DateTime_Txt_input=None,
        window_minutes_before=None,
        window_minutes_after=None,
        output_duration_format=None
    ):
        file_path = InfraSound_DateTime_Txt_input or self.InfraSound_DateTime_Txt_input
        window_minutes_before = window_minutes_before if window_minutes_before is not None else self.window_minutes_before
        window_minutes_after = window_minutes_after if window_minutes_after is not None else self.window_minutes_after
        output_duration_format = output_duration_format or self.output_duration_format

        if file_path is None:
            raise ValueError("No InfraSound_DateTime_Txt_input provided.")

        #df = pd.read_csv(file_path, delim_whitespace=True, header=None)
        df = pd.read_csv(file_path, sep=r"\s+", header=None)

        df.columns = ["Year", "Month", "Day", "Hour", "Minute", "Second"]
        df["Datetime"] = pd.to_datetime(df[["Year", "Month", "Day", "Hour", "Minute", "Second"]])

        def format_window(dt):
            start_dt = dt - timedelta(minutes=window_minutes_before)
            end_dt = dt + timedelta(minutes=window_minutes_after)
            start_str = f"{start_dt.hour:02d}_{start_dt.minute:02d}"
            end_str = f"{end_dt.hour:02d}_{end_dt.minute:02d}"
            return f"{start_str} - {end_str}"

        df["EruptionTimeWindow"] = df["Datetime"].apply(format_window)

        def compute_window_duration(window_str):
            start_str, end_str = window_str.split(" - ")
            start_hour, start_minute = map(int, start_str.split("_"))
            end_hour, end_minute = map(int, end_str.split("_"))
            start_total_minutes = start_hour * 60 + start_minute
            end_total_minutes = end_hour * 60 + end_minute
            if end_total_minutes < start_total_minutes:
                end_total_minutes += 24 * 60
            duration_minutes = end_total_minutes - start_total_minutes
            if output_duration_format == "minutes":
                return duration_minutes
            elif output_duration_format == "HH_MM":
                duration_hour = duration_minutes // 60
                duration_minute = duration_minutes % 60
                return f"{duration_hour:02d}_{duration_minute:02d}"
            else:
                raise ValueError("Invalid output_duration_format. Use 'HH_MM' or 'minutes'.")

        df["WindowDuration_HH_MM"] = df["EruptionTimeWindow"].apply(compute_window_duration)
        
        ##################
       
        # Split "HH_MM" format into separate hour and minute columns
        if output_duration_format == "HH_MM":
            df[["duration_hr", "duration_min"]] = df["WindowDuration_HH_MM"].str.split("_", expand=True).astype(int)

        self.Infrasound_datatime_dataframe=df
        
        return df


    def calculate_column_percentiles(self,percentiles=[5, 50, 95],dataset_type='mono',dataset_name='sparks', InfraSound_DateTime_Txt_input=None,
                                     use_weighted_average=False,plot=False):
        
        """
        Calculates specified column-wise percentiles, mean, and standard deviation
        for plume height datasets. Supports merging 'mastin' and 'sparks' datasets
        and optionally applies weighted averaging. Also supports plotting.

        Parameters:
        ----------
        percentiles : list of int
            List of percentiles to compute (e.g., [5, 50, 95]).

        dataset_type : str
            One of {'mono', 'di', 'both'}. Filters data based on signal type.

        dataset_name : str
            Name of the dataset to process. Use 'mastin_and_sparks' to merge both.

        InfraSound_DateTime_Txt_input : str or None
            Optional path to infrasound datetime file (if not passed in init).

        use_weighted_average : bool
            If True and dataset_name='mastin_and_sparks', computes weighted average
            based on sample size of each source column-wise.

        plot : bool
            If True, generates line plots showing mean, std, and percentiles.

        Returns:
        -------
        pd.DataFrame
            Summary DataFrame containing statistics per column.
        """






        # Load datetime labels from infrasound file
        txt_path = InfraSound_DateTime_Txt_input or self.InfraSound_DateTime_Txt_input
        eruption_df = None
        if txt_path:
            try:
                df = pd.read_csv(txt_path, sep=r"\s+", header=None)
                df.columns = ["Year", "Month", "Day", "Hour", "Minute", "Second"]
                df["Datetime"] = pd.to_datetime(df[["Year", "Month", "Day", "Hour", "Minute", "Second"]])
                eruption_df = df[["Datetime"]]
            except Exception as e:
                print(f"[Error] Could not parse InfraSound datetime file: {e}")

        # Validate dataset type
        valid_types = ['mono', 'di', 'both']
        if dataset_type.lower() not in valid_types:
            raise ValueError(f"Invalid dataset_type '{dataset_type}'. Use 'mono', 'di', or 'both'.")

        rows = []
        summary_rows = []

        # CASE A: Merge mastin and sparks together
        if dataset_name == 'mastin_and_sparks':
            combined_columns = []
            col_weights = []

            for prefix in ['mastin', 'sparks']:
                prefix_data = []
                for file_path, data in zip(self.valid_file_paths, self.datasets):
                    if not os.path.basename(file_path).startswith(prefix):
                        continue

                    file_name = os.path.basename(file_path)
                    is_di = 'di' in file_name.lower()

                    if dataset_type == 'mono' and is_di:
                        continue
                    if dataset_type == 'di' and not is_di:
                        continue

                    prefix_data.append(data)

                if not prefix_data:
                    continue

                stacked = np.vstack(prefix_data)
                combined_columns.append(stacked)
                col_weights.append(np.sum(~np.isnan(stacked), axis=0))  # sample counts per column

            if not combined_columns or len(combined_columns) < 2:
                print("[Warning] One or both datasets missing for 'mastin_and_sparks'.")
                return pd.DataFrame()

            # Option A: Use weighted average
            if use_weighted_average:
                total_weight = np.maximum(np.sum(col_weights, axis=0), 1)
                combined = (
                    sum(w * np.nanmean(data, axis=0) for w, data in zip(col_weights, combined_columns)) / total_weight
                )
                stds = np.std(np.vstack(combined_columns), axis=0)
                counts = total_weight
            else:
                # Option B: Just vertically stack
                merged_data = np.vstack(combined_columns)
                combined = np.nanmean(merged_data, axis=0)
                stds = np.nanstd(merged_data, axis=0)
                counts = np.sum(~np.isnan(merged_data), axis=0)

            if eruption_df is not None and len(eruption_df) >= len(combined):
                datetime_labels = eruption_df["Datetime"].iloc[:len(combined)].tolist()
            else:
                datetime_labels = [f"Col_{i+1}" for i in range(len(combined))]

            row_label = "mastin_and_sparks"
            row_dict = {"Dataset_Label": row_label}

            for idx, (label, mean_val, std_val, count) in enumerate(zip(datetime_labels, combined, stds, counts)):
                col_data = []
                for block in combined_columns:
                    if idx < block.shape[1]:
                        col = block[:, idx]
                        col_data.extend(col[~np.isnan(col)])
                col_data = np.array(col_data)

                for p in percentiles:
                    value = np.percentile(col_data, p) if len(col_data) > 0 else np.nan
                    row_dict[f"Height_km.a.v.l_Percentile_{p}_{label}"] = value

                summary_row = {
                    "Dataset_Label": row_label,
                    "Datetime": label,
                    "Number of samples": len(col_data),
                    "Mean Height (Km)": np.mean(col_data),
                    "SD_Height (Km)": np.std(col_data)
                }
                for p in percentiles:
                    summary_row[f"Percentile_{p}"] = (
                        np.percentile(col_data, p) if len(col_data) > 0 else np.nan
                    )
                summary_rows.append(summary_row)

            rows.append(row_dict)

        # CASE B: Normal (single dataset)
        else:
            if dataset_name not in self.dataset_prefixes:
                raise ValueError(f"Dataset_name '{dataset_name}' not found in dataset_prefixes.")

            dataset_files = [file for file in self.valid_file_paths if os.path.basename(file).startswith(dataset_name)]
            dataset_data = [data for file, data in zip(self.valid_file_paths, self.datasets)
                            if os.path.basename(file).startswith(dataset_name)]

            for file_path, data in zip(dataset_files, dataset_data):
                if data.size == 0:
                    continue
                file_name = os.path.basename(file_path)
                is_di = 'di' in file_name.lower()

                if dataset_type == 'mono' and is_di:
                    continue
                if dataset_type == 'di' and not is_di:
                    continue

                row_label = f"{dataset_name}_{'DI' if is_di else 'Mono'}"
                row_dict = {"Dataset_Label": row_label}

                if eruption_df is not None and len(eruption_df) >= data.shape[1]:
                    datetime_labels = eruption_df["Datetime"].iloc[:data.shape[1]].tolist()
                else:
                    datetime_labels = [f"Col_{i+1}" for i in range(data.shape[1])]

                for col_idx in range(data.shape[1]):
                    col_data = data[:, col_idx]
                    col_data = col_data[~np.isnan(col_data)]
                    label = datetime_labels[col_idx]

                    for p in percentiles:
                        percentile_value = np.percentile(col_data, p) if len(col_data) > 0 else np.nan
                        row_dict[f"Height_km.a.v.l_Percentile_{p}_{label}"] = percentile_value

                    summary_row = {
                        "Dataset_Label": row_label,
                        "Datetime": label,
                        "Number of samples": len(col_data),
                        "Mean Height (Km)": np.mean(col_data) if len(col_data) > 0 else np.nan,
                        "SD_Height (Km)": np.std(col_data) if len(col_data) > 0 else np.nan
                    }

                    for p in percentiles:
                        summary_row[f"Percentile_{p}"] = (
                            np.percentile(col_data, p) if len(col_data) > 0 else np.nan
                        )

                    summary_rows.append(summary_row)

                rows.append(row_dict)

        self.plume_height_percentile_df = pd.DataFrame(rows)
        self.plume_height_summary_df = pd.DataFrame(summary_rows)

        # Optional Plotting
        if plot and not self.plume_height_summary_df.empty:
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates

            df = self.plume_height_summary_df
            df_sorted = df.sort_values("Datetime")

            plt.figure(figsize=(14, 6))
            plt.plot(df_sorted["Datetime"], df_sorted["Mean Height (Km)"], label="Mean", linewidth=2)
            plt.fill_between(df_sorted["Datetime"],
                            df_sorted["Mean Height (Km)"] - df_sorted["SD_Height (Km)"],
                            df_sorted["Mean Height (Km)"] + df_sorted["SD_Height (Km)"],
                            alpha=0.3, label="±1 SD")

            for p in percentiles:
                plt.plot(df_sorted["Datetime"], df_sorted[f"Percentile_{p}"], label=f"P{p}", linestyle="--")

            # Formatting the datetime x-axis
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
            plt.xticks(rotation=45, ha='right')

            plt.xlabel("Datetime")
            plt.ylabel("Height (km a.v.l.)")
            plt.title(f"Plume Heights Summary ({dataset_name})")
            plt.legend()
            plt.grid(True)
            plt.tight_layout()
            plt.show()

        
        self.plume_height_percentile_dataframe=self.plume_height_summary_df
        
        
        return self.plume_height_summary_df


    
    def save_percentile_results_to_csv(self, dataset_name="unknown", dataset_type="mono"):
        """
        Saves the summary and percentile DataFrames to output_csv_dir
        using a timestamped filename that includes dataset info.

        Parameters:
        ----------
        dataset_name : str
            Name of the dataset used to label the file.

        dataset_type : str
            One of {'mono', 'di', 'both'} — used in filename.
        """
        if self.output_csv_dir is None:
            raise ValueError("output_csv_dir is not set.")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_prefix = f"{dataset_name}_{dataset_type}_{timestamp}"

        if self.plume_height_summary_df is not None:
            summary_path = self.output_csv_dir / f"{file_prefix}_summary.csv"
            self.plume_height_summary_df.to_csv(summary_path, index=False)
            print(f"✅ Saved summary to: {summary_path}")
        else:
            print("⚠️ plume_height_summary_df is None — nothing saved for summary.")

        # if self.plume_height_percentile_df is not None:
        #     percentiles_path = self.output_csv_dir / f"{file_prefix}_percentiles.csv"
        #     self.plume_height_percentile_df.to_csv(percentiles_path, index=False)
        #     print(f"✅ Saved percentiles to: {percentiles_path}")
        # else:
        #     print("⚠️ plume_height_percentile_df is None — nothing saved for percentiles.")

    
    
    def ensure_metadata_in_csvs_with_defaults(self, custom_metadata=None, fallback_to_input=False):
        """
        Ensure all CSV files in output_csv_dir have required metadata. If not, insert default or prompted values.
        """
        if self.output_csv_dir is None:
            raise ValueError("output_csv_dir is not set.")

        required_keys = ["Volcano_Name", "Latitude", "Longitude", "Summit_Elevation(m)", "start_date"]
        default_metadata = {
            "Volcano_Name": "Unknown Volcano",
            "Latitude": "0.0",
            "Longitude": "0.0",
            "Summit_Elevation(m)": "0",
            "start_date": "1 January 2000"
        }

        metadata_source = {**default_metadata, **(custom_metadata or {})}

        for csv_path in self.output_csv_dir.rglob("*.csv"):
            with open(csv_path, "r") as f:
                lines = f.readlines()

            metadata = {}
            data_start_index = None
            for i, line in enumerate(lines):
                if line.strip().lower() == "metadata":
                    continue
                if line.strip() == "":
                    continue
                if "Time in hour" in line:
                    data_start_index = i
                    break
                if "," in line:
                    k, *v = [part.strip() for part in line.strip().split(",")]
                    metadata[k] = ",".join(v)

            updated = False
            for key in required_keys:
                if key not in metadata or not metadata[key].strip():
                    default_val = metadata_source.get(key, "")
                    if fallback_to_input:
                        user_val = input(f"{csv_path.name} is missing '{key}'. Enter value [{default_val}]: ").strip()
                        metadata[key] = user_val if user_val else default_val
                    else:
                        metadata[key] = default_val
                    updated = True

            if updated:
                print(f"Updating metadata in {csv_path.name}...")
                new_lines = ["Metadata\n\n"]
                for k, v in metadata.items():
                    new_lines.append(f"{k},{v}\n")
                new_lines.append("\n")
                new_lines.extend(lines[data_start_index:])
                with open(csv_path, "w") as f:
                    f.writelines(new_lines)

    def generate_sim_files_from_user_csv(self, csv_input, volcano_name, latitude, longitude, summit_elevation):
        """
        Generate simulation configuration files from a CSV or DataFrame containing eruption details.
        """
        if self.sim_output_dir is None:
            raise ValueError("sim_output_dir is not set.")

        if isinstance(csv_input, (str, Path)):
            df = pd.read_csv(csv_input)

        elif isinstance(csv_input, pd.DataFrame):
            df = csv_input.copy()

        elif hasattr(self, 'Infrasound_datatime_dataframe') and hasattr(self, 'plume_height_percentile_dataframe'):
            if self.Infrasound_datatime_dataframe is not None and self.plume_height_percentile_dataframe is not None:
                # Merge or concatenate based on shared Datetime column
                df = pd.merge(
                    self.plume_height_percentile_dataframe,
                    self.Infrasound_datatime_dataframe,
                    on="Datetime",
                    how="left"
                )
            else:
                raise ValueError("Required internal dataframes are missing or None.")

        else:
            raise ValueError("csv_input must be a file path, a pandas DataFrame, or the class must contain valid internal data.")

       
       

        if "Datetime" not in df.columns:
            raise ValueError("Input data must contain a 'Datetime' column.")
        df["Datetime"] = pd.to_datetime(df["Datetime"])

        volcano_dir = self.sim_output_dir / volcano_name
        volcano_dir.mkdir(parents=True, exist_ok=True)

        metadata = {
            "Volcano_Name": volcano_name,
            "Latitude": str(latitude),
            "Longitude": str(longitude),
            "Summit_Elevation(m)": str(summit_elevation)
        }

        percentile_columns = {
            "5th": "Percentile_5",
            "50th": "Percentile_50",
            "95th": "Percentile_95"
        }

        for label, column in percentile_columns.items():
            lines = [
                f"simulationStartDatetime {df['Datetime'].iloc[0].strftime('%Y%m%d_%H%M')}",
                "simulationDurationInHour 24",
                f"volcanoName {volcano_name}_273070",
                f"volcanoX {metadata['Longitude']}",
                f"volcanoY {metadata['Latitude']}",
                f"summitHeightInMetre {metadata['Summit_Elevation(m)']}",
                "simulationDomain_xMin 90.0",
                "simulationDomain_xMax 160.0",
                "simulationDomain_yMin -15.0",
                "simulationDomain_yMax 40.0",
                "outputGridSize_dX 0.25",
                "outputGridSize_dY 0.25"
            ]

            for idx, row in df.iterrows():
                try:
                    height = max(0, int(float(row[column]) * 1000))
                except (KeyError, ValueError):
                    print(f"Warning: Missing or invalid {column} at row {idx}, skipping.")
                    continue

                duration_hr = int(row.get("duration_hr", 1))
                duration_min = int(row.get("duration_min", 0))
                time_str = row["Datetime"].strftime("%Y_%m_%d_%H_%M")
                emission = f"emissionSourceParameterSet_{idx+1} {height:04d}_{duration_hr:02d}_{duration_min:02d}_{time_str}"
                lines.append(emission)

            output_file = volcano_dir / f"{volcano_name}_{df['Datetime'].iloc[0].strftime('%Y%m%d')}_{label}.txt"
            with open(output_file, "w") as f:
                f.write("\n".join(lines))

        print(f"Simulation files for {volcano_name} created in: {volcano_dir}")
        
        # Save CSVs (summary + percentiles) before generating sim files
        self.save_percentile_results_to_csv(dataset_name=volcano_name, dataset_type="auto_from_sim")

        # Update metadata in all CSVs in output_csv_dir
        custom_metadata = {
            "Volcano_Name": volcano_name,
            "Latitude": str(latitude),
            "Longitude": str(longitude),
            "Summit_Elevation(m)": str(summit_elevation),
            "start_date": df["Datetime"].min().strftime("%d %B %Y")
        }
        self.ensure_metadata_in_csvs_with_defaults(custom_metadata=custom_metadata, fallback_to_input=False)






# # Example usage:
# analyzer = PlumeHeightAnalyzer_FromInfrasound("./allPlumeHeights/")
# dataset_name = "sparks"  # Change this to an actual dataset name in your folder

# mono_mean = analyzer.get_mono_mean(dataset_name)
# di_mean = analyzer.get_di_mean(dataset_name)

# print(f"Mono Mean for {dataset_name}: {mono_mean}")
# print(f"DI Mean for {dataset_name}: {di_mean}")

# analyzer.visualize_datasets()

# combined=mono_mean + di_mean

# # Round numbers to two decimal places and remove duplicates
# combined = list(set(int(round(num)) for num in combined))

# # Sort the result (optional)
# combined.sort()

# print(f"Combined Mono and di mean Plume Heights: {combined}")


#######################################################################

#######################################################################

import os
import re
import shutil
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from dateutil import parser as dateparser


class PlumeHeightAnalyzerFromSatellite:
    def __init__(self, source_excel: str, working_dir: str):
        self.source_excel = Path(source_excel)
        self.working_dir = Path(working_dir)
        self.output_csv_dir = self.working_dir / "_Metadata"
        self.sim_output_dir = self.working_dir / "NameModel_Simulation_inputFiles"
        self.output_csv_dir.mkdir(parents=True, exist_ok=True)
        self.sim_output_dir.mkdir(parents=True, exist_ok=True)
        self.df = pd.read_excel(source_excel, sheet_name=0, header=None)
        self.skipped_logs = []

    @staticmethod
    def is_date_row(row) -> bool:
        pattern = re.compile(r"\d{1,2}(st|nd|rd|th)?\s+[A-Za-z]+\s*,?\s*\d{4}")
        return any(isinstance(cell, str) and pattern.fullmatch(cell.strip()) for cell in row if isinstance(cell, str))

    @staticmethod
    def clean_string(s: str) -> str:
        return re.sub(r"[^\w\-]", "_", s.strip())

    def extract_csvs_with_metadata(self):
        rows = self.df.values.tolist()
        i = 0
        eruption_counter = 1

        while i < len(rows):
            row = rows[i]

            if any(isinstance(cell, str) and "eruption" in str(cell).lower() for cell in row):
                eruption_title_row = [str(cell) for cell in row if pd.notna(cell)]
                eruption_title = next(cell for cell in eruption_title_row if "eruption" in cell.lower())
                volcano_name = eruption_title.split("Eruption")[0].strip()
                safe_volcano = self.clean_string(volcano_name or f"Volcano_{eruption_counter}")
                eruption_counter += 1

                metadata_base = {
                    "Volcano_Name": eruption_title,
                    "Latitude": "",
                    "Longitude": "",
                    "Summit_Elevation(m)": ""
                }

                for idx, val in enumerate(eruption_title_row):
                    val_l = str(val).lower()
                    if "latitude" in val_l:
                        metadata_base["Latitude"] = str(eruption_title_row[idx + 1]) if idx + 1 < len(eruption_title_row) else ""
                    elif "longitude" in val_l:
                        metadata_base["Longitude"] = str(eruption_title_row[idx + 1]) if idx + 1 < len(eruption_title_row) else ""
                    elif "elevation" in val_l:
                        metadata_base["Summit_Elevation(m)"] = str(eruption_title_row[idx + 1]) if idx + 1 < len(eruption_title_row) else ""

                volcano_dir = self.output_csv_dir / safe_volcano
                volcano_dir.mkdir(parents=True, exist_ok=True)

                i += 1

                while i < len(rows):
                    row = rows[i]
                    if any("eruption" in str(c).lower() for c in row if isinstance(c, str)):
                        break

                    if self.is_date_row(row):
                        date_label = row[0].strip()
                        metadata = metadata_base.copy()
                        metadata["start_date"] = date_label

                        header = [str(h).strip() for h in rows[i + 1]]
                        data_rows = []
                        i += 2

                        while i < len(rows):
                            r = rows[i]
                            if self.is_date_row(r) or any("eruption" in str(c).lower() for c in r if isinstance(c, str)):
                                break
                            if any(pd.notna(cell) for cell in r):
                                data_rows.append(r)
                            i += 1

                        df_block = pd.DataFrame(data_rows, columns=header)
                        file_name = f"{safe_volcano}_{self.clean_string(date_label)}.csv"
                        output_csv = volcano_dir / file_name

                        with open(output_csv, "w") as f:
                            f.write("Metadata\n\n")
                            for k, v in metadata.items():
                                f.write(f"{k},{v}\n")
                            f.write("\n")
                            df_block.to_csv(f, index=False)
                    else:
                        i += 1

    def process_csvs_for_simulation(self, remove_zero_height=True, use_current_time=False):
        for csv_path in self.output_csv_dir.rglob("*.csv"):
            self._process_single_csv(csv_path, remove_zero_height, use_current_time=use_current_time)

    def _process_single_csv(self, csv_path: Path, remove_zero_height=False, use_current_time=False):
        with open(csv_path, "r") as f:
            raw_lines = f.readlines()

        metadata = {}
        header_index = None
        in_meta = False
        for i, line in enumerate(raw_lines):
            if "Metadata" in line:
                in_meta = True
                continue
            if in_meta and line.strip() == "":
                continue
            if in_meta and "Time in hour" in line:
                header_index = i
                break
            if in_meta and "," in line:
                parts = [p.strip().strip('"') for p in line.strip().split(",") if p.strip()]
                if len(parts) >= 2:
                    metadata[parts[0]] = parts[1]

        raw_date = metadata.get("start_date", "").replace("th", "").replace("nd", "").replace("rd", "").replace("st", "").replace(",", "")
        try:
            start_time = dateparser.parse(raw_date)
        except Exception:
            match = re.search(r"\d{4}", csv_path.name)
            year = match.group(0) if match else "2024"
            raw_date_full = f"{raw_date} {year}"
            start_time = dateparser.parse(raw_date_full)
        #start_time = start_time.replace(hour=2, minute=25)
        # ✅ Force current time if requested or parsing failed
        if use_current_time or start_time is None:
            start_time = datetime.now()

        df = pd.read_csv(csv_path, skiprows=header_index)
        volcano_name = metadata.get("Volcano_Name", "Unknown").split()[0]

        volcano_dir = self.sim_output_dir / volcano_name
        volcano_dir.mkdir(parents=True, exist_ok=True)

        # percentiles = {
        #     "5th": lambda row: max((row["Mean Height (Km)"] - 2 * row["SD_Height (Km)"]) * 1000, 0),
        #     "50th": lambda row: row["Mean Height (Km)"] * 1000,
        #     "95th": lambda row: (row["Mean Height (Km)"] + 2 * row["SD_Height (Km)"]) * 1000
        # }
        
        percentiles = {
            "5th": lambda row: max((row["Mean Height (Km)"] + -1.645 * row["SD_Height (Km)"]) * 1000, 0),
            "50th": lambda row: row["Mean Height (Km)"] * 1000,
            "95th": lambda row: (row["Mean Height (Km)"] + 1.645 * row["SD_Height (Km)"]) * 1000,
        }

        for label, func in percentiles.items():
            lines = self._generate_config_file(
                height_func=func,
                df=df,
                start_time=start_time,
                volcano_name=volcano_name,
                metadata=metadata,
                remove_zero_height=remove_zero_height,
                csv_filename=csv_path.name
            )
            file_name = f"{volcano_name}_{start_time.strftime('%Y%m%d')}_{label}.txt"
            with open(volcano_dir / file_name, "w") as f:
                f.write("\n".join(lines))

   

    def _generate_config_file(self, height_func, df, start_time, volcano_name, metadata, remove_zero_height=False, csv_filename=None):
        lines = [
        f"simulationStartDatetime {start_time.strftime('%Y%m%d_%H%M')}",
        "simulationDurationInHour 24",
        f"volcanoName {volcano_name}_273070",
        f"volcanoX {metadata.get('Longitude', 'NA')}",
        f"volcanoY {metadata.get('Latitude', 'NA')}",
        f"summitHeightInMetre {metadata.get('Summit_Elevation(m)', 'NA')}",
        "simulationDomain_xMin 90.0",
        "simulationDomain_xMax 160.0",
        "simulationDomain_yMin -15.0",
        "simulationDomain_yMax 40.0",
        "outputGridSize_dX 0.25",
        "outputGridSize_dY 0.25"
    ]

        current_time = start_time
        emission_counter = 1  # Start counting from 1 for non-zero height plumes

        for idx, row in df.iterrows():
            height = int(height_func(row))

            if remove_zero_height and height == 0:
                self.skipped_logs.append({
                    "Volcano": volcano_name,
                    "Date": start_time.strftime("%Y-%m-%d"),
                    "Row_Index": idx,
                    "Reason": "Plume height is 0",
                    "Source_CSV": csv_filename,
                    "Skipped_Row": row.to_dict()
                })
                continue

            duration_hr = int(row.get("duration_hr", 1 if idx < len(df) - 1 else 0))
            duration_min = int(row.get("duration_min", 0))

            time_str = current_time.strftime("%Y_%m_%d_%H_%M")
            emission = f"emissionSourceParameterSet_{emission_counter} {height:04d}_{duration_hr:02d}_{duration_min:02d}_{time_str}"
            lines.append(emission)

            emission_counter += 1
            current_time += timedelta(hours=1)

        return lines

    def export_skipped_logs(self):
        if not self.skipped_logs:
            print("No lines were skipped.")
            return

        df_log = pd.DataFrame(self.skipped_logs)
        df_log["Skipped_Row"] = df_log["Skipped_Row"].apply(lambda d: str(d))
        log_path = self.sim_output_dir / "skipped_lines_log.csv"
        df_log.to_csv(log_path, index=False)
        print(f"Skipped lines log exported to: {log_path}")

   
#     def ensure_metadata_in_csvs_with_defaults(self, custom_metadata=None, fallback_to_input=False):
#         required_keys = ["Volcano_Name", "Latitude", "Longitude", "Summit_Elevation(m)", "start_date"]
#     default_metadata = {
#         "Volcano_Name": "Unknown Volcano",
#         "Latitude": "0.0",
#         "Longitude": "0.0",
#         "Summit_Elevation(m)": "0",
#         "start_date": "1 January 2000"
#     }
#     metadata_source = {**default_metadata, **(custom_metadata or {})}

#     for csv_path in self.output_csv_dir.rglob("*.csv"):
#         with open(csv_path, "r") as f:
#             lines = f.readlines()

#         metadata = {}
#         data_start_index = None
#         for i, line in enumerate(lines):
#             if line.strip().lower() == "metadata":
#                 continue
#             if line.strip() == "":
#                 continue
#             if "Time in hour" in line:
#                 data_start_index = i
#                 break
#             if "," in line:
#                 k, *v = [part.strip() for part in line.strip().split(",")]
#                 metadata[k] = ",".join(v)

#         updated = False
#         for key in required_keys:
#             if key not in metadata or not metadata[key].strip():
#                 default_val = metadata_source.get(key, "")
#                 if fallback_to_input:
#                     user_val = input(f"{csv_path.name} is missing '{key}'. Enter value [{default_val}]: ").strip()
#                     metadata[key] = user_val if user_val else default_val
#                 else:
#                     metadata[key] = default_val
#                 updated = True

#         if updated:
#             print(f"Updating metadata in {csv_path.name}...")
#             new_lines = ["Metadata\n\n"]
#             for k, v in metadata.items():
#                 new_lines.append(f"{k},{v}\n")
#             new_lines.append("\n")
#             new_lines.extend(lines[data_start_index:])
#             with open(csv_path, "w") as f:
#                 f.writelines(new_lines)

    
    
#    def generate_sim_files_from_user_csv(self, csv_input, volcano_name, latitude, longitude, summit_elevation):
#         # Accept CSV file path or DataFrame directly
#         if isinstance(csv_input, (str, Path)):
#             df = pd.read_csv(csv_input)
#         elif isinstance(csv_input, pd.DataFrame):
#             df = csv_input.copy()
#         else:
#             raise ValueError("csv_input must be a file path or a pandas DataFrame")

#         # Parse datetime column
#         if "Datetime" not in df.columns:
#             raise ValueError("Input data must contain a 'Datetime' column.")
#         df["Datetime"] = pd.to_datetime(df["Datetime"])

#         # Set output directory
#         volcano_dir = self.sim_output_dir / volcano_name
#         volcano_dir.mkdir(parents=True, exist_ok=True)

#         metadata = {
#             "Volcano_Name": volcano_name,
#             "Latitude": str(latitude),
#             "Longitude": str(longitude),
#             "Summit_Elevation(m)": str(summit_elevation)
#         }

#         percentile_columns = {
#             "5th": "Percentile_5",
#             "50th": "Percentile_50",
#             "95th": "Percentile_95"
#         }

#         for label, column in percentile_columns.items():
#             lines = [
#                 f"simulationStartDatetime {df['Datetime'].iloc[0].strftime('%Y%m%d_%H%M')}",
#                 "simulationDurationInHour 24",
#                 f"volcanoName {volcano_name}_273070",
#                 f"volcanoX {metadata['Longitude']}",
#                 f"volcanoY {metadata['Latitude']}",
#                 f"summitHeightInMetre {metadata['Summit_Elevation(m)']}",
#                 "simulationDomain_xMin 90.0",
#                 "simulationDomain_xMax 160.0",
#                 "simulationDomain_yMin -15.0",
#                 "simulationDomain_yMax 40.0",
#                 "outputGridSize_dX 0.25",
#                 "outputGridSize_dY 0.25"
#             ]

#             for idx, row in df.iterrows():
#                 try:
#                     height = max(0, int(float(row[column]) * 1000))
#                 except (KeyError, ValueError):
#                     print(f"Warning: Missing or invalid {column} at row {idx}, skipping.")
#                     continue

#                 duration_hr = int(row.get("duration_hr", 1))
#                 duration_min = int(row.get("duration_min", 0))
#                 time_str = row["Datetime"].strftime("%Y_%m_%d_%H_%M")

#                 emission = f"emissionSourceParameterSet_{idx+1} {height:04d}_{duration_hr:02d}_{duration_min:02d}_{time_str}"
#                 lines.append(emission)

#             output_file = volcano_dir / f"{volcano_name}_{df['Datetime'].iloc[0].strftime('%Y%m%d')}_{label}.txt"
#             with open(output_file, "w") as f:
#                 f.write("\n".join(lines))

#         print(f"Simulation files for {volcano_name} created in: {volcano_dir}")
