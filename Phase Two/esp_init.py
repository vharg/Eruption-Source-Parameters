import os
import pandas as pd

def ESP_INIT(vei_levels=None, PlumeHeight=None, show_plots=False, base_directory="Volcano_Test"):
    """
    Initialize and compute Eruption Source Parameters (ESP) based on provided VEI levels or Plume Height.
    
    This function processes various volcanic datasets and applies Bayesian statistical models to estimate
    eruption-related parameters such as total erupted mass (TEM), mass eruption rate (MER), plume height,
    and fine ash particle size. The results are saved in a specified directory based on input parameters.
    
    Parameters:
    -----------
    vei_levels : list, optional
        A list of Volcanic Explosivity Index (VEI) levels to consider. If None, defaults to [2, 3, 4, 5, 6, 7, 8].
    
    PlumeHeight : float, optional
        The plume height (in km) used as an input parameter for forecasting MER and other eruption parameters.
        If None, the function uses VEI levels to estimate ESP.
    
    show_plots : bool, optional
        If True, generates and displays various plots to visualize the probabilistic distributions and model outputs.
        Default is False.
    
    Returns:
    --------
    None
        Saves output CSV files with computed ESP parameters in a directory named based on the input parameters.
    
    Output Files:
    -------------
    - "VEI_data.csv" : Contains VEI-based probabilistic volume and mass estimates.
    - "MER_results.csv" : Contains estimated Mass Eruption Rate (MER) values.
    - "Plume_Height_results.csv" : Contains estimated plume heights.
    - "Particle_Size_results.csv" : Contains estimated fine ash particle sizes.
    - "TEM_results.csv" (if PlumeHeight is provided): Contains estimated Total Erupted Mass values.
    - "Duration_results.csv" (if PlumeHeight is provided): Contains estimated eruption duration.
    
    Process Flow:
    -------------
    1. Loads datasets from VEI-related studies (Mastin, Aubrey, IVESPA, Sparks, etc.).
    2. If PlumeHeight is provided:
       - Forecasts MER from observed PlumeHeight using Bayesian regression.
       - Forecasts TEM from MER.
       - Forecasts eruption duration from MER.
       - Forecasts fine ash particle size from MER.
    3. If PlumeHeight is not provided:
       - Computes probabilistic volume and mass distributions using VEI levels.
       - Forecasts MER from TEM using Bayesian regression.
       - Calculates Eruption Duration from MER and TEM
       - Forecasts plume height from MER.
       - Forecasts fine ash particle size from MER.
    4. Saves the computed results in structured CSV files for further analysis.
    
    Dependencies:
    -------------
    - `vei` module for dataset loading and correlation analysis.
    - `predictor_generic.BAYESIAN_PREDICTOR` for Bayesian inference and forecasting.
    - `os`, `pandas` for data handling and file operations.
    - `rich.console` and `rich.table` for formatted output display.
    
    Example Usage:
    --------------
    >>> ESP_INIT(vei_levels=[3, 4, 5], show_plots=True)
    >>> ESP_INIT(PlumeHeight=15.0)
    """
    import vei
    from vei import analyze_correlations
    from predictor_generic import BAYESIAN_PREDICTOR
    
    heights = None  # Initialize it at the top

    # Load data
    data_loader = vei.LOADDATA()
    Mastin = data_loader.load_Mastin(as_geodataframe=False)
    Aubrey = data_loader.load_Aubry(as_geodataframe=False)
    IVESPA = data_loader.load_IVESPA(as_geodataframe=False)
    Sparks = data_loader.load_Sparks(as_geodataframe=False)
    mastin_a = data_loader.load_Mastin_a(as_geodataframe=True)

    Combined_datasets = pd.concat([Aubrey, IVESPA, mastin_a], axis=0, join='inner')
    aubrey_datacombined = pd.concat([Aubrey, IVESPA], axis=0, join='inner')
    

    if vei_levels is not None:
        vei_range = vei_levels
        
    else:
        vei_range = [2, 3, 4, 5, 6, 7, 8]

    # Determine folder name based on PlumeHeight
    folder_name = f"ESP_for{PlumeHeight}km" if PlumeHeight is not None else f"ESP_init_forVEI_{vei_range}"
    # Create folder if it does not exist
    folder_name = os.path.join(base_directory, folder_name)
    
    os.makedirs(folder_name, exist_ok=True)
   
    if PlumeHeight is None:
        from vei import VEI_BulkVolume_Mass
        
        

        #percentiles = list(range(5, 96, 5))
        percentiles=[5,25, 50, 75,95]
        vei_model = VEI_BulkVolume_Mass(use_default_densities=False, num_samples=10000000, show_plots=show_plots, output_dir=folder_name)
        vei_model.generate_probabilistic_volumes(sampling_method='exponential', percentiles=percentiles)
        vei_model.calculate_mass(percentiles=percentiles)
        
        vei_model.plot_percentile_contours(data_type="volume", percentiles=percentiles)
        vei_model.plot_percentile_contours(data_type="mass", percentiles=percentiles)

        # 🔥 Plot percentile scatter plots
        vei_model.plot_posterior_samples_histograms_with_percentiles(data_type='volume')
        vei_model.plot_posterior_samples_histograms_with_percentiles(data_type='mass')

        

        filtered_data, filtered_volumes, filtered_masses = vei_model._filter_by_vei(
            vei_range=[2, 3, 4, 5, 6, 7, 8], update_in_place=True, percentiles=percentiles
        )

        data = vei_model.data
        data['VEI'] = pd.to_numeric(data['VEI'], errors='coerce')
        data = data[data['VEI'].isin(vei_range)].reset_index(drop=True)

        # Save VEI data
        data.to_csv(os.path.join(folder_name, "VEI_data.csv"), index=False)
###########################################################################################
        # Forecast MER from TEM
        tem_values = data['Mass_50th_kg'].to_list()
        model = BAYESIAN_PREDICTOR(IVESPA, percentiles=percentiles, calculate_duration=True, output_dir=folder_name, show_plots=show_plots)
        model.set_xvar('TEM_kg')
        model.set_yvar('MER_kg/s')
    
        model.plot_posterior_predictive()

        model.plot_percentiles(y_logscale=True, x_logscale=True)
        
        mer_results = model.predict_with_uncertainty(tem_values)
        mer_results["VEI"] = data['VEI']
        
        # Save MER results
        mer_results.to_csv(os.path.join(folder_name, "MER_results.csv"), index=False)
############################################################################
        # Forecast Plume Height from Mass Eruption Rate (MER)

    
        mer_list=mer_results['MER_kg/s_Percentile_50'].to_list()

    
        
        predictor=BAYESIAN_PREDICTOR(Mastin, percentiles=percentiles, calculate_duration=False, output_dir=folder_name, show_plots=show_plots)
        
        predictor.set_xvar('MER_kg/s')
        predictor.set_yvar('Height_km.a.v.l')
    
        predictor.plot_posterior_predictive()

        predictor.plot_percentiles(y_logscale=False, x_logscale=True)
        
        heights = predictor.predict_with_uncertainty(mer_list)
        
        heights['VEI']=mer_results['VEI']
        # List of columns to be assigned
        columns_to_assign = ['Duration_hr_P5', 'Duration_hr_P25', 'Duration_hr_P50', 'Duration_hr_P75', 'Duration_hr_P95'] #'Duration_hr_best_estimate_Uncertainty'

        # Assign values from mer_results to heights for these columns
        heights[columns_to_assign] = mer_results[columns_to_assign]
        
        
        ###################
        
        
        # Add a bold title using Styler
        styled_table = heights.style.set_caption("<b>VEI and Related Data</b>")

        styled_table

        from rich.console import Console
        from rich.table import Table

        # Ensure VEI is first
        if "VEI" not in heights.columns:
            raise KeyError("The 'VEI' column is missing from the DataFrame.")

        cols = ["VEI"] + [col for col in heights.columns if col != "VEI"]
        heights = heights[cols]

        # Rich Console for better formatting
        console = Console()

        # Function to print DataFrame in chunks of six columns, keeping VEI first
        def print_six_columns_with_vei_first(df):
            num_cols = len(df.columns)
            for i in range(1, num_cols, 3):  # 5 because VEI is fixed
                # Slice five columns at a time, after the first column
                cols = ["VEI"] + list(df.columns[i:i+3])
                
                # Create a table for this chunk
                table = Table(title="VEI and Related Data")
                for col in cols:
                    table.add_column(col, justify="center")
                
                # Add rows to the table
                for _, row in df[cols].iterrows():
                    table.add_row(*[str(cell) for cell in row])
                
                # Print the table
                console.print(table)

        # Display the DataFrame
        print_six_columns_with_vei_first(heights)
        # Save Plume Height results
        heights.to_csv(os.path.join(folder_name, "Plume_Height_results.csv"), index=False)
########################################################################################
        # Forecast Fine Ash particle size from MER
        psize_model = BAYESIAN_PREDICTOR(mastin_a, percentiles=percentiles, calculate_duration=False, output_dir=folder_name, show_plots=show_plots)
        psize_model.set_xvar('MER_kg/s')
        psize_model.set_yvar('MASS_FRACTION_ASH_BELOW_63_micron')
        
        psize_model.plot_posterior_predictive()
        
        psize_model.plot_percentiles(y_logscale=False, x_logscale=False)

        psize_predictions = psize_model.predict_with_uncertainty(mer_results['MER_kg/s_Percentile_95'].to_list())

        print (psize_predictions)
        # Save Particle Size predictions
        psize_predictions.to_csv(os.path.join(folder_name, "Particle_Size_results.csv"), index=False)
###############################################################################################
    else:
        #percentiles = list(range(5, 96, 5))
        percentiles=[5,25, 50, 75,95]
        # Forecast MER from Plume Height
        model_MER = BAYESIAN_PREDICTOR(IVESPA, percentiles=percentiles, calculate_duration=False, output_dir=folder_name, show_plots=show_plots)
        model_MER.set_xvar('Height_km.a.v.l')
        model_MER.set_yvar('MER_kg/s')
        
        model_MER.plot_posterior_predictive()
        model_MER.plot_percentiles(y_logscale=True, x_logscale=False)
        
        mer_results = model_MER.predict_with_uncertainty(PlumeHeight)

        # Save MER results
        mer_results.to_csv(os.path.join(folder_name, "MER_results.csv"), index=False)

        # Forecast TEM from MER
        model_TEM = BAYESIAN_PREDICTOR(IVESPA, percentiles=percentiles, calculate_duration=False, output_dir=folder_name, show_plots=show_plots)
        model_TEM.set_xvar('MER_kg/s')
        model_TEM.set_yvar('TEM_kg')
        
        model_TEM.plot_posterior_predictive()
        model_TEM.plot_percentiles(y_logscale=True, x_logscale=True)
        
        
        tem_results = model_TEM.predict_with_uncertainty(mer_results['MER_kg/s_Percentile_95'].to_list())

        # Save TEM results
        tem_results.to_csv(os.path.join(folder_name, "TEM_results.csv"), index=False)
#############################################################################################
        # Forecast Duration from MER
        model_DURATION = BAYESIAN_PREDICTOR(IVESPA, percentiles=percentiles, calculate_duration=False, output_dir=folder_name, show_plots=show_plots)
        model_DURATION.set_xvar('MER_kg/s')
        model_DURATION.set_yvar('Duration_hours')
        
        model_DURATION.plot_posterior_predictive()
        model_DURATION.plot_percentiles(y_logscale=True, x_logscale=True)
        
        Duration_results = model_DURATION.predict_with_uncertainty(mer_results['MER_kg/s_Percentile_95'].to_list())

        # Save Duration results
        Duration_results.to_csv(os.path.join(folder_name, "Duration_results.csv"), index=False)
########################################################
        # Forecast Fine Ash particle size from MER
        psize_model = BAYESIAN_PREDICTOR(mastin_a, percentiles=percentiles, calculate_duration=False, output_dir=folder_name, show_plots=show_plots)
        psize_model.set_xvar('MER_kg/s')
        psize_model.set_yvar('MASS_FRACTION_ASH_BELOW_63_micron')
        
        psize_model.plot_posterior_predictive()
        
        psize_model.plot_percentiles(y_logscale=False, x_logscale=False)

        psize_predictions = psize_model.predict_with_uncertainty(mer_results['MER_kg/s_Percentile_95'].to_list())

        
        # Save Particle Size predictions
        psize_predictions.to_csv(os.path.join(folder_name, "Particle_Size_results.csv"), index=False)
        
        # Define the directory containing the CSV files
        directory = folder_name

        # Automatically find all CSV files in the directory
        csv_files = [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith('.csv')]

        # Read and concatenate the CSV files
        dfs_auto = [pd.read_csv(fp) for fp in csv_files]
        concatenated_auto_df = pd.concat(dfs_auto, axis=1)

        # Remove duplicate columns by name
        concatenated_auto_df = concatenated_auto_df.loc[:, ~concatenated_auto_df.columns.duplicated()]
        
        heights=concatenated_auto_df
        
        heights.to_csv(os.path.join(folder_name, "all_results_combined.csv"), index=False)

    print(f"Results saved in folder: {folder_name}")
    
    


################################################################################################################3
    
    
#     return heights

# esp_init.py
import os
import pandas as pd

class ESPInitializer:
    """
    A class to compute Eruption Source Parameters (ESP) from either Volcanic Explosivity Index (VEI)
    or plume height using probabilistic and Bayesian approaches.

    Parameters
    ----------
    vei_levels : list of int, optional
        List of VEI levels to include in analysis. Defaults to [2, 3, 4, 5, 6, 7, 8].
    plume_height : float, optional
        Plume height (in km above vent) if no VEI is provided.
    show_plots : bool, optional
        Whether to generate diagnostic plots.
    base_directory : str, optional
        Output base directory to store results.

    Attributes
    ----------
    mer_results : pd.DataFrame
        Forecasted Mass Eruption Rate.
    tem_results : pd.DataFrame
        Forecasted Total Erupted Mass.
    duration_results : pd.DataFrame
        Forecasted eruption duration.
    heights : pd.DataFrame
        Forecasted plume heights.
    psize_predictions : pd.DataFrame
        Forecasted fine ash particle size.

    Example
    -------
    >>> esp = ESPInitializer(plume_height=20)
    >>> esp.run_all_forecasts()
    >>> df = esp.get_results_dataframe()
    >>> print(df.head())
    
    Notes
    -----
    - If VEI-based forecast is used, a posterior VEI model DataFrame is stored as `self.vei_model_data`.

    Example
    -------
    >>> esp = ESPInitializer(vei_levels=[3, 4])
    >>> esp.run_all_forecasts()
    >>> vei_df = esp.get_vei_model_dataframe()

    """

    def __init__(self, vei_levels=None, plume_height=None, show_plots=False, base_directory="Volcano_Test"):
        self.vei_levels = vei_levels or [2, 3, 4, 5, 6, 7, 8]
        self.plume_height = plume_height
        self.show_plots = show_plots
        self.base_directory = base_directory
        self.folder_name = self._create_output_folder()
        self.default_percentiles = [5, 25, 50, 75, 95]

        self.tem_values = None
        self.vei_series = None
        self.mer_results = None
        self.tem_results = None
        self.duration_results = None
        self.psize_predictions = None
        self.heights = None
        self.vei_model_data = None  # Store VEI model output if generated


        import vei
        self.vei = vei
        loader = vei.LOADDATA()
        self.Mastin = loader.load_Mastin(False)
        self.Aubrey = loader.load_Aubry(False)
        self.IVESPA = loader.load_IVESPA(False)
        self.Sparks = loader.load_Sparks(False)
        self.mastin_a = loader.load_Mastin_a(as_geodataframe=True)

    def _create_output_folder(self):
        name = f"ESP_for{self.plume_height}km" if self.plume_height else f"ESP_init_forVEI_{self.vei_levels}"
        folder = os.path.join(self.base_directory, name)
        os.makedirs(folder, exist_ok=True)
        return folder

    
    def run_vei_model(self, percentiles=None, show_plots=None):
        """
        Run the VEI-based probabilistic volume and mass forecast.

        Parameters
        ----------
        percentiles : list[int], optional
            List of percentiles to extract from posterior samples.
        show_plots : bool, optional
            Whether to display plots.

        Returns
        -------
        pd.DataFrame
            VEI model output with volume and mass forecast results.

        Example
        -------
        >>> esp = ESPInitializer(vei_levels=[3, 4])
        >>> vei_df = esp.run_vei_model()
        >>> print(vei_df.columns)
        """
        from vei import VEI_BulkVolume_Mass

        percentiles = percentiles or self.default_percentiles
        show_plots = self.show_plots if show_plots is None else show_plots

        vei_model = VEI_BulkVolume_Mass(
            use_default_densities=False,
            num_samples=10_000_000,
            show_plots=show_plots,
            output_dir=self.folder_name
        )
        vei_model.generate_probabilistic_volumes(sampling_method='exponential', percentiles=percentiles)
        vei_model.calculate_mass(percentiles=percentiles)
        vei_model.plot_percentile_contours("volume", percentiles)
        vei_model.plot_percentile_contours("mass", percentiles)
        vei_model.plot_posterior_samples_histograms_with_percentiles("volume")
        vei_model.plot_posterior_samples_histograms_with_percentiles("mass")

        data = vei_model.data
        data['VEI'] = pd.to_numeric(data['VEI'], errors='coerce')
        data = data[data['VEI'].isin(self.vei_levels)].reset_index(drop=True)
        data.to_csv(os.path.join(self.folder_name, "VEI_data.csv"), index=False)

        self.vei_model_data = data
        return data
    
    
    def run_all_forecasts(self, tem_values=None, vei_series=None, height=None, percentiles=None, show_plots=None):
        """
        Run the full forecasting pipeline using either VEI-based or plume-height-based approach.

        Parameters
        ----------
        tem_values : list[float], optional
            Total Erupted Mass values to initiate the forecast.
        vei_series : list[int], optional
            Corresponding VEI levels.
        height : float, optional
            Plume height to initialize if VEI is not provided.
        percentiles : list[int], optional
            Percentiles to extract from posterior distributions.
        show_plots : bool, optional
            Whether to display plots.

        Example
        -------
        >>> esp = ESPInitializer(vei_levels=[3, 4, 5])
        >>> esp.run_all_forecasts()
        """
        # from vei import VEI_BulkVolume_Mass

        # percentiles = percentiles or self.default_percentiles
        # show_plots = self.show_plots if show_plots is None else show_plots

        # if self.plume_height is None:
        #     vei_model = VEI_BulkVolume_Mass(
        #         use_default_densities=False, num_samples=10_000_000,
        #         show_plots=show_plots, output_dir=self.folder_name
        #     )
        #     vei_model.generate_probabilistic_volumes(sampling_method='exponential', percentiles=percentiles)
        #     vei_model.calculate_mass(percentiles=percentiles)
        #     vei_model.plot_percentile_contours("volume", percentiles)
        #     vei_model.plot_percentile_contours("mass", percentiles)
        #     vei_model.plot_posterior_samples_histograms_with_percentiles("volume")
        #     vei_model.plot_posterior_samples_histograms_with_percentiles("mass")

        #     # data = vei_model.data
        #     # data['VEI'] = pd.to_numeric(data['VEI'], errors='coerce')
        #     # data = data[data['VEI'].isin(self.vei_levels)].reset_index(drop=True)
        #     # data.to_csv(os.path.join(self.folder_name, "VEI_data.csv"), index=False)

        #     # tem_values = data['Mass_50th_kg'].tolist()
        #     # vei_series = data['VEI'].tolist()
            
        #     ##########
        #     data = vei_model.data
        #     data['VEI'] = pd.to_numeric(data['VEI'], errors='coerce')
        #     data = data[data['VEI'].isin(self.vei_levels)].reset_index(drop=True)
        #     data.to_csv(os.path.join(self.folder_name, "VEI_data.csv"), index=False)

        #     self.vei_model_data = data  # store for later access
        #     tem_values = data['Mass_50th_kg'].tolist()
        #     vei_series = data['VEI'].tolist()

        percentiles = percentiles or self.default_percentiles
        show_plots = self.show_plots if show_plots is None else show_plots

        if self.plume_height is None:
            data = self.run_vei_model(percentiles=percentiles, show_plots=show_plots)
            tem_values = data['Mass_50th_kg'].tolist()
            vei_series = data['VEI'].tolist()
 
            ##############

        self.tem_values = tem_values
        self.vei_series = vei_series

        if tem_values:
            self.forecast_mer_from_tem(tem_values, vei_series, percentiles, show_plots)
        elif height or self.plume_height:
            self.forecast_mer_from_height(height or self.plume_height, percentiles, show_plots)

        if self.mer_results is not None:
            self.forecast_tem_from_mer(percentiles=percentiles, show_plots=show_plots)
            self.forecast_duration_from_mer(percentiles=percentiles, show_plots=show_plots)
            self.forecast_particle_size_from_mer(percentiles=percentiles, show_plots=show_plots)
            self.forecast_height_from_mer(percentiles=percentiles, show_plots=show_plots)
            self.combine_results()

    def forecast_mer_from_tem(self, tem_values=None, vei_series=None, percentiles=None, show_plots=None):
        
        """
        Forecast Mass Eruption Rate (MER) from Total Erupted Mass (TEM).

        Parameters
        ----------
        tem_values : list[float], optional
            Total erupted mass values in kilograms.
        vei_series : list[int], optional
            Associated VEI values.
        percentiles : list[int], optional
            List of percentiles to use.
        show_plots : bool, optional
            Whether to generate diagnostic plots.

        Example
        -------
        >>> esp.forecast_mer_from_tem([1e10, 5e11], vei_series=[3, 4])
        """
        from predictor_generic import BAYESIAN_PREDICTOR
        percentiles = percentiles or self.default_percentiles
        show_plots = self.show_plots if show_plots is None else show_plots
        tem_values = tem_values or self.tem_values
        vei_series = vei_series or self.vei_series

        if isinstance(tem_values, pd.Series):
            tem_values = tem_values.tolist()
        if isinstance(vei_series, pd.Series):
            vei_series = vei_series.tolist()

        
        
        model = BAYESIAN_PREDICTOR(
            data=self.IVESPA,
            percentiles=percentiles,
            calculate_duration=True,
            output_dir=self.folder_name,
            show_plots=show_plots
        )
        
        model.set_xvar('TEM_kg')
        model.set_yvar('MER_kg/s')
        
        model.plot_posterior_predictive()
        model.plot_percentiles(True, True)

        self.mer_results = model.predict_with_uncertainty(tem_values)
        if vei_series:
            self.mer_results["VEI"] = vei_series
        self.mer_results.to_csv(os.path.join(self.folder_name, "MER_results.csv"), index=False)

    def forecast_mer_from_height(self, height=None, percentiles=None, show_plots=None):
        """
        Forecast MER from plume height using Bayesian modeling.

        Parameters
        ----------
        height : float or list[float], optional
            Plume height(s) in km above vent level.
        percentiles : list[int], optional
            Percentiles to extract from the forecast.
        show_plots : bool, optional
            Show plots if True.

        Example
        -------
        >>> esp = ESPInitializer(plume_height=20)
        >>> esp.forecast_mer_from_height()
        """
        from predictor_generic import BAYESIAN_PREDICTOR
        percentiles = percentiles or self.default_percentiles
        show_plots = self.show_plots if show_plots is None else show_plots
        height = height or self.plume_height

        model = BAYESIAN_PREDICTOR(
            data=self.IVESPA,
            percentiles=percentiles,
            calculate_duration=False,
            output_dir=self.folder_name,
            show_plots=show_plots
        )
        
        model.set_xvar('Height_km.a.v.l')
        model.set_yvar('MER_kg/s')
        model.plot_posterior_predictive()
        model.plot_percentiles(True, False)

        self.mer_results = model.predict_with_uncertainty(height)
        self.mer_results.to_csv(os.path.join(self.folder_name, "MER_results.csv"), index=False)

    def forecast_tem_from_mer(self, mer_values=None, percentiles=None, show_plots=None):
        """
        Forecast Total Erupted Mass (TEM) from Mass Eruption Rate (MER).

        Parameters
        ----------
        mer_values : list[float], optional
            Mass eruption rate values in kg/s.
        percentiles : list[int], optional
            List of percentiles.
        show_plots : bool, optional
            Whether to display plots.

        Example
        -------
        >>> esp.forecast_tem_from_mer([1e7, 2e8])
        """
        from predictor_generic import BAYESIAN_PREDICTOR
        percentiles = percentiles or self.default_percentiles
        show_plots = self.show_plots if show_plots is None else show_plots
        mer_values = mer_values or self.mer_results['MER_kg/s_Percentile_95'].tolist()

        model = BAYESIAN_PREDICTOR(
            data=self.IVESPA,
            
            percentiles=percentiles,
            calculate_duration=False,
            output_dir=self.folder_name,
            show_plots=show_plots
        )
        
        model.set_xvar('MER_kg/s')
        model.set_yvar('TEM_kg')
        
        model.plot_posterior_predictive()
        model.plot_percentiles(True, True)

        self.tem_results = model.predict_with_uncertainty(mer_values)
        self.tem_results.to_csv(os.path.join(self.folder_name, "TEM_results.csv"), index=False)

    def forecast_duration_from_mer(self, mer_values=None, percentiles=None, show_plots=None):
        """
        Forecast eruption duration in hours from MER.

        Parameters
        ----------
        mer_values : list[float], optional
            MER values in kg/s.
        percentiles : list[int], optional
            Percentiles to extract.
        show_plots : bool, optional
            Whether to plot the forecast.

        Example
        -------
        >>> esp.forecast_duration_from_mer()
        """
        from predictor_generic import BAYESIAN_PREDICTOR
        percentiles = percentiles or self.default_percentiles
        show_plots = self.show_plots if show_plots is None else show_plots
        mer_values = mer_values or self.mer_results['MER_kg/s_Percentile_95'].tolist()

        model = BAYESIAN_PREDICTOR(
            data=self.IVESPA,
            percentiles=percentiles,
            calculate_duration=False,
            output_dir=self.folder_name,
            show_plots=show_plots
        )
        
        model.set_xvar('MER_kg/s')
        model.set_yvar('Duration_hours')
        model.plot_posterior_predictive()
        model.plot_percentiles(True, True)

        self.duration_results = model.predict_with_uncertainty(mer_values)
        self.duration_results.to_csv(os.path.join(self.folder_name, "Duration_results.csv"), index=False)

    def forecast_height_from_mer(self, mer_df=None, percentiles=None, show_plots=None):
        """
        Forecast plume height from MER using Mastin et al. dataset.

        Parameters
        ----------
        mer_df : pd.DataFrame, optional
            DataFrame containing MER values. If None, uses internal forecast.
        percentiles : list[int], optional
            Percentiles to extract.
        show_plots : bool, optional
            Whether to generate visual output.

        Example
        -------
        >>> esp.forecast_height_from_mer()
        """
        from predictor_generic import BAYESIAN_PREDICTOR
        percentiles = percentiles or self.default_percentiles
        show_plots = self.show_plots if show_plots is None else show_plots
        mer_df = mer_df or self.mer_results

        model = BAYESIAN_PREDICTOR(
            data=self.Mastin,
            
            percentiles=percentiles,
            calculate_duration=False,
            output_dir=self.folder_name,
            show_plots=show_plots
        )
        
        model.set_xvar('MER_kg/s')
        model.set_yvar('Height_km.a.v.l')
        
        model.plot_posterior_predictive()
        model.plot_percentiles(False, True)

        self.heights = model.predict_with_uncertainty(mer_df['MER_kg/s_Percentile_50'].tolist())
        if 'VEI' in mer_df:
            self.heights['VEI'] = mer_df['VEI']
        dur_cols = [c for c in mer_df.columns if c.startswith("Duration_hr")]
        for col in dur_cols:
            self.heights[col] = mer_df[col]
        self.heights.to_csv(os.path.join(self.folder_name, "Plume_Height_results.csv"), index=False)

    def forecast_particle_size_from_mer(self, mer_values=None, percentiles=None, show_plots=None):
        """
        Forecast fine ash particle size (<63 micron) from MER.

        Parameters
        ----------
        mer_values : list[float], optional
            List of MER values in kg/s.
        percentiles : list[int], optional
            Percentiles to extract.
        show_plots : bool, optional
            Whether to show plots.

        Example
        -------
        >>> esp.forecast_particle_size_from_mer()
        """
        from predictor_generic import BAYESIAN_PREDICTOR
        percentiles = percentiles or self.default_percentiles
        show_plots = self.show_plots if show_plots is None else show_plots
        mer_values = mer_values or self.mer_results['MER_kg/s_Percentile_95'].tolist()

        model = BAYESIAN_PREDICTOR(
            data=self.mastin_a,
           
            percentiles=percentiles,
            calculate_duration=False,
            output_dir=self.folder_name,
            show_plots=show_plots
        )
        
        model.set_xvar('MER_kg/s')
        model.set_yvar('MASS_FRACTION_ASH_BELOW_63_micron')
        
        model.plot_posterior_predictive()
        model.plot_percentiles(False, False)

        self.psize_predictions = model.predict_with_uncertainty(mer_values)
        self.psize_predictions.to_csv(os.path.join(self.folder_name, "Particle_Size_results.csv"), index=False)

    def combine_results(self):
        csvs = [os.path.join(self.folder_name, f) for f in os.listdir(self.folder_name) if f.endswith(".csv")]
        dfs = [pd.read_csv(f) for f in csvs]
        combined = pd.concat(dfs, axis=1)
        combined = combined.loc[:, ~combined.columns.duplicated()]
        self.heights = combined
        combined.to_csv(os.path.join(self.folder_name, "all_results_combined.csv"), index=False)

    def get_results_dataframe(self, concatenate=True, remove_duplicates=True):
        """
        Retrieve all forecast results as a single DataFrame or a dictionary of DataFrames.

        Parameters
        ----------
        concatenate : bool
            If True, return combined DataFrame. Else, return a dict.
        remove_duplicates : bool
            Remove duplicate columns if combining.

        Returns
        -------
        pd.DataFrame or dict[str, pd.DataFrame]
            Forecast results.

        Example
        -------
        >>> results = esp.get_results_dataframe()
        >>> results.head()
        """
        dataframes = {
            "MER": self.mer_results,
            "TEM": self.tem_results,
            "Duration": self.duration_results,
            "PlumeHeight": self.heights,
            "ParticleSize": self.psize_predictions
        }
        dataframes = {k: v for k, v in dataframes.items() if v is not None}

        if not concatenate:
            return dataframes

        dfs = list(dataframes.values())
        if not dfs:
            return pd.DataFrame()

        combined = pd.concat(dfs, axis=1)
        if remove_duplicates:
            combined = combined.loc[:, ~combined.columns.duplicated()]

        return combined

    def get_vei_model_dataframe(self):
        """
        Return the VEI model data as a pandas DataFrame if available.

        Returns
        -------
        pd.DataFrame or None
            VEI model posterior samples and percentiles.

        Example
        -------
        >>> df = esp.get_vei_model_dataframe()
        >>> if df is not None:
        >>>     print(df.columns)
        """
        return self.vei_model_data
