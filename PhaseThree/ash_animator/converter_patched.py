import os
import re
import zipfile
import numpy as np
import xarray as xr
import tempfile
import shutil
from typing import List, Tuple, Dict


import os
import glob
import shutil
import stat
import matplotlib.pyplot as plt
from datetime import datetime
import matplotlib.dates as mdates

######

from typing import Union, List
import os
import re
import zipfile
import tempfile
import shutil
import glob
import stat
from tqdm import tqdm
from datetime import datetime


#######

class NAMEDataProcessor:
    def __init__(self):
        self._initialize_output_dirs()
        self.run_name=None
        self._run_outputs = []  # Stores (run_name, output_root) per batch

        

    def _initialize_output_dirs(self, custom_output_root: str = None):
        if custom_output_root:
            self.output_root = custom_output_root
        else:
            self.output_root = os.path.join(tempfile.gettempdir(), "name_outputs")

        self.output_3d = os.path.join(self.output_root, "3D")
        self.output_horizontal = os.path.join(self.output_root, "horizontal")
        os.makedirs(self.output_3d, exist_ok=True)
        os.makedirs(self.output_horizontal, exist_ok=True)

    def _sanitize_key(self, key: str) -> str:
        key = re.sub(r'\W+', '_', key)
        if not key[0].isalpha():
            key = f"attr_{key}"
        return key

    def extract_metadata_and_fields(self, lines: List[str], filename: str) -> Tuple[dict, List[str]]:
        metadata = {}
        field_headers = []
        in_fields_section = False
        t_match = re.search(r'_T(\d+)', filename)
        t_key = f"T{t_match.group(1)}" if t_match else "T_unknown"

        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.lower() == "fields:":
                in_fields_section = True
                continue
            if in_fields_section:
                field_headers.append(line)
                dt_match = re.search(r'(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})\s+UTC', line)
                
               
                z_match = re.search(r'Z\s*=\s*(\d+\s*m\s*agl)', line)
                if z_match:
                    metadata[f"{t_key}_altitude"] = z_match.group(1)

                if dt_match:
                    metadata[f"{t_key}_date"] = dt_match.group(1)
                    metadata[f"{t_key}_time"] = dt_match.group(2) + " UTC"
                    
            else:
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip().lower()
                    value = value.strip()
                    substitutions = {
                        "x grid origin": "x_grid_origin",
                        "y grid origin": "y_grid_origin",
                        "x grid size": "x_grid_size",
                        "y grid size": "y_grid_size",
                        "x grid resolution": "x_grid_resolution",
                        "y grid resolution": "y_grid_resolution",
                        "x resolution": "x_grid_resolution",
                        "y resolution": "y_grid_resolution"
                    }
                    key = substitutions.get(key, key)
                    sanitized_key = self._sanitize_key(key)
                    metadata[sanitized_key] = value
                else:
                    tag = "info_" + str(len(metadata)).zfill(3)
                    metadata[tag] = line

        try:
            metadata.update({
                "x_origin": float(metadata["x_grid_origin"]),
                "y_origin": float(metadata["y_grid_origin"]),
                "x_size": int(metadata["x_grid_size"]),
                "y_size": int(metadata["y_grid_size"]),
                "x_res": float(metadata["x_grid_resolution"]),
                "y_res": float(metadata["y_grid_resolution"]),
            })
        except KeyError as e:
            raise ValueError(f"Missing required metadata field: {e}")
        except ValueError as e:
            raise ValueError(f"Invalid value in metadata: {e}")

        if metadata["x_res"] == 0 or metadata["y_res"] == 0:
            raise ZeroDivisionError("Grid resolution cannot be zero.")

        return metadata, field_headers

    def _get_data_lines(self, lines: List[str]) -> List[str]:
        idx = next(i for i, l in enumerate(lines) if l.strip() == "Fields:")
        return lines[idx + 1:]

    def _is_horizontal_file(self, filename: str) -> bool:
        return "HorizontalField" in filename

    
    
    ###########################################################
    
    
    def _convert_horizontal(self, filepath: str, output_filename: str) -> str:
        with open(filepath, 'r') as f:
            lines = f.readlines()

        meta, field_lines = self.extract_metadata_and_fields(lines, filepath)
        
        data_lines = self._get_data_lines(lines)

        lons = np.round(np.arange(meta["x_origin"], meta["x_origin"] + meta["x_size"] * meta["x_res"], meta["x_res"]), 6)
        lats = np.round(np.arange(meta["y_origin"], meta["y_origin"] + meta["y_size"] * meta["y_res"], meta["y_res"]), 6)

        air_conc = np.zeros((meta["y_size"], meta["x_size"]), dtype=np.float32)
        dry_depo = np.zeros((meta["y_size"], meta["x_size"]), dtype=np.float32)
        wet_depo = np.zeros((meta["y_size"], meta["x_size"]), dtype=np.float32)

        valid_data_found = False

        for line in data_lines:
            parts = [p.strip().strip(',') for p in line.strip().split(',') if p.strip()]
            if len(parts) >= 7 and parts[0].isdigit() and parts[1].isdigit():
                try:
                    x = int(parts[0]) - 1
                    y = int(parts[1]) - 1
                    air_val = float(parts[4])
                    dry_val = float(parts[5])
                    wet_val = float(parts[6])

                    if not np.isnan([air_val, dry_val, wet_val]).any() and 0 <= x < meta["x_size"] and 0 <= y < meta["y_size"]:
                        air_conc[y, x] = air_val
                        dry_depo[y, x] = dry_val
                        wet_depo[y, x] = wet_val
                        valid_data_found = True
                except Exception:
                    continue

        if not valid_data_found:
            print(f"⚠ No valid data found in {filepath}. Using zero-filled arrays.")

        ds = xr.Dataset(
            {
                "air_concentration": (['latitude', 'longitude'], air_conc),
                "dry_deposition_rate": (['latitude', 'longitude'], dry_depo),
                "wet_deposition_rate": (['latitude', 'longitude'], wet_depo)
            },
            coords={
                "latitude": lats,
                "longitude": lons
            },
            attrs={
                "title": "Volcanic Ash Horizontal Output (Multiple Fields)",
                "field_descriptions": "\n".join(field_lines),
                "source": "NAME model output processed to NetCDF (horizontal multi-field)",
                **{k: str(v) for k, v in meta.items()}
            }
        )

        ds["air_concentration"].attrs.update({"units": "g/m^3", "long_name": "Boundary Layer Average Air Concentration"})
        ds["dry_deposition_rate"].attrs.update({"units": "g/m^2/s", "long_name": "Dry Deposition Rate"})
        ds["wet_deposition_rate"].attrs.update({"units": "g/m^2/s", "long_name": "Wet Deposition Rate"})
        ds["latitude"].attrs["units"] = "degrees_north"
        ds["longitude"].attrs["units"] = "degrees_east"

        out_path = os.path.join(self.output_horizontal, output_filename)
        ds.to_netcdf(out_path, engine="netcdf4")

        return out_path

    def _convert_3d_group(self, group: List[Tuple[int, str]], output_filename: str) -> str:
        first_file_path = group[0][1]
        with open(first_file_path, 'r') as f:
            lines = f.readlines()
        meta, field_lines = self.extract_metadata_and_fields(lines, first_file_path)

        lons = np.round(np.arange(meta["x_origin"], meta["x_origin"] + meta["x_size"] * meta["x_res"], meta["x_res"]), 6)
        lats = np.round(np.arange(meta["y_origin"], meta["y_origin"] + meta["y_size"] * meta["y_res"], meta["y_res"]), 6)

        z_levels = []
        z_coords = []
        altitude_labels = {}

        for z_idx, filepath in group:
            with open(filepath, 'r') as f:
                lines = f.readlines()
            data_lines = self._get_data_lines(lines)

            grid = np.zeros((meta["y_size"], meta["x_size"]), dtype=np.float32)

            meta_z, _ = self.extract_metadata_and_fields(lines, filepath)
            alt_key = next((k for k in meta_z if k.endswith("_altitude")), None)
            if alt_key:
                altitude_labels[z_idx] = meta_z[alt_key]
            else:
                altitude_labels[z_idx] = "unknown"

            valid_data_found = False
            for line in data_lines:
                parts = [p.strip().strip(',') for p in line.strip().split(',') if p.strip()]
                if len(parts) >= 5 and parts[0].isdigit() and parts[1].isdigit():
                    try:
                        x = int(parts[0]) - 1
                        y = int(parts[1]) - 1
                        val = float(parts[4])
                        if not np.isnan(val) and 0 <= x < meta["x_size"] and 0 <= y < meta["y_size"]:
                            grid[y, x] = val
                            valid_data_found = True
                    except Exception:
                        continue

            z_levels.append(grid)
            z_coords.append(z_idx)

        # Embed T-key altitude mapping in metadata
        t_key_match = re.search(r'_T(\d+)', os.path.basename(group[0][1]))
        if t_key_match:
            t_key_str = f"T{t_key_match.group(1)}"
            meta[f"{t_key_str}_altitudes"] = str(altitude_labels)

        z_cube = np.stack(z_levels, axis=0)
        ds = xr.Dataset(
            {"ash_concentration": (['altitude', 'latitude', 'longitude'], z_cube)},
            coords={
                "altitude": np.array(z_coords, dtype=np.float32),
                "latitude": lats,
                "longitude": lons
            },
            attrs={
                "title": "Volcanic Ash Concentration (3D)",
                "field_descriptions": "\n".join(field_lines),
                "source": "NAME model output processed to NetCDF (3D fields)",
                **{k: str(v) for k, v in meta.items()}
            }
        )

        out_path = os.path.join(self.output_3d, output_filename)
        ds.to_netcdf(out_path, engine="scipy")  # Use "netcdf4" if available
        return out_path




    
    ##########################################################


    
    def batch_process_zip(self, zip_path: Union[str, List[str]], output_root: str = None, cleanup: bool = False) -> List[str]:
        """
        Processes one or more ZIP files containing NAME model outputs.
        Each ZIP file is extracted, its run_name is identified, and outputs are stored
        in a folder named after that run_name.

        Args:
            zip_path (Union[str, List[str]]): One or more paths to ZIP files.
            output_root (str): Optional root output directory.
            cleanup (bool): Whether to delete temporary extracted files.

        Returns:
            List[str]: List of NetCDF file paths generated across all processed ZIPs.
        """

        # Step 1: Handle list input by calling the method recursively
        if isinstance(zip_path, list):
            all_nc_files = []
            for path in zip_path:
                print(f"\n🔁 Processing ZIP: {os.path.basename(path)}")
                nc_files = self.batch_process_zip(path, output_root=output_root, cleanup=cleanup)
                all_nc_files.extend(nc_files)
            return all_nc_files

        # Step 2: Extract ZIP to temporary folder
        zip_base_name = os.path.splitext(os.path.basename(zip_path))[0]
        extract_dir = os.path.join(tempfile.gettempdir(), f"unzipped_{zip_base_name}")
        os.makedirs(extract_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)

        print(f"📂 Extracted {zip_base_name} to: {extract_dir}")

        # Step 3: Find .txt files and extract run_name
        txt_files = []
        self.run_name = None

        for root, _, files in os.walk(extract_dir):
            for file in files:
                if file.endswith(".txt"):
                    txt_path = os.path.join(root, file)
                    txt_files.append(txt_path)

                    # Try extracting run_name from first valid file
                    if not self.run_name:
                        with open(txt_path, 'r') as reader:
                            lines = reader.readlines()
                        try:
                            meta, _ = self.extract_metadata_and_fields(lines, txt_path)
                            self.run_name = meta.get("run_name", None)
                        except Exception:
                            continue

        if not self.run_name:
            raise ValueError(f"❌ No run_name found in {zip_path}")

        # Step 4: Create final output folder for this run
        if output_root:
            final_output_root = os.path.join(output_root, self.run_name)
        else:
            final_output_root = os.path.join(tempfile.gettempdir(), "name_outputs", self.run_name)

        if os.path.exists(final_output_root):
            # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # final_output_root += f"_{timestamp}"
            
            print(f"⚠️ Output folder already exists.skip Creating new folder: {final_output_root}")

        self.output_root = final_output_root
        self._initialize_output_dirs(self.output_root)

        print(f"📁 Output for run '{self.run_name}': {self.output_root}")

        # Step 5: Sort .txt files into horizontal and 3D field groups
        horizontal_files = []
        grouped_3d = {}
        horizontal_groups = {}
        pattern = re.compile(r"_T(\d+)_.*_Z(\d+)\.txt$")

        for f in txt_files:
            if self._is_horizontal_file(f):
                time_match = re.search(r"_T(\d+)", os.path.basename(f))
                time_id = int(time_match.group(1)) if time_match else -1
                horizontal_groups[time_id] = f
                horizontal_files.append(f)
            else:
                match = pattern.search(f)
                if match:
                    t = int(match.group(1))
                    z = int(match.group(2))
                    grouped_3d.setdefault(t, []).append((z, f))

        horizontal_files = sorted(horizontal_files, key=lambda f: int(re.search(r"_T(\d+)_", os.path.basename(f)).group(1)))
        total_items = sum(len(grouped_3d[t]) for t in grouped_3d) + len(horizontal_groups)

        # Step 6: Progress bar for scanning
        with tqdm(total=total_items, desc="🔄 Scanning files...", unit="file") as pbar:
            for t_key in sorted(grouped_3d.keys()):
                for z, _ in sorted(grouped_3d[t_key], key=lambda x: x[0]):
                    pbar.set_description(f"3D file T={t_key}, Z={z}")
                    pbar.update(1)
            for t_key in sorted(horizontal_groups.keys()):
                pbar.set_description(f"Horizontal file T={t_key}")
                pbar.update(1)

        # Step 7: Convert .txt files to NetCDF
        print("\n🚀 Converting to NetCDF...")

        nc_files = []
        for f in horizontal_files:
            base_name = os.path.splitext(os.path.basename(f))[0]
            out_nc = self._convert_horizontal(f, f"{base_name}.nc")
            nc_files.append(out_nc)

        for t_key in sorted(grouped_3d.keys()):
            group = sorted(grouped_3d[t_key], key=lambda x: x[0])
            out_nc = self._convert_3d_group(group, f"T{t_key}.nc")
            nc_files.append(out_nc)

        # Step 8: Cleanup extracted folder
        if cleanup:
            shutil.rmtree(extract_dir, ignore_errors=True)
            print(f"🧹 Cleaned: {extract_dir}")

        # Step 9: Generate summary NetCDF and plots
        summary_nc_name = f"{self.run_name}_datetime_vs_altitude.nc"
        summary_plot_path = os.path.join(self.output_root, f"{self.run_name}_datetime_vs_altitude_plot.png")
        valid_counts_plot_path = os.path.join(self.output_root, f"{self.run_name}_valid_data_counts.png")

        summary_nc_path = self.generate_datetime_vs_altitude_summary(
            summary_output=summary_nc_name,
            plot=False,
            save_plot=summary_plot_path
        )

        self.plot_valid_data_counts_by_attribute(
            save_plot=valid_counts_plot_path,
            plot=False
        )

        print("\n✅ Completed run:", self.run_name)
        print(f"   ↳ Output folder: {self.output_root}")
        
        # Track this run's output for later listing
        self._run_outputs.append((self.run_name, self.output_root))


        return nc_files
    
    
    def list_run_output_folders(self, as_print: bool = True) -> List[str]:
        """
        Lists all run-specific output folders that were processed during this session.

        Args:
            as_print (bool): If True, prints each folder path.

        Returns:
            List[str]: List of run output folder paths.
        """
        if not self._run_outputs:
            raise RuntimeError("No runs have been processed yet. Run batch_process_zip() first.")

        folders = [output_path for _, output_path in self._run_outputs]

        if as_print:
            print("\n📁 Output Folders for All Processed Runs:")
            for name, path in self._run_outputs:
                print(f"   - {name}: {path}")

        return folders






    def generate_datetime_vs_altitude_summary(self, summary_output="datetime_vs_altitude.nc", plot: bool = False, save_plot: str = None):
        """
        Creates a dataset summarizing DateTime vs Altitude vs Mean Ash Concentration and
        number of valid (non-zero, non-NaN) data points per layer. Optionally plots results.

        Args:
            summary_output (str): NetCDF output file name.
            plot (bool): Whether to show a scatter plot.
            save_plot (str): Path to save the plot as PNG or other image format.
        """
        all_datetimes = []
        all_altitudes = []
        all_concentrations = []
        all_valid_counts = []

        nc_files = sorted(glob.glob(os.path.join(self.output_3d, "*.nc")))

        for path in nc_files:
            try:
                ds = xr.open_dataset(path)
                attrs = ds.attrs

                # Extract datetime
                date_str, time_str = None, None
                for k in attrs:
                    if "_date" in k:
                        date_str = attrs[k]
                    if "_time" in k:
                        time_str = attrs[k]

                if date_str and time_str:
                    dt = datetime.strptime(f"{date_str} {time_str.replace(' UTC', '')}", "%d/%m/%Y %H:%M")
                else:
                    print(f"⚠ Skipping {os.path.basename(path)} (missing date/time)")
                    continue

                z_vals = ds["altitude"].values
                ash_data = ds["ash_concentration"].values

                for i, z in enumerate(z_vals):
                    layer = ash_data[i, :, :]
                    mean_conc = np.nanmean(layer)
                    valid_count = np.sum((~np.isnan(layer)) & (layer != 0))

                    all_datetimes.append(dt)
                    all_altitudes.append(z)
                    all_concentrations.append(mean_conc)
                    all_valid_counts.append(valid_count)
                    
                ##################3
                
                        # ✅ Create plume height over time plot
        

                
                ##################

            except Exception as e:
                print(f"⚠ Failed reading {path}: {e}")
                continue

        if not all_datetimes:
            print("❌ No valid 3D data found for summary.")
            return None

        # Save summary dataset
        df = xr.Dataset(
            {
                "mean_ash_concentration": (["entry"], all_concentrations),
                "valid_point_count": (["entry"], all_valid_counts)
            },
            coords={
                "datetime": ("entry", all_datetimes),
                "altitude": ("entry", all_altitudes)
            }
        )

        out_path = os.path.join(self.output_root, summary_output)
        df.to_netcdf(out_path, engine="netcdf4")
        print(f"\n📈 Summary dataset saved at: {out_path}")

        # Plotting
        if plot or save_plot:
            import matplotlib.pyplot as plt
            from matplotlib import dates as mdates

            fig, (ax1, ax2) = plt.subplots(
                2, 1, figsize=(18, 12), sharex=False,
                height_ratios=[1, 1], constrained_layout=False
            )

            # Scatter: Mean Ash Concentration
            sc1 = ax1.scatter(df["datetime"].values, df["altitude"].values,
                            c=df["mean_ash_concentration"].values,
                            cmap="turbo", s=60, alpha=0.9)
            ax1.set_ylabel("Altitude (m)", fontsize=12)
            ax1.set_title("🟢 Mean Ash Concentration over Time & Altitude", fontsize=14, weight='bold')
            ax1.grid(True, linestyle='--', alpha=0.3)
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d-%b\n%H:%M'))
            ax1.xaxis.set_major_locator(mdates.HourLocator(interval=6))  # ⏱ 1-hour intervals
            cbar1 = plt.colorbar(sc1, ax=ax1)
            cbar1.set_label("Mean Ash Concentration (g/m³)", fontsize=11)

            # Scatter: Valid Data Point Count
            sc2 = ax2.scatter(df["datetime"].values, df["altitude"].values,
                            c=df["valid_point_count"].values,
                            cmap="turbo", s=50, alpha=0.85)
            ax2.set_xlabel("Datetime (UTC)", fontsize=12)
            ax2.set_ylabel("Altitude (m)", fontsize=12)
            ax2.set_title("🔵 Valid Data Point Count per Layer", fontsize=13, weight='bold')
            ax2.grid(True, linestyle='--', alpha=0.3)
            ax2.xaxis.set_major_formatter(mdates.DateFormatter('%d-%b\n%H:%M'))
            ax2.xaxis.set_major_locator(mdates.HourLocator(interval=6))  # ⏱ 1-hour intervals
            cbar2 = plt.colorbar(sc2, ax=ax2)
            cbar2.set_label("Non-zero Valid Grid Cells", fontsize=11)
            
            for label in ax1.get_xticklabels():
                    label.set_rotation(90)

            for label in ax2.get_xticklabels():
                label.set_rotation(90)

            fig.suptitle("NAME Model Output Summary: Altitude vs Time", fontsize=15, weight='bold', ha='center', x=0.4, y=0.97)

            if save_plot:
                
                plt.savefig(save_plot, dpi=300, bbox_inches='tight')
                print(f"🖼️ Plot saved to: {save_plot}")
            if plot:
                plt.show()
            else:
                plt.close()

        
        
        return out_path


    def plot_valid_data_counts_by_attribute(self, save_plot: str = None, plot: bool = True, use_log: bool = False):
        """
        Creates a subplot for each attribute showing number of valid data points per file,
        grouped and sorted separately for 2D (horizontal) and 3D fields.

        Args:
            save_plot (str): Optional path to save the figure (PNG, PDF, etc.).
            plot (bool): Whether to display the figure.
            use_log (bool): Whether to use logarithmic y-axis.
        """
        import matplotlib.pyplot as plt
        from collections import defaultdict
        import re

        # ------------------------------------------------------------------
        # Helpers
        # ------------------------------------------------------------------
        # Regex: match Tn at start OR preceded by underscore, case-insensitive
        _t_re = re.compile(r'(?:^|_)T(\d+)', re.IGNORECASE)

        def extract_timestep_key(path: str) -> int:
            """Return numeric timestep for sorting; inf if no Tn found."""
            m = _t_re.search(os.path.basename(path))
            return int(m.group(1)) if m else float('inf')

        def label_from_filename(path: str, prefix: str) -> str:
            """
            Return a short label like '2D-T5' or '3D-T12'.
            prefix should be '2D' or '3D'.
            """
            name = os.path.basename(path)
            m = _t_re.search(name)
            if m:
                return f"{prefix}-T{m.group(1)}"
            # fallback: trim extension and take first 6 chars as last resort
            stem = os.path.splitext(name)[0]
            return f"{prefix}-{stem[:6]}"

        def open_nc_safe(path: str):
            """Try several engines to open NetCDF robustly."""
            for eng in ("netcdf4", "h5netcdf", "scipy"):
                try:
                    return xr.open_dataset(path, engine=eng)
                except Exception:
                    continue
            raise RuntimeError(f"Unable to open NetCDF file with any engine: {path}")

        # ------------------------------------------------------------------
        # Collect & sort file lists
        # ------------------------------------------------------------------
        horizontal_paths = sorted(
            glob.glob(os.path.join(self.output_horizontal, "*.nc")),
            key=extract_timestep_key
        )
        three_d_paths = sorted(
            glob.glob(os.path.join(self.output_3d, "*.nc")),
            key=extract_timestep_key
        )

        # ------------------------------------------------------------------
        # Count valid points (non-NaN, non-zero)
        # attribute_counts: {var_name: [(label, count), ...]}
        # ------------------------------------------------------------------
        attribute_counts = defaultdict(list)

        # 2D files
        for path in horizontal_paths:
            try:
                ds = open_nc_safe(path)
            except Exception as e:
                print(f"⚠ Failed processing 2D file {path}: {e}")
                continue

            short_label = label_from_filename(path, "2D")
            for var in ds.data_vars:
                data = ds[var].values
                count = int(np.sum((~np.isnan(data)) & (data != 0)))
                attribute_counts[var].append((short_label, count))

            ds.close()

        # 3D files
        for path in three_d_paths:
            try:
                ds = open_nc_safe(path)
            except Exception as e:
                print(f"⚠ Failed processing 3D file {path}: {e}")
                continue

            short_label = label_from_filename(path, "3D")
            for var in ds.data_vars:
                data = ds[var].values
                count = int(np.sum((~np.isnan(data)) & (data != 0)))
                attribute_counts[var].append((short_label, count))

            ds.close()

        if not attribute_counts:
            print("❌ No valid data found.")
            return

        # ------------------------------------------------------------------
        # Plotting
        # ------------------------------------------------------------------
        num_attrs = len(attribute_counts)
        fig, axes = plt.subplots(
            num_attrs, 1,
            figsize=(max(12, num_attrs * 3), num_attrs * 4),
            constrained_layout=True
        )

        if num_attrs == 1:
            axes = [axes]

        for ax, (attr, entries) in zip(axes, attribute_counts.items()):
            # entries already in 2D-sorted, then 3D-sorted order
            labels = [label for label, _ in entries]
            counts = [count for _, count in entries]

            ax.bar(labels, counts, color="steelblue", edgecolor="k")
            ax.set_title(f"Valid Data Count: {attr}", fontsize=14)
            ax.set_ylabel("Valid Count", fontsize=12)

            # Let matplotlib handle categorical x positions; just rotate ticks
            ax.set_xticklabels(labels, rotation=90, ha="right", fontsize=6)
            ax.set_xlabel("Timestep (2D = Horizontal Fields, 3D = Vertical Columns)", fontsize=11)

            if use_log:
                ax.set_yscale("log")

            ax.grid(True, linestyle='--', alpha=0.4)

        fig.suptitle("Valid Data Points per File for Each Attribute (2D vs 3D)", fontsize=16, ha='center')

        if save_plot:
            plt.savefig(save_plot, dpi=300)
            print(f"🖼️ Plot saved to: {save_plot}")
        if plot:
            plt.show()
        else:
            plt.close()



