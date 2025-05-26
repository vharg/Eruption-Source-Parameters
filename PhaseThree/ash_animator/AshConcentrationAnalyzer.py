import os
import math
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.gridspec as gridspec
from scipy.interpolate import griddata, RegularGridInterpolator

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cartopy.io.shapereader as shpreader
from adjustText import adjust_text

from predictor_generic import BAYESIAN_PREDICTOR
from .basemaps import draw_etopo_basemap

import matplotlib as mpl
mpl.rcParams['figure.max_open_warning'] = 0  # Suppress figure count warnings


class AshExceedanceAnalyzer_3D:
    
    """
    A class to analyze volcanic ash exceedance probabilities using 3D netCDF datasets.

    This class processes ash concentration data from netCDF (.nc) files, interpolates data onto a common
    spatial grid, and computes exceedance probabilities using Bayesian regression at different altitude levels.
    It provides functionality to visualize these exceedance probabilities on geographic maps, including both
    detailed and zoomed-in views.

    Parameters
    ----------
    nc_file_dir : str
        Directory containing netCDF files with ash concentration data.
    variable : str, optional
        The variable name within netCDF files representing ash concentration. Default is 'ash_concentration'.
    threshold : float, optional
        Threshold value of ash concentration (g/m³) for exceedance probability calculation. Default is 0.008.

    Attributes
    ----------
    nc_files : list of str
        Sorted list of paths to netCDF files.
    lat : ndarray or None
        Latitude grid points.
    lon : ndarray or None
        Longitude grid points.
    grid_shape : tuple or None
        Tuple representing the grid dimensions (latitude, longitude).
    altitude_levels : int or None
        Number of altitude levels in the dataset.
    altitude_data : dict
        Dictionary storing interpolated data arrays indexed by altitude level.
    exceedance_probs : dict
        Dictionary storing exceedance probability maps indexed by altitude level.
    mutual_metadata : dict
        Dictionary storing metadata common to all netCDF files.

    Methods
    -------
    prepare_data()
        Loads, interpolates, and prepares ash concentration data from netCDF files.
    compute_bayesian_exceedance()
        Computes exceedance probabilities using Bayesian linear regression.
    compute_average_bayesian_exceedance()
        Computes average exceedance probability across all altitude levels.
    plot_exceedance_maps(save_dir=None, contour_levels=10)
        Plots exceedance probability maps for each altitude level.
    plot_average_bayesian_exceedance(save_path=None, contour_levels=10, save_dir="Average_Exceedance_Probability")
        Plots average exceedance probability map across all altitude levels.
    plot_all_levels_contour(figsize=(18, 10), contour_levels=10, save_dir="Exced_prob_ZLevels_singlePlot")
        Plots all altitude-level exceedance probability maps in a single figure.

    Private Methods
    ---------------
    _extract_mutual_metadata()
        Extracts metadata common across all netCDF files.
    _draw_metadata_sidebar(fig, meta_dict, ax=None)
        Adds metadata as text sidebar to plots.
    _load_country_geometries()
        Loads geographic country boundary geometries for plotting.
    _load_grid(reference_file)
        Initializes spatial grid from a reference netCDF file.
    _interpolate_to_grid(data, src_lat, src_lon)
        Interpolates data onto the predefined spatial grid.
    _get_max_concentration_location(prob_map)
        Identifies geographic location of maximum exceedance probability.
    _get_zoom_indices(center_lat, center_lon)
        Determines indices and bounds for zoomed-in geographic views.
    _add_country_labels(ax, extent)
        Adds country labels to geographic plots.
    _plot_frame(ax, data, lons, lats, title, levels, scale_label, proj, basemap_mode)
        Creates a single geographic contour plot.

    Examples
    --------
    >>> analyzer = AshExceedanceAnalyzer_3D("path/to/nc/files")
    >>> analyzer.prepare_data()
    >>> analyzer.compute_bayesian_exceedance()
    >>> analyzer.compute_average_bayesian_exceedance()
    >>> analyzer.plot_exceedance_maps(save_dir="output/maps")
    >>> analyzer.plot_average_bayesian_exceedance()
    >>> analyzer.plot_all_levels_contour()
    """
    def __init__(self, nc_file_dir, variable='ash_concentration', threshold=0.008, cmap="rainbow", basemap_mode='stock', zoom_level=10):
        nc_file_paths = [
            os.path.join(root, file)
            for root, _, files in os.walk(nc_file_dir)
            for file in files if file.endswith(".nc")
        ]
        if not nc_file_paths:
            raise FileNotFoundError(f"No .nc files found in directory: {nc_file_dir}")

        self.nc_files = sorted(nc_file_paths)
        self.variable = variable
        self.threshold = threshold
        self.lat = None
        self.lon = None
        self.grid_shape = None
        self.altitude_levels = None
        self.altitude_data = {}
        self.exceedance_probs = {}
        self._load_country_geometries()
        self.zoom_width = 5
        self.zoom_height = 5
        self.cmap = cmap
        self.basemap_mode = basemap_mode
        self.mutual_metadata = {}
        self.zoom_level=zoom_level

    def _extract_mutual_metadata(self):
        all_attrs = []
        for path in self.nc_files:
            with xr.open_dataset(path) as ds:
                all_attrs.append(ds.attrs)

        if not all_attrs:
            return {}

        mutual_keys = set(all_attrs[0].keys())
        for attrs in all_attrs[1:]:
            mutual_keys &= set(attrs.keys())

        self.mutual_metadata = {
            key: all_attrs[0][key]
            for key in mutual_keys
            if all(attr[key] == all_attrs[0][key] for attr in all_attrs)
        }
        return self.mutual_metadata

    def _draw_metadata_sidebar(self, fig, meta_dict, ax=None):
        lines = [
            f"Run name:        {meta_dict.get('run_name', 'N/A')}",
            f"Run time:        {meta_dict.get('run_time', 'N/A')}",
            f"Met data:        {meta_dict.get('met_data', 'N/A')}",
            f"Start release:   {meta_dict.get('start_of_release', 'N/A')}",
            f"End release:     {meta_dict.get('end_of_release', 'N/A')}",
            f"Source strength: {meta_dict.get('source_strength', 'N/A')} g/s",
            f"Release loc:     {meta_dict.get('release_location', 'N/A')}",
            f"Release height:  {meta_dict.get('release_height', 'N/A')} m asl",
            f"Run duration:    {meta_dict.get('run_duration', 'N/A')}"
        ]
        full_text = "\n".join(lines)

        if ax is not None:
            ax.axis('off')
            ax.text(0, 0.5, full_text, va='center', ha='left',
                    fontsize=9, family='monospace', color='black',
                    transform=ax.transAxes,
                    bbox=dict(facecolor='white', alpha=0.8, edgecolor='gray'))
        else:
            fig.text(0.15, 0.09, full_text, va='center', ha='left',
                     fontsize=9, family='monospace', color='black',
                     bbox=dict(facecolor='white', alpha=0.8, edgecolor='gray'))

    def _load_country_geometries(self):
        shapefile_path = shpreader.natural_earth(resolution='110m', category='cultural', name='admin_0_countries')
        reader = shpreader.Reader(shapefile_path)
        self.country_geoms = list(reader.records())

    def _load_grid(self, reference_file):
        ds = xr.open_dataset(reference_file)
        self.lat = ds['latitude'].values if 'latitude' in ds.coords else np.arange(ds[self.variable].shape[1])
        self.lon = ds['longitude'].values if 'longitude' in ds.coords else np.arange(ds[self.variable].shape[2])
        ds.close()
        self.grid_shape = (len(self.lat), len(self.lon))

    def _interpolate_to_grid(self, data, src_lat, src_lon):
        interpolator = RegularGridInterpolator((src_lat, src_lon), data, bounds_error=False, fill_value=None, method='slinear')
        lon_grid, lat_grid = np.meshgrid(self.lon, self.lat)
        points = np.array([lat_grid.ravel(), lon_grid.ravel()]).T
        return interpolator(points).reshape(self.grid_shape)

    def prepare_data(self):
        self._load_grid(self.nc_files[0])
        with xr.open_dataset(self.nc_files[0]) as first_ds:
            self.altitude_levels = first_ds[self.variable].shape[0]

        for z in range(self.altitude_levels):
            stack = np.zeros((len(self.nc_files), *self.grid_shape), dtype=np.float32)
            for t, file in enumerate(self.nc_files):
                with xr.open_dataset(file) as ds:
                    raw_data = ds[self.variable].values[z]
                    src_lat = ds['latitude'].values if 'latitude' in ds.coords else np.arange(raw_data.shape[0])
                    src_lon = ds['longitude'].values if 'longitude' in ds.coords else np.arange(raw_data.shape[1])
                    interpolated = self._interpolate_to_grid(raw_data, src_lat, src_lon)
                    stack[t] = interpolated

            valid_data = (stack > 0) & (~np.isnan(stack))
            if np.sum(valid_data) == 0:
                print(f"Skipping altitude level {z} — no valid data at all.")
                continue
            self.altitude_data[z] = stack

    def compute_bayesian_exceedance(self):
        for z, stack in self.altitude_data.items():
            prob_map = np.full(self.grid_shape, np.nan, dtype=np.float32)
            for i in range(self.grid_shape[0]):
                for j in range(self.grid_shape[1]):
                    y = stack[:, i, j]
                    if np.any(np.isnan(y)) or np.all(y <= 0):
                        continue
                    try:
                        data_dict = {'time': np.arange(len(y)), 'ash_concentration': y}
                        predictor = BAYESIAN_PREDICTOR(pd.DataFrame(data_dict), xvar='time', yvar='ash_concentration', show_plots=False)
                        samples = predictor.sample_posterior(1000)
                        x_log = np.log10(len(y))
                        y_preds = samples['intercept'].values + samples['slope'].values * x_log
                        y_preds_linear = np.clip(np.power(10, y_preds), 0, 1e5)
                        prob = np.mean(y_preds_linear > self.threshold) if self.threshold > 0 else np.mean(y_preds_linear)
                        prob_map[i, j] = np.float32(prob)
                    except Exception:
                        continue
            self.exceedance_probs[1000 * (z + 1)] = prob_map

    def _get_max_concentration_location(self, prob_map):
        if np.all(np.isnan(prob_map)):
            return (
                np.nanmean(self.lat) if isinstance(self.lat, np.ndarray) else self.lat,
                np.nanmean(self.lon) if isinstance(self.lon, np.ndarray) else self.lon
            )
        max_idx = np.unravel_index(np.nanargmax(prob_map), prob_map.shape)
        lat_val = self.lat[max_idx[0]]
        lon_val = self.lon[max_idx[1]]
        if np.isnan(lat_val) or np.isnan(lon_val):
            return (
                np.nanmean(self.lat) if isinstance(self.lat, np.ndarray) else self.lat,
                np.nanmean(self.lon) if isinstance(self.lon, np.ndarray) else self.lon
            )
        return lat_val, lon_val

    def _get_zoom_indices(self, center_lat, center_lon):
        lon_min = center_lon - self.zoom_width / 2
        lon_max = center_lon + self.zoom_width / 2
        lat_min = center_lat - self.zoom_height / 2
        lat_max = center_lat + self.zoom_height / 2
        lat_idx = np.where((self.lat >= lat_min) & (self.lat <= lat_max))[0]
        lon_idx = np.where((self.lon >= lon_min) & (self.lon <= lon_max))[0]
        return lat_idx, lon_idx, lon_min, lon_max, lat_min, lat_max

    def _add_country_labels(self, ax, extent):
        proj = ccrs.PlateCarree()
        texts = []
        for country in self.country_geoms:
            name = country.attributes['NAME_LONG']
            geom = country.geometry
            try:
                lon, lat = geom.centroid.x, geom.centroid.y
                if extent[0] <= lon <= extent[1] and extent[2] <= lat <= extent[3]:
                    text = ax.text(lon, lat, name, fontsize=6, transform=proj,
                                   ha='center', va='center', color='white',
                                   bbox=dict(facecolor='black', alpha=0.5, linewidth=0))
                    texts.append(text)
            except Exception:
                continue
        adjust_text(texts, ax=ax, only_move={'points': 'y', 'text': 'y'},
                    arrowprops=dict(arrowstyle="->", color='white', lw=0.5))

    def _plot_frame(self, ax, data, lons, lats, title, levels, scale_label, proj, basemap_mode):
        ax.set_title(title)
        ax.set_extent([lons.min(), lons.max(), lats.min(), lats.max()])
        try:
            ax.coastlines(zorder=1)
            ax.add_feature(cfeature.BORDERS, linestyle=':', zorder=1)
            draw_etopo_basemap(ax, mode=self.basemap_mode, zoom=self.zoom_level)
        except Exception:
            ax.add_feature(cfeature.OCEAN, zorder=0)
            ax.add_feature(cfeature.LAND, zorder=0)
            ax.coastlines(zorder=1)
            ax.add_feature(cfeature.BORDERS, linestyle=':', zorder=1)

        c = ax.contourf(lons, lats, data, levels=levels, cmap=self.cmap,
                        alpha=0.6, transform=proj, zorder=2, extend="both")
        ax.contour(lons, lats, data, levels=levels, colors='black',
                   linewidths=0.5, transform=proj, zorder=2)

        
        self._extract_mutual_metadata()
        
        raw = self.mutual_metadata.get('release_location')
        if raw:
            try:
                lon_str, lat_str = raw.strip().split()
                lon = float(lon_str[:-1]) * (1 if lon_str[-1].upper() == 'E' else -1)
                lat = float(lat_str[:-1]) * (1 if lat_str[-1].upper() == 'N' else -1)
                ax.plot(lon, lat, marker='^', color='red',
                        markersize=10, transform=proj, label="Vent Location", zorder=5)
                ax.legend(loc="upper left", fontsize=7)
            except Exception:
                pass

        return c

    def compute_average_bayesian_exceedance(self):
        if not self.exceedance_probs:
            raise ValueError("Run compute_bayesian_exceedance() first.")
        all_maps = [v for v in self.exceedance_probs.values()]
        self.average_exceedance_map = np.nanmean(np.stack(all_maps), axis=0)

    def plot_exceedance_maps(self, save_dir=None, contour_levels=10):
        
        
       
        
        valid_lat_mask = np.zeros_like(self.lat, dtype=bool)
        valid_lon_mask = np.zeros_like(self.lon, dtype=bool)

        for data in self.exceedance_probs.values():
            if not np.all(np.isnan(data)):
                valid_lat_mask |= np.any(np.isfinite(data), axis=1)
                valid_lon_mask |= np.any(np.isfinite(data), axis=0)

        lat_valid = self.lat[valid_lat_mask]
        lon_valid = self.lon[valid_lon_mask]
        if lat_valid.size == 0 or lon_valid.size == 0:
            print("⚠ No valid data to plot.")
            return

        extent = [lon_valid.min(), lon_valid.max(), lat_valid.min(), lat_valid.max()]
        
        
        
        for z_m, data in self.exceedance_probs.items():
            proj = ccrs.PlateCarree()
            fig = plt.figure(figsize=(16, 8))
            ax1 = fig.add_subplot(1, 2, 1, projection=proj)
            ax2 = fig.add_subplot(1, 2, 2, projection=proj)

            if not np.any(np.isfinite(data)):
                continue

            lon_grid, lat_grid = np.meshgrid(self.lon, self.lat)
            points = np.column_stack((lon_grid.ravel(), lat_grid.ravel()))
            values = data.ravel()
            mask = np.isfinite(values)
            if np.count_nonzero(mask) < 16:
                continue

            data_interp = griddata(points[mask], values[mask], (lon_grid, lat_grid), method='cubic')
            data_interp = np.clip(data_interp, 0, 1)

            min_val, max_val = np.nanmin(data_interp), np.nanmax(data_interp)
            if not np.isfinite(min_val) or not np.isfinite(max_val) or min_val == max_val:
                continue

            levels = np.linspace(min_val, max_val, contour_levels) if isinstance(contour_levels, int) else np.asarray(contour_levels)
            if len(levels) < 2:
                continue

            
            
            
            
            
            cp1 = self._plot_frame(ax1, data_interp, self.lon, self.lat, f"Altitude {z_m}m (Full)",
                                    levels, f"P(Ash > {self.threshold} g/m³)", proj, self.basemap_mode)
            self._add_country_labels(ax1, [self.lon.min(), self.lon.max(), self.lat.min(), self.lat.max()])

            center_lat, center_lon = self._get_max_concentration_location(data_interp)
            lat_idx, lon_idx, lon_min, lon_max, lat_min, lat_max = self._get_zoom_indices(center_lat, center_lon)
            zoom_data = data_interp[np.ix_(lat_idx, lon_idx)]
            zoom_lat = self.lat[lat_idx]
            zoom_lon = self.lon[lon_idx]

            cp2 = self._plot_frame(ax2, data_interp, self.lon, self.lat, f"Altitude {z_m}m (Zoomed)",
                                    levels, f"P(Ash > {self.threshold} g/m³)", proj, self.basemap_mode)
           
            #ax2.set_extent([lon_min, lon_max, lat_min, lat_max])
            # ax2.relim()
            # ax2.autoscale(tight=True)
            
            ax2.set_extent(extent)
            #self._add_country_labels(ax2, [lon_min, lon_max, lat_min, lat_max])

            cbar_ax = fig.add_axes([1, 0.25, 0.015, 0.5])
            cbar = fig.colorbar(cp2, cax=cbar_ax)
            cbar.set_label(f"P(Ash > {self.threshold} g/m³)", fontsize=12)
            cbar.ax.tick_params(labelsize=9)
            cbar.ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:.2g}'))

            mutual_meta = self._extract_mutual_metadata()
            self._draw_metadata_sidebar(fig, mutual_meta)
            
           # plt.tight_layout()

            if save_dir:
                os.makedirs(save_dir, exist_ok=True)
                file_path = os.path.join(save_dir, f"exceedance_{z_m}m.jpg")
                plt.savefig(file_path, bbox_inches="tight", dpi=200)
                plt.close(fig)

                print(f"📸 Saved plot: {file_path}")
            else:
                plt.show()

    def plot_average_bayesian_exceedance(self, save_path=None, contour_levels=10, save_dir="Average_Exceedance_Probability"):
        if not hasattr(self, 'average_exceedance_map'):
            raise ValueError("Run compute_average_bayesian_exceedance() first.")

        proj = ccrs.PlateCarree()
        fig = plt.figure(figsize=(16, 8))
        ax1 = fig.add_subplot(1, 2, 1, projection=proj)
        ax2 = fig.add_subplot(1, 2, 2, projection=proj)

        data = self.average_exceedance_map
        lon_grid, lat_grid = np.meshgrid(self.lon, self.lat)
        points = np.column_stack((lon_grid.ravel(), lat_grid.ravel()))
        values = data.ravel()
        mask = np.isfinite(values)
        if np.count_nonzero(mask) < 16:
            print("⚠ Skipping plot: insufficient valid data for interpolation")
            return

        data_interp = griddata(points[mask], values[mask], (lon_grid, lat_grid), method='cubic')
        data_interp = np.clip(data_interp, 0, 1)

        min_val, max_val = np.nanmin(data_interp), np.nanmax(data_interp)
        if not np.isfinite(min_val) or not np.isfinite(max_val) or min_val == max_val:
            print("⚠ Skipping average plot: invalid or constant interpolated data")
            return

        levels = np.linspace(min_val, max_val, contour_levels) if isinstance(contour_levels, int) else contour_levels
        if len(levels) < 2:
            print("⚠ Skipping average plot: not enough distinct non-zero contour levels")
            return

        cp1 = self._plot_frame(ax1, data_interp, self.lon, self.lat, "Average Exceedance Probability (Full)",
                            levels, f"Average P(Ash > {self.threshold} g/m³)", proj, self.basemap_mode)
        self._add_country_labels(ax1, [self.lon.min(), self.lon.max(), self.lat.min(), self.lat.max()])

        center_lat, center_lon = self._get_max_concentration_location(data_interp)
        lat_idx, lon_idx, lon_min, lon_max, lat_min, lat_max = self._get_zoom_indices(center_lat, center_lon)

        zoom_data = data_interp[np.ix_(lat_idx, lon_idx)]
        zoom_lat = self.lat[lat_idx]
        zoom_lon = self.lon[lon_idx]

        cp2 = self._plot_frame(ax2, zoom_data, zoom_lon, zoom_lat, "Average Exceedance Probability (Zoomed)",
                            levels, f"Average P(Ash > {self.threshold} g/m³)", proj, self.basemap_mode)
        self._add_country_labels(ax2, [lon_min, lon_max, lat_min, lat_max])

        cbar_ax = fig.add_axes([1, 0.25, 0.015, 0.5])
        cbar = fig.colorbar(cp2, cax=cbar_ax)
        cbar.set_label(f"Average P(Ash > {self.threshold} g/m³)", fontsize=12)
        cbar.ax.tick_params(labelsize=9)
        cbar.ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:.2g}'))

        mutual_meta = self._extract_mutual_metadata()
        self._draw_metadata_sidebar(fig, mutual_meta)

        if save_dir:
            os.makedirs(save_dir, exist_ok=True)
            file_path = os.path.join(save_dir, f"Average_Exceedance_Probability_{self.threshold}.jpg")
            plt.savefig(file_path, bbox_inches="tight", dpi=200)
            plt.close("all")

            print(f"📸 Saved {file_path}")
        else:
            plt.show()


        
    def plot_all_levels_contour(self, figsize=(18, 10), contour_levels=10, save_dir="Exced_prob_ZLevels_singlePlot"):
        
        z_levels = sorted(self.exceedance_probs.keys())
        n_levels = len(z_levels)
        ncols = math.ceil(math.sqrt(n_levels))
        nrows = math.ceil(n_levels / ncols)

        fig = plt.figure(figsize=figsize)
        gs = gridspec.GridSpec(nrows + 1, ncols, height_ratios=[1]*nrows + [0.05], figure=fig)

        resolution_factor = 2
        valid_lat_mask = np.zeros_like(self.lat, dtype=bool)
        valid_lon_mask = np.zeros_like(self.lon, dtype=bool)

        for data in self.exceedance_probs.values():
            if not np.all(np.isnan(data)):
                valid_lat_mask |= np.any(np.isfinite(data), axis=1)
                valid_lon_mask |= np.any(np.isfinite(data), axis=0)

        lat_valid = self.lat[valid_lat_mask]
        lon_valid = self.lon[valid_lon_mask]
        if lat_valid.size == 0 or lon_valid.size == 0:
            print("⚠ No valid data to plot.")
            return

        extent = [lon_valid.min(), lon_valid.max(), lat_valid.min(), lat_valid.max()]
        last_cp = None

        for idx, z in enumerate(z_levels):
            row, col = divmod(idx, ncols)
            ax = fig.add_subplot(gs[row, col], projection=ccrs.PlateCarree())
            data = self.exceedance_probs[z]

            if np.all(np.isnan(data)):
                ax.set_title(f"{z}m (no data)")
                ax.axis('off')
                continue

            lat_fine = np.linspace(self.lat.min(), self.lat.max(), len(self.lat) * resolution_factor)
            lon_fine = np.linspace(self.lon.min(), self.lon.max(), len(self.lon) * resolution_factor)
            lon_grid_fine, lat_grid_fine = np.meshgrid(lon_fine, lat_fine)

            lon_grid, lat_grid = np.meshgrid(self.lon, self.lat)
            points = np.column_stack((lon_grid.ravel(), lat_grid.ravel()))
            values = data.ravel()
            mask = np.isfinite(values)
            if np.count_nonzero(mask) < 16:
                ax.set_title(f"{z}m (insufficient data)")
                ax.axis('off')
                continue

            data_interp = griddata(points[mask], values[mask], (lon_grid_fine, lat_grid_fine), method='cubic')
            data_interp = np.clip(data_interp, 0, 1)
            if np.all(np.isnan(data_interp)):
                ax.set_title(f"{z}m (interp failed)")
                ax.axis('off')
                continue

            min_val, max_val = np.nanmin(data_interp), np.nanmax(data_interp)
            levels = np.linspace(min_val, max_val, contour_levels) if isinstance(contour_levels, int) else contour_levels

            cp = self._plot_frame(ax, data_interp, lon_fine, lat_fine,
                                f"{z}m (P > {self.threshold} g/m³)", levels,
                                f"P(Ash > {self.threshold})", ccrs.PlateCarree(), self.basemap_mode)

            ax.set_extent(extent, crs=ccrs.PlateCarree())
            self._add_country_labels(ax, extent)
            last_cp = cp

        for idx in range(n_levels, nrows * ncols):
            fig.add_subplot(gs[idx // ncols, idx % ncols]).axis('off')

        cbar_ax = fig.add_subplot(gs[-1, :])
        cbar = fig.colorbar(last_cp, cax=cbar_ax, orientation='horizontal')
        cbar.set_label(f"P(Ash concentration > {self.threshold} g/m³)", fontsize=12)
        cbar.ax.tick_params(labelsize=8, direction='out')
        cbar.ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:.2g}'))

        if save_dir:
            os.makedirs(save_dir, exist_ok=True)
            file_path = os.path.join(save_dir, f"Exceedance_probability_ashThresh{self.threshold}_all_ZLevels_singlePlot.jpg")
            plt.savefig(file_path, bbox_inches="tight", dpi=200)
            plt.close("all")
            print(f"📸 Saved {file_path}")
        else:
            plt.show()




import numpy as np
import pandas as pd
import xarray as xr
import os
from scipy.interpolate import RegularGridInterpolator
from predictor_generic import BAYESIAN_PREDICTOR
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.ticker as mticker
from cartopy.io import shapereader as shpreader
from adjustText import adjust_text
import io
import sys




import dask
import dask.array as da
from scipy.interpolate import griddata

class MultiFieldExceedanceAnalyzer_2D:
    """
    A class for analyzing exceedance probabilities of multiple fields using 2D netCDF datasets.

    This class manages data preparation, interpolation, and computation of exceedance probabilities
    for specified variables from netCDF files. It employs Bayesian regression methods and supports
    efficient computation using parallelization with Dask. Visualization functionalities include plotting
    both full and zoomed-in exceedance probability maps.

    Parameters
    ----------
    nc_file_dir : str
        Path to the directory containing netCDF files with the relevant datasets.
    variables : list of str
        List of variable names within the netCDF files to be analyzed.
    threshold : float, optional
        Threshold value for exceedance calculation (default is 0.008).

    Attributes
    ----------
    nc_files : list of str
        Sorted list of paths to netCDF files.
    variables : list of str
        Variables to analyze.
    threshold : float
        Threshold for exceedance calculations.
    lat : ndarray
        Latitude grid points extracted from netCDF data.
    lon : ndarray
        Longitude grid points extracted from netCDF data.
    grid_shape : tuple
        Shape of the spatial grid (latitude, longitude).
    data_stacks : dict
        Dictionary holding stacked data arrays for each variable.
    exceedance_probs : dict
        Dictionary holding computed exceedance probabilities for each variable.
    predicted_medians : dict
        Dictionary holding computed predicted median values for each variable.
    mutual_metadata : dict
        Common metadata extracted from all netCDF files.

    Methods
    -------
    prepare_data()
        Loads and interpolates data for all specified variables from netCDF files.
    compute_bayesian_exceedance()
        Computes exceedance probabilities and predicted medians using Bayesian methods.
    plot_exceedance_map(var, contour_levels=10, save_dir=None)
        Plots exceedance probability maps for a specified variable.

    Private Methods
    ---------------
    _load_grid(reference_file)
        Initializes spatial grid from the first netCDF file.
    _interpolate_to_grid(data, src_lat, src_lon)
        Interpolates data onto the predefined spatial grid.
    _compute_cell_exceedance(var, y)
        Computes exceedance probability and median predictions for a single grid cell.
    _load_country_geometries()
        Loads country boundary geometries for plotting.
    _get_max_concentration_location(prob_map)
        Identifies the location of maximum exceedance probability.
    _get_zoom_indices(center_lat, center_lon)
        Determines indices for creating zoomed-in geographic views.
    _add_country_labels(ax, extent)
        Adds country labels onto geographic plots.
    _extract_mutual_metadata()
        Extracts metadata common to all netCDF files.
    _draw_metadata_sidebar(fig, meta_dict)
        Adds metadata information as a sidebar to plots.
    _plot_frame(ax, data, lons, lats, title, levels, scale_label, proj, basemap_mode)
        Creates individual geographic contour plots.
    interpolate_grid(data, lon_grid, lat_grid)
        Interpolates data onto a specified finer grid.

    Examples
    --------
    >>> analyzer = MultiFieldExceedanceAnalyzer_2D("path/to/data", ['air_concentration', 'dry_deposition_rate', 'wet_deposition_rate'])
    >>> analyzer.prepare_data()
    >>> analyzer.compute_bayesian_exceedance()
    >>> analyzer.plot_exceedance_map("air_concentration", save_dir="output/maps")
    """

    def __init__(self, nc_file_dir, variables: list= ['air_concentration', 'dry_deposition_rate', 'wet_deposition_rate'], 
                 threshold=0.008, cmap='rainbow', basemap_mode='basemap', zoom_level=10):
        
        
        nc_file_paths = [
            os.path.join(root, file)
            for root, _, files in os.walk(nc_file_dir)
            for file in files if file.endswith(".nc")
        ]
        if not nc_file_paths:
            raise FileNotFoundError(f"No .nc files found in directory: {nc_file_dir}")

        
        self.nc_files = sorted(nc_file_paths)
        self.variables = variables
        self.threshold = threshold
        self.lat = None
        self.lon = None
        self.grid_shape = None
        self.data_stacks = {var: [] for var in variables}
        self.exceedance_probs = {}
        self.zoom_width = 5
        self.zoom_height = 5
        self.cmap = cmap
        self._load_country_geometries()
        self.mutual_metadata = {}
        self.predicted_medians = {}  # Store predicted median maps
        self.basemap_mode=basemap_mode
        self.zoom_level=zoom_level




    



    def _load_grid(self, reference_file):
        ds = xr.open_dataset(reference_file)
        self.lat = ds['latitude'].values
        self.lon = ds['longitude'].values
        ds.close()
        self.grid_shape = (len(self.lat), len(self.lon))

    

    def _interpolate_to_grid(self, data, src_lat, src_lon):
        interpolator = RegularGridInterpolator((src_lat, src_lon), data, bounds_error=False, fill_value=None, method='linear')
        lon_grid, lat_grid = np.meshgrid(self.lon, self.lat)
        points = np.array([lat_grid.ravel(), lon_grid.ravel()]).T
        return interpolator(points).reshape(self.grid_shape)
    
    def prepare_data(self):
        self._load_grid(self.nc_files[0])
        for file in self.nc_files:
            ds = xr.open_dataset(file)
            src_lat = ds['latitude'].values
            src_lon = ds['longitude'].values
            for var in self.variables:
                raw_data = ds[var].values
                interpolated = self._interpolate_to_grid(raw_data, src_lat, src_lon)
                self.data_stacks[var].append(interpolated)
            ds.close()
        for var in self.variables:
            self.data_stacks[var] = np.stack(self.data_stacks[var], axis=0)

    


    def compute_bayesian_exceedance(self):
        from dask.diagnostics import ProgressBar

        for var, stack in self.data_stacks.items():
            tasks_prob = []
            tasks_pred = []

            for i in range(self.grid_shape[0]):
                for j in range(self.grid_shape[1]):
                    y = stack[:, i, j]

                    if np.any(np.isnan(y)) or np.all(y <= 0):
                        tasks_prob.append(dask.delayed(np.nan))
                        tasks_pred.append(dask.delayed(np.nan))
                        continue

                    y = y[y > 0]
                    if len(y) < 2:
                        tasks_prob.append(dask.delayed(np.nan))
                        tasks_pred.append(dask.delayed(np.nan))
                        continue

                    task = dask.delayed(self._compute_cell_exceedance)(var, y)
                    tasks_prob.append(task[0])
                    tasks_pred.append(task[1])

            prob_map_da = da.from_delayed(
                dask.delayed(np.array)(tasks_prob).reshape(self.grid_shape),
                shape=self.grid_shape,
                dtype=np.float32
            )

            pred_map_da = da.from_delayed(
                dask.delayed(np.array)(tasks_pred).reshape(self.grid_shape),
                shape=self.grid_shape,
                dtype=np.float32
            )

            # Use a progress bar during computation
            with ProgressBar():
                self.exceedance_probs[var] = prob_map_da.compute()
                self.predicted_medians[var] = pred_map_da.compute()


    def _compute_cell_exceedance(self, var, y):
        try:
            time = np.arange(len(y))
            data_dict = {'time': time, var: y}
            predictor = BAYESIAN_PREDICTOR(pd.DataFrame(data_dict), xvar='time', yvar=var, show_plots=False)
            samples = predictor.sample_posterior(1000)

            x_log = np.log10(len(y))
            y_preds_log = samples['intercept'].values + samples['slope'].values * x_log

            # Exceedance probability
            log_threshold = np.log10(self.threshold)
            prob = np.mean(y_preds_log > log_threshold)

            # Overflow-safe exponentiation
            y_preds_log_clipped = np.clip(y_preds_log, a_min=-np.inf, a_max=38.0)
            y_preds_linear = np.power(10.0, y_preds_log_clipped)
            median_pred = np.median(y_preds_linear)
            
        

            return np.float32(prob) , np.float32(median_pred)

        except Exception:
            return np.nan, np.nan



    def _load_country_geometries(self):
        shapefile_path = shpreader.natural_earth(resolution='110m', category='cultural', name='admin_0_countries')
        reader = shpreader.Reader(shapefile_path)
        self.country_geoms = list(reader.records())

    def _get_max_concentration_location(self, prob_map):
        if np.all(np.isnan(prob_map)):
            return np.mean(self.lat), np.mean(self.lon)
        max_idx = np.unravel_index(np.nanargmax(prob_map), prob_map.shape)
        return self.lat[max_idx[0]], self.lon[max_idx[1]]

    def _get_zoom_indices(self, center_lat, center_lon):
        lon_min = center_lon - self.zoom_width / 2
        lon_max = center_lon + self.zoom_width / 2
        lat_min = center_lat - self.zoom_height / 2
        lat_max = center_lat + self.zoom_height / 2
        lat_idx = np.where((self.lat >= lat_min) & (self.lat <= lat_max))[0]
        lon_idx = np.where((self.lon >= lon_min) & (self.lon <= lon_max))[0]
        return lat_idx, lon_idx, lon_min, lon_max, lat_min, lat_max

    def _add_country_labels(self, ax, extent):
        proj = ccrs.PlateCarree()
        texts = []
        for country in self.country_geoms:
            name = country.attributes['NAME_LONG']
            geom = country.geometry
            try:
                lon, lat = geom.centroid.x, geom.centroid.y
                if extent[0] <= lon <= extent[1] and extent[2] <= lat <= extent[3]:
                    text = ax.text(lon, lat, name, fontsize=6, transform=proj,
                                   ha='center', va='center', color='white',
                                   bbox=dict(facecolor='black', alpha=0.5, linewidth=0))
                    texts.append(text)
            except:
                continue
        adjust_text(texts, ax=ax, only_move={'points': 'y', 'text': 'y'},
                    arrowprops=dict(arrowstyle="->", color='white', lw=0.5))

    def _extract_mutual_metadata(self):
        all_attrs = []
        for path in self.nc_files:
            with xr.open_dataset(path) as ds:
                all_attrs.append(ds.attrs)
        if not all_attrs:
            return {}
        mutual_keys = set(all_attrs[0].keys())
        for attrs in all_attrs[1:]:
            mutual_keys &= set(attrs.keys())
        self.mutual_metadata = {}
        for key in mutual_keys:
            values = [attrs[key] for attrs in all_attrs]
            if all(val == values[0] for val in values):
                self.mutual_metadata[key] = values[0]
        return self.mutual_metadata

    def _draw_metadata_sidebar(self, fig, meta_dict):
        lines = [
            f"Run name:        {meta_dict.get('run_name', 'N/A')}",
            f"Run time:        {meta_dict.get('run_time', 'N/A')}",
            f"Met data:        {meta_dict.get('met_data', 'N/A')}",
            f"Start release:   {meta_dict.get('start_of_release', 'N/A')}",
            f"End release:     {meta_dict.get('end_of_release', 'N/A')}",
            f"Source strength: {meta_dict.get('source_strength', 'N/A')} g/s",
            f"Release loc:     {meta_dict.get('release_location', 'N/A')}",
            f"Release height:  {meta_dict.get('release_height', 'N/A')} m asl",
            f"Run duration:    {meta_dict.get('run_duration', 'N/A')}"
        ]
        full_text = "\n".join(lines)
        fig.text(0.15, 0.09, full_text, va='center', ha='left',
                 fontsize=9, family='monospace', color='black',
                 bbox=dict(facecolor='white', alpha=0.8, edgecolor='gray'))

    def _plot_frame(self, ax, data, lons, lats, title, levels, scale_label, proj, basemap_mode):
        ax.set_title(title)
        ax.set_extent([lons.min(), lons.max(), lats.min(), lats.max()])
        try:
            ax.coastlines(zorder=1)
            ax.add_feature(cfeature.BORDERS, linestyle=':', zorder=1)
            draw_etopo_basemap(ax, mode=self.basemap_mode, zoom=self.zoom_level)
        except:
            ax.add_feature(cfeature.OCEAN, zorder=0)
            ax.add_feature(cfeature.LAND, zorder=0)
            ax.coastlines(zorder=1)
            ax.add_feature(cfeature.BORDERS, linestyle=':', zorder=1)

        c = ax.contourf(lons, lats, data, levels=levels, cmap=self.cmap, alpha=0.6, transform=proj, zorder=2)
        ax.contour(lons, lats, data, levels=levels, colors='black', linewidths=0.5, transform=proj, zorder=2)

        raw = self.mutual_metadata.get('release_location')
        if raw:
            lon_str, lat_str = raw.strip().split()
            lon = float(lon_str[:-1]) * (1 if lon_str[-1].upper() == 'E' else -1)
            lat = float(lat_str[:-1]) * (1 if lat_str[-1].upper() == 'N' else -1)
            ax.plot(lon, lat, marker='^', color='red',
                    markersize=7, transform=proj, label="Vent Location", zorder=5)
            ax.legend(loc="upper left", fontsize=7)

        return c

    def interpolate_grid(self, data, lon_grid, lat_grid):
        data = np.where(data < 0, np.nan, data)
        mask = data > 0
        if np.count_nonzero(mask) < 10:
            return np.full_like(data, np.nan)

        points = np.column_stack((lon_grid[mask], lat_grid[mask]))
        values = data[mask]

        try:
            grid_z = griddata(points, values, (lon_grid, lat_grid), method='cubic')
        except Exception:
            try:
                grid_z = griddata(points, values, (lon_grid, lat_grid), method='linear')
            except Exception:
                grid_z = griddata(points, values, (lon_grid, lat_grid), method='nearest')
        
        return np.where(grid_z < 0, 0, grid_z)


    def plot_exceedance_map(self, var, contour_levels=10, save_dir=None):
        if var not in self.exceedance_probs:
            print(f"No exceedance data for variable '{var}'")
            return

        raw_data = self.exceedance_probs[var]
        self._extract_mutual_metadata()

       # Inside plot_exceedance_map, before interpolation
        lon_grid, lat_grid = np.meshgrid(self.lon, self.lat)
        interpolated_data = self.interpolate_grid(raw_data, lon_grid, lat_grid)


        if np.all(np.isnan(interpolated_data)):
            print(f"Skipping plot for {var}: all values are NaN after interpolation.")
            return

        proj = ccrs.PlateCarree()
        fig = plt.figure(figsize=(16, 8))
        ax1 = fig.add_subplot(1, 2, 1, projection=proj)
        ax2 = fig.add_subplot(1, 2, 2, projection=proj)

        levels = np.linspace(np.nanmin(interpolated_data), np.nanmax(interpolated_data), contour_levels)
        levels = np.unique(levels[levels > 0])
        if len(levels) < 2:
            print(f"Skipping plot for {var}: insufficient nonzero contour levels.")
            return

        # Full map plot
        cp1 = self._plot_frame(ax1, interpolated_data, self.lon, self.lat,
                            f"{var} Exceedance (Full)", levels,
                            f"P({var} > {self.threshold})", proj, "basemap")
        self._add_country_labels(ax1, [self.lon.min(), self.lon.max(), self.lat.min(), self.lat.max()])

        # Zoomed plot
        center_lat, center_lon = self._get_max_concentration_location(interpolated_data)
        lat_idx, lon_idx, lon_min, lon_max, lat_min, lat_max = self._get_zoom_indices(center_lat, center_lon)
        zoom_data = interpolated_data[np.ix_(lat_idx, lon_idx)]
        zoom_lat = self.lat[lat_idx]
        zoom_lon = self.lon[lon_idx]

        cp2 = self._plot_frame(ax2, zoom_data, zoom_lon, zoom_lat,
                            f"{var} Exceedance (Zoomed)", levels,
                            f"P({var} > {self.threshold})", proj, "basemap")
        self._add_country_labels(ax2, [lon_min, lon_max, lat_min, lat_max])

        # Colorbar
        cbar_ax = fig.add_axes([1, 0.25, 0.015, 0.5])
        cbar = fig.colorbar(cp2, cax=cbar_ax)

        units = {
            "air_concentration": "g/m³",
            "dry_deposition_rate": "g/m²/s",
            "wet_deposition_rate": "g/m²/s"
        }
        unit = units.get(var, "unknown")
        cbar.set_label(f"P({var} > {self.threshold:.3g} {unit})", fontsize=12)
        cbar.ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:.2g}'))

        self._draw_metadata_sidebar(fig, self.mutual_metadata)

        if save_dir:
            os.makedirs(save_dir, exist_ok=True)
            out_path = os.path.join(save_dir, f"exceedance_{var}.jpg")
            plt.savefig(out_path, bbox_inches='tight', dpi=200)
            plt.close("all")
            print(f"📸 Saved {out_path}")
        else:
            #plt.tight_layout()
            plt.show()
    
