import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.ticker as mticker
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cartopy.io.shapereader as shpreader
from adjustText import adjust_text
from .interpolation import interpolate_grid , create_grid
from .basemaps import draw_etopo_basemap
import imageio.v2 as imageio
import shutil
import tempfile

class Plot_3DField_Data:
    
    """
    A class for visualizing 3D spatiotemporal field data (e.g., ash concentration) across time and altitude levels.

    This class uses matplotlib and cartopy to create:
      - Animated GIFs of spatial fields at given altitudes
      - Vertical profile animations over time
      - Exported static frames with metadata annotations and zoomed views

    Parameters
    ----------
    animator : object
        A container holding the dataset, including:
        - datasets: list of xarray-like DataArrays with 'ash_concentration'
        - lons, lats: 1D longitude and latitude arrays
        - lat_grid, lon_grid: 2D grid arrays for spatial mapping
        - levels: 1D array of vertical altitude levels (e.g., in km)
    output_dir : str
        Base directory for saving all outputs. Defaults to "plots".
    cmap : str
        Matplotlib colormap name. Defaults to "rainbow".
    fps : int
        Frames per second for GIFs. Defaults to 2.
    include_metadata : bool
        Whether to annotate each figure with simulation metadata. Defaults to True.
    threshold : float
        Value threshold (e.g., in g/m³) to highlight exceedances. Defaults to 0.1.
    zoom_width_deg : float
        Width of the zoomed-in region in degrees. Defaults to 6.0.
    zoom_height_deg : float
        Height of the zoomed-in region in degrees. Defaults to 6.0.
    zoom_level : int
        Zoom level passed to basemap drawing. Defaults to 7.
    basemap_mode : str
        Type of basemap to draw (passed to draw_etopo_basemap). Defaults to "basemap".

    Methods
    -------
    plot_single_z_level(z_km, filename)
        Generate animation over time at a specific altitude level.
    
    plot_vertical_profile_at_time(t_index, filename=None)
        Generate vertical profile GIF for a single timestep.

    animate_altitude(t_index, output_path)
        Animate altitude slices for one timestep.

    animate_all_altitude_profiles(output_folder='altitude_profiles')
        Generate vertical animations for all time steps.

    export_frames_as_jpgs(include_metadata=True)
        Export individual frames as static `.jpg` images with annotations.
    """
    def __init__(self, animator, output_dir="plots", cmap="rainbow", fps=2,
                 include_metadata=True, threshold=0.1,
                 zoom_width_deg=5.0, zoom_height_deg=5.0, zoom_level=10, basemap_mode="basemap"):
        
        if isinstance(animator, str):
                self.animator = self.load_animator_from_nc(animator)
        else:
            self.animator = animator
        
        self.meta_attr=self.animator.datasets[0].attrs
        run_name=self.meta_attr.get('run_name', 'unknown_run')
                
        self.output_dir = os.path.abspath(
            os.path.join(
                os.environ.get("NAME_OUTPUT_DIR", tempfile.gettempdir()),
                output_dir + "/"+ run_name
            )
        )
        
        os.makedirs(self.output_dir, exist_ok=True)
        self.cmap = cmap
        self.fps = fps
        self.include_metadata = include_metadata
        self.threshold = threshold
        self.zoom_width = zoom_width_deg
        self.zoom_height = zoom_height_deg
        shp = shpreader.natural_earth(resolution='110m', category='cultural', name='admin_0_countries')
        self.country_geoms = list(shpreader.Reader(shp).records())
        self.zoom_level=zoom_level
        self.basemap_mode=basemap_mode
        
        
        #############3
        
            
        # Load shapefile once
        countries_shp = shpreader.natural_earth(
            resolution='110m',
            category='cultural',
            name='admin_0_countries'
        )
        self.country_geoms = list(shpreader.Reader(countries_shp).records())

        # Cache extent bounds
        self.lon_min = np.min(self.animator.lons)
        self.lon_max = np.max(self.animator.lons)
        self.lat_min = np.min(self.animator.lats)
        self.lat_max = np.max(self.animator.lats)
        
        self.lon_grid_global, self.lat_grid_global=create_grid(self.meta_attr)
        
        #####################3
    
    def load_animator_from_nc(self, directory):
        """
        Load NetCDF files from a directory and return an animator-like object
        with merged Tn metadata and access utilities.
        """
        import xarray as xr
        import numpy as np
        import glob
        import ast
        import re 
        
        
        def extract_t_index(path):
        # Extract T<number>.nc → number
            name = os.path.basename(path)
            match = re.search(r"T(\d+)\.nc", name)
            return int(match.group(1)) if match else float('inf')  # inf puts unmatched files last

        nc_files = sorted(
            glob.glob(os.path.join(directory, "T*.nc")),
            key=extract_t_index
        )
                
                
        if not nc_files:
            raise FileNotFoundError(f"No NetCDF files found in {directory}")

        datasets = [xr.open_dataset(f) for f in nc_files]
        sample = datasets[0]

        # Flexible variable name detection
        if 'lon' in sample:
            lons = sample['lon'].values
        elif 'longitude' in sample:
            lons = sample['longitude'].values
        else:
            raise KeyError("Could not find 'lon' or 'longitude' in dataset.")

        if 'lat' in sample:
            lats = sample['lat'].values
        elif 'latitude' in sample:
            lats = sample['latitude'].values
        else:
            raise KeyError("Could not find 'lat' or 'latitude' in dataset.")

        if 'level' in sample:
            levels = sample['level'].values
        elif 'altitude' in sample:
            levels = sample['altitude'].values
        else:
            raise KeyError("Could not find 'level' or 'altitude' in dataset.")

        lon_grid, lat_grid = np.meshgrid(lons, lats)

        # 🧠 Combine all metadata from all files
        combined_metadata = {}
        for ds in datasets:
            combined_metadata.update(ds.attrs)

        class SimpleAnimator:
            def __init__(self, datasets, lons, lats, lon_grid, lat_grid, levels, metadata):
                self.datasets = datasets
                self.lons = lons
                self.lats = lats
                self.lon_grid = lon_grid
                self.lat_grid = lat_grid
                self.levels = levels
                self.metadata = metadata

            def summary(self):
                print(f"🗂 Datasets loaded: {len(self.datasets)}")
                print(f"🌍 Grid: {self.lons.shape} lons × {self.lats.shape} lats")
                print(f"📈 Levels: {list(self.levels)}")
                print(f"🧾 Available Tn metadata keys:")
                for key in self.metadata.keys():
                    if key.startswith("T"):
                        print(f"  - {key}")

            def get_altitudes(self, t_index):
                """
                Returns a dictionary mapping z-index to altitude string for time T{t_index + 1}
                """
                import ast
                keys = [f"T{t_index + 1}_altitudes", f"t{t_index + 1}_altitudes"]
                for key in keys:
                    raw = self.metadata.get(key)
                    if raw:
                        try:
                            return ast.literal_eval(raw)
                        except Exception as e:
                            print(f"⚠️ Could not parse {key}: {e}")
                            return None
                print(f"⚠️ Altitude metadata not found for T{t_index + 1}")
                return None

            def get_altitude(self, t_index, level):
                """
                Returns the altitude string for a given time index and level number.

                Parameters
                ----------
                t_index : int
                    Time index (e.g., 2 for T3)
                level : int
                    Level number as defined in metadata (e.g., 3 → '5000 m agl')

                Returns
                -------
                str or None
                    Altitude label like '5000 m agl', or None if not found
                """
                alt_dict = self.get_altitudes(t_index)
                if alt_dict is None:
                    print(f"⚠️ Altitude data not found for T{t_index + 1}")
                    return None

                return alt_dict.get(level)


            
            def get_datetime(self, t_index):
                """
                Returns the date and time for a given timestep index (0-based).
                """
                date_keys = [f"T{t_index + 1}_date", f"t{t_index + 1}_date"]
                time_keys = [f"T{t_index + 1}_time", f"t{t_index + 1}_time"]
                date = next((self.metadata.get(k) for k in date_keys if self.metadata.get(k)), None)
                time = next((self.metadata.get(k) for k in time_keys if self.metadata.get(k)), None)
                if date or time:
                    return {"date": date, "time": time}
                print(f"⚠️ Date/time metadata not found for T{t_index + 1}")
                return None

            def get_available_timesteps(self):
                """
                Returns list of available T indices based on merged metadata.
                """
                ts = set()
                for key in self.metadata:
                    if key.startswith("T") and len(key) > 2 and key[1].isdigit():
                        t_id = key[1:].split("_")[0]
                        if t_id.isdigit():
                            ts.add(int(t_id))
                return sorted(ts)

        return SimpleAnimator(datasets, lons, lats, lon_grid, lat_grid, levels, combined_metadata)




    def _get_date_time(self, t_index):
        ''' Extracates date and Time in UTC '''
        return self.animator.get_datetime(t_index)
    
    def _get_altitude_label(self, t_index, level):
        """
        Extracts altitude metadata string for a given time and z index.
        Falls back to numeric value if metadata is missing.
        """
        #self.animator.get_altitude(t_index=2, level_index=2)
        # → '5000 m agl'   (T3, 3rd level — z=2)
        return self.animator.get_altitude(t_index=t_index, level=level)

        
    def _make_dirs(self, path):
        path = os.path.abspath(os.path.join(os.getcwd(), os.path.dirname(path)))
        os.makedirs(path, exist_ok=True)

    def _get_zoom_indices(self, center_lat, center_lon):
        lon_min = center_lon - self.zoom_width / 2
        lon_max = center_lon + self.zoom_width / 2
        lat_min = center_lat - self.zoom_height / 2
        lat_max = center_lat + self.zoom_height / 2

        # Ensure non-zero extent
        if lon_min == lon_max:
            lon_min -= 0.05
            lon_max += 0.05
        if lat_min == lat_max:
            lat_min -= 0.05
            lat_max += 0.05

        # Also clip to global domain
        lon_min = max(lon_min, np.min(self.animator.lons))
        lon_max = min(lon_max, np.max(self.animator.lons))
        lat_min = max(lat_min, np.min(self.animator.lats))
        lat_max = min(lat_max, np.max(self.animator.lats))

        lat_idx = np.where((self.animator.lats >= lat_min) & (self.animator.lats <= lat_max))[0]
        lon_idx = np.where((self.animator.lons >= lon_min) & (self.animator.lons <= lon_max))[0]

        return lat_idx, lon_idx, lon_min, lon_max, lat_min, lat_max

   
    
    
    def _get_max_concentration_location(self):
        max_conc = -np.inf
        center_lat = center_lon = None
        for ds in self.animator.datasets:
            for z in range(len(self.animator.levels)):
                data = ds['ash_concentration'].values[z]
                if np.max(data) > max_conc:
                    max_conc = np.max(data)
                    max_idx = np.unravel_index(np.argmax(data), data.shape)
                    center_lat = self.animator.lat_grid[max_idx]
                    center_lon = self.animator.lon_grid[max_idx]
        return center_lat, center_lon

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

    
    
    def _plot_frame(self, ax, data, lons, lats, title, levels, scale_label, proj, extent=None):
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
                        alpha=0.6, transform=proj, zorder=2, extend="both", extent=extent)
        ax.contour(lons, lats, data, levels=levels, colors='black',
                   linewidths=0.5, transform=proj, zorder=2, extent=extent)

        
        #self._extract_mutual_metadata()
        
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

 

#  metadata placement function and usage

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
        full_text = "\n".join(lines)  # ✅ actual newlines
        fig.text(0.1, 0.095, full_text, va='center', ha='left',
                fontsize=9, family='monospace', color='black',
                bbox=dict(facecolor='white', alpha=0.8, edgecolor='gray'))



    def plot_single_z_level(self, z_km, filename="z_level.gif", save_frames=True):
        levels = np.array(self.animator.levels)

        # Find closest available Z level
        if not np.any(np.isclose(levels, z_km)):
            closest_z = levels[np.argmin(np.abs(levels - z_km))]
            print(f"⚠ Z level {z_km} km not found. Using closest available level: {closest_z} km instead.")
            z_km = closest_z

        z_index = np.where(np.isclose(levels, z_km))[0][0]
        output_path = os.path.join(self.output_dir, "z_levels", filename)

        # Extract base name and remove spaces
        gif_name = os.path.splitext(os.path.basename(filename))[0].replace(" ", "")

        # Put frames in a folder next to the .gif
        frames_dir = os.path.join(os.path.dirname(output_path), gif_name)

        if save_frames:
            os.makedirs(frames_dir, exist_ok=True)



        fig = plt.figure(figsize=(16, 8))
        proj = ccrs.PlateCarree()
        ax1 = fig.add_subplot(1, 2, 1, projection=proj)
        ax2 = fig.add_subplot(1, 2, 2, projection=proj)

        center_lat, center_lon = self._get_max_concentration_location()
        lat_idx, lon_idx, lon_min, lon_max, lat_min, lat_max = self._get_zoom_indices(center_lat, center_lon)
        
        #lat_idx, lon_idx, lon_min, lon_max, lat_min, lat_max = self._get_zoom_indices( interp, self.lat_grid_global, self.lon_grid_global)

        
        lat_zoom = self.animator.lats[lat_idx]
        lon_zoom = self.animator.lons[lon_idx]

        valid_frames = list(range(len(self.animator.datasets)))

        # 🔵 Precompute global min/max
        all_data = []
        for t in valid_frames:
            data = self.animator.datasets[t]['ash_concentration'].values[z_index]
            interp = interpolate_grid(data,  self.lon_grid_global, self.lat_grid_global)
            interp = np.where(np.isnan(interp), 0, interp)
            all_data.append(interp)

        global_min = min(np.nanmin(arr) for arr in all_data)
        global_max = max(np.nanmax(arr) for arr in all_data)

        if not np.isfinite(global_min):
            global_min = 0
        if not np.isfinite(global_max):
            global_max = 0
        if global_min == global_max:
            levels = [0, 1]
        else:
            levels = np.linspace(global_min, global_max, 20)

        
        def get_full_extent(data_array):
            if hasattr(data_array, 'dims'):
                lat_name = next((d for d in data_array.dims if "lat" in d.lower()), None)
                lon_name = next((d for d in data_array.dims if "lon" in d.lower()), None)
                if lat_name and lon_name:
                    lat = data_array[lat_name]
                    lon = data_array[lon_name]
                else:
                    raise ValueError("Latitude or longitude dimension not found in DataArray.")
            elif isinstance(data_array, np.ndarray) and data_array.ndim == 2:
                # fallback: use array shape with dummy extent
                ny, nx = data_array.shape
                lat = np.linspace(-90, 90, ny)
                lon = np.linspace(-180, 180, nx)
            else:
                raise TypeError("Unsupported type passed to get_full_extent")

            return [lon.min(), lon.max(), lat.min(), lat.max()]

        def update(t):
            ax1.clear()
            ax2.clear()

            interp = all_data[t]
            zoom_plot = interp[np.ix_(lat_idx, lon_idx)]
            valid_vals = interp[np.isfinite(interp)]
            
            alt_label = self._get_altitude_label(t, z_km)
            T_index_date_time=self._get_date_time(t)
            
            Title_zoom = f"Concentration through time at fixed altitude\nT{t+1} | Z_index={z_km} | Alt={alt_label} (Zoom)\n{T_index_date_time}"
            Title_Full = f"Concentration through time at fixed altitude\nT{t+1} | Z_index={z_km} | Alt={alt_label}\n{T_index_date_time}"
 

            c = self._plot_frame(ax1, interp, self.lon_grid_global, self.lat_grid_global,
                                Title_Full, levels, "Linear", proj)
            self._plot_frame(ax2, zoom_plot, lon_zoom, lat_zoom,
                            Title_zoom, levels, "Linear", proj, extent=get_full_extent(zoom_plot))

            self._add_country_labels(ax1, [self.lon_min, self.lon_max, self.lat_min, self.lat_max])
            self._add_country_labels(ax2, [lon_min, lon_max, lat_min, lat_max])

           

            
            if np.nanmax(valid_vals) > self.threshold:
                ax1.contour( self.lon_grid_global, self.lat_grid_global, interp, levels=[self.threshold],
                                colors='yellow', linewidths=2, transform=proj)
                ax2.contour(lon_zoom, lat_zoom, zoom_plot, levels=[self.threshold],
                                colors='yellow', linewidths=2, transform=proj)

                
                ax2.text(0.99, 0.01, f"⚠ Yellow contour shows the chosen threshold of {self.threshold}\n Max concentration: {np.nanmax(valid_vals):.2f} > {self.threshold} g/m³",
                                transform=ax2.transAxes, ha='right', va='bottom',
                                fontsize=9, color='yellow',
                                bbox=dict(facecolor='k', alpha=0.8, edgecolor='yellow'))
            
            
            # Threshold contours
            thresholds = {
                "Low": 0.002,
                "Medium": 0.004
            }
            threshold_colors = {
                "Low": "yellow",
                "Medium": "orange",
                "High": "red"
            }

            # >4 mg/m³ (high risk)
            ax1.contour(
                self.lon_grid_global, self.lat_grid_global, interp,
                levels=[thresholds["Medium"]],
                colors=[threshold_colors["High"]],
                linewidths=2, transform=proj
            )
            ax2.contour(
                lon_zoom, lat_zoom, zoom_plot,
                levels=[thresholds["Medium"]],
                colors=[threshold_colors["High"]],
                linewidths=2, transform=proj
            )

            # >2 mg/m³ (caution)
            ax1.contour(
                self.lon_grid_global, self.lat_grid_global, interp,
                levels=[thresholds["Low"]],
                colors=[threshold_colors["Medium"]],
                linewidths=2, transform=proj
            )
            ax2.contour(
                lon_zoom, lat_zoom, zoom_plot,
                levels=[thresholds["Low"]],
                colors=[threshold_colors["Medium"]],
                linewidths=2, transform=proj
            )

            # Legend
            handles = [
                plt.Line2D([0], [0], color=threshold_colors["Medium"], lw=2, label=">2 mg/m³ caution"),
                plt.Line2D([0], [0], color=threshold_colors["High"], lw=2, label=">4 mg/m³ high risk")
            ]
            ax2.legend(handles=handles, loc="upper right", fontsize=8, title="Ash thresholds")

            if not hasattr(update, "colorbar"):
                update.colorbar = fig.colorbar(c, ax=[ax1, ax2], orientation="vertical")
                update.colorbar.set_label("Ash concentration (g/m³)")
            
            
            # if save_frames:
            #     frame_path = os.path.join(frames_dir, f"frame_{t+1:04d}.png")
            #     fig.savefig(frame_path, dpi=150, bbox_inches="tight")
            if save_frames:
                frame_path = os.path.join(frames_dir, f"frame_{t+1:04d}.png")
                print(f"\n🖼️  [Frame Saver] ➤ Saving frame {t+1:04d}...")
                fig.savefig(frame_path, dpi=150, bbox_inches="tight")
                print(f"✅  [Frame Saved]   ➤ {frame_path}\n")

            
            return []

        self._draw_metadata_sidebar(fig, self.meta_attr)
        self._make_dirs(output_path)
        
        fig.tight_layout()
        ani = animation.FuncAnimation(fig, update, frames=valid_frames, blit=False, cache_frame_data=False)
        ani.save(output_path, writer="pillow", fps=self.fps, dpi=300)
        plt.close()
        print(f"✅ Saved animation Concentration through time at fixed altitude to {output_path}")


    # def plot_single_z_level(self, z_km, filename="z_level.gif", save_frames=True):
    #     levels_arr = np.array(self.animator.levels)

    #     # Find closest available Z level
    #     if not np.any(np.isclose(levels_arr, z_km)):
    #         closest_z = levels_arr[np.argmin(np.abs(levels_arr - z_km))]
    #         print(f"⚠ Z level {z_km} km not found. Using closest available level: {closest_z} km instead.")
    #         z_km = closest_z

    #     z_index = np.where(np.isclose(levels_arr, z_km))[0][0]
    #     output_path = os.path.join(self.output_dir, "z_levels", filename)
    #     gif_name = os.path.splitext(os.path.basename(filename))[0].replace(" ", "")
    #     frames_dir = os.path.join(os.path.dirname(output_path), gif_name)
    #     if save_frames:
    #         os.makedirs(frames_dir, exist_ok=True)

    #     fig = plt.figure(figsize=(16, 8))
    #     proj = ccrs.PlateCarree()
    #     ax1 = fig.add_subplot(1, 2, 1, projection=proj)
    #     ax2 = fig.add_subplot(1, 2, 2, projection=proj)

    #     valid_frames = list(range(len(self.animator.datasets)))

    #     # 🔵 Precompute all frames at this Z level
    #     all_data = []
    #     for t in valid_frames:
    #         data = self.animator.datasets[t]['ash_concentration'].values[z_index]
    #         interp = interpolate_grid(data, self.lon_grid_global, self.lat_grid_global)
    #         interp = np.where(np.isnan(interp), 0, interp)
    #         all_data.append(interp)

    #     global_min = min(np.nanmin(arr) for arr in all_data if np.any(arr))
    #     global_max = max(np.nanmax(arr) for arr in all_data if np.any(arr))
    #     if not np.isfinite(global_min): global_min = 0
    #     if not np.isfinite(global_max): global_max = 1 if global_min == 0 else global_min
    #     levels = [0, 1] if global_min == global_max else np.linspace(global_min, global_max, 20)

    #     def update(t):
    #         ax1.clear()
    #         ax2.clear()

    #         interp = all_data[t]
    #         alt_label = self._get_altitude_label(t, z_km)
    #         T_index_date_time = self._get_date_time(t)

    #         Title_zoom = (
    #             f"Concentration through time at fixed altitude\n"
    #             f"T{t+1} | Z_index={z_index} | Alt={alt_label} (Zoom)\n{T_index_date_time}"
    #         )
    #         Title_Full = (
    #             f"Concentration through time at fixed altitude\n"
    #             f"T{t+1} | Z_index={z_index} | Alt={alt_label}\n{T_index_date_time}"
    #         )

    #         # Full domain plot
    #         c = self._plot_frame(ax1, interp, self.lon_grid_global, self.lat_grid_global,
    #                             Title_Full, levels, "Linear", proj)

    #         # Zoomed view: find bounding box of non-zero plume
    #         nonzero_mask = interp > 0
    #         if not np.any(nonzero_mask):
    #             zoom_extent = [
    #                 self.lon_grid_global.min(), self.lon_grid_global.max(),
    #                 self.lat_grid_global.min(), self.lat_grid_global.max()
    #             ]
    #             zoom_plot = interp
    #             lat_zoom = self.animator.lats
    #             lon_zoom = self.animator.lons
    #         else:
    #             row_idx, col_idx = np.where(nonzero_mask)
    #             lat_vals = self.lat_grid_global[row_idx, col_idx]
    #             lon_vals = self.lon_grid_global[row_idx, col_idx]
    #             zoom_extent = [lon_vals.min(), lon_vals.max(), lat_vals.min(), lat_vals.max()]

    #             lat_mask = (self.lat_grid_global[:, 0] >= zoom_extent[2]) & (self.lat_grid_global[:, 0] <= zoom_extent[3])
    #             lon_mask = (self.lon_grid_global[0, :] >= zoom_extent[0]) & (self.lon_grid_global[0, :] <= zoom_extent[1])
    #             zoom_plot = interp[np.ix_(lat_mask, lon_mask)]
    #             lat_zoom = self.lat_grid_global[lat_mask, 0]
    #             lon_zoom = self.lon_grid_global[0, lon_mask]

    #         self._plot_frame(ax2, zoom_plot, lon_zoom, lat_zoom, Title_zoom,
    #                         levels, "Linear", proj, extent=zoom_extent)

    #         # Add labels
    #         self._add_country_labels(ax1, [self.lon_min, self.lon_max, self.lat_min, self.lat_max])
    #         self._add_country_labels(ax2, zoom_extent)

    #         # Threshold annotation and contours
    #         valid_vals = interp[np.isfinite(interp)]
    #         if np.nanmax(valid_vals) > self.threshold:
    #             for ax, lon_grid, lat_grid, data in [(ax1, self.lon_grid_global, self.lat_grid_global, interp),
    #                                                 (ax2, lon_zoom, lat_zoom, zoom_plot)]:
    #                 ax.contour(lon_grid, lat_grid, data, levels=[self.threshold],
    #                         colors='yellow', linewidths=2, transform=proj)

    #             ax2.text(0.99, 0.01,
    #                     f"⚠ Yellow contour shows the chosen threshold of {self.threshold}\n"
    #                     f"Max concentration: {np.nanmax(valid_vals):.2f} > {self.threshold} g/m³",
    #                     transform=ax2.transAxes, ha='right', va='bottom',
    #                     fontsize=9, color='yellow',
    #                     bbox=dict(facecolor='k', alpha=0.8, edgecolor='yellow'))

    #         # Risk contours
    #         thresholds = {"Low": 0.002, "Medium": 0.004}
    #         threshold_colors = {"Low": "yellow", "Medium": "orange", "High": "red"}
    #         for label, val in thresholds.items():
    #             color = threshold_colors["High"] if label == "Medium" else threshold_colors["Medium"]
    #             for ax, lon, lat, data in [(ax1, self.lon_grid_global, self.lat_grid_global, interp),
    #                                     (ax2, lon_zoom, lat_zoom, zoom_plot)]:
    #                 ax.contour(lon, lat, data, levels=[val], colors=color, linewidths=2, transform=proj)

    #         ax2.legend([
    #             plt.Line2D([0], [0], color=threshold_colors["Medium"], lw=2, label=">2 mg/m³ caution"),
    #             plt.Line2D([0], [0], color=threshold_colors["High"], lw=2, label=">4 mg/m³ high risk")
    #         ], loc="upper right", fontsize=8, title="Ash thresholds")

    #         # Colorbar (right side)
    #         if not hasattr(update, "colorbar"):
    #             cax = ax2.inset_axes([1.02, 0.1, 0.02, 0.8])
    #             update.colorbar = fig.colorbar(c, cax=cax, orientation="vertical")
    #             update.colorbar.set_label("Ash concentration (g/m³)", fontsize=10)

    #         if save_frames:
    #             frame_path = os.path.join(frames_dir, f"frame_{t+1:04d}.png")
    #             print(f"\n🖼️  [Frame Saver] ➤ Saving frame {t+1:04d}...")
    #             fig.savefig(frame_path, dpi=150, bbox_inches="tight")
    #             print(f"✅  [Frame Saved]   ➤ {frame_path}\n")

    #         return []

    #     self._draw_metadata_sidebar(fig, self.meta_attr)
    #     self._make_dirs(output_path)
    #     fig.tight_layout()
    #     ani = animation.FuncAnimation(fig, update, frames=valid_frames, blit=False, cache_frame_data=False)
    #     ani.save(output_path, writer="pillow", fps=self.fps, dpi=300)
    #     plt.close()
    #     print(f"✅ Saved animation Concentration through time at fixed altitude to {output_path}")

      

    def plot_vertical_profile_at_time(self, t_index, filename=None):
        time_label = f"T{t_index+1}"
        for z_index, z_val in enumerate(self.animator.levels):
            alt_label = self._get_altitude_label(t_index, z_val)
            alt_label=alt_label.replace("m agl", "_m_agl")
            filename = f"TimeSlices_Z{z_val:.1f}_{alt_label}.gif"
            filename=filename.replace(" ", "")
            
            self.plot_single_z_level(z_val, filename=os.path.join("vertical_profiles_timeSlice", filename))

    
    ################################################
    
    

    def animate_altitude(self, t_index: int, output_path: str, save_frames=True):
        if not (0 <= t_index < len(self.animator.datasets)):
            print(f"Invalid time index {t_index}. Must be between 0 and {len(self.animator.datasets) - 1}.")
            return

        ds = self.animator.datasets[t_index]
        fig = plt.figure(figsize=(16, 8))
        proj = ccrs.PlateCarree()
        ax1 = fig.add_subplot(1, 2, 1, projection=proj)
        ax2 = fig.add_subplot(1, 2, 2, projection=proj)

        meta = ds.attrs
        center_lat, center_lon = self._get_max_concentration_location()
        if center_lat is None or center_lon is None:
            print(f"No valid data found for time T{t_index + 1}. Skipping...")
            plt.close()
            return

        lat_idx, lon_idx, lon_min, lon_max, lat_min, lat_max = self._get_zoom_indices(center_lat, center_lon)
        
        lat_zoom = self.animator.lats[lat_idx]
        lon_zoom = self.animator.lons[lon_idx]

        valid_z = list(range(len(self.animator.levels)))

        # 🔵 Precompute global min/max
        all_data = []
        for z in valid_z:
            data = ds['ash_concentration'].values[z]
            interp = interpolate_grid(data,  self.lon_grid_global, self.lat_grid_global)
            interp = np.where(np.isnan(interp), 0, interp)
            all_data.append(interp)

        global_min = min(np.nanmin(arr) for arr in all_data)
        global_max = max(np.nanmax(arr) for arr in all_data)

        if not np.isfinite(global_min):
            global_min = 0
        if not np.isfinite(global_max):
            global_max = 0
        if global_min == global_max:
            levels = [0, 1]
        else:
            levels = np.linspace(global_min, global_max, 20)
            
        # Determine subfolder to save frames per GIF
        gif_name = os.path.splitext(os.path.basename(output_path))[0].replace(" ", "")
        frames_dir = os.path.join(os.path.dirname(output_path), gif_name)
        if save_frames:
            os.makedirs(frames_dir, exist_ok=True)



        def get_full_extent(data_array):
            if hasattr(data_array, 'dims'):
                lat_name = next((d for d in data_array.dims if "lat" in d.lower()), None)
                lon_name = next((d for d in data_array.dims if "lon" in d.lower()), None)
                if lat_name and lon_name:
                    lat = data_array[lat_name]
                    lon = data_array[lon_name]
                else:
                    raise ValueError("Latitude or longitude dimension not found in DataArray.")
            elif isinstance(data_array, np.ndarray) and data_array.ndim == 2:
                # fallback: use array shape with dummy extent
                ny, nx = data_array.shape
                lat = np.linspace(-90, 90, ny)
                lon = np.linspace(-180, 180, nx)
            else:
                raise TypeError("Unsupported type passed to get_full_extent")

            return [lon.min(), lon.max(), lat.min(), lat.max()]
        def update(z):
            ax1.clear()
            ax2.clear()

            interp = all_data[z]
            zoom_plot = interp[np.ix_(lat_idx, lon_idx)]
            
            valid_vals = interp[np.isfinite(interp)]

            alt_label = self._get_altitude_label(t_index, z+1)
            T_index_date_time=self._get_date_time(t_index)
            
            Title_zoom = f"Concentration fixed time through altitude\nT{t_index+1} | Z_index={z+1} | Alt={alt_label} (Zoom)\n{T_index_date_time}"
            Title_Full = f"Concentration fixed time through altitude\nT{t_index+1} | Z_index={z+1} | Alt={alt_label}\n{T_index_date_time}"
            ##########3

            c = self._plot_frame(ax1, interp, self.lon_grid_global, self.lat_grid_global, Title_Full, levels, "Linear", proj)
            self._plot_frame(ax2, zoom_plot, lon_zoom, lat_zoom, Title_zoom, levels, "Linear", proj, extent=get_full_extent(zoom_plot))

            self._add_country_labels(ax1, [self.lon_min, self.lon_max, self.lat_min, self.lat_max])
            self._add_country_labels(ax2, [lon_min, lon_max, lat_min, lat_max])

            if self.include_metadata:
                self._draw_metadata_sidebar(fig, meta)

            if np.nanmax(valid_vals) > self.threshold:
                ax1.contour(self.animator.lons, self.animator.lats, interp, levels=[self.threshold],
                                colors='yellow', linewidths=2, transform=proj)
                ax2.contour(lon_zoom, lat_zoom, zoom_plot, levels=[self.threshold],
                                colors='yellow', linewidths=2, transform=proj)

                
                ax2.text(0.99, 0.01, f"⚠ Yellow contour shows the chosen threshold of {self.threshold}\n Max concentration: {np.nanmax(valid_vals):.2f} > {self.threshold} g/m³",
                                transform=ax2.transAxes, ha='right', va='bottom',
                                fontsize=9, color='yellow',
                                bbox=dict(facecolor='k', alpha=0.8, edgecolor='yellow'))
           
             # Threshold contours
            thresholds = {
                "Low": 0.002,
                "Medium": 0.004
            }
            threshold_colors = {
                "Low": "yellow",
                "Medium": "orange",
                "High": "red"
            }

            # >4 mg/m³ (high risk)
            ax1.contour(
                self.lon_grid_global, self.lat_grid_global, interp,
                levels=[thresholds["Medium"]],
                colors=[threshold_colors["High"]],
                linewidths=2, transform=proj
            )
            ax2.contour(
                lon_zoom, lat_zoom, zoom_plot,
                levels=[thresholds["Medium"]],
                colors=[threshold_colors["High"]],
                linewidths=2, transform=proj
            )

            # >2 mg/m³ (caution)
            ax1.contour(
                self.lon_grid_global, self.lat_grid_global, interp,
                levels=[thresholds["Low"]],
                colors=[threshold_colors["Medium"]],
                linewidths=2, transform=proj
            )
            ax2.contour(
                lon_zoom, lat_zoom, zoom_plot,
                levels=[thresholds["Low"]],
                colors=[threshold_colors["Medium"]],
                linewidths=2, transform=proj
            )

            # Legend
            handles = [
                plt.Line2D([0], [0], color=threshold_colors["Medium"], lw=2, label=">2 mg/m³ caution"),
                plt.Line2D([0], [0], color=threshold_colors["High"], lw=2, label=">4 mg/m³ high risk")
            ]
            ax2.legend(handles=handles, loc="upper right", fontsize=8, title="Ash thresholds")

            if not hasattr(update, "colorbar"):
                update.colorbar = fig.colorbar(c, ax=[ax1, ax2], orientation="vertical")
                update.colorbar.set_label("Ash concentration (g/m³)")
            
            if save_frames:
                print(f"\n🖼️  [Frame Saver] ➤ Saving frame {z+1:04d} for Time Index: {t_index:03d}...")
                frame_path = os.path.join(frames_dir, f"frame_{z+1:04d}.png")
                fig.savefig(frame_path, dpi=150, bbox_inches="tight")
                print(f"✅  [Frame Saved]   ➤ {frame_path}\n")


            
            
            return []

        self._make_dirs(output_path)
        fig.tight_layout()
        ani = animation.FuncAnimation(fig, update, frames=valid_z, blit=False, cache_frame_data=False, interval =20)
        ani.save(output_path, writer="pillow", fps=self.fps, dpi=100)   
        #ani.save(output_path + ".mp4", writer="ffmpeg", fps=self.fps, dpi=200)
        plt.close()
        print(f"✅ Saved animation for Concentration fixed time through altitude T{t_index+1} to {output_path}")
        


    def animate_all_altitude_profiles(self, output_folder='altitude_profiles'):
        output_folder = os.path.join(self.output_dir, "altitude_profiles")
        os.makedirs(output_folder, exist_ok=True)

        datasets = getattr(self.animator, 'datasets', None)
        if datasets is None:
            print("❌ Error: self.animator.datasets is None")
            return

        total_profiles = len(datasets)
        print(f"📦 Total altitude profiles to animate: {total_profiles}")

        for t_index in range(total_profiles):
            print(f"🔢 Processing t_index: {t_index}")
            try:
                
                
                output_path = os.path.join(output_folder, f"vertical_T{t_index + 1:02d}.gif")
                
                print(f"🔄 Generating vertical profile animation for T{t_index + 1}...")
                self.animate_altitude(t_index, output_path)
            except IndexError as e:
                print(f"❌ IndexError at t_index {t_index}: {e}")
            except Exception as e:
                print(f"❌ Unexpected error at t_index {t_index}: {e}")

    


    
