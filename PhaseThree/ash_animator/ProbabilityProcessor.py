import os
import re
import ast
import glob
import io
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import numpy.ma as ma
from pathlib import Path
from tqdm import tqdm
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.colors import BoundaryNorm, LogNorm
from matplotlib.ticker import MaxNLocator
from matplotlib.animation import FuncAnimation
from ash_animator.basemaps import draw_etopo_basemap
import cartopy.crs as ccrs
import cartopy.feature as cfeature

import cartopy.io.shapereader as shpreader
from adjustText import adjust_text
import tempfile

import matplotlib.pyplot as plt
from matplotlib import rcParams
from mpl_toolkits.axes_grid1.inset_locator import inset_axes


# Set global font size and aesthetic parameters
# rcParams['font.size'] = 14
# rcParams['axes.titlesize'] = 16
# rcParams['axes.labelsize'] = 14
# rcParams['xtick.labelsize'] = 12
# rcParams['ytick.labelsize'] = 12
# #rcParams['legend.fontsize'] = 12
# rcParams['figure.titlesize'] = 18

# Apply a valid matplotlib style
plt.style.use('classic')  # Other options: 'seaborn-darkgrid', 'seaborn-deep', etc.




class ProbabilityProcessor:
    def __init__(self, input_dir, output_dir="output_probability_maps", time_limit=None, autoload=True, basemap_mode='basemap', basemap_zoom_level= 12):
        
        self.basemap_mode=basemap_mode
        self.basemap_zoom_level=basemap_zoom_level
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        
        
        
        self.time_limit = time_limit
        self.metadata = {}
        self.grid_metadata = {
            "x_origin": 90.0,
            "y_origin": -15.0,
            "x_size": 281,
            "y_size": 221,
            "x_res": 0.25,
            "y_res": 0.25
        }
        self.lon = None
        self.lat = None
        self.simulation_data = {}
        self.sim_names = []
        self.cmap = "turbo"
       
          # Load country geometries for label plotting
        shapefile = shpreader.natural_earth(resolution='110m', category='cultural', name='admin_0_countries')
        self.country_geoms = list(shpreader.Reader(shapefile).records())


        if autoload:
            self._auto_load_all_simulations()

    
        
        os.makedirs(self.output_dir, exist_ok=True)
        
    def _auto_load_all_simulations(self):
        self.sim_names = [d.name for d in self.input_dir.iterdir() if d.is_dir()]
        if not self.sim_names:
            print(f"⚠️ No simulation folders found in: {self.input_dir}")
            return

        def natural_key(path):
            return [int(s) if s.isdigit() else s.lower() for s in re.split(r'(\d+)', path.name)]

        for sim in self.sim_names:
            sim_path = self.input_dir / sim
            files_3d = sorted((sim_path / "3D").glob("*.nc"), key=natural_key)
            files_horizontal = sorted((sim_path / "Horizontal").glob("*.nc"), key=natural_key)
            limit = self.time_limit or min(len(files_3d), len(files_horizontal))
            animator_3d = self.load_animator_from_nc({"files": files_3d[:limit]})
            animator_horizontal = self.load_animator_from_nc({"files": files_horizontal[:limit]})
            self.simulation_data[sim] = {"3D": animator_3d, "Horizontal": animator_horizontal}

        self.time_limit = min(len(v["3D"].datasets) for v in self.simulation_data.values())
        if self.sim_names:
            self.animator3D = self.simulation_data[self.sim_names[0]]["3D"]
            self.animatorHorizontal = self.simulation_data[self.sim_names[0]]["Horizontal"]
            self.metadata = self.animator3D.metadata

    
    def build_grid(self):
        x = self.grid_metadata
        self.lon = x["x_origin"] + np.arange(x["x_size"]) * x["x_res"]
        self.lat = x["y_origin"] + np.arange(x["y_size"]) * x["y_res"]

    def inspect_metadata(self):
        print("\n🔍 Inspecting metadata for all simulations...\n")
        for sim in self.sim_names:
            print(f"Simulation: {sim}")
            for data_key in ["3D", "Horizontal"]:
                try:
                    ds = self.simulation_data[sim][data_key].datasets[0]
                    print(f"  📁 {data_key} file: T1.nc (virtual)")
                    print(f"    - Variables: {list(ds.data_vars)}")
                    print(f"    - Dimensions: {dict(ds.dims)}")
                    print(f"    - Attributes:")
                    for attr, val in ds.attrs.items():
                        print(f"        {attr}: {val}")
                    print("")
                except Exception as e:
                    print(f"  ❌ Could not read {data_key} file for {sim}: {e}")
        print("✅ Metadata inspection complete.\n")


    
    def load_simulation_files(self):
        self.sim_names = [d.name for d in self.input_dir.iterdir() if d.is_dir()]
        for sim in self.sim_names:
            sim_path = self.input_dir / sim
            max_files = len(list((sim_path / "3D").glob("*.nc")))
            limit = self.time_limit if self.time_limit is not None else max_files

            def natural_key(path):
                return [int(s) if s.isdigit() else s.lower() for s in re.split(r'(\d+)', path.name)]

            files_3d = sorted((sim_path / "3D").glob("*.nc"), key=natural_key)[:limit]
            files_horizontal = sorted((sim_path / "Horizontal").glob("*.nc"), key=natural_key)[:limit]

            animator_3d = self.load_animator_from_nc({"files": files_3d})
            animator_horizontal = self.load_animator_from_nc({"files": files_horizontal})

            self.simulation_data[sim] = {
                "3D": animator_3d,
                "Horizontal": animator_horizontal
            }

        self.time_limit = min(len(self.simulation_data[sim]["3D"].datasets) for sim in self.sim_names)

        # Optionally update main metadata from first animator
        # if self.sim_names:
        #     self.metadata = self.simulation_data[self.sim_names[0]]["3D"].metadata
        #     #self.metadata = self.simulation_data[self.sim_names[1]]["Horizontal"].metadata

        if self.simulation_data and self.sim_names:
            self.animator3D = self.simulation_data[self.sim_names[0]]["3D"]
            self.animatorHorizontal = self.simulation_data[self.sim_names[0]]["Horizontal"]
            self.metadata = self.animator3D.metadata
    
    def load_animator_from_nc(self, input):
        """
        Load NetCDF files from a directory or a file list dictionary and return a SimpleAnimator-like object.

        Parameters
        ----------
        input : str or dict
            - If str: path to directory containing T*.nc files
            - If dict: expects {"files": list of NetCDF paths}
        """

        def extract_t_index(path):
            name = os.path.basename(path)
            match = re.search(r"T(\d+)\.nc", name)
            return int(match.group(1)) if match else float("inf")

        # Accept both directory path or dict of files
        if isinstance(input, dict) and "files" in input:
            nc_files = input["files"]
        elif isinstance(input, (str, Path)):
            input = str(input)
            nc_files = sorted(
                glob.glob(os.path.join(input, "T*.nc")),
                key=extract_t_index
            )
        else:
            raise ValueError("Input must be a directory path or a dict with 'files' key")

        if not nc_files:
            raise FileNotFoundError(f"No NetCDF files found in {input}")

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
            levels = None  # No vertical levels, treat as 2D

        lon_grid, lat_grid = np.meshgrid(lons, lats)

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
                alt_dict = self.get_altitudes(t_index)
                return alt_dict.get(level) if alt_dict else None

            def get_datetime(self, t_index):
                date_keys = [f"T{t_index + 1}_date", f"t{t_index + 1}_date"]
                time_keys = [f"T{t_index + 1}_time", f"t{t_index + 1}_time"]
                date = next((self.metadata.get(k) for k in date_keys if self.metadata.get(k)), None)
                time = next((self.metadata.get(k) for k in time_keys if self.metadata.get(k)), None)
                if date or time:
                    return {"date": date, "time": time}
                print(f"⚠️ Date/time metadata not found for T{t_index + 1}")
                return None

            def get_available_timesteps(self):
                ts = set()
                for key in self.metadata:
                    if key.startswith("T") and len(key) > 2 and key[1].isdigit():
                        t_id = key[1:].split("_")[0]
                        if t_id.isdigit():
                            ts.add(int(t_id))
                return sorted(ts)

        return SimpleAnimator(datasets, lons, lats, lon_grid, lat_grid, levels, combined_metadata)

    
    
    def get_coordinates_from_sample(self):
        ds = self.simulation_data[self.sim_names[0]]["3D"].datasets[0]
        if 'lon' in ds:
            lons = ds['lon'].values
        elif 'longitude' in ds:
            lons = ds['longitude'].values
        else:
            raise KeyError("Could not find 'lon' or 'longitude' in dataset.")

        if 'lat' in ds:
            lats = ds['lat'].values
        elif 'latitude' in ds:
            lats = ds['latitude'].values
        else:
            raise KeyError("Could not find 'lat' or 'latitude' in dataset.")

        if 'level' in ds:
            levels = ds['level'].values
        elif 'altitude' in ds:
            levels = ds['altitude'].values
        else:
            levels = None  # 2D dataset fallback

        return lats, lons, levels


    def get_altitudes(self, t_index):
        keys = [f"T{t_index + 1}_altitudes", f"t{t_index + 1}_altitudes"]
        for key in keys:
            raw = self.metadata.get(key)
            if raw:
                try:
                    return ast.literal_eval(raw)
                except Exception as e:
                    print(f"⚠️ Could not parse {key}: {e}")
        return None

    def get_altitude(self, t_index, level):
        alt_dict = self.get_altitudes(t_index)
        return alt_dict.get(level) if alt_dict else None

    def get_datetime(self, t_index):
        date_keys = [f"T{t_index + 1}_date", f"t{t_index + 1}_date"]
        time_keys = [f"T{t_index + 1}_time", f"t{t_index + 1}_time"]
        date = next((self.metadata.get(k) for k in date_keys if self.metadata.get(k)), None)
        time = next((self.metadata.get(k) for k in time_keys if self.metadata.get(k)), None)
        return {"date": date, "time": time} if date or time else None
    
    # def compute_probability(self, data_key, variable_name, output_name, output_dir=None):
    #     print(f"Processing {output_name} for {self.time_limit} time steps...")
    #     time_slices = []
    #     for t_idx in range(self.time_limit):
    #         acc = None
    #         for sim in self.sim_names:
    #             ds = self.simulation_data[sim][data_key].datasets[t_idx]
    #             mask = (ds[variable_name] > 0).astype(np.float32)
    #             acc = mask if acc is None else acc + mask
    #         prob = acc / len(self.sim_names)
    #         prob = prob.expand_dims(time=[t_idx])
    #         time_slices.append(prob)

    #     probability = xr.concat(time_slices, dim="time")
    #     probability.name = output_name
    #     probability.attrs["description"] = f"Probability of {variable_name} > 0 across simulations"
    #     probability.attrs["units"] = "fraction"

    #     # Assign coordinates
    #     sample_ds = self.simulation_data[self.sim_names[0]][data_key].datasets[0]
    #     for dim in sample_ds[variable_name].dims:
    #         coord_val = None
    #         if dim.lower().startswith("lat"):
    #             coord_val = self.lat
    #         elif dim.lower().startswith("lon"):
    #             coord_val = self.lon
    #         elif dim != "time" and dim in sample_ds.coords:
    #             coord_val = sample_ds.coords[dim].values

    #         if coord_val is not None:
    #             # Remove scalar coord if it exists
    #             if dim in probability.coords and probability.coords[dim].ndim == 0:
    #                 probability = probability.drop_vars(dim)
    #             probability = probability.assign_coords({dim: coord_val})


    #     metadata_attrs = {}
    #     for sim in self.sim_names:
    #         src_ds = self.simulation_data[sim][data_key].datasets[0]
    #         for k, v in src_ds.attrs.items():
    #             if k not in metadata_attrs:
    #                 metadata_attrs[k] = v

    #     probability.attrs.update(metadata_attrs)
    #     probability.attrs["generated_by"] = "ProbabilityProcessor"
    #     probability.attrs["source_type"] = data_key
    #     probability.attrs["threshold"] = "probability > 0"

        
    #     # Determine output path
    #     save_dir = Path(output_dir) if output_dir else self.output_dir
    #     save_dir.mkdir(parents=True, exist_ok=True)
    #     output_path = save_dir / f"{output_name}.nc"
        
    #     output_path = self.output_dir / f"{output_name}.nc"
    #     probability.to_netcdf(output_path, engine="scipy")
    #     print(f"✅ Saved to {output_path}")




    def compute_probability(self, data_key, variable_name, output_name, output_dir=None, threshold=0.0):
        print(f"Processing {output_name} for {self.time_limit} time steps with threshold ≥ {threshold}...")
        time_slices = []
        for t_idx in range(self.time_limit):
            acc = None
            
            # if threshold==0.0:
            #     for sim in self.sim_names:
            #         ds = self.simulation_data[sim][data_key].datasets[t_idx]
            #         mask = (ds[variable_name] > 0).astype(np.float32)
            #         acc = mask if acc is None else acc + mask
            # else:
                  
            #     for sim in self.sim_names:
            #         ds = self.simulation_data[sim][data_key].datasets[t_idx]
            #         mask = (ds[variable_name] >= threshold).astype(np.float32)
            #         acc = mask if acc is None else acc + mask
    
            for sim in self.sim_names:
                ds = self.simulation_data[sim][data_key].datasets[t_idx]
                if threshold == 0:
                    mask = (ds[variable_name] > 0).astype(np.float32)
                else:
                    mask = (ds[variable_name] >= threshold).astype(np.float32)
                acc = mask if acc is None else acc + mask

            prob = acc / len(self.sim_names)
            prob = prob.expand_dims(time=[t_idx])
            time_slices.append(prob)

        probability = xr.concat(time_slices, dim="time")
        probability.name = output_name
        probability.attrs["description"] = f"Probability of {variable_name} ≥ {threshold} across simulations"
        probability.attrs["units"] = "fraction"

        # Assign coordinates
        sample_ds = self.simulation_data[self.sim_names[0]][data_key].datasets[0]
        for dim in sample_ds[variable_name].dims:
            coord_val = None
            if dim.lower().startswith("lat"):
                coord_val = self.lat
            elif dim.lower().startswith("lon"):
                coord_val = self.lon
            elif dim != "time" and dim in sample_ds.coords:
                coord_val = sample_ds.coords[dim].values

            if coord_val is not None:
                if dim in probability.coords and probability.coords[dim].ndim == 0:
                    probability = probability.drop_vars(dim)
                probability = probability.assign_coords({dim: coord_val})

        metadata_attrs = {}
        for sim in self.sim_names:
            src_ds = self.simulation_data[sim][data_key].datasets[0]
            for k, v in src_ds.attrs.items():
                if k not in metadata_attrs:
                    metadata_attrs[k] = v

        
        sign = "≥" if threshold != 0 else ">"
        probability.attrs.update(metadata_attrs)
        probability.attrs["generated_by"] = "ProbabilityProcessor"
        probability.attrs["source_type"] = data_key
        probability.attrs["threshold"] = f"probability {sign} {threshold}"

        # # Determine output path
        # save_dir = Path(output_dir) if output_dir else self.output_dir
        # save_dir.mkdir(parents=True, exist_ok=True)
        # output_path = save_dir / f"{output_name}.nc"
        # probability.to_netcdf(output_path, engine="scipy")
        # print(f"✅ Saved to {output_path}")
        
         # ⬇️ Get run_name from metadata
        self.run_name = sample_ds.attrs.get("run_name", "unknown_run").strip().replace(" ", "_")
        # ⬇️ Create subfolder under output_dir
        root_save_dir = Path(output_dir) if output_dir else self.output_dir
        subfolder = root_save_dir # / self.run_name
        subfolder.mkdir(parents=True, exist_ok=True)

        # ⬇️ Save to subfolder
        output_path = subfolder / f"{output_name}_{threshold}.nc"
        probability.to_netcdf(output_path, engine="scipy")

        print(f"✅ Saved to {output_path}")

    
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
            except Exception:
                continue
        adjust_text(texts, ax=ax, only_move={'points': 'y', 'text': 'y'},
                    arrowprops=dict(arrowstyle="->", color='white', lw=0.5))

    def _plot_frame(self, ax, data, lons, lats, title, levels, proj, plot_style="contourf", norm=None, extent=None):
        ax.set_title(title, fontsize=10)
        ax.set_extent([lons.min(), lons.max(), lats.min(), lats.max()], crs=proj)

        try:
            ax.coastlines(zorder=1)
            ax.add_feature(cfeature.BORDERS, linestyle=":", zorder=1)
            draw_etopo_basemap(ax, mode=self.basemap_mode, zoom=self.basemap_zoom_level)
            self._add_country_labels(ax, extent)
        except Exception:
            ax.add_feature(cfeature.LAND, zorder=0)
            ax.add_feature(cfeature.OCEAN, zorder=0)
            ax.coastlines(zorder=1)
            ax.add_feature(cfeature.BORDERS, linestyle=":", zorder=1)

        cmap = plt.get_cmap(self.cmap)
        if norm is None:
            norm = BoundaryNorm(levels, ncolors=cmap.N, clip=False)

        if plot_style == "pcolormesh":
            contour = ax.pcolormesh(lons, lats, data, shading="auto", cmap=cmap, norm=norm, transform=proj, zorder=2, alpha=0.6)
        else:
            contour = ax.contourf(lons, lats, data, levels=levels, cmap=cmap, norm=norm, transform=proj, zorder=2, extend="both", alpha=0.6)
            try:
                ax.contour(lons, lats, data, levels=levels, colors="black", linewidths=0.4, transform=proj, zorder=2)
            except Exception:
                pass  # Skip if contour fails

        raw = self.metadata.get("release_location")
        if raw:
            try:
                lon_str, lat_str = raw.strip().split()
                lon = float(lon_str[:-1]) * (1 if lon_str[-1].upper() == 'E' else -1)
                lat = float(lat_str[:-1]) * (1 if lat_str[-1].upper() == 'N' else -1)
                ax.plot(lon, lat, marker='^', color='red', markersize=8, transform=proj, label="Vent", zorder=5)
                ax.legend(loc="upper left", fontsize=7)
            except Exception:
                pass

        return contour
    
    
    def plot_probability_frame(
        self,
        variable_name,
        time_index=0,
        level_index=0,
        threshold=None,
        cmap="turbo",
        plot_style="contourf",
        extent=None,
        log_scale=False,
        save_path=None
    ):
        filepath = self.output_dir / f"{variable_name}.nc"
        if not filepath.exists():
            print(f"File {filepath} not found.")
            return

        ds = xr.open_dataset(filepath)
        data = ds[variable_name]
        lat_name = next((d for d in data.dims if "lat" in d.lower()), None)
        lon_name = next((d for d in data.dims if "lon" in d.lower()), None)
        is_3d = "time" in data.dims and len(data.dims) == 4

        if is_3d:
            level_dim = [d for d in data.dims if d not in ("time", lat_name, lon_name)][0]
            slice_data = data.isel(time=time_index, **{level_dim: level_index})
        else:
            slice_data = data.isel(time=time_index)

        values = slice_data.values
        if log_scale:
            values = ma.masked_where(values <= 0, values)
            norm = LogNorm(vmin=np.nanmin(values), vmax=np.nanmax(values))
        else:
            if threshold is not None:
                values = ma.masked_where((values < threshold) & (values != 0), values)
            norm = None

        vmin = float(np.nanmin(values))
        vmax = float(np.nanmax(values))
        if vmin == vmax:
            vmax = vmin + 1e-6
        levels = MaxNLocator(nbins=15).tick_values(vmin, vmax)

        lon = slice_data.coords[lon_name].values
        lat = slice_data.coords[lat_name].values

        if extent is None:
            extent = [float(lon.min()), float(lon.max()), float(lat.min()), float(lat.max())]

        valid = ~values.mask if isinstance(values, ma.MaskedArray) else values != 0
        if np.any(valid):
            lat_grid, lon_grid = np.meshgrid(lat, lon, indexing='ij')
            zoom_extent = [
                float(lon_grid[valid].min()), float(lon_grid[valid].max()),
                float(lat_grid[valid].min()), float(lat_grid[valid].max())
            ]
        else:
            zoom_extent = extent

        dt = self.get_datetime(time_index)
        alt = self.get_altitude(time_index, level_index) if is_3d else None
        units = {
            'ash_concentration_probability': 'g/m³', 'air_concentration_probability': 'g/m³',
            'dry_deposition_rate_probability': 'g/(m²·s)',
            'wet_deposition_rate_probability': 'g/(m²·s)' }
            
        unit = units.get(variable_name, 'unknown')
        title_info = "\n".join(filter(None, [
            f"Frame T{time_index + 1}",
            data.attrs.get("description", variable_name),
            f"{dt['date']} {dt['time']}" if dt else None,
            alt or f"Level {level_index}",
            f"Threshold > {threshold}{unit}" if threshold else ""
        ]))
        self.cmap = cmap
        proj = ccrs.PlateCarree()
        fig = plt.figure(figsize=(14, 6))
        ax1 = fig.add_subplot(1, 2, 1, projection=proj)
        ax2 = fig.add_subplot(1, 2, 2, projection=proj)

        self._plot_frame(ax1, values, lon, lat, title_info + " (full)", levels, proj, plot_style, norm=norm, extent=extent)
        self._plot_frame(ax2, values, lon, lat, "Zoomed to plume", levels, proj, plot_style, norm=norm, extent=zoom_extent)
        ax2.set_extent(zoom_extent, crs=proj)

        fig.subplots_adjust(wspace=0.2, bottom=0.25)
        cbar_ax = fig.add_axes([0.2, 0.1, 0.6, 0.03])
        cbar = fig.colorbar(ax2.collections[0], cax=cbar_ax, orientation="horizontal")
        cbar.set_label(f"{data.attrs.get('description', variable_name)} ({data.attrs.get('units', 'fraction')})", fontsize=10, weight="bold")
        if log_scale:
            cbar.ax.set_title("log scale", fontsize=8)
        cbar.ax.tick_params(labelsize=8)

        # if save_path:
        #     fig.savefig(save_path, dpi=150, bbox_inches="tight")
        #     print(f"🖼️ Saved: {save_path}")
        # else:
        #     plt.show()
        
        if save_path:
        # Save to user-defined path
            fig.savefig(save_path, dpi=150, bbox_inches="tight")
            print(f"🖼️ Saved: {save_path}")
        else:
            # Save into run_name subfolder
            #self.run_name = ds.attrs.get("run_name", "unknown_run").strip().replace(" ", "_")
            subfolder = self.output_dir # / self.run_name
            subfolder.mkdir(parents=True, exist_ok=True)
            frame_path = subfolder / f"{variable_name}_frame_T{time_index + 1}.png"
            fig.savefig(frame_path, dpi=150, bbox_inches="tight")
            print(f"🖼️ Saved: {frame_path}")


        plt.close(fig)
        
        
        
    def plot_probability_animation(
        self,
        variable_name,
        level_index=0,
        threshold=None,
        cmap="turbo",
        plot_style="pcolormesh",
        extent=None,
        save_gif=False,
        gif_path=None,
        log_scale=False,
        fps=2, output_dir=None
    ):
        
        #/self.run_name/
        filepath = self.output_dir/ f"{variable_name}_{threshold}.nc"
        
        
        if not filepath.exists():
            print(f"File {filepath} not found.")
            return
        
        ds = xr.open_dataset(filepath)
        data = ds[variable_name]
        lat_name = next((d for d in data.dims if "lat" in d.lower()), None)
        lon_name = next((d for d in data.dims if "lon" in d.lower()), None)
        is_3d = "time" in data.dims and len(data.dims) == 4
        time_len = data.sizes.get("time", 1)
        time_indices = range(time_len)

        values_all = []
        for t in time_indices:
            if is_3d:
                level_dim = [d for d in data.dims if d not in ("time", lat_name, lon_name)][0]
                slice_data = data.isel(time=t, **{level_dim: level_index})
            
            else:
                slice_data = data.isel(time=t)
            v = slice_data.values
            if log_scale:
                v = ma.masked_where(v <= 0, v)
            elif threshold:
                v = ma.masked_where((v < threshold) & (v != 0), v)
            values_all.append(v)

        vmin = float(np.nanmin([np.nanmin(ma.filled(v, np.nan)) for v in values_all]))
        vmax = float(np.nanmax([np.nanmax(ma.filled(v, np.nan)) for v in values_all]))
        if log_scale:
            vmin = max(vmin, 1e-6)
            norm = LogNorm(vmin=vmin, vmax=vmax)
            levels = MaxNLocator(nbins=15).tick_values(vmin, vmax)
        else:
            norm = None
            if vmin == vmax:
                vmax = vmin + 1e-6
            levels = MaxNLocator(nbins=15).tick_values(vmin, vmax)

        self.cmap = cmap
        proj = ccrs.PlateCarree()
        fig = plt.figure(figsize=(16, 12))
        ax1 = fig.add_subplot(1, 2, 1, projection=proj)
        ax2 = fig.add_subplot(1, 2, 2, projection=proj)
        fig.subplots_adjust(wspace=0.2, bottom=0.25)
         # Fancy inset colorbar below ax1
        inset_cbar_ax = inset_axes(
            ax1,
            width="90%",
            height="5%",
            loc="lower left",
            bbox_to_anchor=(0.5, -0.25, 1, 1),
            bbox_transform=ax1.transAxes,
            borderpad=0
        )
        colorbar_obj = [None]

        def update(t_idx):
            ax1.clear()
            ax2.clear()

            if is_3d:
                level_dim = [d for d in data.dims if d not in ("time", lat_name, lon_name)][0]
                slice_data = data.isel(time=t_idx, **{level_dim: level_index})
            else:
                slice_data = data.isel(time=t_idx)
            values = slice_data.values
            if log_scale:
                values = ma.masked_where(values <= 0, values)
            elif threshold:
                values = ma.masked_where((values < threshold) & (values != 0), values)

            lon = slice_data.coords[lon_name].values
            lat = slice_data.coords[lat_name].values

            valid = (values.filled(0) != 0) & ~values.mask if isinstance(values, ma.MaskedArray) else values != 0
            if np.any(valid):
                lat_grid, lon_grid = np.meshgrid(lat, lon, indexing="ij")
                zoom_extent = [
                    float(lon_grid[valid].min()), float(lon_grid[valid].max()),
                    float(lat_grid[valid].min()), float(lat_grid[valid].max())
                ]
            else:
                zoom_extent = extent or [float(lon.min()), float(lon.max()), float(lat.min()), float(lat.max())]

            dt = self.get_datetime(t_idx)
            alt = self.get_altitude(t_idx, level_index) if is_3d else None

            level_index_string = f"{level_index}"
            if variable_name != "ash_concentration_probability":
                level_index_string = "Ground Surface"


            units = {
                'ash_concentration_probability': 'g/m³',
                'air_concentration_probability': 'g/m³',
                'dry_deposition_rate_probability': 'g/(m²·s)',
                'wet_deposition_rate_probability': 'g/(m²·s)'
            }
            unit = units.get(variable_name, '')
            
            sign = "≥" if threshold != 0 else ">"


            title_info = "\n".join(filter(None, [
                f"Frame T{t_idx + 1}",
                f"Probability of {variable_name.replace('_', ' ')} {sign} {threshold} across simulations",
                f"{dt['date']} {dt['time']}" if dt else None,
                alt or f"Level {level_index_string}",
            ]))

            def get_full_extent(data_array):
                lat_name = next((d for d in data_array.dims if "lat" in d.lower()), None)
                lon_name = next((d for d in data_array.dims if "lon" in d.lower()), None)
                lats = data_array.coords[lat_name].values
                lons = data_array.coords[lon_name].values
                return [float(lons.min()), float(lons.max()), float(lats.min()), float(lats.max())]

            self._plot_frame(
                ax1, values, lon, lat,
                title_info + " (full)", levels, proj, plot_style,
                norm=norm, extent=get_full_extent(slice_data)
            )
            self._plot_frame(
                ax2, values, lon, lat,
                "Zoomed to plume", levels, proj, plot_style,
                norm=norm, extent=None
            )
            ax2.set_extent(zoom_extent, crs=proj)

            mappable = ax2.collections[0]
            mappable.set_cmap(plt.get_cmap(self.cmap))

            if colorbar_obj[0] is None:
                colorbar_obj[0] = fig.colorbar(
                    mappable, cax=inset_cbar_ax, orientation="horizontal"
                )
                
                colorbar_obj[0].set_label(
                f"{variable_name.replace('_', ' ')} ({data.attrs.get('units', 'fraction')})",
                fontsize=14, weight="bold", labelpad=10)
                
                inset_cbar_ax.tick_params(labelsize=12, direction="out", length=5)
                inset_cbar_ax.xaxis.set_ticks_position('bottom')
                inset_cbar_ax.xaxis.set_label_position('bottom')
            else:
                colorbar_obj[0].mappable.set_array(mappable.get_array())
                colorbar_obj[0].mappable.set_clim(vmin, vmax)
                colorbar_obj[0].mappable.set_cmap(plt.get_cmap(self.cmap))
        
        ax1.set_aspect('equal')
        ax2.set_aspect('equal')

        if save_gif:
            save_dir = Path(output_dir) if output_dir else self.output_dir
            subfolder = save_dir # / self.run_name
            subfolder.mkdir(parents=True, exist_ok=True)

            gif_out = gif_path or (subfolder / f"{variable_name}_ZLevel_{level_index}_thresh_{threshold}.gif")

            fig.tight_layout()
            anim = FuncAnimation(fig, update, frames=time_indices, repeat=False, blit=False)
            

            anim.save(gif_out, writer="pillow", fps=fps)
            print(f"🎞️ Saved GIF: {gif_out}")
        else:
            plt.show()
        plt.close(fig)
        
    def list_all_timesteps_and_levels(self, sim_type="3D"):
        print(f"\n📊 Listing all time indices and levels for simulation type: {sim_type}")
        for t_index in range(self.time_limit):
            altitudes = self.get_altitudes(t_index)
            level_list=[]
            if altitudes:
                #print(f"T{t_index + 1}:")
                for level, alt in altitudes.items():
                   # print(f"  Level {level}: {alt} m")
                    level_list.append(level)
            else:
                print(f"T{t_index + 1}: ⚠️ No altitude metadata found.")
        return level_list
    
    
    
    def generate_probability_gifs_for_all_levels(
        self,
        variable_name="ash_concentration_probability",
        threshold=0.02,
        log_scale=False,
        save_gif=True,
        output_dir=None,
        fps=2,
        plot_style='pcolormesh',
        cmap='turbo'
    ):
        """
        Generate and optionally save probability animation GIFs for all available vertical levels.

        Parameters
        ----------
        variable_name : str
            Name of the probability variable to plot.
        threshold : float, optional
            Mask threshold below which values are ignored in the plot.
        log_scale : bool, optional
            Whether to use logarithmic color scaling.
        save_gif : bool, optional
            If True, saves GIFs instead of showing plots interactively.
        output_dir : str or Path, optional
            Directory where GIFs will be saved. Defaults to self.output_dir.
        fps : int
            Frames per second for GIF playback.
        plot_style : str
            Plotting style: "contourf" or "pcolormesh".
        cmap : str
            Colormap to use for visualization.
        """
        print(f"\n📽️ Generating GIFs for all vertical levels of {variable_name}...\n")
        levels = self.list_all_timesteps_and_levels()
        print (levels)

        output_dir = Path(output_dir) if output_dir else self.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for i, level in enumerate(levels):
            try:
                print(f"🎯 Processing level {i+1}/{len(levels)}: {level}")

                gif_filename = f"ash_prob_level_{level}.gif"
                gif_path = output_dir / gif_filename

                self.plot_probability_animation(
                    variable_name=variable_name,
                    level_index=level,
                    threshold=threshold,
                    log_scale=log_scale,
                    save_gif=save_gif,
                    gif_path=None,
                    fps=fps,
                    plot_style=plot_style,
                    cmap=cmap
                )

            except Exception as e:
                if i == len(levels) - 1:
                    print(f"⚠️ Skipping last level due to error: {e}")
                else:
                    raise

        # #for i in range(len(levels)):
        # for i, level in enumerate(levels):
        #     try:
        #         print(f"Item {i+1}: {level}")
        
        #         gif_filename = f"ash_prob_level_{levels[i]}.gif"
        #         gif_path = output_dir / gif_filename

        #         self.plot_probability_animation(
        #             variable_name=variable_name,
        #             level_index=levels[i],
        #             threshold=threshold,
        #             log_scale=log_scale,
        #             save_gif=save_gif,
        #             gif_path=None,
        #             fps=fps,
        #             plot_style=plot_style,
        #             cmap=cmap
        #         )
       
        #     except Exception as e:
        #         if i == len(levels) - 1:
        #             print(f"Skipping last item due to error: {e}")
        #         else:
        #             raise  # Only skip failure if it's the last item
            
        


       

    def run_all(self):
        self.build_grid()
        self.load_simulation_files()
        self.compute_probability("3D", "ash_concentration", "ash_concentration_probability")
        self.compute_probability("Horizontal", "air_concentration", "air_concentration_probability")
        self.compute_probability("Horizontal", "dry_deposition_rate", "dry_deposition_rate_probability")
        self.compute_probability("Horizontal", "wet_deposition_rate", "wet_deposition_rate_probability")
        self.list_all_timesteps_and_levels(self, sim_type="3D")
        self.generate_probability_gifs_for_all_levels()
        
        