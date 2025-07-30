# import numpy as np
# import pandas as pd
# import matplotlib.pyplot as plt
# from scipy.stats import t, invgamma, multivariate_normal
# from typing import Optional, Tuple, List, Union
# from matplotlib.colors import LogNorm
# import os

# class BAYESIAN_PREDICTOR:
#     def __init__(self, data: pd.DataFrame, xvar: str = 'Height_km.a.v.l', yvar: str = 'MER_kg/s' , 
#                  percentiles = [5, 25, 50, 75, 95], calculate_duration=False, output_dir=None, show_plots=False):
#         """
#         Initialize the Predict_ASH_BELOW_63_Micron class for Bayesian Regression.

#         :param data: Input dataset as a DataFrame.
#         """
        
#         self.show_plots=show_plots
#         self.data = data.copy()
#         self.xvar = xvar
#         self.yvar = yvar
#         self._prepare_data()
#         self._fit_model()
#         self.posterior_samples_cache = None  # Cache for posterior samples
#         self.percentiles=percentiles
#         self.calculate_duration=calculate_duration
#         self.output_dir=output_dir
      

#     def _save_dataframe(self, df: pd.DataFrame, filename: str):
#         """
#         Save a DataFrame to a CSV file in the output folder.
#         """
#         filepath = os.path.join(self.output_folder, filename)
#         df.to_csv(filepath, index=False)
#         print(f"Saved DataFrame to {filepath}")

#     def _save_plot(self, plt_obj, filename: str):
#         """
#         Save a plot to the output folder.
#         """
#         filepath = os.path.join(self.output_folder, filename)
#         plt_obj.savefig(filepath, dpi=300, bbox_inches='tight')
#         print(f"Saved plot to {filepath}")
#         plt.close()
    
#     def set_xvar(self, new_xvar: str):
#         """
#         Change the independent variable (xvar) used in the model and reinitialize the dataset.

#         :param new_xvar: The new column name to be used as the independent variable.
#         """
#         if new_xvar not in self.data.columns:
#             raise ValueError(f"Column {new_xvar} does not exist in the dataset.")

#         self.xvar = new_xvar
#         self._update_model(varaiable= self.xvar)

#     def set_yvar(self, new_yvar: str):
#         """
#         Change the dependent variable (yvar) used in the model and reinitialize the dataset.

#         :param new_yvar: The new column name to be used as the dependent variable.
#         """
#         if new_yvar not in self.data.columns:
#             raise ValueError(f"Column {new_yvar} does not exist in the dataset.")

#         self.yvar = new_yvar
#         self._update_model(varaiable=self.yvar)

#     def _update_model(self, varaiable=''):
#         """
#         Update the dataset, refit the model, and update outputs after changing xvar or yvar.
#         """
#         self._prepare_data()
#         self._fit_model()
        
#         # Create a folder named after the dependent variable (yvar)
#         if self.output_dir is not None:
#             self.output_folder = self.output_dir
            
#             if self.yvar == "MER_kg/s":
#                 self.output_folder = self.output_dir + "/" + "Forecast_MER_kg_per_second"
#             else:
#                 self.output_folder = self.output_dir + "/" + f"Forecast_{self.yvar}"
                       
#         elif self.output_dir is None:
#             if self.yvar == "MER_kg/s":
#                 self.output_folder = "Forecast_MER_kg_per_second"
#             else:
#                 self.output_folder = f"Forecast_{self.yvar}"
        
        
#         os.makedirs(self.output_folder, exist_ok=True)
        
#         if varaiable==self.xvar:
#             print(f"Model updated with xvar='{self.xvar}'")
#         if varaiable==self.yvar:
#             print(f"Model updated with yvar='{self.yvar}'.")

   
    
#     def _prepare_data(self):
#         if self.xvar not in self.data.columns or self.yvar not in self.data.columns:
#             raise ValueError(f"Columns {self.xvar} and {self.yvar} must exist in the dataset.")

#         self.data = self.data.dropna(subset=[self.xvar, self.yvar])
#         self.data = self.data[(self.data[self.xvar] > 0) & (self.data[self.yvar] > 0)]  # ADD THIS LINE
#         self.log_x = np.log10(self.data[self.xvar].values)
#         self.log_y = np.log10(self.data[self.yvar].values)


    
    
#     def _fit_model(self):
#         X = np.vstack([np.ones(len(self.log_x)), self.log_x]).T
#         y = self.log_y

#         if len(y) <= 2:
#             raise ValueError("Not enough data points to perform regression (need > 2).")

#         self.beta = np.linalg.solve(X.T @ X, X.T @ y)
#         residuals = y - X @ self.beta
#         self.sigma2 = np.sum(residuals**2) / (len(y) - 2)
#         self.X = X
#         self.y = y
#         self.residuals = residuals
#         self.posterior_samples_cache = None


#     def sample_posterior(self, size: int = 10000) -> pd.DataFrame:
#         """
#         Draw samples from the posterior distributions of the model parameters.

#         :param size: Number of posterior samples to draw.
#         :return: DataFrame of sampled parameters (intercept, slope, sigma2).
#         """
#         if self.posterior_samples_cache is not None and len(self.posterior_samples_cache) == size:
#             return self.posterior_samples_cache
#         samples = []
#         for _ in range(size):
#             sigma2_sample = invgamma.rvs(self.data.shape[0] / 2, scale=self.sigma2 * self.data.shape[0] / 2)
#             beta_sample = multivariate_normal.rvs(mean=self.beta, cov=sigma2_sample * np.linalg.inv(self.X.T @ self.X))
#             samples.append([*beta_sample, sigma2_sample])
        
#         self.posterior_samples_cache = pd.DataFrame(samples, columns=['intercept', 'slope', 'sigma2'])
        
      
        
#         return self.posterior_samples_cache
    
   

        

#     def predictive_intervals(self, x: np.ndarray, alpha: float = 0.05) -> Tuple[np.ndarray, np.ndarray]:
#         """
#         Compute predictive intervals for new data points.

#         :param x: Array of new x values (in original space).
#         :param alpha: Significance level for intervals.
#         :return: Lower and upper predictive intervals.
#         """
#         log_x = np.log10(x)
#         y_mean = self.beta[0] + self.beta[1] * log_x
#         mean_x = np.mean(self.log_x)
#         var_x = np.var(self.log_x)
#         n = len(self.y)

#         interval_var = self.sigma2 * (1 + 1 / n + (log_x - mean_x)**2 / (n * var_x))
#         t_dist = t(df=n - 2)
#         margin = t_dist.ppf(1 - alpha / 2) * np.sqrt(interval_var)
        
#         return y_mean - margin, y_mean + margin

#     def calculate_percentiles(self, x: Union[float, np.ndarray], percentiles: List[int] = [5, 25, 50, 75, 95]) -> pd.DataFrame:
#         """
#         Calculate posterior predictive percentiles for given x values.

#         :param x: Single value or array of new x values (in original space).
#         :param percentiles: List of percentiles to calculate.
#         :return: DataFrame with calculated percentiles.
#         """
#         if isinstance(x, (float, int)):
#             x = np.array([x])

#         log_x = np.log10(x)
#         y_mean = self.beta[0] + self.beta[1] * log_x

#         results = pd.DataFrame({self.xvar: x})
#         for p in self.percentiles:
#             results[f'{self.yvar}_Percentile_{p}'] = 10**(y_mean + t.ppf(p / 100, df=len(self.y) - 2) * np.sqrt(self.sigma2))

#         return results
    
    
#     def calculate_percentiles_with_uncertainty(self, x: Union[float, np.ndarray], percentiles: List[int] = [5, 25, 50, 75, 95], num_samples: int = 10000) -> pd.DataFrame:
#         """
#         Calculate posterior predictive percentiles and uncertainty for given x values.

#         :param x: Single value or array of new x values (in original space).
#         :param percentiles: List of percentiles to calculate.
#         :param num_samples: Number of posterior samples for uncertainty estimation.
#         :return: DataFrame with calculated percentiles and their uncertainties.
#         """
#         if isinstance(x, (float, int)):
#             x = np.array([x])

#         posterior_samples = self.sample_posterior(size=num_samples)
#         log_x = np.log10(x)
#         results = pd.DataFrame({self.xvar: x})

#         for p in self.percentiles:
#             percentile_values = []
#             for _, row in posterior_samples.iterrows():
#                 y_pred = row['intercept'] + row['slope'] * log_x
#                 percentile_values.append(10**y_pred)

#             percentiles_array = np.percentile(percentile_values, p, axis=0)
#             results[f'{self.yvar}_Percentile_{p}'] = percentiles_array

#             # results[f'Uncertainty_Lower_{p}'] = np.percentile(percentile_values, max(p - 5, 0), axis=0)
#             # results[f'Uncertainty_Upper_{p}'] = np.percentile(percentile_values, min(p + 5, 100), axis=0)

        
#         return results
    
    
#     def predict_with_uncertainty(self, x_vals: Union[float, np.ndarray], percentiles: List[int] = [5, 25, 50, 75, 95], output_file: Optional[str] = None) -> pd.DataFrame:
#         """
#         Predict Y values from given x values and include uncertainty estimates.

#         :param x_vals: Single value or array of new x values (in original space).
#         :param percentiles: List of percentiles to calculate.
#         :param output_file: If provided, saves the output DataFrame to the specified CSV file.
#         :return: DataFrame with predicted percentiles and uncertainty estimates.
#         """
#         results = self.calculate_percentiles_with_uncertainty(x_vals, self.percentiles)

#         if output_file:
#             results.to_csv(output_file, index=False)
#             print(f"Predictions with uncertainty saved to {output_file}")

#         if self.calculate_duration:
#             results=self.convert_percentiles_to_duration(results)
            
#         # Save predictions
#         if self.yvar=="MER_kg/s":
            
#             filename_csv=f"forecast_MER_kg_per_second.csv"
#         else:
#             filename_csv=f"forecast_{self.yvar}.csv"
        
#         self._save_dataframe(results, filename_csv)

#         return results
    

   
    
#     def plot_posterior_predictive(self, num_posterior_samples: int = 100000, num_predictive_samples: int = 1000):
#         """
#         Plot posterior predictive distributions, including observed data, posterior samples as points, and predictive samples.
        
#         :param num_posterior_samples: Number of posterior samples to visualize.
#         :param num_predictive_samples: Number of predictive samples drawn from the posterior predictive distribution.
#         """
#         # Generate x values for prediction
#         x_vals = np.logspace(np.min(self.log_x), np.max(self.log_x), 100)
#         log_x_vals = np.log10(x_vals)

#         # Compute mean prediction and predictive intervals
#         y_mean = self.beta[0] + self.beta[1] * log_x_vals
#         lower, upper = self.predictive_intervals(x_vals)

#         # Sample posterior parameters
#         posterior_samples = self.sample_posterior(size=num_posterior_samples)

#         # Generate posterior sampled points (using multiple samples at once)
#         posterior_sampled_y = []
#         for _, row in posterior_samples.iterrows():
#             y_pred = row['intercept'] + row['slope'] * log_x_vals
#             posterior_sampled_y.append(10**y_pred)  # Convert back to original scale

#         posterior_sampled_y = np.array(posterior_sampled_y)

#         # Sample from the posterior predictive distribution (including noise)
#         sampled_posterior_params = posterior_samples.sample(n=num_predictive_samples, replace=True)  # Sample multiple at once
#         predictive_samples = []

#         for _, row in sampled_posterior_params.iterrows():
#             sigma_sample = np.sqrt(row['sigma2'])  # Sampled noise standard deviation
#             y_pred = row['intercept'] + row['slope'] * log_x_vals
#             y_noisy = 10**(y_pred + np.random.normal(0, sigma_sample, size=len(log_x_vals)))  # Add Gaussian noise
#             predictive_samples.append(y_noisy)

#         predictive_samples = np.array(predictive_samples)

#         # Number of observed data points
#         num_observed = len(self.data)

#         # Select a subset of samples for visualization
#         sampled_posterior_indices = np.random.choice(range(num_posterior_samples), size=min(50, num_posterior_samples), replace=False)
#         sampled_predictive_indices = np.random.choice(range(num_predictive_samples), size=min(50, num_predictive_samples), replace=False)

#         # Plot observed data
#         plt.figure(figsize=(10, 6))
       

        
#         # Plot predictive samples (Blue dots) - Now properly aligned with predictive interval
#         plt.scatter(np.tile(x_vals, num_predictive_samples), predictive_samples.flatten(),
#                     color='blue', alpha=0.2, s=10, label=f'Posterior Predictive Samples (n={num_predictive_samples * len(x_vals)})')
        
#         # # Plot posterior sampled points (Red dots)
#         # plt.scatter(np.tile(x_vals, num_posterior_samples), posterior_sampled_y.flatten(),
#         #             color='red', alpha=0.4, s=15, label=f'Posterior Samples (n={num_posterior_samples * len(x_vals)})')

#         plt.scatter(self.data[self.xvar], self.data[self.yvar], color='green', alpha=0.8,
#                     label=f'Observed Data (n={num_observed})')

#         # Plot mean prediction line
#         plt.plot(x_vals, 10**y_mean, label='Mean Prediction', color='blue', linewidth=2)

#         # Plot predictive interval
#         plt.fill_between(x_vals, 10**lower, 10**upper, color='lightblue', alpha=0.4, label='Predictive Interval')

#         # Set log scale
#         plt.xscale('log')
#         plt.yscale('log')

#         # Labels and legend
#         plt.xlabel(self.xvar)
#         plt.ylabel(self.yvar)
#         plt.title('Posterior Predictive Plot')
#         plt.legend()
        
        

#         # Save the plot
#         self._save_plot(plt, "posterior_predictive_plot.png")
#         if self.show_plots==True:
#             plt.show()


    

#     def plot_percentiles(self , x_logscale=True, y_logscale=False):
#         """
#         Plot percentiles vs the independent variable with predicted percentile values in the colorbar.
#         """
#         x_vals = np.logspace(np.log10(self.data[self.xvar].min()), np.log10(self.data[self.xvar].max()), 100)
        
#         results = self.calculate_percentiles(x_vals, self.percentiles)

#         plt.figure(figsize=(12, 8))
#         for p in self.percentiles:
#             plt.plot(results[self.xvar], results[f'{self.yvar}_Percentile_{p}'], 
#                      label=f'{p}th Percentile', linewidth=2.5)

#         if x_logscale:
#             plt.xscale('log')
#         if y_logscale:
#             plt.yscale('log')
            
#         plt.xlabel(self.xvar)
#         plt.ylabel(self.yvar)
#         plt.title(f'Percentiles of {self.yvar} vs {self.xvar}')
#         plt.legend()
#         plt.grid(alpha=0.5)
        
       
        
#         # Save the plot
#         self._save_plot(plt, "percentiles_plot.png")
#         if self.show_plots==True:
#             plt.show()

#         height = results[self.xvar]
#         MERs = np.array([results[f'{self.yvar}_Percentile_{p}'] for p in self.percentiles])

#         X, Y = np.meshgrid(height, self.percentiles)
#         Z = MERs

        
#         if y_logscale==False:
#             norm=None
#         else :
#             vmin = Z.min() if Z.min() > 0 else 1e-10  # Ensure vmin is positive
#             norm = LogNorm(vmin=vmin, vmax=Z.max())       
        
       
#         plt.figure(figsize=(12, 8))
#         contour = plt.contourf(X, Y, Z, levels=20, cmap='viridis', alpha=0.9, norm=norm)
#         contour_lines = plt.contour(X, Y, Z, levels=20, colors='black', linewidths=0.8, norm=norm)  # Add contour lines
#         fmt = lambda x: f"{x:.1f}"  # Formatting contour labels to include "km"
#         labels = plt.clabel(contour_lines, inline=True, fontsize=10, fmt=fmt)  # Add contour labels
#         for label in labels:
#             label.set_color('white')  # Set label font color to white
            
       
#         plt.colorbar(contour, label=f'{self.yvar}')
        
#         if x_logscale:
#             plt.xscale('log')
            
#         plt.xlabel(self.xvar)
#         plt.ylabel('Percentiles')
#         plt.title(f'2D Contour Plot: {self.xvar} vs Percentiles of {self.yvar}')
#         plt.grid(alpha=0.5)
        
        
        
#         # Save the plot
#         self._save_plot(plt, "contour_percentiles_plot.png")
#         if self.show_plots==True:
#             plt.show()

    
#     def convert_percentiles_to_duration(self, predictions_df: pd.DataFrame) -> pd.DataFrame:
#         """
#         Convert calculated MER percentiles to eruption duration in hours.
        
#         Handles cases where:
#         - `xvar = "TEM_kg"` and percentiles are `MER_kg/s_Percentile_*`
#         - `xvar = "MER_kg/s"` and percentiles are `TEM_kg_Percentile_*`

#         :param predictions_df: DataFrame with predicted percentiles from predict_with_uncertainty().
#         :return: DataFrame with eruption durations.
#         """
#         if predictions_df is None or predictions_df.empty:
#             raise ValueError("The provided predictions DataFrame is empty.")

#         #print("Columns in predictions_df:", predictions_df.columns.tolist())  # Debugging line

#         # Ensure xvar column exists
#         if self.xvar not in predictions_df.columns:
#             raise KeyError(f"Expected xvar '{self.xvar}' not found in predictions_df.")

#         # Identify percentile columns dynamically
#         if self.xvar == "TEM_kg":
#             # Looking for MER percentiles
#             percentile_cols = [col for col in predictions_df.columns if col.startswith("MER_kg/s_Percentile_")]
#         elif self.xvar == "MER_kg/s":
#             # Looking for TEM percentiles
#             percentile_cols = [col for col in predictions_df.columns if col.startswith("TEM_kg_Percentile_")]
#         else:
#             raise ValueError(f"xvar ('{self.xvar}') must be either 'TEM_kg' or 'MER_kg/s'.")

#         if not percentile_cols:
#             raise KeyError(f"No matching percentile columns found for '{self.xvar}'.")

#        # Store computed durations
#         duration_columns = {}

#         for col in percentile_cols:
#             percentile_name = col.split('_')[-1]  # Extract percentile (e.g., "5", "50", "95")
#             denominator_values = predictions_df[col].values  # MER or TEM values

#             # Compute eruption duration in hours
#             duration_col_name = f'Duration_hr_P{percentile_name}'
#             predictions_df[duration_col_name] = (predictions_df[self.xvar].values / denominator_values) / 3600
#             duration_columns[percentile_name] = duration_col_name  # Store for later use

       

        
#         return predictions_df


# import numpy as np
# import pandas as pd
# import matplotlib.pyplot as plt
# from scipy.stats import t, invgamma, multivariate_normal
# from typing import Optional, Tuple, List, Union
# from matplotlib.colors import LogNorm
# import os

# class BAYESIAN_PREDICTOR:
#     def __init__(self, data: pd.DataFrame, xvar: str = 'Height_km.a.v.l', yvar: str = 'MER_kg/s' , 
#                  percentiles = [5, 25, 50, 75, 95], calculate_duration=False, output_dir=None, show_plots=False):
#         """
#         Initialize the Predict_ASH_BELOW_63_Micron class for Bayesian Regression.

#         :param data: Input dataset as a DataFrame.
#         """
        
#         self.show_plots=show_plots
#         self.data = data.copy()
#         self.xvar = xvar
#         self.yvar = yvar
#         self._prepare_data()
#         self._fit_model()
#         self.posterior_samples_cache = None  # Cache for posterior samples
#         self.percentiles=percentiles
#         self.calculate_duration=calculate_duration
#         self.output_dir=output_dir
#         self.output_folder=self.output_dir
      
#         os.makedirs(self.output_dir, exist_ok=True)


#     def _save_dataframe(self, df: pd.DataFrame, filename: str):
#         """
#         Save a DataFrame to a CSV file in the output folder.
#         """
#         filepath = os.path.join(self.output_folder, filename)
#         df.to_csv(filepath, index=False)
#         print(f"Saved DataFrame to {filepath}")

#     def _save_plot(self, plt_obj, filename: str):
#         """
#         Save a plot to the output folder.
#         """
#         filepath = os.path.join(self.output_folder, filename)
#         plt_obj.savefig(filepath, dpi=300, bbox_inches='tight')
#         print(f"Saved plot to {filepath}")
#         plt.close()
    
#     def set_xvar(self, new_xvar: str):
#         """
#         Change the independent variable (xvar) used in the model and reinitialize the dataset.

#         :param new_xvar: The new column name to be used as the independent variable.
#         """
#         if new_xvar not in self.data.columns:
#             raise ValueError(f"Column {new_xvar} does not exist in the dataset.")

#         self.xvar = new_xvar
#         self._update_model(varaiable= self.xvar)

#     def set_yvar(self, new_yvar: str):
#         """
#         Change the dependent variable (yvar) used in the model and reinitialize the dataset.

#         :param new_yvar: The new column name to be used as the dependent variable.
#         """
#         if new_yvar not in self.data.columns:
#             raise ValueError(f"Column {new_yvar} does not exist in the dataset.")

#         self.yvar = new_yvar
#         self._update_model(varaiable=self.yvar)

#     def _update_model(self, varaiable=''):
#         """
#         Update the dataset, refit the model, and update outputs after changing xvar or yvar.
#         """
#         self._prepare_data()
#         self._fit_model()
        
#         # Create a folder named after the dependent variable (yvar)
#         if self.output_dir is not None:
#             self.output_folder = self.output_dir
            
#             if self.yvar == "MER_kg/s":
#                 self.output_folder = self.output_dir + "/" + "Forecast_MER_kg_per_second"
#             else:
#                 self.output_folder = self.output_dir + "/" + f"Forecast_{self.yvar}"
                       
#         elif self.output_dir is None:
#             if self.yvar == "MER_kg/s":
#                 self.output_folder = "Forecast_MER_kg_per_second"
#             else:
#                 self.output_folder = f"Forecast_{self.yvar}"
        
        
#         os.makedirs(self.output_folder, exist_ok=True)
        
#         if varaiable==self.xvar:
#             print(f"Model updated with xvar='{self.xvar}'")
#         if varaiable==self.yvar:
#             print(f"Model updated with yvar='{self.yvar}'.")

    
    
#     def _prepare_data(self):
#         if self.xvar not in self.data.columns or self.yvar not in self.data.columns:
#             raise ValueError(f"Columns {self.xvar} and {self.yvar} must exist in the dataset.")

#         self.data = self.data.dropna(subset=[self.xvar, self.yvar])
#         self.data = self.data[(self.data[self.xvar] > 0) & (self.data[self.yvar] > 0)]  # ADD THIS LINE
#         self.log_x = np.log10(self.data[self.xvar].values)
#         self.log_y = np.log10(self.data[self.yvar].values)


    
    
#     def _fit_model(self):
#         X = np.vstack([np.ones(len(self.log_x)), self.log_x]).T
#         y = self.log_y

#         if len(y) <= 2:
#             raise ValueError("Not enough data points to perform regression (need > 2).")

#         self.beta = np.linalg.solve(X.T @ X, X.T @ y)
#         residuals = y - X @ self.beta
#         self.sigma2 = np.sum(residuals**2) / (len(y) - 2)
#         self.X = X
#         self.y = y
#         self.residuals = residuals
#         self.posterior_samples_cache = None


#     def sample_posterior(self, size: int = 10000) -> pd.DataFrame:
#         """
#         Draw samples from the posterior distributions of the model parameters.

#         :param size: Number of posterior samples to draw.
#         :return: DataFrame of sampled parameters (intercept, slope, sigma2).
#         """
#         if self.posterior_samples_cache is not None and len(self.posterior_samples_cache) == size:
#             return self.posterior_samples_cache
#         samples = []
#         for _ in range(size):
#             sigma2_sample = invgamma.rvs(self.data.shape[0] / 2, scale=self.sigma2 * self.data.shape[0] / 2)
#             beta_sample = multivariate_normal.rvs(mean=self.beta, cov=sigma2_sample * np.linalg.inv(self.X.T @ self.X))
#             samples.append([*beta_sample, sigma2_sample])
        
#         self.posterior_samples_cache = pd.DataFrame(samples, columns=['intercept', 'slope', 'sigma2'])
        
      
        
#         return self.posterior_samples_cache
    
   

        

#     def predictive_intervals(self, x: np.ndarray, alpha: float = 0.05) -> Tuple[np.ndarray, np.ndarray]:
#         """
#         Compute predictive intervals for new data points.

#         :param x: Array of new x values (in original space).
#         :param alpha: Significance level for intervals.
#         :return: Lower and upper predictive intervals.
#         """
#         log_x = np.log10(x)
#         y_mean = self.beta[0] + self.beta[1] * log_x
#         mean_x = np.mean(self.log_x)
#         var_x = np.var(self.log_x)
#         n = len(self.y)

#         interval_var = self.sigma2 * (1 + 1 / n + (log_x - mean_x)**2 / (n * var_x))
#         t_dist = t(df=n - 2)
#         margin = t_dist.ppf(1 - alpha / 2) * np.sqrt(interval_var)
        
#         return y_mean - margin, y_mean + margin

#     def calculate_percentiles(self, x: Union[float, np.ndarray], percentiles: List[int] = [5, 25, 50, 75, 95]) -> pd.DataFrame:
#         """
#         Calculate posterior predictive percentiles for given x values.

#         :param x: Single value or array of new x values (in original space).
#         :param percentiles: List of percentiles to calculate.
#         :return: DataFrame with calculated percentiles.
#         """
#         if isinstance(x, (float, int)):
#             x = np.array([x])

#         log_x = np.log10(x)
#         y_mean = self.beta[0] + self.beta[1] * log_x

#         results = pd.DataFrame({self.xvar: x})
#         for p in self.percentiles:
#             results[f'{self.yvar}_Percentile_{p}'] = 10**(y_mean + t.ppf(p / 100, df=len(self.y) - 2) * np.sqrt(self.sigma2))

#         return results
    
    
#     def calculate_percentiles_with_uncertainty(self, x: Union[float, np.ndarray], percentiles: List[int] = [5, 25, 50, 75, 95], num_samples: int = 10000) -> pd.DataFrame:
#         """
#         Calculate posterior predictive percentiles and uncertainty for given x values.

#         :param x: Single value or array of new x values (in original space).
#         :param percentiles: List of percentiles to calculate.
#         :param num_samples: Number of posterior samples for uncertainty estimation.
#         :return: DataFrame with calculated percentiles and their uncertainties.
#         """
#         if isinstance(x, (float, int)):
#             x = np.array([x])

#         posterior_samples = self.sample_posterior(size=num_samples)
#         log_x = np.log10(x)
#         results = pd.DataFrame({self.xvar: x})

#         for p in self.percentiles:
#             percentile_values = []
#             for _, row in posterior_samples.iterrows():
#                 y_pred = row['intercept'] + row['slope'] * log_x
#                 percentile_values.append(10**y_pred)

#             percentiles_array = np.percentile(percentile_values, p, axis=0)
#             results[f'{self.yvar}_Percentile_{p}'] = percentiles_array

           
        
#         return results
    
    
#     def predict_with_uncertainty(self, x_vals: Union[float, np.ndarray], percentiles: List[int] = [5, 25, 50, 75, 95], output_file: Optional[str] = None) -> pd.DataFrame:
#         """
#         Predict Y values from given x values and include uncertainty estimates.

#         :param x_vals: Single value or array of new x values (in original space).
#         :param percentiles: List of percentiles to calculate.
#         :param output_file: If provided, saves the output DataFrame to the specified CSV file.
#         :return: DataFrame with predicted percentiles and uncertainty estimates.
#         """
#         results = self.calculate_percentiles_with_uncertainty(x_vals, self.percentiles)

#         if output_file:
#             results.to_csv(output_file, index=False)
#             print(f"Predictions with uncertainty saved to {output_file}")

#         if self.calculate_duration:
#             results=self.convert_percentiles_to_duration(results)
            
#         # Save predictions
#         if self.yvar=="MER_kg/s":
            
#             filename_csv=f"forecast_MER_kg_per_second.csv"
#         else:
#             filename_csv=f"forecast_{self.yvar}.csv"
        
#         self._save_dataframe(results, filename_csv)

#         return results
    

    
#     def plot_posterior_predictive(self, num_posterior_samples: int = 100000, num_predictive_samples: int = 1000):
#         """
#         Plot posterior predictive distributions, including observed data, posterior samples as points, and predictive samples.
        
#         :param num_posterior_samples: Number of posterior samples to visualize.
#         :param num_predictive_samples: Number of predictive samples drawn from the posterior predictive distribution.
#         """
#         # Generate x values for prediction
#         x_vals = np.logspace(np.min(self.log_x), np.max(self.log_x), 100)
#         log_x_vals = np.log10(x_vals)

#         # Compute mean prediction and predictive intervals
#         y_mean = self.beta[0] + self.beta[1] * log_x_vals
#         lower, upper = self.predictive_intervals(x_vals)

#         # Sample posterior parameters
#         posterior_samples = self.sample_posterior(size=num_posterior_samples)

#         # Generate posterior sampled points (using multiple samples at once)
#         posterior_sampled_y = []
#         for _, row in posterior_samples.iterrows():
#             y_pred = row['intercept'] + row['slope'] * log_x_vals
#             posterior_sampled_y.append(10**y_pred)  # Convert back to original scale

#         posterior_sampled_y = np.array(posterior_sampled_y)

#         # Sample from the posterior predictive distribution (including noise)
#         sampled_posterior_params = posterior_samples.sample(n=num_predictive_samples, replace=True)  # Sample multiple at once
#         predictive_samples = []

#         for _, row in sampled_posterior_params.iterrows():
#             sigma_sample = np.sqrt(row['sigma2'])  # Sampled noise standard deviation
#             y_pred = row['intercept'] + row['slope'] * log_x_vals
#             y_noisy = 10**(y_pred + np.random.normal(0, sigma_sample, size=len(log_x_vals)))  # Add Gaussian noise
#             predictive_samples.append(y_noisy)

#         predictive_samples = np.array(predictive_samples)

#         # Number of observed data points
#         num_observed = len(self.data)

#         # Select a subset of samples for visualization
#         sampled_posterior_indices = np.random.choice(range(num_posterior_samples), size=min(50, num_posterior_samples), replace=False)
#         sampled_predictive_indices = np.random.choice(range(num_predictive_samples), size=min(50, num_predictive_samples), replace=False)

#         # Plot observed data
#         plt.figure(figsize=(10, 6))
       

        
#         # Plot predictive samples (Blue dots) - Now properly aligned with predictive interval
#         plt.scatter(np.tile(x_vals, num_predictive_samples), predictive_samples.flatten(),
#                     color='blue', alpha=0.2, s=10, label=f'Posterior Predictive Samples (n={num_predictive_samples * len(x_vals)})')
        
#         # # Plot posterior sampled points (Red dots)
#         # plt.scatter(np.tile(x_vals, num_posterior_samples), posterior_sampled_y.flatten(),
#         #             color='red', alpha=0.4, s=15, label=f'Posterior Samples (n={num_posterior_samples * len(x_vals)})')

#         plt.scatter(self.data[self.xvar], self.data[self.yvar], color='green', alpha=0.8,
#                     label=f'Observed Data (n={num_observed})')

#         # Plot mean prediction line
#         plt.plot(x_vals, 10**y_mean, label='Mean Prediction', color='blue', linewidth=2)

#         # Plot predictive interval
#         plt.fill_between(x_vals, 10**lower, 10**upper, color='lightblue', alpha=0.4, label='Predictive Interval')

#         # Set log scale
#         plt.xscale('log')
#         plt.yscale('log')

#         # Labels and legend
#         plt.xlabel(self.xvar)
#         plt.ylabel(self.yvar)
#         plt.title('Posterior Predictive Plot')
#         plt.legend()
        
        

#         # Save the plot
#         self._save_plot(plt, "posterior_predictive_plot.png")
#         if self.show_plots==True:
#             plt.show()



#     def plot_percentiles(self , x_logscale=True, y_logscale=False):
#         """
#         Plot percentiles vs the independent variable with predicted percentile values in the colorbar.
#         """
#         x_vals = np.logspace(np.log10(self.data[self.xvar].min()), np.log10(self.data[self.xvar].max()), 100)
        
#         results = self.calculate_percentiles(x_vals, self.percentiles)

#         plt.figure(figsize=(12, 8))
#         for p in self.percentiles:
#             plt.plot(results[self.xvar], results[f'{self.yvar}_Percentile_{p}'], 
#                      label=f'{p}th Percentile', linewidth=2.5)

#         if x_logscale:
#             plt.xscale('log')
#         if y_logscale:
#             plt.yscale('log')
            
#         plt.xlabel(self.xvar)
#         plt.ylabel(self.yvar)
#         plt.title(f'Percentiles of {self.yvar} vs {self.xvar}')
#         plt.legend()
#         plt.grid(alpha=0.5)
        
       
        
#         # Save the plot
#         self._save_plot(plt, "percentiles_plot.png")
#         if self.show_plots==True:
#             plt.show()

#         height = results[self.xvar]
#         MERs = np.array([results[f'{self.yvar}_Percentile_{p}'] for p in self.percentiles])

#         X, Y = np.meshgrid(height, self.percentiles)
#         Z = MERs

        
#         if y_logscale==False:
#             norm=None
#         else :
#             vmin = Z.min() if Z.min() > 0 else 1e-10  # Ensure vmin is positive
#             norm = LogNorm(vmin=vmin, vmax=Z.max())       
        
       
#         plt.figure(figsize=(12, 8))
#         contour = plt.contourf(X, Y, Z, levels=20, cmap='viridis', alpha=0.9, norm=norm)
#         contour_lines = plt.contour(X, Y, Z, levels=20, colors='black', linewidths=0.8, norm=norm)  # Add contour lines
#         fmt = lambda x: f"{x:.1f}"  # Formatting contour labels to include "km"
#         labels = plt.clabel(contour_lines, inline=True, fontsize=10, fmt=fmt)  # Add contour labels
#         for label in labels:
#             label.set_color('white')  # Set label font color to white
            
       
#         plt.colorbar(contour, label=f'{self.yvar}')
        
#         if x_logscale:
#             plt.xscale('log')
            
#         plt.xlabel(self.xvar)
#         plt.ylabel('Percentiles')
#         plt.title(f'2D Contour Plot: {self.xvar} vs Percentiles of {self.yvar}')
#         plt.grid(alpha=0.5)
        
        
        
#         # Save the plot
#         self._save_plot(plt, "contour_percentiles_plot.png")
#         if self.show_plots==True:
#             plt.show()

    
#     def convert_percentiles_to_duration(self, predictions_df: pd.DataFrame) -> pd.DataFrame:
#         """
#         Convert calculated MER percentiles to eruption duration in hours.
        
#         Handles cases where:
#         - `xvar = "TEM_kg"` and percentiles are `MER_kg/s_Percentile_*`
#         - `xvar = "MER_kg/s"` and percentiles are `TEM_kg_Percentile_*`

#         :param predictions_df: DataFrame with predicted percentiles from predict_with_uncertainty().
#         :return: DataFrame with eruption durations.
#         """
#         if predictions_df is None or predictions_df.empty:
#             raise ValueError("The provided predictions DataFrame is empty.")

#         #print("Columns in predictions_df:", predictions_df.columns.tolist())  # Debugging line

#         # Ensure xvar column exists
#         if self.xvar not in predictions_df.columns:
#             raise KeyError(f"Expected xvar '{self.xvar}' not found in predictions_df.")

#         # Identify percentile columns dynamically
#         if self.xvar == "TEM_kg":
#             # Looking for MER percentiles
#             percentile_cols = [col for col in predictions_df.columns if col.startswith("MER_kg/s_Percentile_")]
#         elif self.xvar == "MER_kg/s":
#             # Looking for TEM percentiles
#             percentile_cols = [col for col in predictions_df.columns if col.startswith("TEM_kg_Percentile_")]
#         else:
#             raise ValueError(f"xvar ('{self.xvar}') must be either 'TEM_kg' or 'MER_kg/s'.")

#         if not percentile_cols:
#             raise KeyError(f"No matching percentile columns found for '{self.xvar}'.")

#        # Store computed durations
#         duration_columns = {}

#         for col in percentile_cols:
#             percentile_name = col.split('_')[-1]  # Extract percentile (e.g., "5", "50", "95")
#             denominator_values = predictions_df[col].values  # MER or TEM values

#             # Compute eruption duration in hours
#             duration_col_name = f'Duration_hr_P{percentile_name}'
#             predictions_df[duration_col_name] = (predictions_df[self.xvar].values / denominator_values) / 3600
#             duration_columns[percentile_name] = duration_col_name  # Store for later use

      

        
#         return predictions_df


import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import t, invgamma, multivariate_normal
from typing import Optional, Tuple, List, Union
from matplotlib.colors import LogNorm
import os


class BAYESIAN_PREDICTOR:
    def __init__(self, data: pd.DataFrame, xvar: str = 'Height_km.a.v.l', yvar: str = 'MER_kg/s',
                 percentiles=[5, 25, 50, 75, 95], calculate_duration=False,
                 output_dir=None, show_plots=False):
        self.show_plots = show_plots
        self.data = data.copy()
        self.xvar = xvar
        self.yvar = yvar
        self._prepare_data()
        self._fit_model()
        self.posterior_samples_cache = None
        self.percentiles = percentiles
        self.calculate_duration = calculate_duration
        self.output_dir = output_dir
        self.output_folder = self.output_dir or "."

        os.makedirs(self.output_folder, exist_ok=True)

    def _save_dataframe(self, df: pd.DataFrame, filename: str):
        path = os.path.join(self.output_folder, filename)
        df.to_csv(path, index=False)
        print(f"Saved DataFrame to {path}")

    def _save_plot(self, plt_obj, filename: str):
        path = os.path.join(self.output_folder, filename)
        plt_obj.savefig(path, dpi=300, bbox_inches='tight')
        print(f"Saved plot to {path}")
        plt.close()

    def set_xvar(self, new_xvar: str):
        if new_xvar not in self.data.columns:
            raise ValueError(f"{new_xvar} not in data columns")
        self.xvar = new_xvar
        self._update_model(varaiable=self.xvar)

    def set_yvar(self, new_yvar: str):
        if new_yvar not in self.data.columns:
            raise ValueError(f"{new_yvar} not in data columns")
        self.yvar = new_yvar
        self._update_model(varaiable=self.yvar)

    def _update_model(self, varaiable=''):
        self._prepare_data()
        self._fit_model()
        self.output_folder = self.output_dir or "."
        if self.output_dir is not None:
            suffix = "MER_kg_per_second" if self.yvar == "MER_kg/s" else self.yvar
            self.output_folder = os.path.join(self.output_dir, f"Forecast_{suffix}")
        os.makedirs(self.output_folder, exist_ok=True)

    def _prepare_data(self):
        if self.xvar not in self.data.columns or self.yvar not in self.data.columns:
            raise ValueError(f"{self.xvar} and {self.yvar} must exist in data")
        self.data = self.data.dropna(subset=[self.xvar, self.yvar])
        self.data = self.data[(self.data[self.xvar] > 0) & (self.data[self.yvar] > 0)]
        self.log_x = np.log10(self.data[self.xvar].values)
        self.log_y = np.log10(self.data[self.yvar].values)

    def _fit_model(self):
        X = np.vstack([np.ones(len(self.log_x)), self.log_x]).T
        y = self.log_y
        if len(y) <= 2:
            raise ValueError("Need >2 data points")
        self.beta = np.linalg.solve(X.T @ X, X.T @ y)
        residuals = y - X @ self.beta
        self.sigma2 = np.sum(residuals**2) / (len(y)-2)
        self.X, self.y, self.residuals = X, y, residuals
        self.posterior_samples_cache = None

    def sample_posterior(self, size: int = 10000) -> pd.DataFrame:
        if self.posterior_samples_cache is not None and len(self.posterior_samples_cache) == size:
            return self.posterior_samples_cache

        n = self.data.shape[0]
        sigma2_samples = invgamma.rvs(n / 2, scale=self.sigma2 * n / 2, size=size)

        # Base covariance = (X'X)^(-1), so scale this by sigma2_sample for each draw
        base_cov = np.linalg.inv(self.X.T @ self.X)
        # Cholesky of base covariance
        chol = np.linalg.cholesky(base_cov)

        # Draw standard multivariate N(0, I) variables
        z = np.random.randn(size, 2)  # shape (size, num_params)
        # Scale for each draw
        betas = []
        for i in range(size):
            scale = np.sqrt(sigma2_samples[i])
            betas.append(self.beta + chol @ (z[i] * scale))  # vectorize
        betas = np.array(betas)

        self.posterior_samples_cache = pd.DataFrame(
            np.column_stack([betas, sigma2_samples]), columns=['intercept', 'slope', 'sigma2']
        )
        return self.posterior_samples_cache


    def predictive_intervals(self, x: np.ndarray, alpha: float = 0.05) -> Tuple[np.ndarray, np.ndarray]:
        log_x = np.log10(x)
        mean_pred = self.beta[0] + self.beta[1] * log_x
        mean_x = np.mean(self.log_x); var_x = np.var(self.log_x); n = len(self.y)
        interval_var = self.sigma2 * (1 + 1/n + (log_x-mean_x)**2/(n*var_x))
        margin = t.ppf(1 - alpha/2, df=n-2) * np.sqrt(interval_var)
        return mean_pred - margin, mean_pred + margin

    def calculate_percentiles(self, x: Union[float, np.ndarray], percentiles=None) -> pd.DataFrame:
        percentiles = percentiles or self.percentiles
        if isinstance(x, (float, int)):
            x = np.array([x])
        log_x = np.log10(x)
        mean_pred = self.beta[0] + self.beta[1]*log_x
        t_vals = t.ppf(np.array(percentiles)/100, df=len(self.y)-2)
        results = pd.DataFrame({self.xvar: x})
        for p, t_val in zip(percentiles, t_vals):
            results[f"{self.yvar}_Percentile_{p}"] = 10**(mean_pred + t_val*np.sqrt(self.sigma2))
        return results

    def calculate_percentiles_with_uncertainty(self, x: Union[float, np.ndarray], percentiles=None, num_samples=10000) -> pd.DataFrame:
        percentiles = percentiles or self.percentiles
        if isinstance(x, (float, int)):
            x = np.array([x])
        posterior_samples = self.sample_posterior(size=num_samples).values
        intercepts, slopes = posterior_samples[:,0], posterior_samples[:,1]
        log_x = np.log10(x)
        y_pred_matrix = intercepts[:,None] + slopes[:,None]*log_x[None,:]
        y_pred_matrix = 10**y_pred_matrix
        result_df = pd.DataFrame({self.xvar: x})
        for p in percentiles:
            result_df[f"{self.yvar}_Percentile_{p}"] = np.percentile(y_pred_matrix, p, axis=0)
        return result_df

    def predict_with_uncertainty(self, x_vals, percentiles=None, output_file=None) -> pd.DataFrame:
        results = self.calculate_percentiles_with_uncertainty(x_vals, percentiles or self.percentiles)
        if output_file:
            results.to_csv(output_file, index=False)
        if self.calculate_duration:
            results = self.convert_percentiles_to_duration(results)
        filename = f"forecast_{self.yvar}.csv" if self.yvar != "MER_kg/s" else "forecast_MER_kg_per_second.csv"
        self._save_dataframe(results, filename)
        return results

    def plot_posterior_predictive(self, num_posterior_samples=100000, num_predictive_samples=1000):
        x_vals = np.logspace(np.min(self.log_x), np.max(self.log_x), 100)
        log_x_vals = np.log10(x_vals)
        y_mean = self.beta[0] + self.beta[1] * log_x_vals
        lower, upper = self.predictive_intervals(x_vals)
        posterior_samples = self.sample_posterior(size=num_posterior_samples).values
        intercepts, slopes = posterior_samples[:,0], posterior_samples[:,1]
        y_pred_matrix = intercepts[:,None] + slopes[:,None]*log_x_vals
        posterior_sampled_y = 10**y_pred_matrix
        sampled_rows = posterior_samples[np.random.choice(num_posterior_samples, num_predictive_samples)]
        intercepts_pred, slopes_pred, sigma_pred = sampled_rows[:,0], sampled_rows[:,1], np.sqrt(sampled_rows[:,2])
        log_x_vals_matrix = log_x_vals[None,:]
        predictive_means = intercepts_pred[:,None] + slopes_pred[:,None]*log_x_vals_matrix
        noise = np.random.normal(0, sigma_pred[:,None], size=predictive_means.shape)
        predictive_samples = 10**(predictive_means + noise)
        num_observed = len(self.data)

        # Plot
        plt.figure(figsize=(10,6))
        plt.scatter(np.tile(x_vals, num_predictive_samples), predictive_samples.flatten(),
                    color='blue', alpha=0.2, s=10, label='Posterior Predictive Samples')
        plt.scatter(self.data[self.xvar], self.data[self.yvar], color='green', alpha=0.8, label='Observed')
        plt.plot(x_vals, 10**y_mean, label='Mean Prediction', color='blue')
        plt.fill_between(x_vals, 10**lower, 10**upper, color='lightblue', alpha=0.4, label='Predictive Interval')
        plt.xscale('log'); plt.yscale('log')
        plt.xlabel(self.xvar); plt.ylabel(self.yvar); plt.title('Posterior Predictive Plot')
        plt.legend()
        self._save_plot(plt, "posterior_predictive_plot.png")
        if self.show_plots:
            plt.show()

    def plot_percentiles(self, x_logscale=True, y_logscale=False):
        x_vals = np.logspace(np.log10(self.data[self.xvar].min()), np.log10(self.data[self.xvar].max()), 100)
        results = self.calculate_percentiles(x_vals, self.percentiles)
        plt.figure(figsize=(12,8))
        for p in self.percentiles:
            plt.plot(results[self.xvar], results[f"{self.yvar}_Percentile_{p}"], label=f"{p}th Percentile")
        if x_logscale:
            plt.xscale('log')
        if y_logscale:
            plt.yscale('log')
        plt.xlabel(self.xvar); plt.ylabel(self.yvar); plt.title(f"Percentiles of {self.yvar} vs {self.xvar}")
        plt.legend(); plt.grid(alpha=0.5)
        self._save_plot(plt, "percentiles_plot.png")
        if self.show_plots:
            plt.show()
        # Contour
        height = results[self.xvar]
        MERs = np.array([results[f"{self.yvar}_Percentile_{p}"] for p in self.percentiles])
        X, Y = np.meshgrid(height, self.percentiles); Z = MERs
        norm = LogNorm(vmin=Z.min()) if y_logscale else None
        plt.figure(figsize=(12,8))
        contour = plt.contourf(X, Y, Z, levels=20, cmap='viridis', alpha=0.9, norm=norm)
        contour_lines = plt.contour(X, Y, Z, levels=20, colors='black', linewidths=0.8, norm=norm)
        labels = plt.clabel(contour_lines, inline=True, fontsize=10, fmt="%.1f")
        for label in labels:
            label.set_color('white')
        plt.colorbar(contour, label=self.yvar)
        if x_logscale:
            plt.xscale('log')
        plt.xlabel(self.xvar); plt.ylabel('Percentiles'); plt.title(f'2D Contour: {self.xvar} vs Percentiles of {self.yvar}')
        self._save_plot(plt, "contour_percentiles_plot.png")
        if self.show_plots:
            plt.show()

    def convert_percentiles_to_duration(self, predictions_df: pd.DataFrame) -> pd.DataFrame:
        if predictions_df is None or predictions_df.empty:
            raise ValueError("Empty predictions_df")
        if self.xvar not in predictions_df.columns:
            raise KeyError(f"{self.xvar} not in predictions_df columns")
        if self.xvar == "TEM_kg":
            cols = [col for col in predictions_df.columns if col.startswith("MER_kg/s_Percentile_")]
        elif self.xvar == "MER_kg/s":
            cols = [col for col in predictions_df.columns if col.startswith("TEM_kg_Percentile_")]
        else:
            raise ValueError(f"xvar '{self.xvar}' must be 'TEM_kg' or 'MER_kg/s'")
        for col in cols:
            percentile_name = col.split('_')[-1]
            predictions_df[f'Duration_hr_P{percentile_name}'] = (predictions_df[self.xvar]/predictions_df[col]) / 3600
        return predictions_df
