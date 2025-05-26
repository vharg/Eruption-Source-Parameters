import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.ticker as mticker
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cartopy.io.shapereader as shpreader
from adjustText import adjust_text
from ash_animator.interpolation import interpolate_grid
from ash_animator.basemaps import draw_etopo_basemap
import tempfile

class Plot_Horizontal_Data:
    def __init__(self, animator, output_dir="plots", cmap="rainbow", fps=2,
                 include_metadata=True, threshold=0.1,
                 zoom_width_deg=5.0, zoom_height_deg=5.0, zoom_level=10, static_frame_export=False, basemap_mode='stock'):
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
        self.interpolate_grid= interpolate_grid
        self._draw_etopo_basemap=draw_etopo_basemap
        self.zoom_level=zoom_level
        self.static_frame_export=static_frame_export
        self.meta_attr=self.animator.datasets[0].attrs
        self.basemap_mode=basemap_mode

    def _make_dirs(self, path):
        os.makedirs(os.path.abspath(os.path.join(os.getcwd(), os.path.dirname(path))), exist_ok=True)

    def _get_max_concentration_location(self, field):
        max_val = -np.inf
        lat = lon = None
        for ds in self.animator.datasets:
            data = ds[field].values
            if np.max(data) > max_val:
                max_val = np.max(data)
                idx = np.unravel_index(np.argmax(data), data.shape)
                lat = self.animator.lat_grid[idx]
                lon = self.animator.lon_grid[idx]
        return lat, lon

    def _get_zoom_indices(self, center_lat, center_lon):
        lon_min = center_lon - self.zoom_width / 2
        lon_max = center_lon + self.zoom_width / 2
        lat_min = center_lat - self.zoom_height / 2
        lat_max = center_lat + self.zoom_height / 2
        lat_idx = np.where((self.animator.lats >= lat_min) & (self.animator.lats <= lat_max))[0]
        lon_idx = np.where((self.animator.lons >= lon_min) & (self.animator.lons <= lon_max))[0]
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

        # Split into two columns
        mid = len(lines) // 2 + len(lines) % 2
        left_lines = lines[:mid]
        right_lines = lines[mid:]

        left_text = "\n".join(left_lines)
        right_text = "\n".join(right_lines)

        # right column
        fig.text(0.05, 0.05, left_text, va='bottom', ha='left',
                fontsize=9, family='monospace', color='black',
                bbox=dict(facecolor='white', alpha=0.8, edgecolor='gray'))

        # left column
        fig.text(0.3, 0.05, right_text, va='bottom', ha='left',
                fontsize=9, family='monospace', color='black',
                bbox=dict(facecolor='white', alpha=0.8, edgecolor='gray'))

    
    

    def _plot_frame(self, ax, data, lons, lats, title, levels, scale_label, proj, basemap_mode='basemap'):
        ax.set_title(title)
        ax.set_extent([lons.min(), lons.max(), lats.min(), lats.max()])
        try:
            ax.coastlines(zorder=1)
            ax.add_feature(cfeature.BORDERS, linestyle=':', zorder=1)
            draw_etopo_basemap(ax, mode= self.basemap_mode, zoom=self.zoom_level)
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
    # def _plot_frame(self, ax, data, lons, lats, title, levels, scale_label, proj):
    #     draw_etopo_basemap(ax, mode='basemap', zoom=self.zoom_level)
    #     c = ax.contourf(lons, lats, data, levels=levels, cmap=self.cmap, alpha=0.6, transform=proj)
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

    def get_available_2d_fields(self):
        ds = self.animator.datasets[0]
        return [v for v in ds.data_vars if ds[v].ndim == 2]

    def plot_single_field_over_time(self, field, filename="field.gif"):
        output_path = os.path.join(self.output_dir, "2d_fields", field, filename)
        meta = self.animator.datasets[0].attrs
        center_lat, center_lon = self._get_max_concentration_location(field)
        lat_idx, lon_idx, lon_min, lon_max, lat_min, lat_max = self._get_zoom_indices(center_lat, center_lon)
        lat_zoom = self.animator.lats[lat_idx]
        lon_zoom = self.animator.lons[lon_idx]

        valid_frames = []
        for t in range(len(self.animator.datasets)):
            data = self.animator.datasets[t][field].values
            interp = self.interpolate_grid(data, self.animator.lon_grid, self.animator.lat_grid)
            if np.isfinite(interp).sum() > 0:
                valid_frames.append(t)

        if not valid_frames:
            print(f"No valid frames to plot for field '{field}'.")
            return

        fig = plt.figure(figsize=(16, 8))
        proj = ccrs.PlateCarree()
        ax1 = fig.add_subplot(1, 2, 1, projection=proj)
        ax2 = fig.add_subplot(1, 2, 2, projection=proj)

        def update(t):
            ax1.clear()
            ax2.clear()
            data = self.animator.datasets[t][field].values
            interp = self.interpolate_grid(data, self.animator.lon_grid, self.animator.lat_grid)
            zoom = interp[np.ix_(lat_idx, lon_idx)]
            valid = interp[np.isfinite(interp)]
            if valid.size == 0:
                return []

            min_val, max_val = np.nanmin(valid), np.nanmax(valid)
            log_cutoff = 1e-3
            use_log = min_val > log_cutoff and (max_val / (min_val + 1e-6)) > 100
            levels = np.logspace(np.log10(log_cutoff), np.log10(max_val), 20) if use_log else np.linspace(0, max_val, 20)
            plot_data = np.where(interp > log_cutoff, interp, np.nan) if use_log else interp
            scale_label = "Log" if use_log else "Linear"

            c = self._plot_frame(ax1, plot_data, self.animator.lons, self.animator.lats,
                                 f"T{t+1} | {field} (Full - {scale_label})", levels, scale_label, proj)
            self._plot_frame(ax2, zoom, lon_zoom, lat_zoom,
                             f"T{t+1} | {field} (Zoom - {scale_label})", levels, scale_label, proj)

            self._add_country_labels(ax1, [self.animator.lons.min(), self.animator.lons.max(),
                                           self.animator.lats.min(), self.animator.lats.max()])
            self._add_country_labels(ax2, [lon_min, lon_max, lat_min, lat_max])

           # Inside update() function:
            if not hasattr(update, "colorbar"):
                unit_label =  f"{field}:({self.animator.datasets[0][field].attrs.get('units', field)})" #self.animator.datasets[0][field].attrs.get("units", field)
                update.colorbar = fig.colorbar(c, ax=[ax1, ax2], orientation='vertical', label=unit_label)
                formatter = mticker.FuncFormatter(lambda x, _: f'{x:.2g}')
                update.colorbar.ax.yaxis.set_major_formatter(formatter)

            
            if np.nanmax(valid) > self.threshold:
                ax1.contour(self.animator.lons, self.animator.lats, interp, levels=[self.threshold],
                        colors='red', linewidths=2, transform=proj)
                ax2.contour(lon_zoom, lat_zoom, zoom, levels=[self.threshold],
                            colors='red', linewidths=2, transform=proj)
                ax2.text(0.99, 0.01, f"⚠ Max Thresold Exceed: {np.nanmax(valid):.2f} > {self.threshold}",
                        transform=ax2.transAxes, ha='right', va='bottom',
                        fontsize=9, color='red',
                        bbox=dict(facecolor='white', alpha=0.8, edgecolor='red'))

            if self.static_frame_export:
                frame_folder = os.path.join(self.output_dir, "frames", field)
            os.makedirs(frame_folder, exist_ok=True)
            frame_path = os.path.join(frame_folder, f"frame_{t+1:04d}.jpg")
            plt.savefig(frame_path, bbox_inches='tight')
            print(f"🖼️ Saved static frame: {frame_path}")
                    
            return []

        if self.include_metadata:
            self._draw_metadata_sidebar(fig, meta)

        self._make_dirs(output_path)
        fig.tight_layout()
        ani = animation.FuncAnimation(fig, update, frames=valid_frames, blit=False, cache_frame_data =False)
        ani.save(output_path, writer='pillow', fps=self.fps)
        plt.close()
        print(f"✅ Saved enhanced 2D animation for {field} to {output_path}")

    # def export_frames_as_jpgs(self, fields=None, include_metadata=True):
    #     all_fields = self.get_available_2d_fields()
    #     if fields:
    #         fields = [f for f in fields if f in all_fields]
    #     else:
    #         fields = all_fields

    #     meta = self.animator.datasets[0].attrs

    #     for field in fields:
    #         print(f"📤 Exporting frames for field: {field}")
    #         output_folder = os.path.join(self.output_dir, "frames", field)
    #         os.makedirs(output_folder, exist_ok=True)

    #         center_lat, center_lon = self._get_max_concentration_location(field)
    #         lat_idx, lon_idx, lon_min, lon_max, lat_min, lat_max = self._get_zoom_indices(center_lat, center_lon)
    #         lat_zoom = self.animator.lats[lat_idx]
    #         lon_zoom = self.animator.lons[lon_idx]

    #         for t, ds in enumerate(self.animator.datasets):
    #             data = ds[field].values
    #             interp = self.interpolate_grid(data, self.animator.lon_grid, self.animator.lat_grid)
    #             if not np.isfinite(interp).any():
    #                 continue

    #             fig = plt.figure(figsize=(16, 8))
    #             proj = ccrs.PlateCarree()
    #             ax1 = fig.add_subplot(1, 2, 1, projection=proj)
    #             ax2 = fig.add_subplot(1, 2, 2, projection=proj)
    #             zoom = interp[np.ix_(lat_idx, lon_idx)]
    #             valid = interp[np.isfinite(interp)]
    #             min_val, max_val = np.nanmin(valid), np.nanmax(valid)
    #             log_cutoff = 1e-3
    #             use_log = min_val > log_cutoff and (max_val / (min_val + 1e-6)) > 100
    #             levels = np.logspace(np.log10(log_cutoff), np.log10(max_val), 20) if use_log else np.linspace(0, max_val, 20)
    #             plot_data = np.where(interp > log_cutoff, interp, np.nan) if use_log else interp
    #             scale_label = "Log" if use_log else "Linear"

    #             c = self._plot_frame(ax1, plot_data, self.animator.lons, self.animator.lats,
    #                                 f"T{t+1} | {field} (Full - {scale_label})", levels, scale_label, proj)
    #             self._plot_frame(ax2, zoom, lon_zoom, lat_zoom,
    #                             f"T{t+1} | {field} (Zoom - {scale_label})", levels, scale_label, proj)

    #             self._add_country_labels(ax1, [self.animator.lons.min(), self.animator.lons.max(),
    #                                         self.animator.lats.min(), self.animator.lats.max()])
    #             self._add_country_labels(ax2, [lon_min, lon_max, lat_min, lat_max])

    #             if include_metadata:
    #                 self._draw_metadata_sidebar(fig, meta)

    #             cbar = fig.colorbar(c, ax=[ax1, ax2], orientation='vertical', shrink=0.75, pad=0.03)
    #             unit_label = f"{field}:({self.animator.datasets[0][field].attrs.get('units', field)})"
    #             cbar.set_label(unit_label)
    #             formatter = mticker.FuncFormatter(lambda x, _: f'{x:.2g}')
    #             cbar.ax.yaxis.set_major_formatter(formatter)

    #             if np.nanmax(valid) > self.threshold:
    #                 ax1.contour(self.animator.lons, self.animator.lats, interp, levels=[self.threshold],
    #                             colors='red', linewidths=2, transform=proj)
    #                 ax2.contour(lon_zoom, lat_zoom, zoom, levels=[self.threshold],
    #                             colors='red', linewidths=2, transform=proj)
    #                 ax2.text(0.99, 0.01, f"⚠ Max: {np.nanmax(valid):.2f} > {self.threshold}",
    #                         transform=ax2.transAxes, ha='right', va='bottom',
    #                         fontsize=9, color='red',
    #                         bbox=dict(facecolor='white', alpha=0.8, edgecolor='red'))

    #             frame_path = os.path.join(output_folder, f"frame_{t+1:04d}.jpg")
    #             plt.savefig(frame_path, dpi=150, bbox_inches='tight')
    #             plt.close(fig)
    #             print(f"📸 Saved {frame_path}")
