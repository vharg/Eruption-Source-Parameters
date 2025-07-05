import os
import math
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.gridspec as gridspec
from scipy.interpolate import griddata, RegularGridInterpolator
from .interpolation import  create_grid, interpolate_grid

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cartopy.io.shapereader as shpreader
from adjustText import adjust_text

from predictor_generic import BAYESIAN_PREDICTOR
from .basemaps import draw_etopo_basemap

import matplotlib as mpl
mpl.rcParams['figure.max_open_warning'] = 0  # Suppress figure count warnings
import tempfile

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
    compute_summary_bayesian_exceedance()
        Computes average exceedance probability across all altitude levels.
    plot_exceedance_maps(save_dir=None, contour_levels=10)
        Plots exceedance probability maps for each altitude level.
    plot_summary_bayesian_exceedance(save_path=None, contour_levels=10, save_dir="Average_Exceedance_Probability")
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
    >>> analyzer.compute_summary_bayesian_exceedance()
    >>> analyzer.plot_exceedance_maps(save_dir="output/maps")
    >>> analyzer.plot_summary_bayesian_exceedance()
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
        """
        Initializes spatial grid from metadata if possible, else fall back to dataset.
        """
        if not self.mutual_metadata:
            self._extract_mutual_metadata()

        required_keys = [
            "x_origin", "y_origin", "x_res", "y_res", "x_grid_size", "y_grid_size"
        ]

        if all(k in self.mutual_metadata for k in required_keys):
            # Use metadata
            lon_grid, lat_grid = create_grid(self.mutual_metadata)
            self.lon = lon_grid[0, :]
            self.lat = lat_grid[:, 0]
            self.lon_grid = lon_grid
            self.lat_grid = lat_grid
        else:
            # Fallback to dataset coords
            with xr.open_dataset(reference_file) as ds:
                self.lat = ds["latitude"].values if "latitude" in ds.coords else np.arange(ds[self.variable].shape[1])
                self.lon = ds["longitude"].values if "longitude" in ds.coords else np.arange(ds[self.variable].shape[2])
                #self.lon_grid, self.lat_grid = np.meshgrid(self.lon, self.lat)
                lon_grid = self.lon_grid
                lat_grid = self.lat_grid


        self.grid_shape = self.lat_grid.shape


   

   

    def prepare_data(self):
        self._load_grid(self.nc_files[0])
        with xr.open_dataset(self.nc_files[0]) as first_ds:
            self.altitude_levels = first_ds[self.variable].shape[0]

        for z in range(self.altitude_levels):
            stack = np.zeros((len(self.nc_files), *self.grid_shape), dtype=np.float32)
            for t, file in enumerate(self.nc_files):
                with xr.open_dataset(file) as ds:
                    raw_data = ds[self.variable].values[z]

                    # ✅ Replace nodata/NaN with zero
                    raw_data = np.where(~np.isfinite(raw_data), 0, raw_data)

                    src_lat = ds['latitude'].values if 'latitude' in ds.coords else np.arange(raw_data.shape[0])
                    src_lon = ds['longitude'].values if 'longitude' in ds.coords else np.arange(raw_data.shape[1])
                    #interpolated = self._interpolate_to_grid(raw_data, src_lat, src_lon)
                    interpolated=interpolate_grid(raw_data,self.lat, self.lon, self.mutual_metadata)

                    # Also fill NaNs in interpolated result
                    interpolated = np.where(~np.isfinite(interpolated), 0, interpolated)

                    stack[t] = interpolated

            self.altitude_data[z] = stack

    def compute_bayesian_exceedance(self):
        from tqdm import tqdm
        import logging


        for z, stack in self.altitude_data.items():
            prob_map = np.full(self.grid_shape, np.nan, dtype=np.float32)

            total_cells = self.grid_shape[0] * self.grid_shape[1]
            pbar = tqdm(total=total_cells, desc=f"Processing altitude {z+1} km", unit="cell")

            for i in range(self.grid_shape[0]):
                for j in range(self.grid_shape[1]):
                    y = stack[:, i, j]
                    pbar.update(1)

                    # Skip invalid data
                    if np.any(np.isnan(y)) or np.all(y <= 0):
                        continue

                    try:
                        data_dict = {
                            'time': np.arange(len(y)),
                            'ash_concentration': y
                        }

                        predictor = BAYESIAN_PREDICTOR(
                            pd.DataFrame(data_dict),
                            xvar='time',
                            yvar='ash_concentration',
                            show_plots=False
                        )

                        samples = predictor.sample_posterior(1000)
                        x_log = np.log10(len(y))
                        y_preds = samples['intercept'].values + samples['slope'].values * x_log

                        if self.threshold > 0:
                            log_threshold = np.log10(self.threshold)
                            prob = np.mean(y_preds > log_threshold)
                        else:
                            y_preds_clipped = np.clip(y_preds, -10, 5)
                            y_preds_linear = np.power(10, y_preds_clipped)
                            prob = np.mean(y_preds_linear)

                        prob_map[i, j] = np.float32(prob)

                    except Exception as e:
                        logging.warning(f"Bayesian prediction failed at z={z}, i={i}, j={j}: {e}")
                        continue

            pbar.close()
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

   
    
    def _get_zoom_indices(self, data):
        """
        Determines zoom indices covering all cells with data >0.
        If no cells >0, fallback to center of grid.
        Returns:
            lat_idx, lon_idx, lon_min, lon_max, lat_min, lat_max
        """
        mask = data > 0

        if not np.any(mask):
            # No valid data—fallback to center
            center_lat = np.nanmean(self.lat) if isinstance(self.lat, np.ndarray) else self.lat
            center_lon = np.nanmean(self.lon) if isinstance(self.lon, np.ndarray) else self.lon
            logger.warning("No valid exceedance data >0. Using grid center for zoom.")
            lat_idx = np.arange(len(self.lat))
            lon_idx = np.arange(len(self.lon))
            return lat_idx, lon_idx, self.lon.min(), self.lon.max(), self.lat.min(), self.lat.max()

        # Get indices where data >0
        rows, cols = np.where(mask)

        # Compute min/max of lat/lon covering all nonzero data
        lat_min = self.lat[rows.min()]
        lat_max = self.lat[rows.max()]
        lon_min = self.lon[cols.min()]
        lon_max = self.lon[cols.max()]

        # Determine index ranges
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

   
    
    

    def _plot_frame(self, ax, data, lons, lats, title, levels=None, scale_label=None, proj=None, basemap_mode=None):
        
         # Ensure NaNs are replaced by zeros
        #data = np.nan_to_num(data, nan=0)
        # data=interpolate_grid(data, lons, lats, self.mutual_metadata)
        # data = np.nan_to_num(data, nan=0)
        from matplotlib.ticker import MaxNLocator
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

        # Automatically determine contour levels if not specified
        if levels is None:
            vmin = np.nanmin(data)
            vmax = np.nanmax(data)
            if np.isclose(vmin, vmax):
                vmin -= 1
                vmax += 1
            locator = MaxNLocator(nbins=12)
            levels = locator.tick_values(vmin, vmax)
            # Ensure 0 is included
            if 0 not in levels:
                levels = np.sort(np.append(levels, 0))

        # Plot filled and line contours
        c = ax.contourf(lons, lats, data, levels=levels, cmap=self.cmap,
                        alpha=0.6, transform=proj, zorder=2, extend="both")
        ax.contour(lons, lats, data, levels=levels, colors='black',
                linewidths=0.5, transform=proj, zorder=2)

        # Extract and plot vent location (if available)
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

    def compute_summary_bayesian_exceedance(self):
        if not self.exceedance_probs:
            raise ValueError("Run compute_bayesian_exceedance() first.")
        all_maps = [v for v in self.exceedance_probs.values()]
        #if summary_exceedance_Map=='mean':
        self.average_exceedance_map = np.nanmean(np.stack(all_maps), axis=0)
        #if summary_exceedance_Map=='max':
        self.max_exceedance_map = np.nanmax(np.stack(all_maps), axis=0)
        return self.average_exceedance_map, self.max_exceedance_map

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
        
        if save_dir:
            run_name = self.mutual_metadata.get('run_name')
            save_dir = os.path.abspath(
            os.path.join(
                os.environ.get("NAME_OUTPUT_DIR", tempfile.gettempdir()),
                save_dir + "/"+ run_name))
            os.makedirs(save_dir, exist_ok=True)
    
        for z_m, data in self.exceedance_probs.items():
            proj = ccrs.PlateCarree()
            fig = plt.figure(figsize=(16, 8))
            ax1 = fig.add_subplot(1, 2, 1, projection=proj)
            ax2 = fig.add_subplot(1, 2, 2, projection=proj)

            if not np.any(np.isfinite(data)):
                continue

            #lon_grid, lat_grid = np.meshgrid(self.lon, self.lat)
            lon_grid = self.lon_grid
            lat_grid = self.lat_grid

            
            points = np.column_stack((lon_grid.ravel(), lat_grid.ravel()))
            values = data.ravel()
            mask = np.isfinite(values)
            # if np.count_nonzero(mask) < 16:
            #     continue

            data_interp = griddata(points[mask], values[mask], (lon_grid, lat_grid), method='cubic', fill_value=0, rescale =True)
            data_interp = np.clip(data_interp, 0, 1)

            min_val, max_val = np.nanmin(data_interp), np.nanmax(data_interp)
            if not np.isfinite(min_val) or not np.isfinite(max_val) or min_val == max_val:
                continue

            levels = np.linspace(min_val, max_val, contour_levels) if isinstance(contour_levels, int) else np.asarray(contour_levels)
            # if len(levels) < 2:
            #     continue

            
            
            
            
            levels=None
            cp1 = self._plot_frame(ax1, data_interp, self.lon, self.lat, f"Altitude {z_m}m (Full)",
                                    levels, f"P(Ash > {self.threshold} g/m³)", proj, self.basemap_mode)
            self._add_country_labels(ax1, [self.lon.min(), self.lon.max(), self.lat.min(), self.lat.max()])

            center_lat, center_lon = self._get_max_concentration_location(data_interp)
            lat_idx, lon_idx, lon_min, lon_max, lat_min, lat_max = self._get_zoom_indices(data_interp)
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
               
                file_path = os.path.join(save_dir, f"exceedance_{z_m}m.jpg")
                plt.savefig(file_path, bbox_inches="tight", dpi=200)
                plt.close(fig)

                print(f"📸 Saved plot: {file_path}")
            else:
                plt.show()

   

    def plot_summary_bayesian_exceedance( self, save_dir="summary_Exceedance_Probability", contour_levels=10):
        """
        Plot and save both the average and maximum exceedance probability maps.
        """
        if not hasattr(self, "average_exceedance_map") or not hasattr(self, "max_exceedance_map"):
            raise ValueError(
                "Run compute_summary_bayesian_exceedance() first to generate summary maps."
            )

        proj = ccrs.PlateCarree()

        def _plot_and_save(data, title_prefix, filename_suffix):
            fig, (ax1, ax2) = plt.subplots(
                1, 2, figsize=(16, 8), subplot_kw={"projection": proj}
            )

            lon_grid = self.lon_grid
            lat_grid = self.lat_grid

            # Flatten
            points = np.column_stack((lon_grid.ravel(), lat_grid.ravel()))
            values = data.ravel()
            mask = np.isfinite(values)

            if np.count_nonzero(mask) < 16:
                print(f"⚠ Skipping {title_prefix} plot: insufficient valid data for interpolation")
                return

            # Interpolate
            data_interp = griddata(
                points[mask],
                values[mask],
                (lon_grid, lat_grid),
                method="cubic",
                rescale=True,
                fill_value=0,
            )
            data_interp = np.clip(data_interp, 0, 1)

            min_val, max_val = np.nanmin(data_interp), np.nanmax(data_interp)

            levels = (
                np.linspace(min_val, max_val, contour_levels)
                if isinstance(contour_levels, int)
                else contour_levels
            )

            # Full view
            cp1 = self._plot_frame(
                ax1,
                data_interp,
                self.lon,
                self.lat,
                f"{title_prefix} (Full)",
                levels,
                proj,
                
            )
            self._add_country_labels(
                ax1, [self.lon.min(), self.lon.max(), self.lat.min(), self.lat.max()]
            )

            # Zoom
            lat_idx, lon_idx, lon_min, lon_max, lat_min, lat_max = self._get_zoom_indices(data_interp)
            zoom_data = data_interp[np.ix_(lat_idx, lon_idx)]
            zoom_lat = self.lat[lat_idx]
            zoom_lon = self.lon[lon_idx]

            cp2 = self._plot_frame(
                ax2,
                zoom_data,
                zoom_lon,
                zoom_lat,
                f"{title_prefix} (Zoomed)",
                levels,
                proj,
               
            )
            self._add_country_labels(ax2, [lon_min, lon_max, lat_min, lat_max])

            # Colorbar
            cbar_ax = fig.add_axes([1, 0.25, 0.015, 0.5])
            cbar = fig.colorbar(cp2, cax=cbar_ax)
            cbar.set_label(f"{title_prefix}", fontsize=12)
            cbar.ax.tick_params(labelsize=9)
            cbar.ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.2g}"))

            # Sidebar
            mutual_meta = self._extract_mutual_metadata()
            self._draw_metadata_sidebar(fig, mutual_meta)

            # Save
            if save_dir:
                run_name = mutual_meta.get("run_name", "unknown_run")
                out_dir = os.path.abspath(
                    os.path.join(
                        os.environ.get("NAME_OUTPUT_DIR", tempfile.gettempdir()),
                        save_dir,
                        run_name,
                    )
                )
                os.makedirs(out_dir, exist_ok=True)
                file_path = os.path.join(out_dir, f"{filename_suffix}.jpg")
                plt.savefig(file_path, bbox_inches="tight", dpi=200)
                plt.close("all")
                print(f"📸 Saved {file_path}")
            else:
                plt.show()

        # Plot average exceedance
        _plot_and_save(
            self.average_exceedance_map,
            title_prefix=f"Average Exceedance Probability (> {self.threshold} g/m³)",
            filename_suffix=f"Average_Exceedance_Probability_{self.threshold}",
        )

        # Plot maximum exceedance
        _plot_and_save(
            self.max_exceedance_map,
            title_prefix=f"Maximum Exceedance Probability (> {self.threshold} g/m³)",
            filename_suffix=f"Maximum_Exceedance_Probability_{self.threshold}",
        )

        
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

            #lon_grid, lat_grid = np.meshgrid(self.lon, self.lat)
            
            lon_grid = self.lon_grid
            lat_grid = self.lat_grid

            points = np.column_stack((lon_grid.ravel(), lat_grid.ravel()))
            values = data.ravel()
            mask = np.isfinite(values)
            if np.count_nonzero(mask) < 16:
                ax.set_title(f"{z}m (insufficient data)")
                ax.axis('off')
                continue

            data_interp = griddata(points[mask], values[mask], (lon_grid_fine, lat_grid_fine), method='cubic', rescale=True, fill_value=0)
            data_interp = np.clip(data_interp, 0, 1)
            if np.all(np.isnan(data_interp)):
                ax.set_title(f"{z}m (interp failed)")
                ax.axis('off')
                continue

            min_val, max_val = np.nanmin(data_interp), np.nanmax(data_interp)
            levels = np.linspace(min_val, max_val, contour_levels) if isinstance(contour_levels, int) else contour_levels

            levels=None #### set levels to None automtically assign contour intervals
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
            
            run_name = self.mutual_metadata.get('run_name')
            save_dir = os.path.abspath(
            os.path.join(
                os.environ.get("NAME_OUTPUT_DIR", tempfile.gettempdir()),
                save_dir + "/"+ run_name))
             
            os.makedirs(save_dir, exist_ok=True)
            file_path = os.path.join(save_dir, f"Exceedance_probability_ashThresh{self.threshold}_all_ZLevels_singlePlot.jpg")
            plt.savefig(file_path, bbox_inches="tight", dpi=200)
            plt.close("all")
            print(f"📸 Saved {file_path}")
        else:
            plt.show()
            
        ##############################
        # Below commented code is Useless :D
    # def compute_exceedance_probability_time_series(self):
    #     """
    #     Computes the temporal evolution of exceedance probability over all grid cells.

    #     This method loops over each timestep and altitude level, computing the fraction of grid cells
    #     where ash concentration exceeds the specified threshold.

    #     The result is stored in:
    #         self.exceedance_time_series[z_level] = pd.DataFrame with columns:
    #             - 'time_index'
    #             - 'fraction_exceeding'

    #     This allows visualizing exceedance probability as a function of time.
    #     """
    #     self.exceedance_time_series = {}
    #     if not self.altitude_data:
    #         raise ValueError("You must call prepare_data() first to load data.")
        
    #     for z, stack in self.altitude_data.items():
    #         n_timesteps = stack.shape[0]
    #         fractions = []
    #         for t in range(n_timesteps):
    #             data_t = stack[t]
    #             n_valid = np.sum(np.isfinite(data_t))
    #             n_exceed = np.sum(data_t > self.threshold)
    #             fraction = n_exceed / n_valid if n_valid > 0 else np.nan
    #             fractions.append(fraction)

    #         df = pd.DataFrame({
    #             "time_index": np.arange(n_timesteps),
    #             "fraction_exceeding": fractions
    #         })
    #         self.exceedance_time_series[z] = df

        
    #     def plot_exceedance_probability_time_series(self, z_level=None, contour_levels=10, save_dir=None):
    #         """
    #         Plots exceedance probability time series along with map snapshots of the last timestep.

    #         This visualization includes:
    #             - Time series of fraction of grid cells exceeding the threshold.
    #             - Full map of exceedance at the last timestep.
    #             - Zoomed-in map around the highest exceedance region.
    #             - Metadata annotation sidebar.
    #             - Country labels.
    #             - Colorbar for concentration.

    #         Parameters
    #         ----------
    #         z_level : int, optional
    #             Altitude level index to plot. If None, uses the lowest altitude.
    #         contour_levels : int or array-like, optional
    #             Number of contour intervals or explicit levels for color mapping.
    #         save_dir : str, optional
    #             Directory to save the figure. If None, displays the figure interactively.
    #         """
    #         import matplotlib.gridspec as gridspec

    #         if not hasattr(self, "exceedance_time_series"):
    #             raise ValueError("Run compute_exceedance_probability_time_series() first.")

    #         if z_level is None:
    #             z_level = min(self.exceedance_time_series.keys())

    #         df = self.exceedance_time_series[z_level]
    #         last_timestep = self.altitude_data[z_level][-1]

    #         proj = ccrs.PlateCarree()
    #         fig = plt.figure(figsize=(20, 12))
    #         gs = gridspec.GridSpec(
    #             2, 3, width_ratios=[1, 1, 0.2], height_ratios=[1, 1], figure=fig
    #         )

    #         # Time series plot
    #         ax_ts = fig.add_subplot(gs[0, :2])
    #         ax_ts.plot(
    #             df["time_index"],
    #             df["fraction_exceeding"],
    #             marker="o",
    #             color="tab:blue",
    #             label=f"Altitude {z_level*1000} m"
    #         )
    #         ax_ts.set_xlabel("Time Index")
    #         ax_ts.set_ylabel(f"Fraction Exceeding {self.threshold} g/m³")
    #         ax_ts.set_title("Temporal Evolution of Exceedance Probability")
    #         ax_ts.grid(True)
    #         ax_ts.legend()

    #         # Determine contour levels
    #         vmin = np.nanmin(last_timestep)
    #         vmax = np.nanmax(last_timestep)
    #         if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin == vmax:
    #             vmin, vmax = 0, 1
    #         if isinstance(contour_levels, int):
    #             levels = np.linspace(vmin, vmax, contour_levels)
    #         else:
    #             levels = np.asarray(contour_levels)

    #         # Full map of last timestep
    #         ax_map = fig.add_subplot(gs[1, 0], projection=proj)
    #         cp1 = self._plot_frame(
    #             ax_map,
    #             last_timestep,
    #             self.lon,
    #             self.lat,
    #             title=f"Exceedance Map - Last Timestep (Full View)",
    #             levels=levels,
    #             scale_label=f"Ash Concentration (g/m³)",
    #             proj=proj,
    #             basemap_mode=self.basemap_mode
    #         )
    #         self._add_country_labels(
    #             ax_map, [self.lon.min(), self.lon.max(), self.lat.min(), self.lat.max()]
    #         )

    #         # Zoomed-in map of last timestep
    #         lat_idx, lon_idx, lon_min, lon_max, lat_min, lat_max = self._get_zoom_indices(last_timestep)
    #         zoom_data = last_timestep[np.ix_(lat_idx, lon_idx)]
    #         zoom_lat = self.lat[lat_idx]
    #         zoom_lon = self.lon[lon_idx]
    #         ax_zoom = fig.add_subplot(gs[1, 1], projection=proj)
    #         cp2 = self._plot_frame(
    #             ax_zoom,
    #             zoom_data,
    #             zoom_lon,
    #             zoom_lat,
    #             title=f"Exceedance Map - Zoomed View",
    #             levels=levels,
    #             scale_label=f"Ash Concentration (g/m³)",
    #             proj=proj,
    #             basemap_mode=self.basemap_mode
    #         )
    #         ax_zoom.set_extent([lon_min, lon_max, lat_min, lat_max], crs=proj)
    #         self._add_country_labels(ax_zoom, [lon_min, lon_max, lat_min, lat_max])

    #         # Colorbar for maps
    #         cbar_ax = fig.add_axes([0.92, 0.15, 0.02, 0.65])
    #         cbar = fig.colorbar(cp2, cax=cbar_ax)
    #         cbar.set_label(f"Ash Concentration (g/m³)", fontsize=11)
    #         cbar.ax.tick_params(labelsize=9)
    #         cbar.ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.2g}"))

    #         # Metadata sidebar
    #         ax_meta = fig.add_subplot(gs[:, 2])
    #         mutual_meta = self._extract_mutual_metadata()
    #         self._draw_metadata_sidebar(fig, mutual_meta, ax=ax_meta)

    #         plt.tight_layout(rect=[0, 0, 0.9, 1])

    #         if save_dir:
    #             # Compose directory path
    #             run_name = mutual_meta.get("run_name", "unknown_run")
    #             out_dir = os.path.abspath(
    #                 os.path.join(
    #                     os.environ.get("NAME_OUTPUT_DIR", tempfile.gettempdir()),
    #                     save_dir,
    #                     run_name
    #                 )
    #             )
    #             os.makedirs(out_dir, exist_ok=True)
    #             file_path = os.path.join(
    #                 out_dir,
    #                 f"Exceedance_TimeSeries_Altitude{z_level*1000}_Thresh{self.threshold}.jpg"
    #             )
    #             plt.savefig(file_path, bbox_inches="tight", dpi=200)
    #             plt.close("all")
    #             print(f"📸 Saved {file_path}")
    #         else:
    #             plt.show()

        
        ############################
            
            
#######################################################################################################



import numpy as np
import pandas as pd
import xarray as xr
import os
import logging
from scipy.interpolate import RegularGridInterpolator, griddata
from predictor_generic import BAYESIAN_PREDICTOR
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.ticker as mticker
from cartopy.io import shapereader as shpreader
from adjustText import adjust_text
from tqdm.auto import tqdm
from .basemaps import draw_etopo_basemap
from .interpolation import interpolate_grid
import tempfile

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


class MultiFieldExceedanceAnalyzer_2D:
    """
    A class to analyze exceedance probabilities of multiple fields using 2D netCDF datasets.

    Exceedance probability measures the likelihood that a variable exceeds a specified threshold
    at each grid cell over time. For example, it can represent the probability that air concentration
    exceeds a safety limit.

    How Exceedance Is Calculated:
    -----------------------------------
    For each grid cell:
    1. The time series of values is extracted (one value per timestep).
    2. A Bayesian linear regression is fitted to the log10-transformed values over time.
    3. From the posterior samples of the regression model, predictions are generated.
    4. The exceedance probability is estimated as the fraction of samples where the predicted value
    exceeds the threshold (log-transformed).
    5. The median of the predicted values (back-transformed to linear scale) is also computed.

    The resulting exceedance map visualizes this probability spatially across the study area,
    helping identify regions where thresholds are more likely to be exceeded.

    Features:
    ----------
    - Supports multiple variables from netCDF files.
    - Automatically builds the spatial grid from latitude/longitude variables or metadata.
    - Interpolates input data onto a common grid.
    - Visualizes exceedance probabilities as contour maps with country boundaries and optional vent locations.
    - Provides both full and zoomed-in plots.
    - Logs computation steps and any issues.
    
    """

    def __init__(self, nc_file_dir, variables=None, threshold=0.008,
                 cmap='viridis', basemap_mode='basemap', zoom_level=10):
        if variables is None:
            variables = ['air_concentration', 'dry_deposition_rate', 'wet_deposition_rate']

        nc_file_paths = [
            os.path.join(root, file)
            for root, _, files in os.walk(nc_file_dir)
            for file in files if file.endswith(".nc")
        ]
        if not nc_file_paths:
            logger.error(f"No .nc files found in directory: {nc_file_dir}")
            raise FileNotFoundError(f"No .nc files found in directory: {nc_file_dir}")

        self.nc_files = sorted(nc_file_paths)
        self.variables = variables
        self.threshold = threshold
        self.cmap = cmap
        self.basemap_mode = basemap_mode
        self.zoom_level = zoom_level

        self.lat = None
        self.lon = None
        self.grid_shape = None
        self.data_stacks = {var: [] for var in variables}
        self.exceedance_probs = {}
        self.predicted_medians = {}
        self.mutual_metadata = {}

        self.zoom_width = 5
        self.zoom_height = 5

        self._load_country_geometries()
        self._extract_mutual_metadata()
        
        #self.interpolate_grid=interpolate_grid()

    def _define_grid(self):
        """
        Defines the common grid for interpolation based on metadata or coordinate variables.
        """
        ds = xr.open_dataset(self.nc_files[0])
        attrs = ds.attrs

        if "latitude" in ds and "longitude" in ds:
            lat = ds["latitude"].values
            lon = ds["longitude"].values
            if lat.ndim == 1 and lon.ndim == 1:
                self.lat = lat
                self.lon = lon
                logger.info("Grid defined using latitude/longitude variables.")
            else:
                logger.error("2D curvilinear grids are not supported.")
                raise NotImplementedError("2D curvilinear grids are not supported.")
        else:
            try:
                if all(k in attrs for k in ("x_origin", "y_origin", "x_res", "y_res", "latitude_points", "longitude_points")):
                    x_origin = attrs["x_origin"]
                    y_origin = attrs["y_origin"]
                    x_res = attrs["x_res"]
                    y_res = attrs["y_res"]
                    lat_pts = attrs["latitude_points"]
                    lon_pts = attrs["longitude_points"]
                    self.lat = y_origin + y_res * np.arange(lat_pts)
                    self.lon = x_origin + x_res * np.arange(lon_pts)
                    logger.info(
                        f"Grid defined from x_origin/y_origin and resolution: "
                        f"x_origin={x_origin}, y_origin={y_origin}, "
                        f"x_res={x_res}, y_res={y_res}, "
                        f"latitude_points={lat_pts}, longitude_points={lon_pts}"
                    )
                elif all(k in attrs for k in ("latitude_min", "latitude_max", "longitude_min", "longitude_max", "latitude_points", "longitude_points")):
                    lat_min = attrs["latitude_min"]
                    lat_max = attrs["latitude_max"]
                    lon_min = attrs["longitude_min"]
                    lon_max = attrs["longitude_max"]
                    lat_pts = attrs["latitude_points"]
                    lon_pts = attrs["longitude_points"]
                    self.lat = np.linspace(lat_min, lat_max, lat_pts)
                    self.lon = np.linspace(lon_min, lon_max, lon_pts)
                    logger.info(
                        f"Grid defined using latitude/longitude min/max: "
                        f"lat [{lat_min}, {lat_max}] ({lat_pts}), "
                        f"lon [{lon_min}, {lon_max}] ({lon_pts})"
                    )
                else:
                    logger.error("Metadata is incomplete. Expected either (x_origin/y_origin/x_res/y_res) with points or (lat/lon min/max) with points.")
                    raise KeyError("Missing grid metadata.")
            except KeyError as e:
                logger.error(f"Missing metadata attribute: {e}")
                raise

        self.grid_shape = (len(self.lat), len(self.lon))
        ds.close()
        
        
    def _interpolate_to_grid(self, data, src_lat, src_lon):
        interpolator = RegularGridInterpolator(
            (src_lat, src_lon),
            data,
            bounds_error=False,
            fill_value=0
        )
        lon_grid, lat_grid = np.meshgrid(self.lon, self.lat)
        interpolated = interpolator(np.column_stack([lat_grid.ravel(), lon_grid.ravel()])).reshape(self.grid_shape)
       
        
        
        
        return np.nan_to_num(interpolated, nan=0)
    
    
    

    def prepare_data(self):
        self._define_grid()
        logger.info("Preparing data...")
        for file in tqdm(self.nc_files, desc="Interpolating files", unit="file", dynamic_ncols=True):
            ds = xr.open_dataset(file)
            src_lat = ds["latitude"].values
            src_lon = ds["longitude"].values
            for var in tqdm(self.variables, desc=f"Variables in {os.path.basename(file)}", leave=False, unit="var"):
                interpolated = self._interpolate_to_grid(ds[var].values, self.lat, self.lon)
                self.data_stacks[var].append(interpolated)
            ds.close()
        for var in self.variables:
            self.data_stacks[var] = np.stack(self.data_stacks[var], axis=0)
        logger.info("Data preparation complete.")

    # def compute_bayesian_exceedance(self):
    #     logger.info("Computing exceedance probabilities...")
    #     for var, stack in self.data_stacks.items():
    #         prob_map = np.full(self.grid_shape, np.nan, dtype=np.float32)
    #         median_map = np.full(self.grid_shape, np.nan, dtype=np.float32)
    #         flat_indices = list(np.ndindex(self.grid_shape))

    #         pbar = tqdm(flat_indices, desc=f"Computing '{var}'", unit="cell", dynamic_ncols=True)

    #         for i, j in pbar:
    #             y = stack[:, i, j]
    #             if np.all(np.isnan(y)) or np.all(y <= 0):
    #                 continue
    #             y = y[y > 0]
    #             if len(y) < 2:
    #                 continue
    #             prob, median = self._compute_cell_exceedance(var, y)
    #             prob_map[i, j] = prob
    #             median_map[i, j] = median

    #         self.exceedance_probs[var] = np.nan_to_num(prob_map, nan=0)
    #         self.predicted_medians[var] = np.nan_to_num(median_map, nan=0)

    #     logger.info("Exceedance computation complete.")

    def _compute_cell_exceedance(self, var, y):
        try:
            df = pd.DataFrame({'time': np.arange(len(y)), var: y})
            predictor = BAYESIAN_PREDICTOR(df, xvar='time', yvar=var, show_plots=False)
            samples = predictor.sample_posterior(1000)
            x_log = np.log10(len(y))
            y_preds_log = samples['intercept'].values + samples['slope'].values * x_log
            prob = np.mean(y_preds_log > np.log10(self.threshold))
            median_pred = np.median(np.power(10, np.clip(y_preds_log, -10, 5)))
            return np.float32(prob), np.float32(median_pred)
        except Exception as e:
            logger.error(f"Error in exceedance computation for {var}: {e}")
            return np.nan, np.nan
    
    def compute_bayesian_exceedance(self, variable=None):
        """
        Compute exceedance probabilities and predicted medians.

        Parameters
        ----------
        variable : str or None
            If provided, compute only for this variable.
            If None (default), compute for all variables.
        """
        if variable:
            if variable not in self.data_stacks:
                logger.error(f"Variable '{variable}' not found in prepared data.")
                raise ValueError(f"Variable '{variable}' not found.")
            variables_to_compute = [variable]
        else:
            variables_to_compute = list(self.data_stacks.keys())

        logger.info("Computing exceedance probabilities...")

        for var in variables_to_compute:
            stack = self.data_stacks[var]
            prob_map = np.full(self.grid_shape, np.nan, dtype=np.float32)
            median_map = np.full(self.grid_shape, np.nan, dtype=np.float32)
            flat_indices = list(np.ndindex(self.grid_shape))

            pbar = tqdm(flat_indices, desc=f"Computing '{var}'", unit="cell", dynamic_ncols=True)

            for i, j in pbar:
                y = stack[:, i, j]
                if np.all(np.isnan(y)) or np.all(y <= 0):
                    continue
                y = y[y > 0]
                if len(y) < 2:
                    continue
                prob, median = self._compute_cell_exceedance(var, y)
                prob_map[i, j] = prob
                median_map[i, j] = median

            self.exceedance_probs[var] = np.nan_to_num(prob_map, nan=0)
            self.predicted_medians[var] = np.nan_to_num(median_map, nan=0)

        logger.info("Exceedance computation complete.")



    def _load_country_geometries(self):
        shp = shpreader.natural_earth(resolution='110m', category='cultural', name='admin_0_countries')
        self.country_geoms = list(shpreader.Reader(shp).records())

    def _extract_mutual_metadata(self):
        all_attrs = []
        for path in self.nc_files:
            with xr.open_dataset(path) as ds:
                all_attrs.append(ds.attrs)
        if not all_attrs:
            return {}
        keys = set(all_attrs[0]).intersection(*[set(d) for d in all_attrs[1:]])
        self.mutual_metadata = {k: all_attrs[0][k] for k in keys}
        return self.mutual_metadata

    def _get_max_concentration_location(self, data):
        if np.all(data == 0):
            return np.mean(self.lat), np.mean(self.lon)
        idx = np.unravel_index(np.nanargmax(data), data.shape)
        return self.lat[idx[0]], self.lon[idx[1]]

    def _get_zoom_indices(self, data):
        """
        Determines zoom indices covering all cells with data >0.
        If no valid data, returns indices covering the full grid.
        Returns:
            lat_idx, lon_idx, lon_min, lon_max, lat_min, lat_max
        """
        mask = data > 0

        if not np.any(mask):
            # No valid data
            logger.warning("No valid exceedance data >0. Using full grid extent for zoom.")
            lat_idx = np.arange(len(self.lat))
            lon_idx = np.arange(len(self.lon))
            return (
                lat_idx,
                lon_idx,
                self.lon.min(),
                self.lon.max(),
                self.lat.min(),
                self.lat.max()
            )

        # Find bounding box of nonzero data
        rows, cols = np.where(mask)
        lat_min = self.lat[rows.min()]
        lat_max = self.lat[rows.max()]
        lon_min = self.lon[cols.min()]
        lon_max = self.lon[cols.max()]

        # Determine index ranges
        lat_idx = np.where((self.lat >= lat_min) & (self.lat <= lat_max))[0]
        lon_idx = np.where((self.lon >= lon_min) & (self.lon <= lon_max))[0]

        return lat_idx, lon_idx, lon_min, lon_max, lat_min, lat_max
    
    
    # def _get_zoom_indices(self, center_lat, center_lon):
    #     lon_min = center_lon - self.zoom_width / 2
    #     lon_max = center_lon + self.zoom_width / 2
    #     lat_min = center_lat - self.zoom_height / 2
    #     lat_max = center_lat + self.zoom_height / 2
    #     lat_idx = np.where((self.lat >= lat_min) & (self.lat <= lat_max))[0]
    #     lon_idx = np.where((self.lon >= lon_min) & (self.lon <= lon_max))[0]
    #     return lat_idx, lon_idx, lon_min, lon_max, lat_min, lat_max

    # def interpolate_grid(self, data, lon_grid, lat_grid):
    #     mask = data > 0
    #     if np.count_nonzero(mask) < 10:
    #         return np.zeros_like(data)
    #     points = np.column_stack((lon_grid[mask], lat_grid[mask]))
    #     values = data[mask]
    #     for method in ["cubic", "linear", "nearest"]:
    #         try:
    #             z = griddata(points, values, (lon_grid, lat_grid), method=method)
    #             return np.nan_to_num(z, nan=0)
    #         except Exception as e:
    #             logger.warning(f"Interpolation with method {method} failed: {e}")
    #             continue
    #     return np.zeros_like(data)

    def _plot_frame(self, ax, data, lons, lats, title, levels, proj, var):
        
        
        ax.set_title(f"{title}\nThreshold: {self.threshold}")
        ax.set_extent([lons.min(), lons.max(), lats.min(), lats.max()])
        ax.coastlines()
        ax.add_feature(cfeature.BORDERS, linestyle=':')
        draw_etopo_basemap(ax, mode=self.basemap_mode, zoom=self.zoom_level)
        c = ax.contourf(
            lons, lats, data,
            levels=levels,
            cmap=self.cmap,
            alpha=0.4,
            transform=proj
        )
        ax.contour(lons, lats, data, levels=levels, colors='black', linewidths=0.2, transform=proj)
        return c

    def _add_country_labels(self, ax, extent):
        proj = ccrs.PlateCarree()
        texts = []
        for country in self.country_geoms:
            name = country.attributes.get('NAME_LONG', '')
            geom = country.geometry
            try:
                lon, lat = geom.centroid.x, geom.centroid.y
                if extent[0] <= lon <= extent[1] and extent[2] <= lat <= extent[3]:
                    text = ax.text(
                        lon, lat, name, fontsize=6, transform=proj,
                        ha='center', va='center', color='white',
                        bbox=dict(facecolor='black', alpha=0.5, linewidth=0)
                    )
                    texts.append(text)
            except Exception:
                continue
        adjust_text(
            texts, ax=ax, only_move={'points': 'y', 'text': 'y'},
            arrowprops=dict(arrowstyle="->", color='white', lw=0.5)
        )

    def plot_exceedance_map(self, var, contour_levels=10, save_dir=None):
        if var not in self.exceedance_probs:
            logger.warning(f"No data for variable '{var}'.")
            return

        
        raw_data = self.exceedance_probs[var]
        lon_grid, lat_grid = np.meshgrid(self.lon, self.lat)
        data_filled = interpolate_grid(raw_data, lon_grid, lat_grid, self.mutual_metadata)
        data_filled = np.clip(data_filled, 0, 1)
        units = {
            'air_concentration': 'g/m³',
            'dry_deposition_rate': 'g/m²',
            'wet_deposition_rate': 'g/m²'
        }
        unit = units.get(var, 'unknown')

        proj = ccrs.PlateCarree()
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8), subplot_kw={'projection': proj})

        max_val = np.nanmax(data_filled)
        levels = np.linspace(0, max_val if max_val > 0 else 1, contour_levels)

        cp1 = self._plot_frame(
            ax1, data_filled, self.lon, self.lat,
            f"{var} Exceedance (Full)\nUnits: {unit}", levels, proj, var
        )
        self._add_country_labels(ax1, [self.lon.min(), self.lon.max(), self.lat.min(), self.lat.max()])

        center_lat, center_lon = self._get_max_concentration_location(data_filled)
        lat_idx, lon_idx, lon_min, lon_max, lat_min, lat_max = self._get_zoom_indices(data_filled)
        zoom_data = data_filled[np.ix_(lat_idx, lon_idx)]
        zoom_lats = self.lat[lat_idx]
        zoom_lons = self.lon[lon_idx]

        cp2 = self._plot_frame(
            ax2, zoom_data, zoom_lons, zoom_lats,
            f"{var} Exceedance (Zoomed)\nUnits: {unit}", levels, proj, var
        )
        self._add_country_labels(ax2, [lon_min, lon_max, lat_min, lat_max])

        if 'release_location' in self.mutual_metadata:
            try:
                lon_str, lat_str = self.mutual_metadata['release_location'].strip().split()
                lon = float(lon_str[:-1]) * (1 if lon_str[-1] == 'E' else -1)
                lat = float(lat_str[:-1]) * (1 if lat_str[-1] == 'N' else -1)
                for ax in (ax1, ax2):
                    ax.plot(lon, lat, marker='^', color='red', markersize=7, transform=proj, label="Vent")
                    ax.legend(fontsize=7)
            except Exception as e:
                #logger.error(f"Failed to parse release_location: {e}")
                pass

        cbar_ax = fig.add_axes([1, 0.25, 0.015, 0.5])
        cbar = fig.colorbar(cp2, cax=cbar_ax)
        cbar.set_label(f"P({var} > {self.threshold} {unit})")
        cbar.ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:.2g}'))

        self._draw_metadata_sidebar(fig, self.mutual_metadata)
        
        run_name=self.mutual_metadata['run_name']
                
        

        if save_dir:
            
            save_dir = os.path.abspath(
            os.path.join(
                os.environ.get("NAME_OUTPUT_DIR", tempfile.gettempdir()),
                save_dir + "/"+ run_name))
            
            os.makedirs(save_dir, exist_ok=True)
            path = os.path.join(save_dir, f"{var}_exceedance_map.png")
            plt.savefig(path, dpi=200, bbox_inches='tight')
            plt.close()
            logger.info(f"Saved plot to {path}")
            print(f"✅ Plot saved to: {path}")
        else:
            plt.show()


    def _draw_metadata_sidebar(self, fig, meta_dict):
        lines = [f"{k}: {meta_dict.get(k, 'N/A')}" for k in [
            "run_name", "run_time", "met_data", "start_of_release",
            "end_of_release", "source_strength", "release_location",
            "release_height", "run_duration"
        ]]
        fig.text(0.15, 0.08, "\n".join(lines), ha="left", va="center",
                 fontsize=9, bbox=dict(facecolor='white', alpha=0.8, edgecolor='gray'))
