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

    
    
    def _plot_frame(self, ax, data, lons, lats, title, levels, scale_label, proj):
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



    def plot_single_z_level(self, z_km, filename="z_level.gif"):
        levels = np.array(self.animator.levels)

        # Find closest available Z level
        if not np.any(np.isclose(levels, z_km)):
            closest_z = levels[np.argmin(np.abs(levels - z_km))]
            print(f"⚠ Z level {z_km} km not found. Using closest available level: {closest_z} km instead.")
            z_km = closest_z

        z_index = np.where(np.isclose(levels, z_km))[0][0]
        output_path = os.path.join(self.output_dir, "z_levels", filename)

        fig = plt.figure(figsize=(16, 8))
        proj = ccrs.PlateCarree()
        ax1 = fig.add_subplot(1, 2, 1, projection=proj)
        ax2 = fig.add_subplot(1, 2, 2, projection=proj)

        center_lat, center_lon = self._get_max_concentration_location()
        lat_idx, lon_idx, lon_min, lon_max, lat_min, lat_max = self._get_zoom_indices(center_lat, center_lon)
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

        def update(t):
            ax1.clear()
            ax2.clear()

            interp = all_data[t]
            zoom_plot = interp[np.ix_(lat_idx, lon_idx)]
            valid_vals = interp[np.isfinite(interp)]

            c = self._plot_frame(ax1, interp, self.lon_grid_global, self.lat_grid_global,
                                f"T{t+1} | Alt: {z_km} km", levels, "Linear", proj)
            self._plot_frame(ax2, zoom_plot, lon_zoom, lat_zoom,
                            f"T{t+1} | Alt: {z_km} km (Zoom)", levels, "Linear", proj)

            self._add_country_labels(ax1, [self.lon_min, self.lon_max, self.lat_min, self.lat_max])
            self._add_country_labels(ax2, [lon_min, lon_max, lat_min, lat_max])

           

            
            if np.nanmax(valid_vals) > self.threshold:
                ax1.contour( self.lon_grid_global, self.lat_grid_global, interp, levels=[self.threshold],
                                colors='yellow', linewidths=2, transform=proj)
                ax2.contour(lon_zoom, lat_zoom, zoom_plot, levels=[self.threshold],
                                colors='yellow', linewidths=2, transform=proj)

                
                ax2.text(0.99, 0.01, f"⚠ Max Thresold Exceed: {np.nanmax(valid_vals):.2f} > {self.threshold} g/m³",
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
            
            
            
            
            return []

        self._draw_metadata_sidebar(fig, self.meta_attr)
        self._make_dirs(output_path)
        fig.tight_layout()
        ani = animation.FuncAnimation(fig, update, frames=valid_frames, blit=False, cache_frame_data=False)
        ani.save(output_path, writer="pillow", fps=self.fps, dpi=300)
        plt.close()
        print(f"✅ Saved Z-level animation to {output_path}")



        # self._draw_metadata_sidebar(fig, meta)
        # self._make_dirs(output_path)
        # fig.tight_layout()
        # ani = animation.FuncAnimation(fig, update, frames=valid_frames, blit=False, cache_frame_data =False)
        # ani.save(output_path, writer='pillow', fps=self.fps, dpi=300)
        # plt.close()
        # print(f"✅ Saved Z-level animation to {output_path}")

    def plot_vertical_profile_at_time(self, t_index, filename=None):
        time_label = f"T{t_index+1}"
        for z_index, z_val in enumerate(self.animator.levels):
            filename = f"TimeSlices_Z{z_val:.1f}km.gif"
            self.plot_single_z_level(z_val, filename=os.path.join("vertical_profiles_timeSlice", filename))

    
    ################################################
    
    

    def animate_altitude(self, t_index: int, output_path: str):
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

        def update(z):
            ax1.clear()
            ax2.clear()

            interp = all_data[z]
            zoom_plot = interp[np.ix_(lat_idx, lon_idx)]
            
            valid_vals = interp[np.isfinite(interp)]

            title1 = f"T{t_index+1} | Alt: {self.animator.levels[z]} km"
            title2 = f"T{t_index+1} | Alt: {self.animator.levels[z]} km (Zoom)"

            c = self._plot_frame(ax1, interp, self.lon_grid_global, self.lat_grid_global, title1, levels, "Linear", proj)
            self._plot_frame(ax2, zoom_plot, lon_zoom, lat_zoom, title2, levels, "Linear", proj)

            self._add_country_labels(ax1, [self.lon_min, self.lon_max, self.lat_min, self.lat_max])
            self._add_country_labels(ax2, [lon_min, lon_max, lat_min, lat_max])

            if self.include_metadata:
                self._draw_metadata_sidebar(fig, meta)

            if np.nanmax(valid_vals) > self.threshold:
                ax1.contour(self.animator.lons, self.animator.lats, interp, levels=[self.threshold],
                                colors='yellow', linewidths=2, transform=proj)
                ax2.contour(lon_zoom, lat_zoom, zoom_plot, levels=[self.threshold],
                                colors='yellow', linewidths=2, transform=proj)

                
                ax2.text(0.99, 0.01, f"⚠ Max Thresold Exceed: {np.nanmax(valid_vals):.2f} > {self.threshold} g/m³",
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
            
            
            return []

        self._make_dirs(output_path)
        fig.tight_layout()
        ani = animation.FuncAnimation(fig, update, frames=valid_z, blit=False, cache_frame_data=False, interval =20)
        ani.save(output_path, writer="pillow", fps=self.fps, dpi=100)   
        #ani.save(output_path + ".mp4", writer="ffmpeg", fps=self.fps, dpi=200)
        plt.close()
        print(f"✅ Saved altitude animation for T{t_index+1} to {output_path}")
        


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

    


    
    def export_frames_as_jpgs(self, include_metadata: bool = True):
        output_folder = os.path.join(self.output_dir, "frames")
        os.makedirs(output_folder, exist_ok=True)
        meta = self.animator.datasets[0].attrs

        for z_index, z_val in enumerate(self.animator.levels):
            z_dir = os.path.join(output_folder, f"Z{z_val:.1f}km")
            os.makedirs(z_dir, exist_ok=True)
            for t in range(len(self.animator.datasets)):
                data = self.animator.datasets[t]['ash_concentration'].values[z_index]
                interp = interpolate_grid(data,  self.lon_grid_global, self.lat_grid_global)
                interp = np.where(np.isnan(interp), 0, interp)

                min_val = np.nanmin(interp)
                max_val = np.nanmax(interp)

                if not np.isfinite(min_val):
                    min_val = 0
                if not np.isfinite(max_val):
                    max_val = 0

                if min_val == max_val:
                    levels = [0, 1]
                else:
                    levels = np.linspace(min_val, max_val, 20)

                fig = plt.figure(figsize=(16, 8))
                proj = ccrs.PlateCarree()
                ax1 = fig.add_subplot(1, 2, 1, projection=proj)
                ax2 = fig.add_subplot(1, 2, 2, projection=proj)

                center_lat, center_lon = self._get_max_concentration_location()
                lat_idx, lon_idx, lon_min, lon_max, lat_min, lat_max = self._get_zoom_indices(center_lat, center_lon)
                zoom_plot = interp[np.ix_(lat_idx, lon_idx)]
                lon_zoom = self.animator.lons[lon_idx]
                lat_zoom = self.animator.lats[lat_idx]

                c = self._plot_frame(ax1, interp, self.lon_grid_global, self.lat_grid_global,
                                    f"T{t+1} | Alt: {z_val} km", levels, "Linear", proj)
                self._plot_frame(ax2, zoom_plot, lon_zoom, lat_zoom,
                                f"T{t+1} | Alt: {z_val} km (Zoom)", levels, "Linear", proj)

                self._add_country_labels(ax1, [self.lon_min, self.lon_max, self.lat_min, self.lat_max])
                self._add_country_labels(ax2, [lon_min, lon_max, lat_min, lat_max])
                
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

               

                if include_metadata:
                    self._draw_metadata_sidebar(fig, meta)

                cbar = fig.colorbar(c, ax=[ax1, ax2], orientation="vertical")
                cbar.set_label("Ash concentration (g/m³)")

                frame_path = os.path.join(z_dir, f"frame_{t+1:04d}.jpg")
                plt.savefig(frame_path, bbox_inches="tight")
                plt.close()
                print(f"📸 Saved {frame_path}")
