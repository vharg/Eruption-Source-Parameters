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
    downloaded_VAA_report, latest_VAA_report , latest_date_data=scraper.download_vaa_text(output_dir="./TVAAC_test", filtered_results=search_results, csv=True, gdf=whelley_data, get_latest_date_data_option=True)

    # Parse VONA from MAGAMA VONA Center

    from vep_vaa_text import MAGMA_VONA_PARSER

    parser = MAGMA_VONA_PARSER("All Volcanoes", BASE_FOLDER='Magma_Test')

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
    table_tvaac = Table(title="VONA Message Attributes from TVAAC VONA Center", show_lines=True, title_style="bold blue")

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
            table_tvaac.add_row(f"Possible VEI Levels for Volcano {volcano_name} (Whelley et al. 2015)", str(vei_range))
        else:
            table_tvaac.add_row("Possible VEI Levels", "No data available")
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
                table_magma.add_row(f"Possible VEI Levels for Volcano {volcano_name_magma} (Whelley et al. 2015)", str(vei_range_Magma))
            else:
                table_magma.add_row("Possible VEI Levels", "No data available")
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

class PlumeHeightAnalyzer_FromInfrasound:
    def __init__(self, folder_path):
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
        self.folder_path = folder_path
        self.datasets = []
        self.valid_file_paths = []
        self.dataset_prefixes = set()
        self.mean_values = {}

        # Load datasets
        self.load_datasets()
        self.calculate_mean_values()

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

    def visualize_datasets(self):
        """
        Generates scatter plots and median trend lines for the datasets.
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
            vmin=min(np.min(np.median(data, axis=0)) for data in self.datasets),
            vmax=max(np.max(np.median(data, axis=0)) for data in self.datasets)
        )

        # Process each dataset separately
        for idx, dataset_prefix in enumerate(sorted(self.dataset_prefixes)):
            ax = fig.add_subplot(gs[idx]) if num_datasets > 1 else plt.gca()

            dataset_files = [file for file in self.valid_file_paths if os.path.basename(file).startswith(dataset_prefix)]
            dataset_data = [data for file, data in zip(self.valid_file_paths, self.datasets) if os.path.basename(file).startswith(dataset_prefix)]

            for file_path, data in zip(dataset_files, dataset_data):
                file_name = os.path.basename(file_path)
                
                linestyle = 'dashed' if 'di' in file_name.lower() else 'solid'

                # Compute medians
                medians = np.median(data, axis=0)

                # Normalize transparency
                median_min, median_max = np.min(medians), np.max(medians)
                normalized_alphas = (medians - median_min) / (median_max - median_min + 1e-6) * 0.7 + 0.3

                # Plot scatter points with color based on colormap
                scatter_colors = cmap(norm(data.flatten()))
                ax.scatter(
                    np.tile(np.arange(data.shape[1]), data.shape[0]),
                    data.flatten(),
                    color=scatter_colors,
                    s=2,
                    alpha=0.4
                )

                # Plot median line with color mapping
                for i in range(len(medians) - 1):
                    color = cmap(norm(medians[i]))
                    ax.plot([i, i + 1], [medians[i], medians[i + 1]], color=color, alpha=normalized_alphas[i], linestyle=linestyle, linewidth=2)

            ax.set_xlabel("Column Index", fontsize=12)
            ax.set_ylabel("Plume Heights", fontsize=12)
            ax.set_title(f"Scatter Plot for {dataset_prefix} Data 1000 run on 1-15% mass load", fontsize=14)
            ax.grid(True, linestyle='--', alpha=0.6)

            # Add legend for DI and Mono
            ax.plot([], [], color='black', linestyle='dashed', label="DI")
            ax.plot([], [], color='black', linestyle='solid', label="Mono")
            ax.legend(loc="upper right", fontsize=10, frameon=True)

        # Add colorbar
        cbar_ax = fig.add_axes([0.92, 0.15, 0.02, 0.7])
        cbar = plt.colorbar(cm.ScalarMappable(norm=norm, cmap=cmap), cax=cbar_ax)
        cbar.set_label("Median Value", fontsize=12)

        # Show plot
        plt.show()



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
