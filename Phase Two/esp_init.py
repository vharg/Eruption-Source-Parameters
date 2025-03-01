import os
import pandas as pd

def ESP_INIT(vei_levels=None, PlumeHeight=None, show_plots=False):
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
    os.makedirs(folder_name, exist_ok=True)
   
    if PlumeHeight is None:
        from vei import VEI_BulkVolume_Mass
        
        

        percentiles = list(range(5, 96, 5))
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
        percentiles = list(range(5, 96, 5))
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

    print(f"Results saved in folder: {folder_name}")
