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


