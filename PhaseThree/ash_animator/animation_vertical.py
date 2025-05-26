
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.ticker as mticker
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cartopy.io.shapereader as shpreader
from .interpolation import interpolate_grid
from .basemaps import draw_etopo_basemap

# def animate_vertical_profile(animator, t_index: int, output_path: str, fps: int = 2, include_metadata: bool = True, threshold: float = 0.1):
#     if not (0 <= t_index < len(animator.datasets)):
#         print(f"Invalid time index {t_index}. Must be between 0 and {len(animator.datasets) - 1}.")
#         return

#     ds = animator.datasets[t_index]
#     fig = plt.figure(figsize=(16, 7))
#     proj = ccrs.PlateCarree()
#     ax1 = fig.add_subplot(1, 2, 1, projection=proj)
#     ax2 = fig.add_subplot(1, 2, 2, projection=proj)

#     meta = ds.attrs
#     legend_text = (
#         f"Run name:         {meta.get('run_name', 'N/A')}\n"
#         f"Run time:         {meta.get('run_time', 'N/A')}\n"
#         f"Met data:         {meta.get('met_data', 'N/A')}\n"
#         f"Start release:    {meta.get('start_of_release', 'N/A')}\n"
#         f"End release:      {meta.get('end_of_release', 'N/A')}\n"
#         f"Source strength:  {meta.get('source_strength', 'N/A')} g/s\n"
#         f"Release loc:      {meta.get('release_location', 'N/A')}\n"
#         f"Release height:   {meta.get('release_height', 'N/A')} m asl\n"
#         f"Run duration:     {meta.get('run_duration', 'N/A')}"
#     )

#     valid_mask = np.stack([ds['ash_concentration'].values[z] for z in range(len(animator.levels))]).max(axis=0) > 0
#     y_idx, x_idx = np.where(valid_mask)

#     if y_idx.size == 0 or x_idx.size == 0:
#         print(f"No valid data found for time T{t_index+1}. Skipping...")
#         plt.close()
#         return

#     y_min, y_max = y_idx.min(), y_idx.max()
#     x_min, x_max = x_idx.min(), x_idx.max()
#     buffer_y = int((y_max - y_min) * 0.1)
#     buffer_x = int((x_max - x_min) * 0.1)
#     y_start = max(0, y_min - buffer_y)
#     y_end = min(animator.lat_grid.shape[0], y_max + buffer_y + 1)
#     x_start = max(0, x_min - buffer_x)
#     x_end = min(animator.lon_grid.shape[1], x_max + buffer_x + 1)

#     lat_zoom = animator.lats[y_start:y_end]
#     lon_zoom = animator.lons[x_start:x_end]
#     lon_zoom_grid, lat_zoom_grid = np.meshgrid(lon_zoom, lat_zoom)

#     z_indices_with_data = []
#     for z_index in range(len(animator.levels)):
#         data = ds['ash_concentration'].values[z_index]
#         interp = interpolate_grid(data, animator.lon_grid, animator.lat_grid)
#         if np.isfinite(interp).sum() > 0:
#             z_indices_with_data.append(z_index)

#     if not z_indices_with_data:
#         print(f"No valid Z-levels at time T{t_index+1}.")
#         plt.close()
#         return

#     def update(z_index):
#         ax1.clear()
#         ax2.clear()

#         data = ds['ash_concentration'].values[z_index]
#         interp = interpolate_grid(data, animator.lon_grid, animator.lat_grid)
#         interp = np.where(interp < 0, np.nan, interp)
#         zoom_plot = interp[y_start:y_end, x_start:x_end]

#         valid_vals = interp[np.isfinite(interp)]
#         if valid_vals.size == 0:
#             return []

#         min_val = np.nanmin(valid_vals)
#         max_val = np.nanmax(valid_vals)
#         log_cutoff = 1e-3
#         use_log = min_val > log_cutoff and (max_val / (min_val + 1e-6)) > 100

#         levels = np.logspace(np.log10(log_cutoff), np.log10(max_val), 20) if use_log else np.linspace(0, max_val, 20)
#         data_for_plot = np.where(interp > log_cutoff, interp, 0) if use_log else interp
#         scale_label = "Log" if use_log else "Linear"

#         draw_etopo_basemap(ax1, mode='stock')
#         draw_etopo_basemap(ax2, mode='stock')

#         c1 = ax1.contourf(animator.lons, animator.lats, data_for_plot, levels=levels,
#                         cmap="rainbow", alpha=0.6, transform=proj)
#         ax1.set_title(f"T{t_index+1} | Alt: {animator.levels[z_index]} km (Full - {scale_label})")
#         ax1.set_extent([animator.lons.min(), animator.lons.max(), animator.lats.min(), animator.lats.max()])
#         ax1.coastlines(); ax1.add_feature(cfeature.BORDERS, linestyle=':')
#         ax1.add_feature(cfeature.LAND); ax1.add_feature(cfeature.OCEAN)

#         c2 = ax2.contourf(lon_zoom_grid, lat_zoom_grid, zoom_plot, levels=levels,
#                         cmap="rainbow", alpha=0.6, transform=proj)
#         ax2.set_title(f"T{t_index+1} | Alt: {animator.levels[z_index]} km (Zoom - {scale_label})")
#         ax2.set_extent([lon_zoom.min(), lon_zoom.max(), lat_zoom.min(), lat_zoom.max()])
#         ax2.coastlines(); ax2.add_feature(cfeature.BORDERS, linestyle=':')
#         ax2.add_feature(cfeature.LAND); ax2.add_feature(cfeature.OCEAN)

#         for ax in [ax1, ax2]:
#             ax.text(0.01, 0.98, f"Altitude: {animator.levels[z_index]:.2f} km", transform=ax.transAxes,
#                     fontsize=9, color='white', va='top', ha='left',
#                     bbox=dict(facecolor='black', alpha=0.4, boxstyle='round'))

#             if include_metadata:
#                 ax.text(0.01, 0.01,
#                         f"Source: NAME\nRes: {animator.x_res:.2f}°\n{meta.get('run_name', 'N/A')}",
#                         transform=ax.transAxes, fontsize=8, color='white',
#                         bbox=dict(facecolor='black', alpha=0.5))

#         if np.nanmax(valid_vals) > threshold:
#             for ax in [ax1, ax2]:
#                 ax.text(0.99, 0.01, f"⚠ Exceeds {threshold} g/m³!", transform=ax.transAxes,
#                         ha='right', va='bottom', fontsize=10, color='red',
#                         bbox=dict(facecolor='white', alpha=0.8, edgecolor='red'))
#             ax1.contour(animator.lons, animator.lats, interp, levels=[threshold], colors='red', linewidths=2, transform=proj)
#             ax2.contour(lon_zoom_grid, lat_zoom_grid, zoom_plot, levels=[threshold], colors='red', linewidths=2, transform=proj)

#         if include_metadata and not hasattr(update, "legend_text"):
#             ax1.annotate(legend_text, xy=(0.75, 0.99), xycoords='axes fraction',
#                         fontsize=8, ha='left', va='top',
#                         bbox=dict(boxstyle="round", facecolor="white", edgecolor="gray"))

#         if not hasattr(update, "colorbar"):
#             update.colorbar = fig.colorbar(c1, ax=[ax1, ax2], orientation='vertical',
#                                         label="Ash concentration (g/m³)")
#             formatter = mticker.FuncFormatter(lambda x, _: f'{x:.2g}')
#             update.colorbar.ax.yaxis.set_major_formatter(formatter)

#             if use_log:
#                 update.colorbar.ax.text(1.05, 1.02, "log scale", transform=update.colorbar.ax.transAxes,
#                                         fontsize=9, color='gray', rotation=90, ha='left', va='bottom')

#         return []

#     os.makedirs(os.path.dirname(output_path), exist_ok=True)
#     ani = animation.FuncAnimation(fig, update, frames=z_indices_with_data, blit=False)
#     ani.save(output_path, writer='pillow', fps=fps)
#     plt.close()
#     print(f"✅ Saved vertical profile animation for T{t_index+1} to {output_path}")

# def animate_all_vertical_profiles(animator, output_folder: str, fps: int = 2, include_metadata: bool = True, threshold: float = 0.1):
#     os.makedirs(output_folder, exist_ok=True)
#     for t_index in range(len(animator.datasets)):
#         output_path = os.path.join(output_folder, f"vertical_T{t_index+1:02d}.gif")
#         print(f"🔄 Generating vertical profile animation for T{t_index+1}...")
#         animate_vertical_profile(animator, t_index, output_path, fps, include_metadata, threshold)

import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.ticker as mticker
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cartopy.io.shapereader as shpreader
from .interpolation import interpolate_grid
from .basemaps import draw_etopo_basemap
from adjustText import adjust_text

def animate_vertical_profile(animator, t_index: int, output_path: str, fps: int = 2,
                             include_metadata: bool = True, threshold: float = 0.1,
                             zoom_width_deg: float = 6.0, zoom_height_deg: float = 6.0):
    if not (0 <= t_index < len(animator.datasets)):
        print(f"Invalid time index {t_index}. Must be between 0 and {len(animator.datasets) - 1}.")
        return

    countries_shp = shpreader.natural_earth(resolution='110m', category='cultural', name='admin_0_countries')
    reader = shpreader.Reader(countries_shp)
    country_geoms = list(reader.records())
   
    ds = animator.datasets[t_index]
    fig = plt.figure(figsize=(18, 7))  # Wider for metadata outside
    proj = ccrs.PlateCarree()
    ax1 = fig.add_subplot(1, 2, 1, projection=proj)
    ax2 = fig.add_subplot(1, 2, 2, projection=proj)

    meta = ds.attrs
    legend_text = (
        f"Run name:         {meta.get('run_name', 'N/A')}\n"
        f"Run time:         {meta.get('run_time', 'N/A')}\n"
        f"Met data:         {meta.get('met_data', 'N/A')}\n"
        f"Start release:    {meta.get('start_of_release', 'N/A')}\n"
        f"End release:      {meta.get('end_of_release', 'N/A')}\n"
        f"Source strength:  {meta.get('source_strength', 'N/A')} g/s\n"
        f"Release loc:      {meta.get('release_location', 'N/A')}\n"
        f"Release height:   {meta.get('release_height', 'N/A')} m asl\n"
        f"Run duration:     {meta.get('run_duration', 'N/A')}"
    )

    # 🔍 Find most active point at this time step
    max_conc = -np.inf
    center_lat = center_lon = None
    for z in range(len(animator.levels)):
        data = ds['ash_concentration'].values[z]
        if np.max(data) > max_conc:
            max_conc = np.max(data)
            max_idx = np.unravel_index(np.argmax(data), data.shape)
            center_lat = animator.lat_grid[max_idx]
            center_lon = animator.lon_grid[max_idx]

    if center_lat is None or center_lon is None:
        print(f"No valid data found for time T{t_index+1}. Skipping...")
        plt.close()
        return

    # 🌍 Define fixed zoom extents
    lon_zoom_min = center_lon - zoom_width_deg / 2
    lon_zoom_max = center_lon + zoom_width_deg / 2
    lat_zoom_min = center_lat - zoom_height_deg / 2
    lat_zoom_max = center_lat + zoom_height_deg / 2

    lat_zoom = animator.lats[(animator.lats >= lat_zoom_min) & (animator.lats <= lat_zoom_max)]
    lon_zoom = animator.lons[(animator.lons >= lon_zoom_min) & (animator.lons <= lon_zoom_max)]
    lon_zoom_grid, lat_zoom_grid = np.meshgrid(lon_zoom, lat_zoom)

    z_indices_with_data = []
    for z_index in range(len(animator.levels)):
        data = ds['ash_concentration'].values[z_index]
        interp = interpolate_grid(data, animator.lon_grid, animator.lat_grid)
        if np.isfinite(interp).sum() > 0:
            z_indices_with_data.append(z_index)

    if not z_indices_with_data:
        print(f"No valid Z-levels at time T{t_index+1}.")
        plt.close()
        return

    def update(z_index):
        ax1.clear()
        ax2.clear()

        data = ds['ash_concentration'].values[z_index]
        interp = interpolate_grid(data, animator.lon_grid, animator.lat_grid)
        interp = np.where(interp < 0, np.nan, interp)

        lat_idx = np.where((animator.lats >= lat_zoom_min) & (animator.lats <= lat_zoom_max))[0]
        lon_idx = np.where((animator.lons >= lon_zoom_min) & (animator.lons <= lon_zoom_max))[0]
        zoom_plot = interp[np.ix_(lat_idx, lon_idx)]

        valid_vals = interp[np.isfinite(interp)]
        if valid_vals.size == 0:
            return []

        min_val = np.nanmin(valid_vals)
        max_val = np.nanmax(valid_vals)
        log_cutoff = 1e-3
        use_log = min_val > log_cutoff and (max_val / (min_val + 1e-6)) > 100

        levels = np.logspace(np.log10(log_cutoff), np.log10(max_val), 20) if use_log else np.linspace(0, max_val, 20)
        data_for_plot = np.where(interp > log_cutoff, interp, 0) if use_log else interp
        scale_label = "Log" if use_log else "Linear"

        draw_etopo_basemap(ax1, mode='stock')
        draw_etopo_basemap(ax2, mode='stock')

        c1 = ax1.contourf(animator.lons, animator.lats, data_for_plot, levels=levels,
                          cmap="rainbow", alpha=0.6, transform=proj)
        ax1.set_title(f"T{t_index+1} | Alt: {animator.levels[z_index]} km (Full - {scale_label})")
        ax1.set_extent([animator.lons.min(), animator.lons.max(), animator.lats.min(), animator.lats.max()])
        ax1.coastlines(); ax1.add_feature(cfeature.BORDERS, linestyle=':')
        ax1.add_feature(cfeature.LAND); ax1.add_feature(cfeature.OCEAN)

        c2 = ax2.contourf(lon_zoom_grid, lat_zoom_grid, zoom_plot, levels=levels,
                          cmap="rainbow", alpha=0.6, transform=proj)
        ax2.set_title(f"T{t_index+1} | Alt: {animator.levels[z_index]} km (Zoom - {scale_label})")
        ax2.set_extent([lon_zoom_min, lon_zoom_max, lat_zoom_min, lat_zoom_max])
        ax2.coastlines(); ax2.add_feature(cfeature.BORDERS, linestyle=':')
        ax2.add_feature(cfeature.LAND); ax2.add_feature(cfeature.OCEAN)

        for ax in [ax1, ax2]:
            ax.text(0.01, 0.98, f"Altitude: {animator.levels[z_index]:.2f} km", transform=ax.transAxes,
                    fontsize=9, color='white', va='top', ha='left',
                    bbox=dict(facecolor='black', alpha=0.4, boxstyle='round'))

        if include_metadata:
            fig.text(0.50, 0.1, legend_text, va='center', ha='left', fontsize=8,
                     bbox=dict(facecolor='white', alpha=0.8, edgecolor='gray'),
                     transform=fig.transFigure)

        if np.nanmax(valid_vals) > threshold:
            for ax in [ax1, ax2]:
                ax.text(0.99, 0.01, f"⚠ Exceeds {threshold} g/m³!", transform=ax.transAxes,
                        ha='right', va='bottom', fontsize=10, color='red',
                        bbox=dict(facecolor='white', alpha=0.8, edgecolor='red'))
            ax1.contour(animator.lons, animator.lats, interp, levels=[threshold], colors='red', linewidths=2, transform=proj)
            ax2.contour(lon_zoom_grid, lat_zoom_grid, zoom_plot, levels=[threshold], colors='red', linewidths=2, transform=proj)

        if not hasattr(update, "colorbar"):
            update.colorbar = fig.colorbar(c1, ax=[ax1, ax2], orientation='vertical',
                                           label="Ash concentration (g/m³)", shrink=0.75)
            formatter = mticker.FuncFormatter(lambda x, _: f'{x:.2g}')
            update.colorbar.ax.yaxis.set_major_formatter(formatter)

            if use_log:
                update.colorbar.ax.text(1.05, 1.02, "log scale", transform=update.colorbar.ax.transAxes,
                                        fontsize=9, color='gray', rotation=90, ha='left', va='bottom')

        ######################3
        
            
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
        
            
            ############################################
        
        
        
        
        return []

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    ani = animation.FuncAnimation(fig, update, frames=z_indices_with_data, blit=False)
    ani.save(output_path, writer='pillow', fps=fps)
    plt.close()
    print(f"✅ Saved vertical profile animation for T{t_index+1} to {output_path}")


def animate_all_vertical_profiles(animator, output_folder: str, fps: int = 2,
                                  include_metadata: bool = True, threshold: float = 0.1,
                                  zoom_width_deg: float = 10.0, zoom_height_deg: float = 6.0):
    os.makedirs(output_folder, exist_ok=True)
    for t_index in range(len(animator.datasets)):
        output_path = os.path.join(output_folder, f"vertical_T{t_index+1:02d}.gif")
        print(f"🔄 Generating vertical profile animation for T{t_index+1}...")
        animate_vertical_profile(animator, t_index, output_path, fps,
                                 include_metadata, threshold,
                                 zoom_width_deg, zoom_height_deg)
