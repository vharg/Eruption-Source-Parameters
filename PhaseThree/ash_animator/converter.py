

# Re-defining the integrated class first
import os
import re
import zipfile
import numpy as np
import xarray as xr
from typing import List, Tuple
import shutil


import tempfile  # Added for safe temp directory usage

class NAMEDataProcessor:
    def __init__(self, output_root: str = None):
        if output_root is None:
            output_root = os.path.join(tempfile.gettempdir(), "name_outputs")
        self.output_root = output_root
        self.output_3d = os.path.join(self.output_root, "3D")
        self.output_horizontal = os.path.join(self.output_root, "horizontal")
        os.makedirs(self.output_3d, exist_ok=True)
        os.makedirs(self.output_horizontal, exist_ok=True)
        self.output_root = output_root
        self.output_3d = os.path.join(self.output_root, "3D")
        self.output_horizontal = os.path.join(self.output_root, "horizontal")
        os.makedirs(self.output_3d, exist_ok=True)
        os.makedirs(self.output_horizontal, exist_ok=True)

    def _sanitize_key(self, key: str) -> str:
        key = re.sub(r'\W+', '_', key)
        if not key[0].isalpha():
            key = f"attr_{key}"
        return key

    def _parse_metadata(self, lines: List[str]) -> dict:
        metadata = {}
        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                clean_key = self._sanitize_key(key.strip().lower())
                metadata[clean_key] = value.strip()

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

        return metadata

    def _get_data_lines(self, lines: List[str]) -> List[str]:
        idx = next(i for i, l in enumerate(lines) if l.strip() == "Fields:")
        return lines[idx + 1:]

    def _is_horizontal_file(self, filename: str) -> bool:
        return "HorizontalField" in filename

    def _convert_horizontal(self, filepath: str, output_filename: str) -> str:
        with open(filepath, 'r') as f:
            lines = f.readlines()

        meta = self._parse_metadata(lines)
        data_lines = self._get_data_lines(lines)

        lons = np.round(np.arange(meta["x_origin"], meta["x_origin"] + meta["x_size"] * meta["x_res"], meta["x_res"]), 6)
        lats = np.round(np.arange(meta["y_origin"], meta["y_origin"] + meta["y_size"] * meta["y_res"], meta["y_res"]), 6)

        air_conc = np.zeros((meta["y_size"], meta["x_size"]), dtype=np.float32)
        dry_depo = np.zeros((meta["y_size"], meta["x_size"]), dtype=np.float32)
        wet_depo = np.zeros((meta["y_size"], meta["x_size"]), dtype=np.float32)

        for line in data_lines:
            parts = [p.strip().strip(',') for p in line.strip().split(',') if p.strip()]
            if len(parts) >= 7 and parts[0].isdigit() and parts[1].isdigit():
                try:
                    x = int(parts[0]) - 1
                    y = int(parts[1]) - 1
                    air_val = float(parts[4])
                    dry_val = float(parts[5])
                    wet_val = float(parts[6])
                    if 0 <= x < meta["x_size"] and 0 <= y < meta["y_size"]:
                        air_conc[y, x] = air_val
                        dry_depo[y, x] = dry_val
                        wet_depo[y, x] = wet_val
                except Exception:
                    continue

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
                "source": "NAME model output processed to NetCDF (horizontal multi-field)",
                **{k: str(v) for k, v in meta.items()}
            }
        )

        ds["air_concentration"].attrs.update({
            "units": "g/m^3",
            "long_name": "Boundary Layer Average Air Concentration"
        })
        ds["dry_deposition_rate"].attrs.update({
            "units": "g/m^2/s",
            "long_name": "Dry Deposition Rate"
        })
        ds["wet_deposition_rate"].attrs.update({
            "units": "g/m^2/s",
            "long_name": "Wet Deposition Rate"
        })
        ds["latitude"].attrs["units"] = "degrees_north"
        ds["longitude"].attrs["units"] = "degrees_east"

        out_path = os.path.join(self.output_horizontal, output_filename)
        ds.to_netcdf(out_path, engine="netcdf4")

        return out_path

  
    def _convert_3d_group(self, group: List[Tuple[int, str]], output_filename: str) -> str:
        first_file_path = group[0][1]
        with open(first_file_path, 'r') as f:
            lines = f.readlines()
        meta = self._parse_metadata(lines)

        lons = np.round(np.arange(meta["x_origin"], meta["x_origin"] + meta["x_size"] * meta["x_res"], meta["x_res"]), 6)
        lats = np.round(np.arange(meta["y_origin"], meta["y_origin"] + meta["y_size"] * meta["y_res"], meta["y_res"]), 6)

        z_levels = []
        z_coords = []

        for z_idx, filepath in group:
            with open(filepath, 'r') as f:
                lines = f.readlines()
            data_lines = self._get_data_lines(lines)
            grid = np.zeros((meta["y_size"], meta["x_size"]), dtype=np.float32)

            for line in data_lines:
                parts = [p.strip().strip(',') for p in line.strip().split(',') if p.strip()]
                if len(parts) >= 5 and parts[0].isdigit() and parts[1].isdigit():
                    try:
                        x = int(parts[0]) - 1
                        y = int(parts[1]) - 1
                        val = float(parts[4])
                        if 0 <= x < meta["x_size"] and 0 <= y < meta["y_size"]:
                            grid[y, x] = val
                    except Exception:
                        continue
            z_levels.append(grid)
            z_coords.append(z_idx)

        z_cube = np.stack(z_levels, axis=0)
        ds = xr.Dataset(
            {
                "ash_concentration": (['altitude', 'latitude', 'longitude'], z_cube)
            },
            coords={
                "altitude": np.array(z_coords, dtype=np.float32),
                "latitude": lats,
                "longitude": lons
            },
            attrs={
                "title": "Volcanic Ash Concentration (3D)",
                "source": "NAME model output processed to NetCDF (3D fields)",
                **{k: str(v) for k, v in meta.items()}
            }
        )

        out_path = os.path.join(self.output_3d, output_filename)

        # 🔥 Check if file exists, delete it first
        # if os.path.exists(out_path):
        #     os.remove(out_path)

        # 🔥 Save NetCDF safely using netCDF4
        ds.to_netcdf(out_path, engine="netcdf4")

        return out_path


    def batch_process_zip(self, zip_path: str) -> List[str]:
        extract_dir = os.path.join(tempfile.gettempdir(), "unzipped_name_extract")

        os.makedirs(extract_dir, exist_ok=True)
        
        ###
        

            # Function to empty folder contents
        def empty_folder(folder_path):
            import os
            import glob
            files = glob.glob(os.path.join(folder_path, '*'))
            for f in files:
                try:
                    os.remove(f)
                except IsADirectoryError:
                    shutil.rmtree(f)

        # 🛠 Clear cached open files and garbage collect before deleting
        
        # 🔥 Empty previous outputs, do not delete folders
        if os.path.exists(self.output_3d):
            empty_folder(self.output_3d)
        else:
            os.makedirs(self.output_3d, exist_ok=True)

        # if os.path.exists(self.output_horizontal):
        #     empty_folder(self.output_horizontal)
        # else:
        #     os.makedirs(self.output_horizontal, exist_ok=True)

        # if os.path.exists(extract_dir):
        #     shutil.rmtree(extract_dir)
        # os.makedirs(extract_dir, exist_ok=True)

        

        
        
        #####

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)

        txt_files = []
        for root, _, files in os.walk(extract_dir):
            for file in files:
                if file.endswith(".txt"):
                    txt_files.append(os.path.join(root, file))

        horizontal_files = []
        grouped_3d = {}

        pattern = re.compile(r"_T(\d+)_.*_Z(\d+)\.txt$")

        for f in txt_files:
            if self._is_horizontal_file(f):
                horizontal_files.append(f)
            else:
                match = pattern.search(f)
                if match:
                    t = int(match.group(1))
                    z = int(match.group(2))
                    grouped_3d.setdefault(t, []).append((z, f))

        nc_files = []

        # Process horizontal
        for f in sorted(horizontal_files):
            base_name = os.path.splitext(os.path.basename(f))[0]
            out_nc = self._convert_horizontal(f, f"{base_name}.nc")
            nc_files.append(out_nc)

        # Process 3D
        for t_key in sorted(grouped_3d):
            group = sorted(grouped_3d[t_key])
            out_nc = self._convert_3d_group(group, f"T{t_key}.nc")
            nc_files.append(out_nc)

        return nc_files