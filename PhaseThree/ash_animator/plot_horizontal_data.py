import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.animation as animation
from scipy.interpolate import griddata
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cartopy.io.shapereader as shpreader
from adjustText import adjust_text
from ash_animator.basemaps import draw_etopo_basemap
import tempfile
import glob
import re
import xarray as xr

class Plot_Horizontal_Data:
    def __init__(self, animator, output_dir="plots", cmap="rainbow", fps=2,
                 include_metadata=True, threshold=0.1,
                 zoom_width_deg=5.0, zoom_height_deg=5.0, zoom_level=10,
                 static_frame_export=False, basemap_mode='stock'):
        
        
        ##########################
        
         # Auto-detect: folder path or animator object
        if isinstance(animator, str) and os.path.isdir(animator):
            # It's a directory path
             # Regex: match Tn at start OR preceded by underscore, case-insensitive
            _t_re = re.compile(r'(?:^|_)T(\d+)', re.IGNORECASE)
            def extract_timestep_key(path: str) -> int:
                """Return numeric timestep for sorting; inf if no Tn found."""
                m = _t_re.search(os.path.basename(path))
                return int(m.group(1)) if m else float('inf')
            
            nc_files = sorted(glob.glob(os.path.join(animator, "*.nc")), key=extract_timestep_key)
            if not nc_files:
                raise ValueError(f"No .nc files found in folder: {animator}")

            datasets = [xr.open_dataset(f) for f in nc_files]

            class AnimatorLike:
                def __init__(self, datasets):
                    self.datasets = datasets
                    # Use variables commonly found in NetCDF files
                    sample = datasets[0]
                    lat_name = next((v for v in ['lat', 'latitude', 'y'] if v in sample.variables), None)
                    lon_name = next((v for v in ['lon', 'longitude', 'x'] if v in sample.variables), None)
                    if lat_name is None or lon_name is None:
                        raise ValueError("Latitude or longitude variables not found in .nc file.")
                    self.lat_grid, self.lon_grid = np.meshgrid(sample[lat_name].values, sample[lon_name].values)

            self.animator = AnimatorLike(datasets)
        elif hasattr(animator, 'datasets'):
            # It's an animator object
            self.animator = animator
        else:
            raise ValueError("Input must be either an animator object or a valid folder path containing .nc files.")
        
        
        
        #######################
        
        
        #self.animator = animator
        
        # Save metadata
        self.meta_attr = self.animator.datasets[0].attrs
        
        run_name=self.meta_attr.get('run_name', 'unknown_run')
                
        self.output_dir = os.path.abspath(
            os.path.join(
                os.environ.get("NAME_OUTPUT_DIR", tempfile.gettempdir()),
                output_dir + "/"+ run_name
            )
        )

        
        # self.output_dir = os.path.abspath(
        #     os.path.join(
        #         os.environ.get("NAME_OUTPUT_DIR", tempfile.gettempdir()), output_dir
        #     )
        # )
        os.makedirs(self.output_dir, exist_ok=True)

        self.cmap = cmap
        self.fps = fps
        self.include_metadata = include_metadata
        self.threshold = threshold
        self.zoom_width = zoom_width_deg
        self.zoom_height = zoom_height_deg
        self.zoom_level = zoom_level
        self.static_frame_export = static_frame_export
        self.basemap_mode = basemap_mode

       
        # Extract uniform grid
        self.attrs = self._extract_mutual_metadata()
        
        self.lons, self.lats, (self.lon_grid, self.lat_grid) = self.create_grid(self.attrs)

        # Load countries
        self._load_country_geometries()

    def _extract_mutual_metadata(self):
        all_attrs = [ds.attrs for ds in self.animator.datasets]
        mutual_keys = set(all_attrs[0].keys())
        for attrs in all_attrs[1:]:
            mutual_keys &= set(attrs.keys())
        mutual_meta = {
            key: all_attrs[0][key]
            for key in mutual_keys
            if all(a[key] == all_attrs[0][key] for a in all_attrs)
        }
        return mutual_meta

    def create_grid(self, attrs: dict):
        x_origin = float(attrs.get("x_origin"))
        y_origin = float(attrs.get("y_origin"))
        x_res = float(attrs.get("x_res"))
        y_res = float(attrs.get("y_res"))
        x_grid_size = int(attrs.get("x_grid_size"))
        y_grid_size = int(attrs.get("y_grid_size"))
        lons = np.round(
            np.linspace(x_origin, x_origin + (x_grid_size - 1) * x_res, x_grid_size), 6
        )
        lats = np.round(
            np.linspace(y_origin, y_origin + (y_grid_size - 1) * y_res, y_grid_size), 6
        )
        lon_grid, lat_grid = np.meshgrid(lons, lats)
        return lons, lats, (lon_grid, lat_grid)

    def interpolate_grid(self, data: np.ndarray) -> np.ndarray:
        data = np.where(data < 0, 0, data)
        mask = data > 0
        if np.count_nonzero(mask) < 10:
            return np.full_like(data, 0)

        points = np.column_stack((self.lon_grid[mask], self.lat_grid[mask]))
        values = data[mask]

        for method in ['cubic', 'linear', 'nearest']:
            try:
                grid_z = griddata(points, values, (self.lon_grid, self.lat_grid), method="linear")
                break
            except Exception:
                continue

        return np.where(np.isnan(grid_z) | (grid_z < 0), 0, grid_z)

    def _load_country_geometries(self):
        shp_path = shpreader.natural_earth(
            resolution='110m', category='cultural', name='admin_0_countries'
        )
        self.country_geoms = list(shpreader.Reader(shp_path).records())

    def _get_max_concentration_location(self, field):
        max_val = -np.inf
        lat = lon = None
        for ds in self.animator.datasets:
            data = ds[field].values
            if np.nanmax(data) > max_val:
                max_val = np.max(data)
                idx = np.unravel_index(np.argmax(data), data.shape)
                lat = self.animator.lat_grid[idx]
                lon = self.animator.lon_grid[idx]
        return lat, lon

    # def _get_zoom_indices(self, center_lat, center_lon):
    #     """Get lat/lon index ranges for zoomed-in extent, clipped to bounds."""
    #     lon_min = max(center_lon - self.zoom_width / 2, self.lons.min())
    #     lon_max = min(center_lon + self.zoom_width / 2, self.lons.max())
    #     lat_min = max(center_lat - self.zoom_height / 2, self.lats.min())
    #     lat_max = min(center_lat + self.zoom_height / 2, self.lats.max())

    #     lat_idx = np.where((self.lats >= lat_min) & (self.lats <= lat_max))[0]
    #     lon_idx = np.where((self.lons >= lon_min) & (self.lons <= lon_max))[0]

    #     # Ensure at least 2 grid points are included (for plotting)
    #     if len(lat_idx) < 2:
    #         lat_idx = np.argsort(np.abs(self.lats - center_lat))[:2]
    #         lat_min, lat_max = self.lats[lat_idx].min(), self.lats[lat_idx].max()

    #     if len(lon_idx) < 2:
    #         lon_idx = np.argsort(np.abs(self.lons - center_lon))[:2]
    #         lon_min, lon_max = self.lons[lon_idx].min(), self.lons[lon_idx].max()

    #     return lat_idx, lon_idx, lon_min, lon_max, lat_min, lat_max
    
    def _get_zoom_indices(self, center_lat, center_lon, data=None):
        """
        Get lat/lon index ranges for zoomed-in extent, clipped to non-zero data if provided.
        
        If `data` is provided (2D numpy array), the extent will be clipped tightly
        to the region where data != 0. Otherwise, it uses a fixed zoom window.
        """
        # Default zoom bounds based on fixed width/height
        lon_min = max(center_lon - self.zoom_width / 2, self.lons.min())
        lon_max = min(center_lon + self.zoom_width / 2, self.lons.max())
        lat_min = max(center_lat - self.zoom_height / 2, self.lats.min())
        lat_max = min(center_lat + self.zoom_height / 2, self.lats.max())

        # Initial indices within zoom window
        lat_idx = np.where((self.lats >= lat_min) & (self.lats <= lat_max))[0]
        lon_idx = np.where((self.lons >= lon_min) & (self.lons <= lon_max))[0]

        # Ensure at least 2 grid points
        if len(lat_idx) < 2:
            lat_idx = np.argsort(np.abs(self.lats - center_lat))[:2]
            lat_min, lat_max = self.lats[lat_idx].min(), self.lats[lat_idx].max()

        if len(lon_idx) < 2:
            lon_idx = np.argsort(np.abs(self.lons - center_lon))[:2]
            lon_min, lon_max = self.lons[lon_idx].min(), self.lons[lon_idx].max()

        # If data is provided, further clip to non-zero region
        if data is not None:
            zoom_data = data[np.ix_(lat_idx, lon_idx)]
            lat_zoom = self.lats[lat_idx]
            lon_zoom = self.lons[lon_idx]
            lat_grid, lon_grid = np.meshgrid(lat_zoom, lon_zoom, indexing="ij")

            valid = zoom_data != 0
            if np.any(valid):
                lat_valid = lat_grid[valid]
                lon_valid = lon_grid[valid]
                lat_min, lat_max = float(lat_valid.min()), float(lat_valid.max())
                lon_min, lon_max = float(lon_valid.min()), float(lon_valid.max())

        return lat_idx, lon_idx, lon_min, lon_max, lat_min, lat_max



    def _add_country_labels(self, ax, extent):
        proj = ccrs.PlateCarree()
        texts = []
        for country in self.country_geoms:
            name = country.attributes['NAME_LONG']
            try:
                lon, lat = country.geometry.centroid.x, country.geometry.centroid.y
                if extent[0] <= lon <= extent[1] and extent[2] <= lat <= extent[3]:
                    text = ax.text(
                        lon, lat, name, fontsize=6, transform=proj,
                        ha='center', va='center', color='white',
                        bbox=dict(facecolor='black', alpha=0.5, linewidth=0)
                    )
                    texts.append(text)
            except:
                continue
        adjust_text(
            texts, ax=ax, only_move={'points': 'y', 'text': 'y'},
            arrowprops=dict(arrowstyle="->", color='white', lw=0.5)
        )

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
        mid = len(lines) // 2 + len(lines) % 2
        left_text = "\n".join(lines[:mid])
        right_text = "\n".join(lines[mid:])

        fig.text(
            0.05, 0.05, left_text, va='bottom', ha='left',
            fontsize=9, family='monospace', color='black',
            bbox=dict(facecolor='white', alpha=0.8, edgecolor='gray')
        )
        fig.text(
            0.3, 0.05, right_text, va='bottom', ha='left',
            fontsize=9, family='monospace', color='black',
            bbox=dict(facecolor='white', alpha=0.8, edgecolor='gray')
        )

    def _plot_frame(self, ax, data, lons, lats, title, levels, scale_label, proj):
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

        c = ax.contourf(
            lons, lats, data, levels=levels, cmap=self.cmap,
            alpha=0.6, transform=proj, zorder=2, extend="both"
        )
        ax.contour(
            lons, lats, data, levels=levels, colors='black',
            linewidths=0.5, transform=proj, zorder=2
        )
        
        
        raw = self.meta_attr.get('release_location')
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

    def _generate_levels(self, valid_values, log_cutoff=1e-3, num_levels=20):
        """Generate clean increasing levels array for contouring."""
        min_val, max_val = np.nanmin(valid_values), np.nanmax(valid_values)
        if not np.isfinite(min_val) or not np.isfinite(max_val) or min_val >= max_val:
            return None

        use_log = min_val > log_cutoff and (max_val / (min_val + 1e-6)) > 100
        if use_log:
            levels = np.logspace(np.log10(log_cutoff), np.log10(max_val), num_levels)
        else:
            levels = np.linspace(min_val, max_val, num_levels)

        levels = np.unique(levels)
        return levels

    
    def _compute_global_levels(self, field, log_cutoff=1e-3, num_levels=20):
        """Compute global min/max and consistent contour levels across all valid frames."""
        all_valid_values = []
        valid_frames = []

        for t, ds in enumerate(self.animator.datasets):
            data = ds[field].values
            interp = self.interpolate_grid(data)
            if np.isfinite(interp).sum() > 0:
                valid_frames.append(t)
                all_valid_values.append(interp[np.isfinite(interp)])

        if not valid_frames:
            return [], None, None, None  # No data

        all_valid_values = np.concatenate(all_valid_values)
        global_min = np.nanmin(all_valid_values)
        global_max = np.nanmax(all_valid_values)

        use_log = global_min > log_cutoff and (global_max / (global_min + 1e-6)) > 100
        levels = (np.logspace(np.log10(log_cutoff), np.log10(global_max), num_levels)
                if use_log else np.linspace(0, global_max, num_levels))

        # Clean and validate levels
        levels = np.unique(np.nan_to_num(levels, nan=log_cutoff, posinf=global_max, neginf=0))
        if len(levels) < 2 or levels[-1] <= levels[0]:
            levels = np.array([0, global_max if global_max > 0 else 1e-6])

        return valid_frames, levels, use_log, global_max


    def _get_timestep_metadata(self, t_idx):
        """Extract Tn_date and Tn_time for a given timestep."""
        attrs = self.animator.datasets[t_idx].attrs
        date_key = f"T{t_idx+1}_date"
        time_key = f"T{t_idx+1}_time"
        date_str = attrs.get(date_key, "??/??/????")
        time_str = attrs.get(time_key, "??:??")
        return date_str, time_str

    
    # def plot_single_field_over_time(self, field, filename="field.gif"):
    #     output_path = os.path.join(self.output_dir, "2d_fields", field, filename)
    #     meta = self.meta_attr
    #     raw = self.meta_attr.get('release_location')
    #     # if raw:
    #     #     try:
    #     #         lon_str, lat_str = raw.strip().split()
    #     #         center_lon = float(lon_str[:-1]) * (1 if lon_str[-1].upper() == 'E' else -1)
    #     #         center_lat = float(lat_str[:-1]) * (1 if lat_str[-1].upper() == 'N' else -1)
    #     #     except Exception:
    #     #         center_lat, center_lon = self._get_max_concentration_location(field)
    #     # else:
    #     #     center_lat, center_lon = self._get_max_concentration_location(field)
    #     # lat_idx, lon_idx, lon_min, lon_max, lat_min, lat_max = self._get_zoom_indices(center_lat, center_lon)
    #     # lat_zoom = self.lats[lat_idx]
    #     # lon_zoom = self.lons[lon_idx]

    #     # ✅ Find valid frames that produce non-empty data
    #     valid_frames, levels, use_log, global_max = self._compute_global_levels(field)
    #     if not valid_frames:
    #         print(f"No valid frames to plot for field '{field}'.")
    #         return


       

    #     fig = plt.figure(figsize=(16, 8))
    #     proj = ccrs.PlateCarree()
    #     ax1 = fig.add_subplot(1, 2, 1, projection=proj)
    #     ax2 = fig.add_subplot(1, 2, 2, projection=proj)

    #     def update(t_idx):
            
            
    #         raw = self.meta_attr.get('release_location')
    #         if raw:
    #             try:
    #                 lon_str, lat_str = raw.strip().split()
    #                 center_lon = float(lon_str[:-1]) * (1 if lon_str[-1].upper() == 'E' else -1)
    #                 center_lat = float(lat_str[:-1]) * (1 if lat_str[-1].upper() == 'N' else -1)
    #             except Exception:
    #                 center_lat, center_lon = self._get_max_concentration_location(field)
    #         else:
    #             center_lat, center_lon = self._get_max_concentration_location(field)
           
    #         ax1.clear()
    #         ax2.clear()
    #         t = valid_frames[t_idx]

    #         data = self.animator.datasets[t][field].values
            
           
            
            
    #         interp = self.interpolate_grid(data)
            
            
    #         lat_idx, lon_idx, lon_min, lon_max, lat_min, lat_max = self._get_zoom_indices(center_lat, center_lon, data=interp)
    #         lat_zoom = self.lats[lat_idx]
    #         lon_zoom = self.lons[lon_idx]
            
            
    #         zoom = interp[np.ix_(lat_idx, lon_idx)]
    #         valid = interp[np.isfinite(interp)]
            
    #         zoom = interp[np.ix_(lat_idx, lon_idx)]
    #         nonzero_mask = (zoom > 0)

    #         if np.any(nonzero_mask):
    #             lat_valid = lat_zoom[nonzero_mask.any(axis=1)]
    #             lon_valid = lon_zoom[nonzero_mask.any(axis=0)]
    #             if lat_valid.size > 0 and lon_valid.size > 0:
    #                 lat_min_dynamic = lat_valid.min()
    #                 lat_max_dynamic = lat_valid.max()
    #                 lon_min_dynamic = lon_valid.min()
    #                 lon_max_dynamic = lon_valid.max()
    #                 ax2.set_extent([lon_min_dynamic, lon_max_dynamic, lat_min_dynamic, lat_max_dynamic], crs=proj)

    #         #################
            
    #         # Compute zoomed region data
           
          

          
            
    #         ##############3

    #         # Use log thresholding only if applicable
    #         log_cutoff = 1e-3
    #         plot_data = np.where(interp > log_cutoff, interp, np.nan) if use_log else interp
    #         scale_label = "Log" if use_log else "Linear"
            
    #         #########
            
    #         # Get metadata date/time string for this timestep
    #         date_str, time_str = self._get_timestep_metadata(t)

    #         # Format the time label for plot titles
    #         time_label = f"{date_str} {time_str}"

            
    #         ##########

    #         # Plot full and zoom views
    #         c = self._plot_frame(
    #         ax1, plot_data, self.lons, self.lats,
    #         f"T{t+1} | {field} (Full - {scale_label})\n{time_label}",
    #         levels, scale_label, proj)

    #         self._plot_frame(
    #         ax2, zoom, lon_zoom, lat_zoom,
    #         f"T{t+1} | {field} (Zoom - {scale_label})\n{time_label}",
    #         levels, scale_label, proj)

    #         self._add_country_labels(
    #             ax1, [self.lons.min(), self.lons.max(), self.lats.min(), self.lats.max()]
    #         )
    #         self._add_country_labels(
    #             ax2, [lon_min, lon_max, lat_min, lat_max]
    #         )
            
           
            

    #         # Colorbar (only once)
    #         if not hasattr(update, "colorbar"):
    #             unit_label = f"{field}:({self.animator.datasets[0][field].attrs.get('units', field)})"
    #             update.colorbar = fig.colorbar(
    #                 c, ax=[ax1, ax2], orientation='vertical', label=unit_label
    #             )
    #             update.colorbar.ax.yaxis.set_major_formatter(
    #                 mticker.FuncFormatter(lambda x, _: f"{x:.2g}")
    #             )

    #         # Threshold warning overlay
    #         if np.nanmax(valid) > self.threshold:
    #             ax1.contour(
    #                 self.lons, self.lats, interp, levels=[self.threshold],
    #                 colors='red', linewidths=2, transform=proj
    #             )
    #             ax2.contour(
    #                 lon_zoom, lat_zoom, zoom, levels=[self.threshold],
    #                 colors='red', linewidths=2, transform=proj
    #             )
    #             ax2.text(
    #                 0.99, 0.01,
    #                 f"⚠ Red contour shows the chosen threshold of {self.threshold}\n Max concentration =: {np.nanmax(valid):.2f} > {self.threshold}",
    #                 transform=ax2.transAxes, ha='right', va='bottom',
    #                 fontsize=9, color='red',
    #                 bbox=dict(facecolor='white', alpha=0.8, edgecolor='red')
    #             )

    #         # Save static frame if enabled
    #         if self.static_frame_export:
    #             frame_folder = os.path.join(self.output_dir, "frames", field)
    #             os.makedirs(frame_folder, exist_ok=True)
    #             frame_path = os.path.join(frame_folder, f"frame_{t+1:04d}.jpg")
    #             plt.savefig(frame_path, bbox_inches='tight')
    #             print(f"🖼️ Saved static frame: {frame_path}")

    #         return []

    #     if self.include_metadata:
    #         self._draw_metadata_sidebar(fig, meta)

    #     self._make_dirs(output_path)
    #     fig.tight_layout()

    #     # ✅ Animate only valid frames
    #     ani = animation.FuncAnimation(
    #         fig, update, frames=range(len(valid_frames)),
    #         blit=False, cache_frame_data=False
    #     )
    #     ani.save(output_path, writer='pillow', fps=self.fps)
    #     plt.close(fig)
    #     print(f"✅ Saved enhanced 2D animation for {field} to {output_path}")

    def plot_single_field_over_time(self, field, filename="field.gif"):
        output_path = os.path.join(self.output_dir, "2d_fields", field, filename)
        meta = self.meta_attr

        # ✅ Find valid frames that produce non-empty data
        valid_frames, levels, use_log, global_max = self._compute_global_levels(field)
        if not valid_frames:
            print(f"No valid frames to plot for field '{field}'.")
            return

        fig = plt.figure(figsize=(16, 8))
        proj = ccrs.PlateCarree()
        ax1 = fig.add_subplot(1, 2, 1, projection=proj)
        ax2 = fig.add_subplot(1, 2, 2, projection=proj)

        def update(t_idx):
            ax1.clear()
            ax2.clear()
            t = valid_frames[t_idx]

            # Load and interpolate
            data = self.animator.datasets[t][field].values
            interp = self.interpolate_grid(data)

            # Mask and mesh
            valid_mask = (interp > 0) & np.isfinite(interp)
            lon_mesh, lat_mesh = np.meshgrid(self.lons, self.lats)

            if np.any(valid_mask):
                valid_lats = lat_mesh[valid_mask]
                valid_lons = lon_mesh[valid_mask]
                lat_min, lat_max = valid_lats.min(), valid_lats.max()
                lon_min, lon_max = valid_lons.min(), valid_lons.max()
            else:
                print(f"⚠ No non-zero data found at frame T{t + 1}, using full domain for zoom.")
                lat_min, lat_max = self.lats.min(), self.lats.max()
                lon_min, lon_max = self.lons.min(), self.lons.max()

            # Plot full domain
            log_cutoff = 1e-3
            plot_data = np.where(interp > log_cutoff, interp, np.nan) if use_log else interp
            scale_label = "Log" if use_log else "Linear"

            # Time label
            date_str, time_str = self._get_timestep_metadata(t)
            time_label = f"{date_str} {time_str}"

            c = self._plot_frame(
                ax1, plot_data, self.lons, self.lats,
                f"T{t + 1} | {field} (Full - {scale_label})\n{time_label}",
                levels, scale_label, proj
            )

            # Zoom data
            lat_mask = (self.lats >= lat_min) & (self.lats <= lat_max)
            lon_mask = (self.lons >= lon_min) & (self.lons <= lon_max)
            zoom_data = interp[np.ix_(lat_mask, lon_mask)]
            lat_zoom = self.lats[lat_mask]
            lon_zoom = self.lons[lon_mask]

            self._plot_frame(
                ax2, zoom_data, lon_zoom, lat_zoom,
                f"T{t + 1} | {field} (Zoom - {scale_label})\n{time_label}",
                levels, scale_label, proj
            )
            ax2.set_extent([lon_min, lon_max, lat_min, lat_max], crs=proj)

            # Add country labels
            self._add_country_labels(ax1, [self.lons.min(), self.lons.max(), self.lats.min(), self.lats.max()])
            self._add_country_labels(ax2, [lon_min, lon_max, lat_min, lat_max])

            # Colorbar once
            if not hasattr(update, "colorbar"):
                unit_label = f"{field}:({self.animator.datasets[0][field].attrs.get('units', field)})"
                update.colorbar = fig.colorbar(
                    c, ax=[ax1, ax2], orientation='vertical', label=unit_label
                )
                update.colorbar.ax.yaxis.set_major_formatter(
                    mticker.FuncFormatter(lambda x, _: f"{x:.2g}")
                )

            # Threshold warning
            if np.nanmax(interp) > self.threshold:
                ax1.contour(
                    self.lons, self.lats, interp, levels=[self.threshold],
                    colors='red', linewidths=2, transform=proj
                )
                ax2.contour(
                    lon_zoom, lat_zoom, zoom_data, levels=[self.threshold],
                    colors='red', linewidths=2, transform=proj
                )
                ax2.text(
                    0.99, 0.01,
                    f"⚠ Red contour shows the chosen threshold of {self.threshold}\nMax concentration = {np.nanmax(interp):.2f} > {self.threshold}",
                    transform=ax2.transAxes, ha='right', va='bottom',
                    fontsize=9, color='red',
                    bbox=dict(facecolor='white', alpha=0.8, edgecolor='red')
                )
            # elif not np.any(valid_mask):
            #     ax2.text(
            #         0.5, 0.5, "No plume detected",
            #         transform=ax2.transAxes, ha='center', va='center',
            #         fontsize=12, color='gray',
            #         bbox=dict(facecolor='white', alpha=0.6, edgecolor='gray')
            #     )

            # Save static frame
            if self.static_frame_export:
                frame_folder = os.path.join(self.output_dir, "frames", field)
                os.makedirs(frame_folder, exist_ok=True)
                frame_path = os.path.join(frame_folder, f"frame_{t + 1:04d}.jpg")
                plt.savefig(frame_path, bbox_inches='tight')
                print(f"🖼️ Saved static frame: {frame_path}")

            # ✅ Return at least one artist for animation
            return [ax1.images[0]] if ax1.images else [ax1]

        # Optional metadata
        if self.include_metadata:
            self._draw_metadata_sidebar(fig, meta)

        self._make_dirs(output_path)
        fig.tight_layout()

        ani = animation.FuncAnimation(
            fig, update, frames=range(len(valid_frames)),
            blit=False, cache_frame_data=False
        )
        ani.save(output_path, writer='pillow', fps=self.fps)
        plt.close(fig)
        print(f"✅ Saved enhanced 2D animation for {field} to {output_path}")


    def _make_dirs(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
