'''

## Contact Details

**Dr. Mahmud Muhammad**  
(PhD, MSc, and BSc in Geology)  
Email: [mahmud.geology@hotmail.com](mailto:mahmud.geology@hotmail.com)  
Website: [mahmudm.com](http://mahmudm.com)


'''


import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import t, invgamma, multivariate_normal
from typing import Optional, Tuple, List, Union

class MERPredictor:
    def __init__(self, data: pd.DataFrame):
        """
        Initialize the MERPredictor class for Bayesian Regression.

        :param data: Input dataset as a DataFrame.
        """
        self.data = data.copy()
        self.xvar = 'TEM_kg'
        self.yvar = 'MER_kg/s'
        self._prepare_data()
        self._fit_model()

    def _prepare_data(self):
        """
        Prepares the dataset by ensuring the necessary columns exist and converting to log space.
        """
        if self.xvar not in self.data.columns or self.yvar not in self.data.columns:
            raise ValueError(f"Columns {self.xvar} and {self.yvar} must exist in the dataset.")

        self.data = self.data.dropna(subset=[self.xvar, self.yvar])
        self.data['log_x'] = np.log10(self.data[self.xvar])
        self.data['log_y'] = np.log10(self.data[self.yvar])

    def _fit_model(self):
        """
        Performs Bayesian linear regression using Maximum Likelihood Estimation (MLE).
        """
        X = np.vstack([np.ones(self.data.shape[0]), self.data['log_x']]).T
        y = self.data['log_y'].values

        self.beta = np.linalg.inv(X.T @ X) @ X.T @ y  # MLE for beta
        residuals = y - X @ self.beta
        self.sigma2 = np.sum(residuals**2) / (len(y) - 2)  # MLE for variance
        self.X = X
        self.y = y
        self.residuals = residuals

    def sample_posterior(self, size: int = 10000) -> pd.DataFrame:
        """
        Draw samples from the posterior distributions of the model parameters.

        :param size: Number of posterior samples to draw.
        :return: DataFrame of sampled parameters (intercept, slope, sigma2).
        """
        samples = []
        for _ in range(size):
            sigma2_sample = invgamma.rvs(self.data.shape[0] / 2, scale=self.sigma2 * self.data.shape[0] / 2)
            beta_sample = multivariate_normal.rvs(mean=self.beta, cov=sigma2_sample * np.linalg.inv(self.X.T @ self.X))
            samples.append([*beta_sample, sigma2_sample])
        return pd.DataFrame(samples, columns=['intercept', 'slope', 'sigma2'])

    def predictive_intervals(self, x: np.ndarray, alpha: float = 0.05) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute predictive intervals for new data points.

        :param x: Array of new x values (in original space).
        :param alpha: Significance level for intervals.
        :return: Lower and upper predictive intervals.
        """
        log_x = np.log10(x)
        y_mean = self.beta[0] + self.beta[1] * log_x
        mean_x = np.mean(self.data['log_x'])
        var_x = np.var(self.data['log_x'])
        n = len(self.y)

        interval_var = self.sigma2 * (1 + 1 / n + (log_x - mean_x)**2 / (n * var_x))
        t_dist = t(df=n - 2)
        margin = t_dist.ppf(1 - alpha / 2) * np.sqrt(interval_var)

        return y_mean - margin, y_mean + margin

    # def calculate_percentiles(self, x: np.ndarray, percentiles: List[int] = [5, 25, 50, 75, 95]) -> pd.DataFrame:
    #     """
    #     Calculate posterior predictive percentiles for given x values.

    #     :param x: Array of new x values (in original space).
    #     :param percentiles: List of percentiles to calculate.
    #     :return: DataFrame with calculated percentiles.
    #     """
    #     log_x = np.log10(x)
    #     y_mean = self.beta[0] + self.beta[1] * log_x

    #     results = pd.DataFrame({'TEM_kg': x})
    #     for p in percentiles:
    #         results[f'MERPercentile_{p}'] = 10**(y_mean + t.ppf(p / 100, df=len(self.y) - 2) * np.sqrt(self.sigma2))

    #     return results
    ####################################################################################################################
    
    # def calculate_percentiles(self, x: np.ndarray, percentiles: List[int] = [5, 25, 50, 75, 95]) -> pd.DataFrame:
    #     """
    #     Calculate posterior predictive percentiles and their uncertainties for given x values.

    #     :param x: Array of new x values (in original space).
    #     :param percentiles: List of percentiles to calculate.
    #     :return: DataFrame with calculated percentiles and uncertainties.
    #     """
    #     log_x = np.log10(x)
    #     y_mean = self.beta[0] + self.beta[1] * log_x

    #     # Variance for predictive distribution
    #     mean_x = np.mean(self.data['log_x'])
    #     var_x = np.var(self.data['log_x'])
    #     n = len(self.y)
    #     interval_var = self.sigma2 * (1 + 1 / n + (log_x - mean_x)**2 / (n * var_x))

    #     results = pd.DataFrame({'TEM_kg': x})
    #     for p in percentiles:
    #         t_dist = t(df=n - 2)
    #         margin = t_dist.ppf(p / 100) * np.sqrt(interval_var)
    #         results[f'MERPercentile_{p}'] = 10**(y_mean + margin)
    #         results[f'Uncertainty_{p}'] = margin  # Adding the uncertainty for each percentile

    #     return results
    
    
    ######################################################
    
    
    def calculate_percentiles(self, x: Union[float, np.ndarray], percentiles: List[int] = [5, 25, 50, 75, 95], num_samples: int = 10000) -> pd.DataFrame:
        """
        Calculate posterior predictive percentiles and uncertainty for given x values.

        :param x: Single value or array of new x values (in original space).
        :param percentiles: List of percentiles to calculate.
        :param num_samples: Number of posterior samples for uncertainty estimation.
        :return: DataFrame with calculated percentiles and their uncertainties.
        """
        if isinstance(x, (float, int)):
            x = np.array([x])

        posterior_samples = self.sample_posterior(size=num_samples)
        log_x = np.log10(x)
        results = pd.DataFrame({'TEM_kg': x})

        for p in percentiles:
            percentile_values = []
            for _, row in posterior_samples.iterrows():
                y_pred = row['intercept'] + row['slope'] * log_x
                percentile_values.append(10**(y_pred))
            
            percentiles_array = np.percentile(percentile_values, p, axis=0)
            results[f'MERPercentile_{p}'] = percentiles_array

            # Uncertainty estimation
            results[f'Uncertainty_Lower_{p}'] = np.percentile(percentile_values, max(p - 5, 0), axis=0)
            results[f'Uncertainty_Upper_{p}'] = np.percentile(percentile_values, min(p + 5, 100), axis=0)

            # Calculate Best_MER_Estimate_km from the 95th and 5th percentiles
        if 'MERPercentile_95' in results and 'MERPercentile_5' in results:
            results['Best_MER_Estimate_kg/s'] = (results['MERPercentile_95'] - results['MERPercentile_5'])
            
            
            # Calculate Best_MER_Estimate_km_Uncertainty
        if 'Uncertainty_Upper_95' in results and 'Uncertainty_Upper_5' in results:
            results['Best_MER_Estimate_kg/s_Uncertainty'] = (
                (results['Uncertainty_Upper_95'] - results['Uncertainty_Upper_5'])
            )
            
        
        return results
    
    
    
    
    ##########################################
    
    
    
    


    def predict_mer(self, tem_values: Union[float, List[float]], output_file: str = 'predicted_mer.csv') -> pd.DataFrame:
        """
        Predict MER values from single or multiple TEM values and save results as a CSV.

        :param tem_values: Single TEM value or a list of TEM values.
        :param output_file: Output CSV filename.
        """
        if isinstance(tem_values, (float, int)):
            tem_values = [tem_values]
        tem_values = np.array(tem_values)

        predictions = self.calculate_percentiles(tem_values)
        durations = self.convert_percentiles_to_duration(tem_values)
        
        # Merge predictions with durations
        merged_results = pd.merge(predictions, durations, on='TEM_kg')
        merged_results.to_csv(output_file, index=False)
        print(f"Predictions and durations saved to {output_file}")
        
        return merged_results

    def convert_percentiles_to_duration(self, tem_values: Union[float, List[float]]) -> pd.DataFrame:
        """
        Convert calculated MER percentiles to eruption duration in hours.

        :param tem_values: Single TEM value or a list of TEM values.
        :return: DataFrame with TEM values and corresponding durations for each percentile.
        """
        if isinstance(tem_values, (float, int)):
            tem_values = [tem_values]
        tem_values = np.array(tem_values)

        results = self.calculate_percentiles(tem_values)

        duration_results = pd.DataFrame({'TEM_kg': results['TEM_kg']})
        for col in results.columns:
            if col.startswith('MERPercentile_'):
                percentile_name = col.split('_')[-1]
                duration_results[f'Duration_hr_P{percentile_name}'] = duration_results['TEM_kg'] / results[col] / 3600

        for col in results.columns:
            if col=='Best_MER_Estimate_kg/s':
                duration_results['Duration_hr_best_estimate'] = duration_results['TEM_kg'] / results[col] / 3600
            elif col=="Best_MER_Estimate_kg/s_Uncertainty":
                duration_results['Duration_hr_best_estimate_Uncertainty'] = duration_results['TEM_kg'] / results[col] / 3600
        
        return duration_results

    def plot_posterior_predictive(self):
        """
        Plot posterior predictive PDFs and CDFs.
        """
        x_vals = np.linspace(self.data[self.xvar].min(), self.data[self.xvar].max(), 100)
        log_x_vals = np.log10(x_vals)
        y_mean = self.beta[0] + self.beta[1] * log_x_vals

        lower, upper = self.predictive_intervals(x_vals)
        num_data_points = len(self.data)
        plt.figure(figsize=(10, 6))
        plt.plot(x_vals, 10**y_mean, label='Mean Prediction', color='blue')
        plt.fill_between(x_vals, 10**lower, 10**upper, color='lightblue', alpha=0.5, label='Predictive Interval')
        plt.scatter(self.data[self.xvar], self.data[self.yvar], color='black', label=f'Data Points (n={num_data_points})')
        plt.xscale('log')
        plt.yscale('log')
        plt.xlabel(self.xvar)
        plt.ylabel(self.yvar)
        plt.legend()
        plt.title('Posterior Predictive Plot')
        plt.show()

    def plot_percentiles_vs_tem(self):
        """
        Create a 2D contour plot of MERPercentile vs TEM_kg for specific percentiles [5, 25, 50, 75, 95].
        """
        # Define the x (TEM_kg) values
        x_vals = np.logspace(np.log10(self.data[self.xvar].min()), np.log10(self.data[self.xvar].max()), 100)
        percentiles = [5, 25, 50, 75, 95]  # Specific percentiles

        # Calculate results for each x and percentile
        results = self.calculate_percentiles(x_vals, percentiles)
        
        # Create a 2D grid for TEM_kg (X) and percentiles (Y)
        X, Y = np.meshgrid(x_vals, percentiles)
        Z = np.array([results[f'MERPercentile_{p}'] for p in percentiles])  # Z is MERPercentile

        plt.figure(figsize=(12, 8))
        from matplotlib.colors import LogNorm
        # Create contour plot
        contour = plt.contourf(X, Y, Z, levels=20, cmap='viridis', alpha=0.9, norm=LogNorm(vmin=Z.min(), vmax=Z.max()))
        contour_lines = plt.contour(X, Y, Z, levels=20, colors='black', linewidths=0.8, norm=LogNorm(vmin=Z.min(), vmax=Z.max()))  # Add contour lines
        fmt = lambda x: f"{x:.1f} kg/s"  # Formatting contour labels to include "km"
        labels = plt.clabel(contour_lines, inline=True, fontsize=10, fmt=fmt)  # Add contour labels
        for label in labels:
            label.set_color('white')  # Set label font color to white

        cbar = plt.colorbar(contour)
        cbar.set_label('MER (kg/s)', weight='bold')
        # Set log scale for TEM
        plt.xscale('log')
        plt.xlabel('TEM_kg')
        plt.ylabel('Percentiles (%)')
        plt.title('2D Contour Plot: MER vs TEM for Specific Percentiles')
        plt.show()

    