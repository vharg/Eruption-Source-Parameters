
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.ticker as mticker
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from .interpolation import interpolate_grid
from .basemaps import draw_etopo_basemap

def animate_single_z_level(animator, z_km: float, output_path: str, fps: int = 2, include_metadata: bool = True, threshold: float = 0.1):
    if z_km not in animator.levels:
        print(f"Z level {z_km} km not found in dataset.")
        return

    z_index = np.where(animator.levels == z_km)[0][0]
    fig = plt.figure(figsize=(16, 7))
    proj = ccrs.PlateCarree()
    ax1 = fig.add_subplot(1, 2, 1, projection=proj)
    ax2 = fig.add_subplot(1, 2, 2, projection=proj)

    meta = animator.datasets[0].attrs
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

    valid_mask = np.stack([
        ds['ash_concentration'].values[z_index] for ds in animator.datasets
    ]).max(axis=0) > 0
    y_idx, x_idx = np.where(valid_mask)

    if y_idx.size == 0 or x_idx.size == 0:
        print(f"Z level {z_km} km has no valid data. Skipping...")
        plt.close()
        return

    y_min, y_max = y_idx.min(), y_idx.max()
    x_min, x_max = x_idx.min(), x_idx.max()
    buffer_y = int((y_max - y_min) * 0.5)
    buffer_x = int((x_max - x_min) * 0.5)
    y_start = max(0, y_min - buffer_y)
    y_end = min(animator.lat_grid.shape[0], y_max + buffer_y + 1)
    x_start = max(0, x_min - buffer_x)
    x_end = min(animator.lon_grid.shape[1], x_max + buffer_x + 1)

    lat_zoom = animator.lats[y_start:y_end]
    lon_zoom = animator.lons[x_start:x_end]
    lon_zoom_grid, lat_zoom_grid = np.meshgrid(lon_zoom, lat_zoom)

    valid_frames = []
    for t in range(len(animator.datasets)):
        interp = interpolate_grid(animator.datasets[t]['ash_concentration'].values[z_index],
                                  animator.lon_grid, animator.lat_grid)
        if np.isfinite(interp).sum() > 0:
            valid_frames.append(t)

    if not valid_frames:
        print(f"No valid frames for Z={z_km} km. Skipping animation.")
        plt.close()
        return

    def update(t):
        ax1.clear()
        ax2.clear()

        data = animator.datasets[t]['ash_concentration'].values[z_index]
        interp = interpolate_grid(data, animator.lon_grid, animator.lat_grid)
        interp = np.where(interp < 0, np.nan, interp)
        zoom_plot = interp[y_start:y_end, x_start:x_end]

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
        ax1.set_title(f"T{t+1} | Alt: {z_km} km (Full - {scale_label})")
        ax1.set_extent([animator.lons.min(), animator.lons.max(), animator.lats.min(), animator.lats.max()])
        ax1.coastlines(); ax1.add_feature(cfeature.BORDERS); ax1.add_feature(cfeature.LAND); ax1.add_feature(cfeature.OCEAN)

        c2 = ax2.contourf(lon_zoom_grid, lat_zoom_grid, zoom_plot, levels=levels,
                        cmap="rainbow", alpha=0.6, transform=proj)
        ax2.set_title(f"T{t+1} | Alt: {z_km} km (Zoom - {scale_label})")
        ax2.set_extent([lon_zoom.min(), lon_zoom.max(), lat_zoom.min(), lat_zoom.max()])
        ax2.coastlines(); ax2.add_feature(cfeature.BORDERS); ax2.add_feature(cfeature.LAND); ax2.add_feature(cfeature.OCEAN)

        if not hasattr(update, "colorbar"):
            update.colorbar = fig.colorbar(c1, ax=[ax1, ax2], orientation='vertical',
                                        label="Ash concentration (g/m³)")
            formatter = mticker.FuncFormatter(lambda x, _: f'{x:.2g}')
            update.colorbar.ax.yaxis.set_major_formatter(formatter)
            if use_log:
                update.colorbar.ax.text(1.05, 1.02, "log scale", transform=update.colorbar.ax.transAxes,
                                        fontsize=9, color='gray', rotation=90, ha='left', va='bottom')

        if include_metadata:
            ax1.annotate(legend_text, xy=(0.75, 0.99), xycoords='axes fraction',
                        fontsize=8, ha='left', va='top',
                        bbox=dict(boxstyle="round", facecolor="white", edgecolor="gray"))
            for ax in [ax1, ax2]:
                ax.text(0.01, 0.01,
                        f"Source: NAME\nRes: {animator.x_res:.2f}°\n{meta.get('run_name', 'N/A')}",
                        transform=ax.transAxes, fontsize=8, color='white',
                        bbox=dict(facecolor='black', alpha=0.5))

        for ax in [ax1, ax2]:
            ax.text(0.01, 0.98, f"Time step T{t+1}", transform=ax.transAxes,
                    fontsize=9, color='white', va='top', ha='left',
                    bbox=dict(facecolor='black', alpha=0.4, boxstyle='round'))

        if np.nanmax(valid_vals) > threshold:
            alert_text = f"⚠ Exceeds {threshold} g/m³!"
            for ax in [ax1, ax2]:
                ax.text(0.99, 0.01, alert_text, transform=ax.transAxes,
                        ha='right', va='bottom', fontsize=10, color='red',
                        bbox=dict(facecolor='white', alpha=0.8, edgecolor='red'))
            ax1.contour(animator.lons, animator.lats, interp, levels=[threshold], colors='red', linewidths=2, transform=proj)
            ax2.contour(lon_zoom_grid, lat_zoom_grid, zoom_plot, levels=[threshold], colors='red', linewidths=2, transform=proj)

        return []

    ani = animation.FuncAnimation(fig, update, frames=valid_frames, blit=False)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    ani.save(output_path, writer='pillow', fps=fps)
    plt.close()
    print(f"✅ Saved animation for Z={z_km} km to {output_path}")
