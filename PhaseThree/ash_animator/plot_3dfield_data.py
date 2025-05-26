import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.ticker as mticker
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cartopy.io.shapereader as shpreader
from adjustText import adjust_text
from .interpolation import interpolate_grid
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
                
        self.output_dir = os.path.abspath(
            os.path.join(
                os.environ.get("NAME_OUTPUT_DIR", tempfile.gettempdir()),
                output_dir
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
        self.meta_attr=self.animator.datasets[0].attrs
        
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
        
        #####################3
        
    def _make_dirs(self, path):
        path = os.path.abspath(os.path.join(os.getcwd(), os.path.dirname(path)))
        os.makedirs(path, exist_ok=True)

    def _get_zoom_indices(self, center_lat, center_lon):
        lon_min = center_lon - self.zoom_width / 2
        lon_max = center_lon + self.zoom_width / 2
        lat_min = center_lat - self.zoom_height / 2
        lat_max = center_lat + self.zoom_height / 2
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

    # def _plot_frame(self, ax, data, lons, lats, title, levels, scale_label, proj):
    #     draw_etopo_basemap(ax, mode="basemap", zoom=self.zoom_level)
    #     c = ax.contourf(lons, lats, data, levels=levels, cmap=self.cmap, alpha=0.6, transform=proj)
    #     ax.contour(lons, lats, data, levels=levels, colors='black', linewidths=0.5, transform=proj)
    #     ax.set_title(title)
    #     ax.set_extent([lons.min(), lons.max(), lats.min(), lats.max()])
    #     ax.coastlines()
    #     ax.add_feature(cfeature.BORDERS, linestyle=':')
    #     ax.add_feature(cfeature.LAND)
    #     ax.add_feature(cfeature.OCEAN)
        
    #     raw= (self.meta_attr.get('release_location'))
        
    #     if raw is not None:
    #         # Split and strip
    #         lon_str, lat_str = raw.strip().split()
            
    #                 # Convert to float with direction handling
    #         lon = float(lon_str[:-1]) * (1 if lon_str[-1].upper() == 'E' else -1)
    #         lat = float(lat_str[:-1]) * (1 if lat_str[-1].upper() == 'N' else -1)
            
    #         ax.plot(lon, lat, marker='^', color='yellow',
    #             markersize=7, transform=proj, label="Vent Location", zorder=5)
    #         ax.legend(loc="upper left", fontsize=7)
    #     return c
    
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
           
        # if z_km not in self.animator.levels:
        #     print(f"Z level {z_km} km not found.")
        #     return
        # z_index = np.where(self.animator.levels == z_km)[0][0]
        
        levels = np.array(self.animator.levels)

        # Find closest available Z level
        if not np.any(np.isclose(levels, z_km)):
            closest_z = levels[np.argmin(np.abs(levels - z_km))]
            print(f"⚠ Z level {z_km} km not found. Using closest available level: {closest_z} km instead.")
            z_km = closest_z

        z_indices = np.where(np.isclose(levels, z_km))[0]
        if len(z_indices) == 0:
            print(f"❌ No matching Z level found near {z_km} km.")
            return

        z_index = z_indices[0]
        print(f"✅ Z index: {z_index} for Z = {z_km} km")
        
        output_path = os.path.join(self.output_dir, "z_levels", filename)
        fig = plt.figure(figsize=(16, 8))
        proj = ccrs.PlateCarree()
        ax1 = fig.add_subplot(1, 2, 1, projection=proj)
        ax2 = fig.add_subplot(1, 2, 2, projection=proj)

        center_lat, center_lon = self._get_max_concentration_location()
        lat_idx, lon_idx, lon_min, lon_max, lat_min, lat_max = self._get_zoom_indices(center_lat, center_lon)
        lat_zoom = self.animator.lats[lat_idx]
        lon_zoom = self.animator.lons[lon_idx]
        lon_zoom_grid, lat_zoom_grid = np.meshgrid(lon_zoom, lat_zoom)
        
       

        meta = self.animator.datasets[0].attrs
        valid_frames = []
        for t in range(len(self.animator.datasets)):
            interp = interpolate_grid(self.animator.datasets[t]['ash_concentration'].values[z_index],
                                      self.animator.lon_grid, self.animator.lat_grid)
            if np.isfinite(interp).sum() > 0:
                valid_frames.append(t)
        if not valid_frames:
            print(f"No valid frames for Z={z_km} km.")
            plt.close()
            return

        def update(t):
            ax1.clear()
            ax2.clear()

            data = self.animator.datasets[t]['ash_concentration'].values[z_index]
            interp = interpolate_grid(data, self.animator.lon_grid, self.animator.lat_grid)
            interp = np.where(interp < 0, np.nan, interp)
            zoom_plot = interp[np.ix_(lat_idx, lon_idx)]

            valid_vals = interp[np.isfinite(interp)]
            if valid_vals.size == 0:
                return []

            min_val, max_val = np.nanmin(valid_vals), np.nanmax(valid_vals)
            log_cutoff = 1e-3
            use_log = min_val > log_cutoff and (max_val / (min_val + 1e-6)) > 100

            levels = (
                np.logspace(np.log10(log_cutoff), np.log10(max_val), 20)
                if use_log else
                np.linspace(0, max_val, 20)
            )
            data_for_plot = np.where(interp > log_cutoff, interp, np.nan) if use_log else interp
            scale_label = "Log" if use_log else "Linear"

            c = self._plot_frame(ax1, data_for_plot, self.animator.lons, self.animator.lats,
                                f"T{t+1} | Alt: {z_km} km (Full - {scale_label})", levels, scale_label, proj)
            self._plot_frame(ax2, zoom_plot, lon_zoom, lat_zoom,
                            f"T{t} | Alt: {z_km} km (Zoom - {scale_label})", levels, scale_label, proj)

            self._add_country_labels(ax1, [self.animator.lons.min(), self.animator.lons.max(),
                                        self.animator.lats.min(), self.animator.lats.max()])
            self._add_country_labels(ax2, [lon_min, lon_max, lat_min, lat_max])

            if not hasattr(update, "colorbar"):
                update.colorbar = fig.colorbar(c, ax=[ax1, ax2], orientation='vertical',
                                            label="Ash concentration (g/m³)")
                formatter = mticker.FuncFormatter(lambda x, _: f'{x:.2g}')
                update.colorbar.ax.yaxis.set_major_formatter(formatter)

            # ✅ Draw threshold outline and label only if exceeded
            if np.nanmax(valid_vals) > self.threshold:
                ax1.contour(self.animator.lons, self.animator.lats, interp, levels=[self.threshold],
                            colors='red', linewidths=2, transform=proj)
                ax2.contour(lon_zoom, lat_zoom, zoom_plot, levels=[self.threshold],
                            colors='red', linewidths=2, transform=proj)
                ax2.text(0.99, 0.01, f"⚠ Max Thresold Exceed: {np.nanmax(valid_vals):.2f} > {self.threshold} g/m³",
                        transform=ax2.transAxes, ha='right', va='bottom',
                        fontsize=9, color='red',
                        bbox=dict(facecolor='white', alpha=0.8, edgecolor='red'))

            return []

  


        self._draw_metadata_sidebar(fig, meta)
        self._make_dirs(output_path)
        fig.tight_layout()
        ani = animation.FuncAnimation(fig, update, frames=valid_frames, blit=False, cache_frame_data =False)
        ani.save(output_path, writer='pillow', fps=self.fps, dpi=300)
        plt.close()
        print(f"✅ Saved Z-level animation to {output_path}")

    def plot_vertical_profile_at_time(self, t_index, filename=None):
        time_label = f"T{t_index+1}"
        for z_index, z_val in enumerate(self.animator.levels):
            filename = f"TimeSlices_Z{z_val:.1f}km.gif"
            self.plot_single_z_level(z_val, filename=os.path.join("vertical_profiles_timeSlice", filename))

    
    ################################################
    
    
    
    def animate_altitude(self, t_index: int, output_path: str):
        if not (0 <= t_index < len(self.animator.datasets)):
            print(f"Invalid time index {t_index}. Must be between 0 and {len(self.animator.datasets) - 1}.")
        

        ds = self.animator.datasets[t_index]
        fig = plt.figure(figsize=(18, 7))
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
        lon_zoom_grid, lat_zoom_grid = np.meshgrid(lon_zoom, lat_zoom)

        z_indices_with_data = []
        for z_index in range(len(self.animator.levels)):
            data = ds['ash_concentration'].values[z_index]
            interp = interpolate_grid(data, self.animator.lon_grid, self.animator.lat_grid)
            if np.isfinite(interp).sum() > 0:
                z_indices_with_data.append(z_index)

        if not z_indices_with_data:
            print(f"No valid Z-levels at time T{t_index + 1}.")
            plt.close()
            return

        def update(z_index):
            ax1.clear()
            ax2.clear()

            data = ds['ash_concentration'].values[z_index]
            interp = interpolate_grid(data, self.animator.lon_grid, self.animator.lat_grid)
            interp = np.where(interp < 0, np.nan, interp)
            zoom_plot = interp[np.ix_(lat_idx, lon_idx)]

            valid_vals = interp[np.isfinite(interp)]
            #valid_vals = interp[np.isfinite(interp)].astype(np.float64)

            if valid_vals.size == 0:
                return []

            min_val, max_val = np.nanmin(valid_vals), np.nanmax(valid_vals)
            log_cutoff = 1e-3
            use_log = min_val > log_cutoff and (max_val / (min_val + 1e-6)) > 100

            levels = np.logspace(np.log10(log_cutoff), np.log10(max_val), 20) if use_log else np.linspace(0, max_val, 20)
            data_for_plot = np.where(interp > log_cutoff, interp, np.nan) if use_log else interp
            scale_label = "Log" if use_log else "Linear"

            title1 = f"T{t_index + 1} | Alt: {self.animator.levels[z_index]} km (Full - {scale_label})"
            title2 = f"T{t_index + 1} | Alt: {self.animator.levels[z_index]} km (Zoom - {scale_label})"

            c1 = self._plot_frame(ax1, data_for_plot, self.animator.lons, self.animator.lats, title1, levels, scale_label, proj)
            self._plot_frame(ax2, zoom_plot, lon_zoom, lat_zoom, title2, levels, scale_label, proj)

            self._add_country_labels(ax1, [self.lon_min, self.lon_max, self.lat_min, self.lat_max])
            self._add_country_labels(ax2, [lon_min, lon_max, lat_min, lat_max])

            if self.include_metadata:
                self._draw_metadata_sidebar(fig, meta)

            if not hasattr(update, "colorbar"):
                update.colorbar = fig.colorbar(c1, ax=[ax1, ax2], orientation='vertical',
                                                label="Ash concentration (g/m³)", shrink=0.75)
                formatter = mticker.FuncFormatter(lambda x, _: f'{x:.2g}')
                update.colorbar.ax.yaxis.set_major_formatter(formatter)

            if np.nanmax(valid_vals) > self.threshold:
                ax1.contour(self.animator.lons, self.animator.lats, interp, levels=[self.threshold],
                            colors='red', linewidths=2, transform=proj)
                ax2.contour(lon_zoom, lat_zoom, zoom_plot, levels=[self.threshold],
                            colors='red', linewidths=2, transform=proj)

            
                ax2.text(0.99, 0.01, f"⚠ Max Thresold Exceed: {np.nanmax(valid_vals):.2f} > {self.threshold} g/m³",
                            transform=ax2.transAxes, ha='right', va='bottom',
                            fontsize=9, color='red',
                            bbox=dict(facecolor='white', alpha=0.8, edgecolor='red'))
            return []

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        #fig.set_size_inches(18, 7)
        fig.tight_layout(rect=[0.02, 0.02, 0.98, 0.98])
        ani = animation.FuncAnimation(fig, update, frames=z_indices_with_data, blit=False, cache_frame_data =False)
        
        if not z_indices_with_data:
            print(f"❌ No valid frames to animate for T={t_index}.")
            plt.close()
        else:

            ani.save(output_path, writer='pillow', fps=self.fps, dpi=200)
            plt.close()
            print(f"✅ Saved vertical profile animation for T{t_index + 1} to {output_path}")



    # def animate_all_altitude_profiles(self, output_folder='altitude_profiles'):
    #     output_folder = os.path.join(self.output_dir, "altitude_profiles")
    #     os.makedirs(output_folder, exist_ok=True)
    #     for t_index in range(len(self.animator.datasets)):
    #         output_path = os.path.join(output_folder, f"vertical_T{t_index + 1:02d}.gif")
    #         print(f"🔄 Generating vertical profile animation for T{t_index + 1}...")
    #         self.animate_altitude(t_index, output_path)

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
        legend_text = "\\n".join([
            f"Run name:        {meta.get('run_name', 'N/A')}",
            f"Run time:        {meta.get('run_time', 'N/A')}",
            f"Met data:        {meta.get('met_data', 'N/A')}",
            f"Start release:   {meta.get('start_of_release', 'N/A')}",
            f"End release:     {meta.get('end_of_release', 'N/A')}",
            f"Strength:        {meta.get('source_strength', 'N/A')} g/s",
            f"Location:        {meta.get('release_location', 'N/A')}",
            f"Height:          {meta.get('release_height', 'N/A')} m asl",
            f"Duration:        {meta.get('run_duration', 'N/A')}"
        ])
        for z_index, z_val in enumerate(self.animator.levels):
            z_dir = os.path.join(output_folder, f"Z{z_val:.1f}km")
            os.makedirs(z_dir, exist_ok=True)
            for t in range(len(self.animator.datasets)):
                data = self.animator.datasets[t]['ash_concentration'].values[z_index]
                interp = interpolate_grid(data, self.animator.lon_grid, self.animator.lat_grid)
                if not np.isfinite(interp).any():
                    continue
                fig = plt.figure(figsize=(16, 8))
                proj = ccrs.PlateCarree()
                ax1 = fig.add_subplot(1, 2, 1, projection=proj)
                ax2 = fig.add_subplot(1, 2, 2, projection=proj)
                valid_vals = interp[np.isfinite(interp)]
                min_val, max_val = np.nanmin(valid_vals), np.nanmax(valid_vals)
                log_cutoff = 1e-3
                use_log = min_val > log_cutoff and (max_val / (min_val + 1e-6)) > 100
                levels = np.logspace(np.log10(log_cutoff), np.log10(max_val), 20) if use_log else np.linspace(0, max_val, 20)
                data_for_plot = np.where(interp > log_cutoff, interp, np.nan) if use_log else interp
                scale_label = "Log" if use_log else "Linear"
                center_lat, center_lon = self._get_max_concentration_location()
                lat_idx, lon_idx, lon_min, lon_max, lat_min, lat_max = self._get_zoom_indices(center_lat, center_lon)
                zoom_plot = interp[np.ix_(lat_idx, lon_idx)]
                lon_zoom = self.animator.lons[lon_idx]
                lat_zoom = self.animator.lats[lat_idx]
                c1 = self._plot_frame(ax1, data_for_plot, self.animator.lons, self.animator.lats,
                                      f"T{t+1} | Alt: {z_val} km (Full - {scale_label})", levels, scale_label, proj)
                self._plot_frame(ax2, zoom_plot, lon_zoom, lat_zoom,
                                 f"T{t+1} | Alt: {z_val} km (Zoom - {scale_label})", levels, scale_label, proj)
                self._add_country_labels(ax1, [self.animator.lons.min(), self.animator.lons.max(),
                                               self.animator.lats.min(), self.animator.lats.max()])
                self._add_country_labels(ax2, [lon_min, lon_max, lat_min, lat_max])
                
                if np.nanmax(valid_vals) > self.threshold:
                    ax1.contour(self.animator.lons, self.animator.lats, interp, levels=[self.threshold],
                                colors='red', linewidths=2, transform=proj)
                    ax2.contour(lon_zoom, lat_zoom, zoom_plot, levels=[self.threshold],
                                colors='red', linewidths=2, transform=proj)
                    ax2.text(0.99, 0.01, f"⚠ Max: {np.nanmax(valid_vals):.2f} > {self.threshold} g/m³",
                             transform=ax2.transAxes, ha='right', va='bottom',
                             fontsize=9, color='red',
                             bbox=dict(facecolor='white', alpha=0.8, edgecolor='red'))
                if include_metadata:
                    self._draw_metadata_sidebar(fig, meta)
                cbar = fig.colorbar(c1, ax=[ax1, ax2], orientation='vertical', shrink=0.75, pad=0.03)
                cbar.set_label("Ash concentration (g/m³)")
                formatter = mticker.FuncFormatter(lambda x, _: f'{x:.2g}')
                cbar.ax.yaxis.set_major_formatter(formatter)
                frame_path = os.path.join(z_dir, f"frame_{t+1:04d}.jpg")
                plt.savefig(frame_path, bbox_inches='tight')
                plt.close()
                print(f"📸 Saved {frame_path}")
