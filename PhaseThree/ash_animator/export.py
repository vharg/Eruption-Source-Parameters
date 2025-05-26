
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from .interpolation import interpolate_grid
from .basemaps import draw_etopo_basemap

def export_frames_as_jpgs(animator, output_folder: str, include_metadata: bool = True):
    os.makedirs(output_folder, exist_ok=True)

    meta = animator.datasets[0].attrs
    legend_text = (
        f"Run name:           {meta.get('run_name', 'N/A')}\n"
        f"Run time:           {meta.get('run_time', 'N/A')}\n"
        f"Met data:           {meta.get('met_data', 'N/A')}\n"
        f"Start of release:   {meta.get('start_of_release', 'N/A')}\n"
        f"End of release:     {meta.get('end_of_release', 'N/A')}\n"
        f"Source strength:    {meta.get('source_strength', 'N/A')} g / s\n"
        f"Release location:   {meta.get('release_location', 'N/A')}\n"
        f"Release height:     {meta.get('release_height', 'N/A')} m asl\n"
        f"Run duration:       {meta.get('run_duration', 'N/A')}"
    )

    for z_index, z_val in enumerate(animator.levels):
        z_dir = os.path.join(output_folder, f"ash_T1-Tn_Z{z_index+1}")
        os.makedirs(z_dir, exist_ok=True)

        valid_mask = np.stack([
            ds['ash_concentration'].values[z_index] for ds in animator.datasets
        ]).max(axis=0) > 0
        y_idx, x_idx = np.where(valid_mask)

        if y_idx.size == 0 or x_idx.size == 0:
            print(f"Z level {z_val} km has no valid data. Skipping...")
            continue

        y_min, y_max = y_idx.min(), y_idx.max()
        x_min, x_max = x_idx.min(), x_idx.max()

        for t in range(len(animator.datasets)):
            data = animator.datasets[t]['ash_concentration'].values[z_index]
            interp = interpolate_grid(data, animator.lon_grid, animator.lat_grid)
            if np.isfinite(interp).sum() == 0:
                continue

            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8), subplot_kw={'projection': ccrs.PlateCarree()})
            valid_vals = interp[np.isfinite(interp)]
            min_val = np.nanmin(valid_vals)
            max_val = np.nanmax(valid_vals)
            log_cutoff = 1e-3
            log_ratio = max_val / (min_val + 1e-6)
            use_log = min_val > log_cutoff and log_ratio > 100

            levels = np.logspace(np.log10(log_cutoff), np.log10(max_val), 20) if use_log else np.linspace(0, max_val, 20)
            data_for_plot = np.where(interp > log_cutoff, interp, np.nan) if use_log else interp
            scale_label = "Hybrid Log" if use_log else "Linear"

            # Plot full
            c1 = ax1.contourf(animator.lons, animator.lats, data_for_plot, levels=levels,
                            cmap="rainbow", alpha=0.6, transform=ccrs.PlateCarree())
            draw_etopo_basemap(ax1, mode='stock')
            ax1.set_extent([animator.lons.min(), animator.lons.max(), animator.lats.min(), animator.lats.max()])
            ax1.set_title(f"T{t+1} | Alt: {z_val} km (Full - {scale_label})")
            ax1.coastlines(); ax1.add_feature(cfeature.BORDERS)
            ax1.add_feature(cfeature.LAND); ax1.add_feature(cfeature.OCEAN)

            # Zoom region
            buffer_y = int((y_max - y_min) * 0.5)
            buffer_x = int((x_max - x_min) * 0.5)

            y_start = max(0, y_min - buffer_y)
            y_end = min(data_for_plot.shape[0], y_max + buffer_y + 1)
            x_start = max(0, x_min - buffer_x)
            x_end = min(data_for_plot.shape[1], x_max + buffer_x + 1)

            zoom = data_for_plot[y_start:y_end, x_start:x_end]
            lon_zoom = animator.lons[x_start:x_end]
            lat_zoom = animator.lats[y_start:y_end]

            c2 = ax2.contourf(lon_zoom, lat_zoom, zoom, levels=levels,
                            cmap="rainbow", alpha=0.6, transform=ccrs.PlateCarree())
            draw_etopo_basemap(ax2, mode='stock')
            ax2.set_extent([lon_zoom.min(), lon_zoom.max(), lat_zoom.min(), lat_zoom.max()])
            ax2.set_title(f"T{t+1} | Alt: {z_val} km (Zoom - {scale_label})")
            ax2.coastlines(); ax2.add_feature(cfeature.BORDERS)
            ax2.add_feature(cfeature.LAND); ax2.add_feature(cfeature.OCEAN)

            for ax in [ax1, ax2]:
                ax.text(0.01, 0.98, f"Time step T{t+1}", transform=ax.transAxes,
                        fontsize=9, color='white', va='top', ha='left',
                        bbox=dict(facecolor='black', alpha=0.4, boxstyle='round'))

            if include_metadata:
                for ax in [ax1, ax2]:
                    ax.text(0.01, 0.01,
                            f"Source: NAME model\nRes: {animator.x_res:.2f}°\n{meta.get('run_name', 'N/A')}",
                            transform=ax.transAxes, fontsize=8, color='white',
                            bbox=dict(facecolor='black', alpha=0.5))
                ax1.annotate(legend_text, xy=(0.75, 0.99), xycoords='axes fraction',
                            fontsize=8, ha='left', va='top',
                            bbox=dict(boxstyle="round", facecolor="white", edgecolor="gray"),
                            annotation_clip=False)

            cbar = fig.colorbar(c1, ax=[ax1, ax2], orientation='vertical', shrink=0.75, pad=0.03)
            cbar.set_label("Ash concentration (g/m³)")
            formatter = mticker.FuncFormatter(lambda x, _: f'{x:.2g}')
            cbar.ax.yaxis.set_major_formatter(formatter)

            if use_log:
                cbar.ax.text(1.1, 1.02, "log scale", transform=cbar.ax.transAxes,
                            fontsize=9, color='gray', rotation=90, ha='left', va='bottom')

            frame_path = os.path.join(z_dir, f"frame_{t+1:04d}.jpg")
            plt.savefig(frame_path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            print(f"Saved {frame_path}")
