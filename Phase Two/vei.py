import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.interpolate import griddata
from matplotlib.colors import LogNorm
from scipy.stats import lognorm, uniform, norm, gamma, expon, ks_2samp, gaussian_kde
from matplotlib.ticker import ScalarFormatter, LogLocator


class VEI_BulkVolume_Mass:
    """
        **VEI_BulkVolume_Mass: A Model for Volcanic Bulk Volume and Mass Estimation**
        
        This class models volcanic bulk volume and mass across different VEI (Volcanic Explosivity Index) levels.
        It uses empirical and probabilistic approaches, Bayesian updating for densities, and offers visualization and data export tools.

        **Key Features:**
            - Generates **probabilistic volume estimates** for different VEI levels.
            - Computes **mass distributions** using density-based Bayesian updating.
            - Supports **Monte Carlo simulations** for uncertainty quantification.
            - Provides **visualizations** (histograms, heatmaps, percentile bands).
            - Enables **data export** in CSV and PDF formats.

        **Attributes:**
            - `data` (pd.DataFrame): Contains VEI levels, bulk volumes, and masses.
            - `probabilistic_volumes_posterior_samples` (dict): Stores Monte Carlo volume samples per VEI.
            - `mass_distributions` (dict): Stores computed mass distributions per VEI.
            - `vei_levels` (list): List of active VEI levels (default: [0-8]).
            - `bulk_volume_ranges` (list of tuples): Min/max volume ranges for each VEI.
            - `density_min` (float): Minimum density value (default: 800 kg/m³).
            - `density_max` (float): Maximum density value (default: 1200 kg/m³).

        **Parameters:**
            - `use_default_densities` (bool, optional): Use predefined bulk density values (default: `True`).
            - `density_min` (int, optional): User-defined minimum density value (default: `800`).
            - `density_max` (int, optional): User-defined maximum density value (default: `1200`).
            - `num_samples` (int, optional): Number of Monte Carlo samples for volume estimation (default: `100000`).

        **Example Usage:**
            ```python
            vei = VEI_BulkVolume_Mass()
            vei.generate_probabilistic_volumes()
            vei.calculate_mass()
            vei.plot_percentiles_heatmap()
            vei.export_volumes_and_masses()
        ```
    """

    
    DEFAULT_BULK_DENSITY_VALUES = [
        1040, 1040, 1400, 1400, 1000, 1000, 1000, 1000, 1750, 1750, 900, 900,
        1000, 900, 1200, 1200, 1200, 1200, 1000, 997, 997, 1250, 1600, 560,
        600, 600, 1339, 1343, 1572, 1579, 1300, 1300, 1300, 1000, 1000, 1067,
        1067, 1067, 1067, 1000, 1070, 1000, 1000, 1000, 1000, 1000, 1000, 1400,
        1400, 1400, 1226, 1350, 1140, 1190, 1190, 1000, 666, 666, 1000, 700,
        1000, 1000, 450, 450, 1030, 1250, 450, 1000, 1000, 1000, 1000, 1400,
        1000, 1000, 1000, 1400, 1400, 1100, 1000, 900, 950, 1600, 1600, 1250,
        1000, 1100, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000
    ]
    
    def __init__(self, use_default_densities=True, density_min=800, density_max=1200,
                 num_samples=10000, show_plots=False, output_dir=None):
        
        """
            Initializes the VEI_BulkVolume_Mass model.

        **Parameters:**
        
            - `use_default_densities` (bool, optional): Use predefined density values if `True`, otherwise use custom values.
            - `density_min` (float, optional): Minimum density value in kg/m³.
            - `density_max` (float, optional): Maximum density value in kg/m³.
            - `num_samples` (int, optional): Number of Monte Carlo samples for volume estimation.
        """
        
        self.num_samples = num_samples
        self.use_default_densities = use_default_densities
        
        self.show_plots=show_plots
        
        self.output_dir=output_dir
        
        if self.output_dir is not None:
            self.output_folder=self.output_dir
        else:
            self.output_folder="VEI_to_TEM"
        
        
        
        os.makedirs(self.output_folder, exist_ok=True)
        
        # Set density values
        if use_default_densities:
            self._estimate_density_bounds()
        else:
            self.density_min = density_min
            self.density_max = density_max
        
        # self.density_min = density_min
        # self.density_max = density_max

        # 🔥 Define VEI Levels First!
        self.vei_levels = list(range(9))  # VEI levels from 0 to 8

        # 🔥 Convert BULK_VOLUME_RANGES into a List of Tuples
        self.bulk_volume_ranges = [
            (0, 1e-05),
            (1e-05, 0.001),
            (0.001, 0.01),
            (0.01, 0.1),
            (0.1, 1),
            (1, 10),
            (10, 100),
            (100, 1000),
            (1000, 10000)
        ]

        # 🔥 Ensure BULK_VOLUME_RANGES is assigned as an instance attribute
        self.data = pd.DataFrame({'VEI': self.vei_levels})
        self.probabilistic_volumes_posterior_samples = {}
        self.mass_distributions = {}

    def _save_plot(self, plt_obj, filename: str):
        """
        Save a plot to the output folder.
        """
        filepath = os.path.join(self.output_folder, filename)
        plt_obj.savefig(filepath, dpi=300, bbox_inches='tight')
        print(f"Saved plot to {filepath}")
        plt.close()
        
    def _save_dataframe(self, df: pd.DataFrame, filename: str):
        """
        Save a DataFrame to a CSV file in the output folder.
        """
        filepath = os.path.join(self.output_folder, filename)
        df.to_csv(filepath, index=False)
        print(f"Saved DataFrame to {filepath}")

    
    def generate_probabilistic_volumes(self, sampling_method='exponential', percentiles=[5, 10, 25, 50, 75, 90, 95]):
        """
            Generates **probabilistic bulk volume estimates** for different VEI levels using Monte Carlo simulations.
            Bayesian updating is applied to constrain volume estimates.

            **Parameters:**
                - `sampling_method` (str, optional): Defines the probability distribution used for volume sampling.
                    - `'uniform'`: Uniform distribution between min/max volume range.
                    - `'normal'`: Normal distribution with Bayesian adjustment.
                    - `'exponential'`: Exponential distribution (default).
                - `percentiles` (list, optional): List of percentiles to compute for each VEI level (default: `[5, 10, 25, 50, 75, 90, 95]`).

            **Raises:**
                - `RuntimeError`: If **all VEI levels** are filtered out, preventing valid volume generation.

            **Example Usage:**
                ```python
                vei.generate_probabilistic_volumes(sampling_method='normal')
            ```
        """
        
        print("Generating probabilistic volumes using Bayesian updating...")

        # 🔥 VEI "Best Estimate Volume" values from prior knowledge
        VEI_PRIOR_VOLUMES = {
            0: 0.0005,
            1: 0.005,
            2: 0.1,
            3: 3,
            4: 30,
            5: 100,
            6: 500,
            7: 1000,
            8: 2500
        }

        # 🔥 Ensure we are using only the filtered VEI levels
        if not self.vei_levels:
            raise RuntimeError("No VEI levels available for sampling. Did you filter all VEI levels?")

        samples_per_vei = self.num_samples // len(self.vei_levels)
        probabilistic_volumes = {}
        
        def truncated_normal_exponential_bias(min_vol, max_vol, prior_mean, samples_per_vei, weight_prior=5, weight_mean=1):
            """
            Generates samples from a truncated normal distribution while making it behave like an exponential distribution.
            - Strong bias toward small values.
            - Uses Bayesian updating to refine mean volume estimate with higher weight on prior knowledge.
            """
            from scipy.stats import truncnorm

            mean_vol = (min_vol + max_vol) / 2  # Midpoint of range

            # Bayesian updating with a strong weight on smaller values (prior_mean)
            updated_mean = (weight_prior * prior_mean + weight_mean * mean_vol) / (weight_prior + weight_mean)

            # Reduce standard deviation to cluster more samples near the lower range
            std_dev_vol = (max_vol - min_vol) / 3  # Make it tighter than usual

            # Define truncated normal bounds in standard normal units
            a, b = (min_vol - updated_mean) / std_dev_vol, (max_vol - updated_mean) / std_dev_vol

            # Sample from truncated normal distribution
            samples = truncnorm.rvs(a, b, loc=updated_mean, scale=std_dev_vol, size=samples_per_vei)

            return samples

        # Generate probabilistic volumes only for selected VEI levels
        for vei, (min_vol, max_vol) in zip(self.vei_levels, self.bulk_volume_ranges):
            if vei not in self.vei_levels:  # 🚨 Ensure we skip filtered VEI levels
                continue

            prior_mean = VEI_PRIOR_VOLUMES[vei]  # Use given prior estimates
            valid_samples = []

            while len(valid_samples) < samples_per_vei:
                if sampling_method == 'uniform':
                    new_samples = np.random.uniform(min_vol, max_vol, samples_per_vei)
                elif sampling_method == 'normal':
                    #🔥Bayesian Updating: Adjust mean towards prior knowledge
                    mean_vol = (min_vol + max_vol) / 2
                    updated_mean = (prior_mean + mean_vol) / 2  # Weighted mean with prior
                    std_dev_vol = (max_vol - min_vol) / 3
                    new_samples = np.random.normal(updated_mean, std_dev_vol, samples_per_vei)
                    #new_samples=truncated_normal_exponential_bias(min_vol, max_vol, prior_mean, samples_per_vei)
                     
                    
                    
                elif sampling_method == 'exponential':
                    scale = (max_vol - min_vol) / 2
                    new_samples = np.random.exponential(scale, samples_per_vei) + min_vol
                else:
                    raise ValueError("Invalid sampling method.")

                # 🔥 Keep only valid samples within bounds
                valid_samples.extend([v for v in new_samples if min_vol <= v <= max_vol])

            # Select only the required number of samples
            valid_samples = np.array(valid_samples[:samples_per_vei])
            probabilistic_volumes[vei] = valid_samples * 1e9  # Convert to cubic meters

        # Store posterior samples
        self.probabilistic_volumes_posterior_samples = probabilistic_volumes

        # 🔥 Compute mean bulk volume for each VEI
        self.data['Probabilistic_Bulk_Volume_m3'] = [
            np.mean(probabilistic_volumes[vei]) if vei in probabilistic_volumes else np.nan
            for vei in self.vei_levels
        ]

        # 🔥 Compute percentiles for each VEI while keeping values within bounds
        for p in percentiles:
            self.data[f'Probabilistic_Bulk_Volume_{p}th_m3'] = [
                max(min_vol * 1e9, min(np.percentile(probabilistic_volumes[vei], p), max_vol * 1e9)) 
                if vei in probabilistic_volumes else np.nan
                for vei, (min_vol, max_vol) in zip(self.vei_levels, self.bulk_volume_ranges)
            ]

        # Compute uncertainty based on 95th and 5th percentile differences
        self.data['Uncertainty_Prob_Volume_m3'] = (
            self.data['Probabilistic_Bulk_Volume_95th_m3'] - self.data['Probabilistic_Bulk_Volume_5th_m3']
        )

        print("✅ Probabilistic volumes successfully generated within valid VEI bounds!")
        
        

    #####################
    
    def _estimate_density_bounds(self):
        """Estimate density bounds using Bayesian probability updating on DEFAULT_BULK_DENSITY_VALUES."""
        sample_mean = np.mean(self.DEFAULT_BULK_DENSITY_VALUES)
        sample_std = np.std(self.DEFAULT_BULK_DENSITY_VALUES)

        # Bayesian updating: Assume weak prior centered at 1000 with high variance
        prior_mean = 1000
        prior_std = 300

        posterior_variance = 1 / ((1 / prior_std**2) + (len(self.DEFAULT_BULK_DENSITY_VALUES) / sample_std**2))
        posterior_mean = posterior_variance * ((prior_mean / prior_std**2) + (len(self.DEFAULT_BULK_DENSITY_VALUES) * sample_mean / sample_std**2))

        # Set density bounds as +/- 2 standard deviations from posterior mean
        self.density_min = max(0, posterior_mean - 2 * np.sqrt(posterior_variance))
        self.density_max = posterior_mean + 2 * np.sqrt(posterior_variance)
        print(f"Density bounds estimated using Bayesian updating:\nDensity Min: {self.density_min:.2f}, Density Max: {self.density_max:.2f}")

    
   

        
    def _best_density_strategy(self):
        """Determine the best strategy for sampling densities using log-normal, uniform, or normal."""
        densities = np.array(self.DEFAULT_BULK_DENSITY_VALUES)

        # Logarithmic scaling of densities
        log_densities = np.log10(densities)
        min_log = np.min(log_densities)
        log_shift = 1 - min_log if min_log < 1 else 0  # Ensure positivity
        shifted_log_densities = log_densities + log_shift

        # Adjusted distributions with logarithmic trend
        def log_normal_shifted(size):
            samples = lognorm.rvs(s=0.5, scale=10**np.mean(shifted_log_densities), size=size)
            return np.clip(samples, 0.1 * 10**np.mean(shifted_log_densities), 10 * 10**np.mean(shifted_log_densities))

        strategies = {
            'log-normal': lambda size: np.clip(lognorm.rvs(s=0.5, scale=np.mean(densities), size=size), 0.1, None),
            'uniform': lambda size: np.clip(uniform.rvs(np.min(densities), np.ptp(densities), size=size), 0.1, None),
            'normal': lambda size: np.clip(norm.rvs(np.mean(densities), np.std(densities), size=size), 0.1, None),
            'log-normal-adjusted': log_normal_shifted
        }

        best_strategy = None
        min_variance = float('inf')

        for name, strategy in strategies.items():
            samples = strategy(self.num_samples)
            variance = np.var(samples)
            if variance < min_variance:
                min_variance = variance
                best_strategy = name
        
        print(f"Best density sampling strategy: {best_strategy}")
        return strategies[best_strategy]
    
    
    
    #############
        

    def calculate_mass(self, percentiles=[5, 10, 25, 50, 75, 90, 95]):
        """
        Calculate mass for different percentiles using density distributions.
        """
        print("Calculating mass...")

        # Sample densities using a uniform distribution
        sampled_densities = np.random.uniform(self.density_min, self.density_max, self.num_samples)

        # Calculate mean mass based on bulk volume and mean density
        self.data['Mean_Mass_kg'] = self.data['Probabilistic_Bulk_Volume_m3'] * np.mean(sampled_densities)
        
        mass_distributions = {}

        # Compute mass distributions for each VEI
        for vei in self.vei_levels:
            mass_distributions[vei] = self.probabilistic_volumes_posterior_samples[vei] * np.mean(sampled_densities)

       
        
        self.mass_distributions = mass_distributions

        # Compute percentiles for mass distributions
        for p in percentiles:
            self.data[f'Mass_{p}th_kg'] = [
                np.percentile(mass_distributions[vei], p) for vei in self.vei_levels
            ]

        # Compute uncertainty in mass estimation
        self.data['Uncertainty_Mass_kg'] = (
            self.data['Mass_95th_kg'] - self.data['Mass_5th_kg']
        )

        print("✅ Mass calculation completed!")
        
        

    def plot_histogram_sample_frequency_per_vei(self, probabilistic_data, title="Distribution"):
        """
        Plot histogram functions for sampled volumes/masses separately for each VEI.
        """
        if not isinstance(probabilistic_data, dict) or not all(isinstance(v, np.ndarray) for v in probabilistic_data.values()):
            raise TypeError("Expected a dictionary {VEI: numpy array of samples}, but received a different format.")

        num_veis = len(probabilistic_data)
        fig, axes = plt.subplots(1, num_veis, figsize=(4 * num_veis, 6), sharey=True)

        palette = sns.color_palette("tab10", n_colors=num_veis)

        for i, (vei, samples) in enumerate(probabilistic_data.items()):
            samples = samples[samples > 0]  

            if len(samples) > 1 and np.var(samples) > 0:
                ax = axes[i] if num_veis > 1 else axes

                sns.histplot(
                    samples,
                    ax=ax,
                    bins="auto",
                    kde=False,
                    stat="count",
                    alpha=0.6,
                    color=palette[i]
                )

                ax.set_xlabel(f"VEI {vei}", fontsize=12)
                if i == 0:
                    ax.set_ylabel("Sample Frequency", fontsize=12)
                ax.set_title(f"Histogram for VEI {vei}", fontsize=14, fontweight="bold")
                ax.grid(True, which="both", linestyle="--", linewidth=0.6, alpha=0.7)

        plt.suptitle(title, fontsize=16, fontweight="bold")
        plt.tight_layout()
        plt.show()

    
    def _filter_by_vei(self, vei_range=None, update_in_place=True, percentiles=[5, 10, 25, 50, 75, 90, 95]):
        """
        Filter the VEI levels, DataFrame, and future volume/mass distributions for specific VEI levels or ranges.
        Ensures that the bulk volume values do not exceed the defined volume ranges.

        Parameters:
        - vei_range (int, list, tuple, or None): Specifies the VEI levels to filter.
        - int: Filters for a single VEI level.
        - list: Filters for specific VEI levels.
        - tuple: Filters for a range of VEI levels.
        - None: No filtering applied.
        - update_in_place (bool): If True, updates the object's VEI levels, data, and distributions in place.

        Returns:
        - filtered_data (pd.DataFrame): Filtered summary DataFrame.
        - filtered_volumes (dict or None): Filtered volume distributions (if computed).
        - filtered_masses (dict or None): Filtered mass distributions (if computed).
        """

        if vei_range is None:
            return self.data, self.probabilistic_volumes_posterior_samples, self.mass_distributions

        # 🔥 Determine VEI filtering mask
        if isinstance(vei_range, int):
            filter_mask = {vei_range}
        elif isinstance(vei_range, (list, tuple)):
            if isinstance(vei_range, tuple):  # Range of VEI
                filter_mask = {vei for vei in self.vei_levels if vei_range[0] <= vei <= vei_range[1]}
            else:  # List of VEI values
                filter_mask = {vei for vei in self.vei_levels if vei in vei_range}
        else:
            raise ValueError("Invalid VEI range. Provide an int, list, tuple (range), or None.")

        # 🔥 Filter VEI levels
        filtered_vei_levels = sorted(filter_mask.intersection(set(self.vei_levels)))

        # 🔥 Handle case where no valid VEI levels remain
        if not filtered_vei_levels:
            raise RuntimeError("No valid VEI levels remain after filtering. Check `vei_range`.")

        # 🔥 Filter volume distributions if they exist
        filtered_volumes = None
        filtered_masses = None

        if self.probabilistic_volumes_posterior_samples:
            filtered_volumes = {
                vei: np.clip(self.probabilistic_volumes_posterior_samples[vei], 
                            self.bulk_volume_ranges[vei][0] * 1e9, 
                            self.bulk_volume_ranges[vei][1] * 1e9)
                for vei in filtered_vei_levels if vei in self.probabilistic_volumes_posterior_samples
            }

        if self.mass_distributions:
            filtered_masses = {
                vei: self.mass_distributions[vei]
                for vei in filtered_vei_levels if vei in self.mass_distributions
            }

        # 🔥 Filter the DataFrame and ensure values stay within their respective volume ranges
        filtered_data = self.data[self.data["VEI"].isin(filtered_vei_levels)].reset_index(drop=True)

        # 🔥 Check if volume columns exist before filtering
        existing_columns = set(self.data.columns)

        for p in percentiles:
            volume_col = f'Probabilistic_Bulk_Volume_{p}th_m3'
            if volume_col in existing_columns:  # 🔥 Only process if the column exists
                filtered_data[volume_col] = [
                    np.clip(self.data.loc[self.data['VEI'] == vei, volume_col].values[0], 
                            self.bulk_volume_ranges[vei][0] * 1e9, 
                            self.bulk_volume_ranges[vei][1] * 1e9)
                    if vei in self.data["VEI"].values else np.nan
                    for vei in filtered_vei_levels
                ]

        # 🔥 Update model in place if specified
        if update_in_place:
            self.vei_levels = filtered_vei_levels  # Update VEI levels before calculating volume/mass
            self.data = filtered_data
            self.probabilistic_volumes_posterior_samples = filtered_volumes if filtered_volumes else {}
            self.mass_distributions = filtered_masses if filtered_masses else {}
            print("✅ VEI model updated in place with filtered VEI levels, ensuring volumes remain within valid ranges.")

        return filtered_data, filtered_volumes, filtered_masses


    
    def summary(self):
        """Print summary of computed data."""
        print(self.data)

    
    def plot_percentile_contours(self, data_type="volume", percentiles=[5, 10, 25, 50, 75, 90, 95]):
        """
        Plot filled contour plots for percentile distributions of volume or mass.
        """
        
        
        print(f"Plotting {data_type} percentile contours...")

        # Select appropriate data
        if data_type == "volume":
            dataset = self.data
            value_prefix = "Probabilistic_Bulk_Volume"  # 🔥 Volume uses "m3" (not "m³")
            unit = "m3"
            title = "Volume Percentile Probability Bands"
        elif data_type == "mass":
            dataset = self.data
            value_prefix = "Mass"  # 🔥 Mass uses "kg"
            unit = "kg"
            title = "Mass Percentile Probability Bands"
        else:
            raise ValueError("Invalid data_type. Choose 'volume' or 'mass'.")

        # Prepare the original meshgrid and data
        vei_levels = dataset["VEI"].values

        # 🔥 Ensure we get the correct percentile values based on the type
        values = np.array([
            dataset[f"{value_prefix}_{p}th_{unit}"].values for p in percentiles
        ])

        X, Y = np.meshgrid(vei_levels, percentiles)
        Z = np.array(values)

        # Interpolate to a finer grid for smoother contours
        finer_vei = np.linspace(vei_levels.min(), vei_levels.max(), 100)  
        finer_percentiles = np.linspace(min(percentiles), max(percentiles), 100)
        X_fine, Y_fine = np.meshgrid(finer_vei, finer_percentiles)
        Z_fine = griddata((X.flatten(), Y.flatten()), Z.flatten(), (X_fine, Y_fine), method='cubic')

        # Fill gaps by replacing NaN values with nearest neighbors
        Z_fine = np.nan_to_num(Z_fine, nan=np.nanmin(Z))

        # Generate filled contour plot with log scale
        fig = plt.figure(figsize=(12, 8))
        filled_contour = plt.contourf(
            X, Y, Z, levels=20, cmap="plasma", alpha=0.75, norm=LogNorm(vmin=Z.min(), vmax=Z.max())
        )
        cbar = plt.colorbar(filled_contour, pad=0.02, aspect=30, shrink=0.8)
        cbar.set_label(f"{title} [{unit}, Log Scale]", fontsize=12)

        # Add labeled contour lines for clarity
        contour_lines = plt.contour(
            X, Y, Z, levels=10, colors='black', linewidths=0.8, linestyles='solid', norm=LogNorm(vmin=Z.min(), vmax=Z.max())
        )
        plt.clabel(contour_lines, inline=True, fontsize=10, fmt="%.1e", colors='white')

        # Add labels, grid, and custom aesthetics
        plt.title(f"{title} with Log-Scaled Contours", fontsize=14, weight='bold')
        plt.xlabel("VEI Level", fontsize=12)
        plt.ylabel("Percentile (%)", fontsize=12)
        plt.xticks(fontsize=10)
        plt.yticks(fontsize=10)
        plt.grid(True, linestyle='--', alpha=0.5)

        # Display the plot
        plt.tight_layout()
        
        
        
         # Save the plot
        self._save_plot(plt, f"plot_percentile_contours_VEI{data_type}.png")

        if self.show_plots==True:
            plt.show()
    
    def plot_posterior_samples_histograms_with_percentiles(self, data_type="volume"):
        """
        Plot histogram functions for sampled volumes or masses separately for each VEI.
        Uses histogram frequency counts to show the distribution of posterior samples.
        Overlays percentile bands (5th, 10th, 25th, 50th, 75th, 90th, 95th) with color-coded lines.
        Adds a single shared legend below all plots instead of individual legends.

        Parameters:
        - data_type (str): Choose either "volume" or "mass".
        """

        # 🔥 Ensure valid input type
        if data_type not in ["volume", "mass"]:
            raise ValueError("Invalid data_type. Choose 'volume' or 'mass'.")

        # **Select the right dataset**
        if data_type == "volume":
            probabilistic_data = self.probabilistic_volumes_posterior_samples
            title = "Volume Posterior Sample Frequency with Percentiles"
            xlabel = "Bulk Volume (m³, Log Scale)"
            percentiles_columns = {5: "red", 10: "orange", 25: "green", 50: "blue", 75: "purple", 90: "brown", 95: "black"}
        else:
            probabilistic_data = self.mass_distributions
            title = "Mass Posterior Sample Frequency with Percentiles"
            xlabel = "Mass (kg, Log Scale)"
            percentiles_columns = {5: "red", 10: "orange", 25: "green", 50: "blue", 75: "purple", 90: "brown", 95: "black"}

        # 🔥 Ensure data exists
        if not probabilistic_data:
            raise RuntimeError(f"No posterior samples found for {data_type}. Please run calculations first.")

        # 🔥 Extract VEI levels and define color palette
        vei_levels = self.vei_levels
        num_veis = len(vei_levels)
        palette = sns.color_palette("tab10", n_colors=num_veis)

        # 🎨 **Create a Horizontal Grid of Histograms**
        fig, axes = plt.subplots(1, num_veis, figsize=(4 * num_veis, 6), sharey=True)

        for i, vei in enumerate(vei_levels):
            samples = probabilistic_data.get(vei, np.array([]))
            samples = samples[samples > 0]  # 🔥 Remove zero values

            if len(samples) > 1 and np.var(samples) > 0:
                ax = axes[i] if num_veis > 1 else axes

                sns.histplot(
                    samples,
                    ax=ax,
                    bins="auto",
                    kde=False,
                    stat="count",
                    alpha=0.9,
                    color=palette[i]
                )
                
               
                # **Overlay Percentile Bands**
                for p, color in percentiles_columns.items():
                    col_name = f'Probabilistic_Bulk_Volume_{p}th_m3' if data_type == "volume" else f'Mass_{p}th_kg'
                    if col_name in self.data.columns:
                        percentile_value = self.data.loc[self.data["VEI"] == vei, col_name].values[0]
                        ax.axvline(percentile_value, linestyle="dashed", alpha=0.8, color=color, lw=1)

                ax.set_xscale("log")  # ✅ Set X-axis to log scale
                ax.set_xlabel(f"Volume (cubic meter)", fontsize=12)
                if i == 0:
                    ax.set_ylabel("Sample Frequency", fontsize=12)

                ax.set_title(f"Histogram for VEI {vei}", fontsize=14, fontweight="bold")
                ax.grid(True, which="both", linestyle="--", linewidth=0.6, alpha=0.7)

        plt.suptitle(title, fontsize=16, fontweight="bold")

        # 🔥 Add a single shared legend below the plots
        handles = [plt.Line2D([0], [0], color=color, linestyle="dashed", lw=2, label=f"{p}th Percentile") for p, color in percentiles_columns.items()]
        fig.legend(handles=handles, loc="lower center", ncol=7, fontsize=12, frameon=False, bbox_to_anchor=(0.5, -0.05))

        plt.tight_layout(rect=[0, 0, 1, 0.9])  # Adjust layout to fit the legend below
        
        
       
    
        # Save the plot
        self._save_plot(plt, f"plot_posterior_samples_histograms_VEI{data_type}.png")
        if self.show_plots==True:
            plt.show()

# Load Eruption source paramerter Datasets
import pandas as pd
import geopandas as gpd
import numpy as np
import os 
class LOADDATA:
    def __init__(self):
        
        # Get the script's directory
        script_dir = os.path.dirname(os.path.abspath(__file__))  
        data_dir = os.path.join(script_dir, "data")  # Ensure the data folder path is absolute

        def safe_read_csv(filename, encoding="ISO-8859-1"):
            """
            Safely reads a CSV file from the 'data' directory.
            - If the file exists, it is loaded into a DataFrame.
            - If the file is missing, a warning is printed, and None is returned.
            
            Parameters:
                filename (str): The name of the CSV file (e.g., "IVESPAData.csv")
            
            Returns:
                pd.DataFrame or None: Loaded DataFrame if the file exists, otherwise None.
            """
            file_path = os.path.join(data_dir, filename)  # Construct full file path
            
            if os.path.exists(file_path):
                try:
                    return pd.read_csv(file_path, encoding=encoding)  # Load CSV if it exists
                except UnicodeDecodeError:
                    print(f"Encoding error in {filename}. Trying 'ISO-8859-1'.")
                    try:
                        return pd.read_csv(file_path, encoding="ISO-8859-1")  # Try ISO encoding
                    except Exception as e:
                        print(f"Error reading {filename} with 'ISO-8859-1': {e}")
                        return None
                except Exception as e:
                    print(f"Error reading {filename}: {e}")
                    return None
            else:
                print(f"Warning: Missing file {filename} at {file_path}")
                return None  # Return None if file does not exist

        # Load all datasets safely
        self.datasets = {
            "IVESPA": safe_read_csv("IVESPAData.csv"),
            "Aubry": safe_read_csv("AubryData.csv"),
            "Mastin": safe_read_csv("MastinData.csv"),
            "Sparks": safe_read_csv("SparksData.csv"),
            "whelley_2015": safe_read_csv("Whelley_2015.csv"),
            'Mastin_a': safe_read_csv("volcanoExport.csv")
        }
        
        
        # self.datasets = {
        #     "IVESPA": pd.read_csv("./data/IVESPAData.csv"),
        #     "Aubry": pd.read_csv("./data/AubryData.csv"),
        #     "Mastin": pd.read_csv("./data/MastinData.csv"),
        #     "Sparks": pd.read_csv("./data/SparksData.csv"),
        #     "whelley_2015": pd.read_csv("./data/Whelley_2015.csv"),
        #     'Mastin_a': pd.read_csv("./data/volcanoExport.csv",  encoding='ISO-8859-1')
        # }

    def load_IVESPA(self, as_geodataframe: bool = False):
        df = self.datasets["IVESPA"]
        
        # Ensure numeric types for calculations
        df["TEM_kg"] = pd.to_numeric(df.get("TEM_kg", np.nan), errors="coerce")
        df["Duration_hours"] = pd.to_numeric(df.get("Duration_hours", np.nan), errors="coerce")
        df["Tephra Plume Top Best estimate (km a.s.l.)"] = pd.to_numeric(
            df.get("Tephra Plume Top Best estimate (km a.s.l.)", np.nan), errors="coerce"
        )
        df["Vent altitude (m a.s.l.)"] = pd.to_numeric(
            df.get("Vent altitude (m a.s.l.)", np.nan), errors="coerce"
        )

        # Calculate MER (kg/s) safely
        df["MER_kg/s"] = df["TEM_kg"] / (df["Duration_hours"].replace(0, np.nan) * 3600)

        # Calculate Plume height safely
        df["Height_km.a.v.l"] = (
            df["Tephra Plume Top Best estimate (km a.s.l.)"]
            - df["Vent altitude (m a.s.l.)"] / 1000.0
        )

        # Combine Volcano and Event Name
        df["Name"] = df["Volcano"].fillna("").combine(
            df["Event Name"].fillna(""), lambda a, b: a + " " + b
        )
        
        # Rename Columns to standard names
        df.rename(columns={
            'TEM Best estimate (kg)': 'TEM_kg', 
            'Duration Best estimate (hours)': 'Duration_hours'
        }, inplace=True)
        
       

        # Select and return required columns
        #df = df[['VEI', 'Height_km.a.v.l', 'TEM_kg', 'MER_kg/s', 'Duration_hours']]

        if as_geodataframe:
            df = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df['Longitude'], df['Latitude']))
            df.set_crs(epsg=4326, inplace=True)

        return df

    def load_Aubry(self, as_geodataframe: bool = False):
        df = self.datasets["Aubry"]

        

        df['MER (kg/s)'] = df['Erupted tephra mass (kg)'] / (df['Duration (hrs)'] * 3600.0)
        df['Name'] = df['Volcano'].combine(df['Eruption'], lambda a, b: a + " " + (str(b) or ""))
        
        
        
        # Rename Columns to standard names
        df.rename(columns={
            'Erupted tephra mass (kg)': 'TEM_kg',
            'Duration (hrs)': 'Duration_hours',
            'Plume height (km a.v.l.)': 'Height_km.a.v.l',
            "MER (kg/s)": "MER_kg/s"
        }, inplace=True)
        
        # if 'VEI' not in df.columns:
        #     df['VEI'] = None

        # Select and return required columns
        #df = df[['Height_km.a.v.l', 'TEM_kg', 'MER_kg/s', 'Duration_hours']]

        if as_geodataframe:
            df = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df['Longitude'], df['Latitude']))
            df.set_crs(epsg=4326, inplace=True)

        return df

    def load_Mastin(self, as_geodataframe: bool = False):
        df = self.datasets["Mastin"]

        # Compute TEM_kg using MER and Duration
        df['TEM_kg'] = df['MER (kg/s)'] / 3600 * df['Duration (hours)']

        # Rename Columns to standard names
        df.rename(columns={
            'Duration (hours)': 'Duration_hours',
            'Plume height (km a.v.l.)': 'Height_km.a.v.l',
            "MER (kg/s)": "MER_kg/s"
        }, inplace=True)

        # Select and return required columns
        #df = df[['VEI', 'Height_km.a.v.l', 'TEM_kg', 'MER_kg/s', 'Duration_hours']]

        if as_geodataframe:
            df = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df['Longitude'], df['Latitude']))
            df.set_crs(epsg=4326, inplace=True)

        return df
    
    def load_Mastin_a(self, as_geodataframe: bool = False):
        df = self.datasets["Mastin_a"]

        # Compute TEM_kg using MER and Duration
        df['TEM_kg'] = df['MER (kg/s)'] / 3600 * df['Duration (hours)']

        # Rename Columns to standard names
        df.rename(columns={
            'Duration (hours)': 'Duration_hours',
            'Plume height (km a.v.l.)': 'Height_km.a.v.l',
            "MER (kg/s)": "MER_kg/s"
        }, inplace=True)

        # Select and return required columns
        #df = df[['VEI', 'Height_km.a.v.l', 'TEM_kg', 'MER_kg/s', 'Duration_hours']]

        if as_geodataframe:
            df = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df['Longitude'], df['Latitude']))
            df.set_crs(epsg=4326, inplace=True)

        return df

    def load_Sparks(self, as_geodataframe: bool = False):
        df = self.datasets["Sparks"]

        # Compute TEM_kg using MER and Duration
        df['TEM_kg'] = df['MER (kg/s)'] / 3600 * df['Duration (hours)']

        # Rename Columns to standard names
        df.rename(columns={
            'Duration (hours)': 'Duration_hours',
            'Plume height (km a.v.l.)': 'Height_km.a.v.l',
            "MER (kg/s)": "MER_kg/s"
        }, inplace=True)

        if 'VEI' not in df.columns:
            df['VEI'] = None

        # Select and return required columns
        #df = df[['VEI', 'Height_km.a.v.l', 'TEM_kg', 'MER_kg/s', 'Duration_hours']]

        if as_geodataframe:
            df = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df['Longitude'], df['Latitude']))
            df.set_crs(epsg=4326, inplace=True)

        return df
    
    def whelley_2015(self, as_geodataframe: bool = False):
        df=self.datasets["whelley_2015"]
        
        if as_geodataframe:
            df = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df['Longitude'], df['Latitude']))
            df.set_crs(epsg=4326, inplace=True)

        return df
    
    def search_whelley_2015(self, max_vei_returns=None, **kwargs):
        """
        Search the whelley_2015 dataframe using one or multiple columns.

        Parameters:
        max_vei_returns: int, optional
            The maximum number of VEI values to return, in descending order. Default is None (return all non-zero VEI values).
        **kwargs: Key-value pairs where keys are column names, and values are the values to search for.
            If 'coordinates' is used as a key, its value must be a tuple (lat, lon).

        Returns:
        A filtered dataframe containing matching rows and a list of VEI values in descending order.

        Example:
        # Search by Volcano Number (unique ID):
        search_whelley_2015(Volcano_Number=345060)

        # Search by Volcano name:
        search_whelley_2015(Volcano="Mount St. Helens")

        # Search by geographic coordinates:
        search_whelley_2015(coordinates=(45.1, -122.2))

        # Search by elevation range:
        search_whelley_2015(Elevation_m=(2500, 3000))

        # Search by volcano classification:
        search_whelley_2015(Classification="Stratovolcano")

        # Search by Volcanic Explosivity Index (VEI):
        search_whelley_2015(VEI_5=1)

        Columns available for search:
        - 'Volcano Number': Search by unique volcano identification number.
        - 'Volcano': Search by the volcano's name.
        - 'Latitude' and 'Longitude': Search by geographic coordinates (e.g., coordinates=(45.1, -122.2)).
        - 'Elevation (m)': Search by elevation range or specific value.
        - 'Classification': Search by volcano classification.
        - 'VEI X' (e.g., 'VEI 5'): Search by Volcanic Explosivity Index values.
        """
        df = self.datasets.get("whelley_2015")
        df = df.drop(columns=['VEI 1'])

        for column, value in kwargs.items():
            if column == 'coordinates':
                if not isinstance(value, tuple) or len(value) != 2:
                    raise ValueError("For 'coordinates', the value must be a tuple of (lat, lon).")
                lat, lon = value
                df = df[(df['Latitude'] == lat) & (df['Longitude'] == lon)]
            elif column in df.columns:
                if isinstance(value, tuple) and len(value) == 2:
                    df = df[(df[column] >= value[0]) & (df[column] <= value[1])]
                elif isinstance(value, str):
                    df = df[df[column].str.contains(value, case=False, na=False)]
                else:
                    df = df[df[column] == value]
            else:
                raise ValueError(f"Invalid column: {column}. Please use a valid column name.")

        # Identify the VEI columns with non-zero values
        vei_columns = [col for col in df.columns if col.startswith("VEI ")]
        if not vei_columns:
            print("No VEI columns found in the dataset.")
            return df, []

        vei_sums = df[vei_columns].sum()
        non_zero_vei = vei_sums[vei_sums > 0].sort_values(ascending=False)

        if max_vei_returns:
            non_zero_vei = non_zero_vei.head(max_vei_returns)

        vei_values = non_zero_vei.index.str.extract(r'(\d+)')[0].astype(int).tolist()

        print(f"Top VEI values returned: {vei_values}")
        return df, vei_values

    
        

# Initialize the LOADDATA class
data_loader = LOADDATA()


# Initialize the LOADDATA class
#data_loader = LOADDATA()


##############################################

# Explor data correlations

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

def analyze_correlations(dataframe, dataset_name, threshold=0.6):
    """
    Analyze correlations among specific columns, filter based on a user-defined threshold,
    and visualize the best correlations using scatter plots.

    Parameters:
        dataframe (pd.DataFrame): Input DataFrame containing relevant columns.
        dataset_name (str): Name of the dataset for plot titles.
        threshold (float): User-defined threshold for correlation filtering (default is 0.6).

    Returns:
        pd.DataFrame: DataFrame with correlation pairs and their values above the threshold.
    """
    # Define columns of interest
    columns_of_interest = ['Height_km.a.v.l', 'TEM_kg', 'MER_kg/s', 'Duration_hours']
    columns_to_check = ["Brunt-Väisälä frequency", 'VEI', 'MASS_FRACTION_ASH_BELOW_63_micron']

    # Check if each column in `columns_to_check` exists in the dataframe
    for column in columns_to_check:
        if column in dataframe.columns:
            columns_of_interest.append(column)

    # Filter and drop rows with missing values
    filtered_data = dataframe[columns_of_interest].dropna()

    # Define correlation methods
    methods = ['pearson', 'spearman', 'kendall']
    correlation_results = {}

    # Compute correlation matrices for each method
    for method in methods:
        correlation_results[method] = filtered_data.corr(method=method)

    # Combine all correlation results
    combined_correlations = []
    for method, matrix in correlation_results.items():
        sorted_pairs = (
            matrix.unstack()
            .reset_index()
            .rename(columns={0: 'Correlation', 'level_0': 'Column1', 'level_1': 'Column2'})
        )
        sorted_pairs['Method'] = method
        combined_correlations.append(sorted_pairs)

    combined_correlations_df = pd.concat(combined_correlations)
    combined_correlations_df = combined_correlations_df[combined_correlations_df['Column1'] != combined_correlations_df['Column2']]
    combined_correlations_df['Abs_Correlation'] = combined_correlations_df['Correlation'].abs()

    # Filter correlations above the threshold
    filtered_correlations = combined_correlations_df[combined_correlations_df['Abs_Correlation'] >= threshold]

    # Select the best correlation for each unique pair
    best_correlations = (
        filtered_correlations.loc[
            filtered_correlations.groupby(['Column1', 'Column2'])['Abs_Correlation'].idxmax().dropna()
        ]
    )

    # Plot heatmap for the best method
    if not best_correlations.empty:
        best_method = best_correlations.iloc[0]['Method']
        correlation_matrix = correlation_results[best_method]

        plt.figure(figsize=(10, 8))
        heatmap = sns.heatmap(
            correlation_matrix,
            annot=True,
            cmap='coolwarm',
            fmt=".2f",
            square=True,
            cbar=True,
            linewidths=0.5,
            linecolor='black'
        )
        plt.title(f"Correlation Heatmap for {dataset_name} (Method: {best_method})", fontsize=14)
        plt.tight_layout()
        plt.show()

    # Combined scatter plots for the best pairs
    if not best_correlations.empty:
        plt.figure(figsize=(12, 8))

        plotted_pairs = set()  # Track plotted pairs to avoid duplicates

        for _, row in best_correlations.iterrows():
            col1, col2, method, corr = row['Column1'], row['Column2'], row['Method'], row['Correlation']

            # Ensure each pair is plotted only once (ignore reversed pairs)
            if (col2, col1) in plotted_pairs or (col1, col2) in plotted_pairs:
                continue

            plotted_pairs.add((col1, col2))

            x_data, y_data = filtered_data[col1], filtered_data[col2]

            # Determine if log scale is needed
            x_scale = 'log' # if (x_data.min() > 0 and x_data.max() / x_data.min() > 10) else 'linear'
            y_scale = 'log' #if (y_data.min() > 0 and y_data.max() / y_data.min() > 10) else 'linear'

            plt.scatter(
                x_data,
                y_data,
                alpha=0.7,
                label=f"{col1} vs {col2} (Corr: {corr:.2f}, {method})"
            )

            # Apply log scale if needed
            plt.xscale(x_scale)
            plt.yscale(y_scale)

        plt.legend(loc='best', fontsize=9)
        plt.title(f"Scatter Plots of Correlation Pairs for {dataset_name}", fontsize=14)
        plt.xlabel("X-axis (variable dependent)", fontsize=12)
        plt.ylabel("Y-axis (variable dependent)", fontsize=12)
        plt.tight_layout()
        plt.show()

    return best_correlations