
# import os
# import numpy as np
# import matplotlib.pyplot as plt
# import matplotlib.animation as animation
# import matplotlib.ticker as mticker
# import cartopy.crs as ccrs
# import cartopy.feature as cfeature
# from adjustText import adjust_text
# import cartopy.io.shapereader as shpreader
# from .interpolation import interpolate_grid
# from .basemaps import draw_etopo_basemap

# def animate_all_z_levels(animator, output_folder: str, fps: int = 2, threshold: float = 0.1):
#     os.makedirs(output_folder, exist_ok=True)

#     countries_shp = shpreader.natural_earth(resolution='110m', category='cultural', name='admin_0_countries')
#     reader = shpreader.Reader(countries_shp)
#     country_geoms = list(reader.records())

#     for z_index, z_val in enumerate(animator.levels):
#         fig = plt.figure(figsize=(16, 7))
#         proj = ccrs.PlateCarree()
#         ax1 = fig.add_subplot(1, 2, 1, projection=proj)
#         ax2 = fig.add_subplot(1, 2, 2, projection=proj)

#         valid_mask = np.stack([
#             ds['ash_concentration'].values[z_index] for ds in animator.datasets
#         ]).max(axis=0) > 0
#         y_idx, x_idx = np.where(valid_mask)

#         if y_idx.size == 0 or x_idx.size == 0:
#             print(f"Z level {z_val} km has no valid data. Skipping...")
#             plt.close()
#             continue

#         y_min, y_max = y_idx.min(), y_idx.max()
#         x_min, x_max = x_idx.min(), x_idx.max()

#         buffer_y = int((y_max - y_min) * 0.5)
#         buffer_x = int((x_max - x_min) * 0.5)

#         y_start = max(0, y_min - buffer_y)
#         y_end = min(animator.lat_grid.shape[0], y_max + buffer_y + 1)
#         x_start = max(0, x_min - buffer_x)
#         x_end = min(animator.lon_grid.shape[1], x_max + buffer_x + 1)

#         lat_zoom = animator.lats[y_start:y_end]
#         lon_zoom = animator.lons[x_start:x_end]
#         lon_zoom_grid, lat_zoom_grid = np.meshgrid(lon_zoom, lat_zoom)

#         valid_frames = []
#         for t in range(len(animator.datasets)):
#             data = animator.datasets[t]['ash_concentration'].values[z_index]
#             interp = interpolate_grid(data, animator.lon_grid, animator.lat_grid)
#             interp = np.where(interp < 0, np.nan, interp)
#             if np.isfinite(interp).sum() > 0:
#                 valid_frames.append(t)

#         if not valid_frames:
#             print(f"No valid frames for Z={z_val} km. Skipping animation.")
#             plt.close()
#             continue

#         def update(t):
#             ax1.clear()
#             ax2.clear()

#             data = animator.datasets[t]['ash_concentration'].values[z_index]
#             interp = interpolate_grid(data, animator.lon_grid, animator.lat_grid)
#             interp = np.where(interp < 0, np.nan, interp)
#             zoom_plot = interp[y_start:y_end, x_start:x_end]

#             valid_vals = interp[np.isfinite(interp)]
#             if valid_vals.size == 0:
#                 return []

#             min_val = np.nanmin(valid_vals)
#             max_val = np.nanmax(valid_vals)
#             log_cutoff = 1e-3
#             log_ratio = max_val / (min_val + 1e-6)
#             use_log = min_val > log_cutoff and log_ratio > 100

#             if use_log:
#                 data_for_plot = np.where(interp > log_cutoff, interp, np.nan)
#                 levels = np.logspace(np.log10(log_cutoff), np.log10(max_val), 20)
#                 scale_label = "Hybrid Log"
#             else:
#                 data_for_plot = interp
#                 levels = np.linspace(0, max_val, 20)
#                 scale_label = "Linear"

#             draw_etopo_basemap(ax1, mode='stock')
#             draw_etopo_basemap(ax2, mode='stock')

#             c1 = ax1.contourf(animator.lons, animator.lats, data_for_plot, levels=levels,
#                             cmap="rainbow", alpha=0.6, transform=proj)
#             ax1.contour(animator.lons, animator.lats, data_for_plot, levels=levels,
#                         colors='black', linewidths=0.5, transform=proj)
#             ax1.set_title(f"T{t+1} | Alt: {z_val} km (Full - {scale_label})")
#             ax1.set_extent([animator.lons.min(), animator.lons.max(), animator.lats.min(), animator.lats.max()])
#             ax1.coastlines()
#             ax1.add_feature(cfeature.BORDERS, linestyle=':')
#             ax1.add_feature(cfeature.LAND)
#             ax1.add_feature(cfeature.OCEAN)

#             c2 = ax2.contourf(lon_zoom_grid, lat_zoom_grid, zoom_plot, levels=levels,
#                             cmap="rainbow", alpha=0.4, transform=proj)
#             ax2.contour(lon_zoom_grid, lat_zoom_grid, zoom_plot, levels=levels,
#                         colors='black', linewidths=0.5, transform=proj)
#             ax2.set_title(f"T{t+1} | Alt: {z_val} km (Zoom - {scale_label})")
#             ax2.set_extent([lon_zoom.min(), lon_zoom.max(), lat_zoom.min(), lat_zoom.max()])
#             ax2.coastlines()
#             ax2.add_feature(cfeature.BORDERS, linestyle=':')
#             ax2.add_feature(cfeature.LAND)
#             ax2.add_feature(cfeature.OCEAN)

#             ax2.text(animator.lons[0], animator.lats[0], animator.country_label, fontsize=9, color='white',
#                     transform=proj, bbox=dict(facecolor='black', alpha=0.5))

#             texts_ax1, texts_ax2 = [], []
#             for country in country_geoms:
#                 name = country.attributes['NAME_LONG']
#                 geom = country.geometry
#                 try:
#                     lon, lat = geom.centroid.x, geom.centroid.y
#                     if (lon_zoom.min() <= lon <= lon_zoom.max()) and (lat_zoom.min() <= lat <= lat_zoom.max()):
#                         text = ax2.text(lon, lat, name, fontsize=6, transform=proj,
#                                         ha='center', va='center', color='white',
#                                         bbox=dict(facecolor='black', alpha=0.5, linewidth=0))
#                         texts_ax2.append(text)

#                     if (animator.lons.min() <= lon <= animator.lons.max()) and (animator.lats.min() <= lat <= animator.lats.max()):
#                         text = ax1.text(lon, lat, name, fontsize=6, transform=proj,
#                                         ha='center', va='center', color='white',
#                                         bbox=dict(facecolor='black', alpha=0.5, linewidth=0))
#                         texts_ax1.append(text)
#                 except:
#                     continue

#             adjust_text(texts_ax1, ax=ax1, only_move={'points': 'y', 'text': 'y'},
#                         arrowprops=dict(arrowstyle="->", color='white', lw=0.5))
#             adjust_text(texts_ax2, ax=ax2, only_move={'points': 'y', 'text': 'y'},
#                         arrowprops=dict(arrowstyle="->", color='white', lw=0.5))

#             if np.nanmax(valid_vals) > threshold:
#                 alert_text = f"⚠ Exceeds {threshold} g/m³!"
#                 for ax in [ax1, ax2]:
#                     ax.text(0.99, 0.01, alert_text, transform=ax.transAxes,
#                             ha='right', va='bottom', fontsize=10, color='red',
#                             bbox=dict(facecolor='white', alpha=0.8, edgecolor='red'))
#                 ax1.contour(animator.lons, animator.lats, interp, levels=[threshold], colors='red', linewidths=2, transform=proj)
#                 ax2.contour(lon_zoom_grid, lat_zoom_grid, zoom_plot, levels=[threshold], colors='red', linewidths=2, transform=proj)

#             if not hasattr(update, "colorbar"):
#                 update.colorbar = fig.colorbar(c1, ax=[ax1, ax2], orientation='vertical',
#                                             label="Ash concentration (g/m³)")
#                 formatter = mticker.FuncFormatter(lambda x, _: f'{x:.2g}')
#                 update.colorbar.ax.yaxis.set_major_formatter(formatter)
#                 if use_log:
#                     update.colorbar.ax.text(1.05, 1.02, "log scale", transform=update.colorbar.ax.transAxes,
#                                             fontsize=9, color='gray', rotation=90, ha='left', va='bottom')

#             return []

#         ani = animation.FuncAnimation(fig, update, frames=valid_frames, blit=False)
#         gif_path = os.path.join(output_folder, f"ash_T1-Tn_Z{z_index+1}.gif")
#         ani.save(gif_path, writer='pillow', fps=fps)
#         plt.close()
#         print(f"✅ Saved animation for Z={z_val} km to {gif_path}")
###################################################################################################################
# import os
# import numpy as np
# import matplotlib.pyplot as plt
# import matplotlib.animation as animation
# import matplotlib.ticker as mticker
# import cartopy.crs as ccrs
# import cartopy.feature as cfeature
# from adjustText import adjust_text
# import cartopy.io.shapereader as shpreader
# from .interpolation import interpolate_grid
# from .basemaps import draw_etopo_basemap

# def animate_all_z_levels(animator, output_folder: str, fps: int = 2, threshold: float = 0.1):
#     os.makedirs(output_folder, exist_ok=True)

#     countries_shp = shpreader.natural_earth(resolution='110m', category='cultural', name='admin_0_countries')
#     reader = shpreader.Reader(countries_shp)
#     country_geoms = list(reader.records())

#     # Compute consistent zoom window across all z-levels and time frames
#     valid_mask_all = np.zeros_like(animator.datasets[0]['ash_concentration'].values[0], dtype=bool)
#     for ds in animator.datasets:
#         for z in range(len(animator.levels)):
#             valid_mask_all |= ds['ash_concentration'].values[z] > 0

#     y_idx_all, x_idx_all = np.where(valid_mask_all)
#     if y_idx_all.size == 0 or x_idx_all.size == 0:
#         raise ValueError("No valid data found across any Z level or frame.")

#     y_min, y_max = y_idx_all.min(), y_idx_all.max()
#     x_min, x_max = x_idx_all.min(), x_idx_all.max()
#     buffer_y = int((y_max - y_min) * 0.5)
#     buffer_x = int((x_max - x_min) * 0.5)

#     y_start = max(0, y_min - buffer_y)
#     y_end = min(animator.lat_grid.shape[0], y_max + buffer_y + 1)
#     x_start = max(0, x_min - buffer_x)
#     x_end = min(animator.lon_grid.shape[1], x_max + buffer_x + 1)

#     lat_zoom = animator.lats[y_start:y_end]
#     lon_zoom = animator.lons[x_start:x_end]
#     lon_zoom_grid, lat_zoom_grid = np.meshgrid(lon_zoom, lat_zoom)

#     for z_index, z_val in enumerate(animator.levels):
#         fig = plt.figure(figsize=(16, 7))
#         proj = ccrs.PlateCarree()
#         ax1 = fig.add_subplot(1, 2, 1, projection=proj)
#         ax2 = fig.add_subplot(1, 2, 2, projection=proj)

#         valid_frames = []
#         for t in range(len(animator.datasets)):
#             data = animator.datasets[t]['ash_concentration'].values[z_index]
#             interp = interpolate_grid(data, animator.lon_grid, animator.lat_grid)
#             interp = np.where(interp < 0, np.nan, interp)
#             if np.isfinite(interp).sum() > 0:
#                 valid_frames.append(t)

#         if not valid_frames:
#             print(f"No valid frames for Z={z_val} km. Skipping animation.")
#             plt.close()
#             continue

#         def update(t):
#             ax1.clear()
#             ax2.clear()

#             data = animator.datasets[t]['ash_concentration'].values[z_index]
#             interp = interpolate_grid(data, animator.lon_grid, animator.lat_grid)
#             interp = np.where(interp < 0, np.nan, interp)
#             zoom_plot = interp[y_start:y_end, x_start:x_end]

#             valid_vals = interp[np.isfinite(interp)]
#             if valid_vals.size == 0:
#                 return []

#             min_val = np.nanmin(valid_vals)
#             max_val = np.nanmax(valid_vals)
#             log_cutoff = 1e-3
#             log_ratio = max_val / (min_val + 1e-6)
#             use_log = min_val > log_cutoff and log_ratio > 100

#             if use_log:
#                 data_for_plot = np.where(interp > log_cutoff, interp, np.nan)
#                 levels = np.logspace(np.log10(log_cutoff), np.log10(max_val), 20)
#                 scale_label = "Hybrid Log"
#             else:
#                 data_for_plot = interp
#                 levels = np.linspace(0, max_val, 20)
#                 scale_label = "Linear"

#             draw_etopo_basemap(ax1, mode='stock')
#             draw_etopo_basemap(ax2, mode='stock')

#             c1 = ax1.contourf(animator.lons, animator.lats, data_for_plot, levels=levels,
#                             cmap="rainbow", alpha=0.6, transform=proj)
#             ax1.contour(animator.lons, animator.lats, data_for_plot, levels=levels,
#                         colors='black', linewidths=0.5, transform=proj)
#             ax1.set_title(f"T{t+1} | Alt: {z_val} km (Full - {scale_label})")
#             ax1.set_extent([animator.lons.min(), animator.lons.max(), animator.lats.min(), animator.lats.max()])
#             ax1.coastlines()
#             ax1.add_feature(cfeature.BORDERS, linestyle=':')
#             ax1.add_feature(cfeature.LAND)
#             ax1.add_feature(cfeature.OCEAN)

#             c2 = ax2.contourf(lon_zoom_grid, lat_zoom_grid, zoom_plot, levels=levels,
#                             cmap="rainbow", alpha=0.4, transform=proj)
#             ax2.contour(lon_zoom_grid, lat_zoom_grid, zoom_plot, levels=levels,
#                         colors='black', linewidths=0.5, transform=proj)
#             ax2.set_title(f"T{t+1} | Alt: {z_val} km (Zoom - {scale_label})")
#             ax2.set_extent([lon_zoom.min(), lon_zoom.max(), lat_zoom.min(), lat_zoom.max()])
#             ax2.coastlines()
#             ax2.add_feature(cfeature.BORDERS, linestyle=':')
#             ax2.add_feature(cfeature.LAND)
#             ax2.add_feature(cfeature.OCEAN)

#             ax2.text(animator.lons[0], animator.lats[0], animator.country_label, fontsize=9, color='white',
#                      transform=proj, bbox=dict(facecolor='black', alpha=0.5))

#             texts_ax1, texts_ax2 = [], []
#             for country in country_geoms:
#                 name = country.attributes['NAME_LONG']
#                 geom = country.geometry
#                 try:
#                     lon, lat = geom.centroid.x, geom.centroid.y
#                     if (lon_zoom.min() <= lon <= lon_zoom.max()) and (lat_zoom.min() <= lat <= lat_zoom.max()):
#                         text = ax2.text(lon, lat, name, fontsize=6, transform=proj,
#                                         ha='center', va='center', color='white',
#                                         bbox=dict(facecolor='black', alpha=0.5, linewidth=0))
#                         texts_ax2.append(text)

#                     if (animator.lons.min() <= lon <= animator.lons.max()) and (animator.lats.min() <= lat <= animator.lats.max()):
#                         text = ax1.text(lon, lat, name, fontsize=6, transform=proj,
#                                         ha='center', va='center', color='white',
#                                         bbox=dict(facecolor='black', alpha=0.5, linewidth=0))
#                         texts_ax1.append(text)
#                 except:
#                     continue

#             adjust_text(texts_ax1, ax=ax1, only_move={'points': 'y', 'text': 'y'},
#                         arrowprops=dict(arrowstyle="->", color='white', lw=0.5))
#             adjust_text(texts_ax2, ax=ax2, only_move={'points': 'y', 'text': 'y'},
#                         arrowprops=dict(arrowstyle="->", color='white', lw=0.5))

#             if np.nanmax(valid_vals) > threshold:
#                 alert_text = f"⚠ Exceeds {threshold} g/m³!"
#                 for ax in [ax1, ax2]:
#                     ax.text(0.99, 0.01, alert_text, transform=ax.transAxes,
#                             ha='right', va='bottom', fontsize=10, color='red',
#                             bbox=dict(facecolor='white', alpha=0.8, edgecolor='red'))
#                 ax1.contour(animator.lons, animator.lats, interp, levels=[threshold], colors='red', linewidths=2, transform=proj)
#                 ax2.contour(lon_zoom_grid, lat_zoom_grid, zoom_plot, levels=[threshold], colors='red', linewidths=2, transform=proj)

#             if not hasattr(update, "colorbar"):
#                 update.colorbar = fig.colorbar(c1, ax=[ax1, ax2], orientation='vertical',
#                                                label="Ash concentration (g/m³)")
#                 formatter = mticker.FuncFormatter(lambda x, _: f'{x:.2g}')
#                 update.colorbar.ax.yaxis.set_major_formatter(formatter)
#                 if use_log:
#                     update.colorbar.ax.text(1.05, 1.02, "log scale", transform=update.colorbar.ax.transAxes,
#                                             fontsize=9, color='gray', rotation=90, ha='left', va='bottom')

#             return []

#         ani = animation.FuncAnimation(fig, update, frames=valid_frames, blit=False)
#         gif_path = os.path.join(output_folder, f"ash_T1-Tn_Z{z_index+1}.gif")
#         ani.save(gif_path, writer='pillow', fps=fps)
#         plt.close()
#         print(f"✅ Saved animation for Z={z_val} km to {gif_path}")


import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.ticker as mticker
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from adjustText import adjust_text
import cartopy.io.shapereader as shpreader
from .interpolation import interpolate_grid
from .basemaps import draw_etopo_basemap

def animate_all_z_levels(animator, output_folder: str, fps: int = 2, threshold: float = 0.1,
                         zoom_width_deg: float = 6.0, zoom_height_deg: float = 6.0):
    os.makedirs(output_folder, exist_ok=True)

    countries_shp = shpreader.natural_earth(resolution='110m', category='cultural', name='admin_0_countries')
    reader = shpreader.Reader(countries_shp)
    country_geoms = list(reader.records())

    # Find the most active region (max concentration point)
    max_conc = -np.inf
    center_lat = center_lon = None
    for ds in animator.datasets:
        for z in range(len(animator.levels)):
            data = ds['ash_concentration'].values[z]
            if np.max(data) > max_conc:
                max_conc = np.max(data)
                max_idx = np.unravel_index(np.argmax(data), data.shape)
                center_lat = animator.lat_grid[max_idx]
                center_lon = animator.lon_grid[max_idx]

    if center_lat is None or center_lon is None:
        raise ValueError("No valid concentration found to determine zoom center.")

    # Compute fixed zoom extents in lat/lon degrees
    lon_zoom_min = center_lon - zoom_width_deg / 2
    lon_zoom_max = center_lon + zoom_width_deg / 2
    lat_zoom_min = center_lat - zoom_height_deg / 2
    lat_zoom_max = center_lat + zoom_height_deg / 2

    # Create zoom grids for plotting
    lat_zoom = animator.lats[(animator.lats >= lat_zoom_min) & (animator.lats <= lat_zoom_max)]
    lon_zoom = animator.lons[(animator.lons >= lon_zoom_min) & (animator.lons <= lon_zoom_max)]
    lon_zoom_grid, lat_zoom_grid = np.meshgrid(lon_zoom, lat_zoom)

    for z_index, z_val in enumerate(animator.levels):
        fig = plt.figure(figsize=(16, 7))
        proj = ccrs.PlateCarree()
        ax1 = fig.add_subplot(1, 2, 1, projection=proj)
        ax2 = fig.add_subplot(1, 2, 2, projection=proj)

        valid_frames = []
        for t in range(len(animator.datasets)):
            data = animator.datasets[t]['ash_concentration'].values[z_index]
            interp = interpolate_grid(data, animator.lon_grid, animator.lat_grid)
            interp = np.where(interp < 0, np.nan, interp)
            if np.isfinite(interp).sum() > 0:
                valid_frames.append(t)

        if not valid_frames:
            print(f"No valid frames for Z={z_val} km. Skipping animation.")
            plt.close()
            continue

        def update(t):
            ax1.clear()
            ax2.clear()

            data = animator.datasets[t]['ash_concentration'].values[z_index]
            interp = interpolate_grid(data, animator.lon_grid, animator.lat_grid)
            interp = np.where(interp < 0, np.nan, interp)

            # Extract zoom window from interpolated data
            lat_idx = np.where((animator.lats >= lat_zoom_min) & (animator.lats <= lat_zoom_max))[0]
            lon_idx = np.where((animator.lons >= lon_zoom_min) & (animator.lons <= lon_zoom_max))[0]
            zoom_plot = interp[np.ix_(lat_idx, lon_idx)]

            valid_vals = interp[np.isfinite(interp)]
            if valid_vals.size == 0:
                return []

            min_val = np.nanmin(valid_vals)
            max_val = np.nanmax(valid_vals)
            log_cutoff = 1e-3
            log_ratio = max_val / (min_val + 1e-6)
            use_log = min_val > log_cutoff and log_ratio > 100

            if use_log:
                data_for_plot = np.where(interp > log_cutoff, interp, np.nan)
                levels = np.logspace(np.log10(log_cutoff), np.log10(max_val), 20)
                scale_label = "Hybrid Log"
            else:
                data_for_plot = interp
                levels = np.linspace(0, max_val, 20)
                scale_label = "Linear"

            draw_etopo_basemap(ax1, mode='stock')
            draw_etopo_basemap(ax2, mode='stock')

            c1 = ax1.contourf(animator.lons, animator.lats, data_for_plot, levels=levels,
                            cmap="rainbow", alpha=0.6, transform=proj)
            ax1.contour(animator.lons, animator.lats, data_for_plot, levels=levels,
                        colors='black', linewidths=0.5, transform=proj)
            ax1.set_title(f"T{t+1} | Alt: {z_val} km (Full - {scale_label})")
            ax1.set_extent([animator.lons.min(), animator.lons.max(), animator.lats.min(), animator.lats.max()])
            ax1.coastlines()
            ax1.add_feature(cfeature.BORDERS, linestyle=':')
            ax1.add_feature(cfeature.LAND)
            ax1.add_feature(cfeature.OCEAN)

            c2 = ax2.contourf(lon_zoom_grid, lat_zoom_grid, zoom_plot, levels=levels,
                            cmap="rainbow", alpha=0.4, transform=proj)
            ax2.contour(lon_zoom_grid, lat_zoom_grid, zoom_plot, levels=levels,
                        colors='black', linewidths=0.5, transform=proj)
            ax2.set_title(f"T{t+1} | Alt: {z_val} km (Zoom - {scale_label})")
            ax2.set_extent([lon_zoom_min, lon_zoom_max, lat_zoom_min, lat_zoom_max])
            ax2.coastlines()
            ax2.add_feature(cfeature.BORDERS, linestyle=':')
            ax2.add_feature(cfeature.LAND)
            ax2.add_feature(cfeature.OCEAN)

            ax2.text(animator.lons[0], animator.lats[0], animator.country_label, fontsize=9, color='white',
                     transform=proj, bbox=dict(facecolor='black', alpha=0.5))

            texts_ax1, texts_ax2 = [], []
            for country in country_geoms:
                name = country.attributes['NAME_LONG']
                geom = country.geometry
                try:
                    lon, lat = geom.centroid.x, geom.centroid.y
                    if (lon_zoom_min <= lon <= lon_zoom_max) and (lat_zoom_min <= lat <= lat_zoom_max):
                        text = ax2.text(lon, lat, name, fontsize=6, transform=proj,
                                        ha='center', va='center', color='white',
                                        bbox=dict(facecolor='black', alpha=0.5, linewidth=0))
                        texts_ax2.append(text)

                    if (animator.lons.min() <= lon <= animator.lons.max()) and (animator.lats.min() <= lat <= animator.lats.max()):
                        text = ax1.text(lon, lat, name, fontsize=6, transform=proj,
                                        ha='center', va='center', color='white',
                                        bbox=dict(facecolor='black', alpha=0.5, linewidth=0))
                        texts_ax1.append(text)
                except:
                    continue

            adjust_text(texts_ax1, ax=ax1, only_move={'points': 'y', 'text': 'y'},
                        arrowprops=dict(arrowstyle="->", color='white', lw=0.5))
            adjust_text(texts_ax2, ax=ax2, only_move={'points': 'y', 'text': 'y'},
                        arrowprops=dict(arrowstyle="->", color='white', lw=0.5))

            if np.nanmax(valid_vals) > threshold:
                alert_text = f"⚠ Exceeds {threshold} g/m³!"
                for ax in [ax1, ax2]:
                    ax.text(0.99, 0.01, alert_text, transform=ax.transAxes,
                            ha='right', va='bottom', fontsize=10, color='red',
                            bbox=dict(facecolor='white', alpha=0.8, edgecolor='red'))
                ax1.contour(animator.lons, animator.lats, interp, levels=[threshold], colors='red', linewidths=2, transform=proj)
                ax2.contour(lon_zoom_grid, lat_zoom_grid, zoom_plot, levels=[threshold], colors='red', linewidths=2, transform=proj)

            if not hasattr(update, "colorbar"):
                update.colorbar = fig.colorbar(c1, ax=[ax1, ax2], orientation='vertical',
                                               label="Ash concentration (g/m³)")
                formatter = mticker.FuncFormatter(lambda x, _: f'{x:.2g}')
                update.colorbar.ax.yaxis.set_major_formatter(formatter)
                if use_log:
                    update.colorbar.ax.text(1.05, 1.02, "log scale", transform=update.colorbar.ax.transAxes,
                                            fontsize=9, color='gray', rotation=90, ha='left', va='bottom')

            return []

        ani = animation.FuncAnimation(fig, update, frames=valid_frames, blit=False)
        gif_path = os.path.join(output_folder, f"ash_T1-Tn_Z{z_index+1}.gif")
        ani.save(gif_path, writer='pillow', fps=fps)
        plt.close()
        print(f"✅ Saved animation for Z={z_val} km to {gif_path}")
