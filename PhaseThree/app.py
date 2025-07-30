
import os
import glob
import shutil
import io
import logging
import panel as pn
import xarray as xr
import numpy as np
from datetime import datetime
from types import SimpleNamespace
from collections import defaultdict
from ash_animator.converter import NAMEDataProcessor
from ash_animator.plot_3dfield_data import Plot_3DField_Data
from ash_animator.plot_horizontal_data import Plot_Horizontal_Data
from ash_animator.AshConcentrationAnalyzer import AshExceedanceAnalyzer_3D, MultiFieldExceedanceAnalyzer_2D
from ash_animator.ProbabilityProcessor import ProbabilityProcessor

import contextlib
import sys
import matplotlib.pyplot as plt
import tempfile
import json
import errno
import stat

pn.extension('filedropper', raw_css=["""
.debugger-pane pre {
    background-color: #1f1f1f;
    color: #dcdcdc;
    font-family: 'Segoe UI Mono', Consolas, monospace;
    padding: 16px;
    border-radius: 12px;
    overflow-y: auto;
    overflow-x: hidden;
    max-height: 300px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
    margin: 0;
    white-space: pre-wrap;
    word-break: break-word;
    transition: background-color 0.3s ease;
}


.bk.panel-widget-box {
    background-color: #ffffff;
    border-radius: 12px;
    padding: 12px;
    box-shadow: 0 1px 8px rgba(0, 0, 0, 0.08);
}
.bk.card {
    border-radius: 16px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
    background: linear-gradient(to right, #f9f9f9, #ffffff);
}
.bk-btn-primary {
    border-radius: 8px;
    font-weight: 500;
    font-family: "Segoe UI", sans-serif;
    background-color: #2563eb;
    color: white;
    transition: all 0.2s ease-in-out;
}
.bk-btn-primary:hover {
    background-color: #1e40af;
}
.bk-pane-markdown h2, .bk-pane-markdown h3 {
    font-family: "Segoe UI", sans-serif;
    color: #333333;
    margin-bottom: 8px;
}
"""])

pn.config.raw_css.append("body { font-family: 'Segoe UI', sans-serif; }")


# ========== Terminal Output Management ==========

class LiveOutput(io.StringIO):
    def __init__(self, pane, max_length=10000):
        super().__init__()
        self.pane = pane
        self._buffer = ""
        self.max_length = max_length

    def write(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Escape HTML
        safe_msg = (
            msg.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

        # Color tagging and emojis
        if "error" in safe_msg.lower() or "exception" in safe_msg.lower() or "❌" in safe_msg:
            styled_msg = f"<span style='color:#000;'>🛑 [{timestamp}] {safe_msg.strip()}</span>"
        elif "success" in safe_msg.lower() or "✅" in safe_msg:
            styled_msg = f"<span style='color:#000;'>✅ [{timestamp}] {safe_msg.strip()}</span>"
        elif "warning" in safe_msg.lower() or "⚠️" in safe_msg.lower():
            styled_msg = f"<span style='color:#000;'>⚠️ [{timestamp}] {safe_msg.strip()}</span>"
        elif "info" in safe_msg.lower() or "ℹ️" in safe_msg:
            styled_msg = f"<span style='color:#38bdf8;'>ℹ️ [{timestamp}] {safe_msg.strip()}</span>"
        else:
            styled_msg = f"<span style='color:#dcdcdc;'>[{timestamp}] {safe_msg.strip()}</span>"

        # Add line and clip buffer
        self._buffer += styled_msg + "<br>"
        if len(self._buffer) > self.max_length:
            self._buffer = "...\n" + self._buffer[-self.max_length:]

        # Scroll script to keep at bottom
        scroll_script = (
            "<script>var e = document.getElementById('log-content');"
            "if(e) e.scrollTop = e.scrollHeight;</script>"
        )

        self.pane.object = (
            f"<pre id='log-content' class='debugger-pane'>{self._buffer}</pre>{scroll_script}"
        )
        return len(msg)



    def flush(self):
        pass


terminal_output = pn.pane.HTML(
    "<pre id='log-content' style='margin:0; font-family:monospace; white-space:pre-wrap;'>"
    "Live terminal output will appear here..."
    "</pre>",
    sizing_mode="stretch_width",
    css_classes=["debugger-pane"]
)

output_buffer = LiveOutput(terminal_output)

def clear_terminal_output(event=None):
    terminal_output.object = (
        "<pre id='log-content' class='debugger-pane'></pre>"
    )
    output_buffer.truncate(0)
    output_buffer.seek(0)

clear_output_button = pn.widgets.Button(
    name="🧹 Clear Output", button_type="danger", width=150
)
clear_output_button.on_click(clear_terminal_output)

def capture_terminal_output(func):
    def wrapper(*args, **kwargs):
        live_output = LiveOutput(terminal_output)
        with contextlib.redirect_stdout(live_output), contextlib.redirect_stderr(live_output):
            try:
                func(*args, **kwargs)
            except Exception as e:
                print(f"❌ Exception: {e}")
    return wrapper


# ========== Media & Logging Setup ==========
MEDIA_DIR = os.path.abspath(os.path.join(".", "media"))
os.makedirs(MEDIA_DIR, exist_ok=True)

LOG_FILE = os.path.join(MEDIA_DIR, "app_errors.log")
logging.basicConfig(filename=LOG_FILE, level=logging.ERROR,
                    format="%(asctime)s - %(levelname)s - %(message)s")

# Global State
animator_obj = {}
run_project_paths = {}

# ========== File Upload Widgets ==========
file_input = pn.widgets.FileInput(accept=".zip")
file_dropper = pn.widgets.FileDropper(
    name="📂 Drag & Drop ZIP file here",
    multiple=True
)

status = pn.pane.Markdown("""
### 📌 Getting Started with NAME Model Output Simulation Visualization

#### ✅ Instructions:
- 🗂️ **Step 1 (Optional)**: Upload your own NAME Model Simulation output in `.ZIP` format  
  If no file is uploaded, default data from **Taal Volcano** will be used.

- ▶️ **Step 2 (Required)**: Click **`Process Zip`**  
  This will process either your uploaded file or the default dataset.

- 📥 **Step 3 (Optional)**: Click **`Download Plots and Data`** to export results.
---
""")

# Handle drag-drop saving
def on_file_drop(event):
    file_data = event.new
    if file_data:
        for filename, file_bytes in file_data.items():
            zip_path = os.path.join(MEDIA_DIR, filename)
            with open(zip_path, "wb") as f:
                f.write(file_bytes)
            file_input.filename = filename
            file_input.value = file_bytes
            print(f"✅ Uploaded file saved to: {zip_path}")
            status.object = f"📂 Uploaded file saved to: {zip_path}"

file_dropper.param.watch(on_file_drop, 'value')


process_button = pn.widgets.Button(name="📦 Process ZIP", button_type="primary")
reset_button = pn.widgets.Button(name="🔄 Reset App", button_type="danger")
run_all_button = pn.widgets.Button(name="🚀 Run ALL Analysis", button_type="primary", width=200)

download_button = pn.widgets.FileDownload(
    label="⬇️ Download All Plots and Data",
    filename="all_exports.zip",
    button_type="success",
    callback=lambda: io.BytesIO(
        open(shutil.make_archive(
            os.path.join(MEDIA_DIR, "all_exports").replace(".zip", ""),
            "zip", MEDIA_DIR
        ), 'rb').read()
    )
)

log_link = pn.widgets.FileDownload(
    label="🪵 View Error Log", file=LOG_FILE,
    filename="app_errors.log", button_type="warning"
)


all_cmaps = plt.colormaps()
cmap_select = pn.widgets.Select(name='Colormap', options=sorted(all_cmaps), value='turbo')
basemap_select = pn.widgets.Select(name='Basemap Mode', options=["default","basemap", "stock", "contextily"])
zoom_slider = pn.widgets.IntSlider(name='Basemap Zoom Level', start=1, end=30, value=10)

# Combined FloatInput + Slider pairs
threshold_3d_input = pn.widgets.FloatInput(name='3D Concentration Threshold (g/m³)', step=0.01, value=0.1, format='0.0000000')
threshold_3d_slider = pn.widgets.FloatSlider(start=0.0, end=1.0, step=0.01, value=0.1, format='0.0000000')
threshold_3d_input.link(threshold_3d_slider, value='value')
threshold_3d_slider.link(threshold_3d_input, value='value')
threshold_slider_3d = threshold_3d_input
threshold_slider_3d_combined = pn.Row(threshold_3d_slider, threshold_3d_input)

threshold_2d_input = pn.widgets.FloatInput(name='2D Threshold (g/m³ or g/(m²·s))', step=0.01, value=0.005, format='0.0000000')
threshold_2d_slider = pn.widgets.FloatSlider(start=0.0, end=1.0, step=0.01, value=0.005, format='0.0000000')
threshold_2d_input.link(threshold_2d_slider, value='value')
threshold_2d_slider.link(threshold_2d_input, value='value')
threshold_slider_2d = threshold_2d_input
threshold_slider_2d_combined = pn.Row(threshold_2d_slider, threshold_2d_input)

exceedance_input_3d = pn.widgets.FloatInput(name="3D Probability Threshold (g/m³)", step=0.0001, value=0.002, format='0.0000000')


exceedance_slider_3d = pn.widgets.FloatSlider(start=0.0, end=1.0, step=0.0001, value=0.002, format='0.0000000')
exceedance_input_3d.link(exceedance_slider_3d, value='value')
exceedance_slider_3d.link(exceedance_input_3d, value='value')

exceedance_threshold_3d = exceedance_input_3d
exceedance_threshold_3d_combined = pn.Row(exceedance_slider_3d, exceedance_input_3d)

exceedance_input_2d = pn.widgets.FloatInput(name="2D Probability Threshold (g/m³ or g/(m²·s))", step=0.0001, value=0.00001, format='0.0000000')
exceedance_slider_2d = pn.widgets.FloatSlider(start=0.0, end=1.0, step=0.0001, value=0.00001, format='0.0000000')
exceedance_input_2d.link(exceedance_slider_2d, value='value')
exceedance_slider_2d.link(exceedance_input_2d, value='value')
exceedance_threshold_2d = exceedance_input_2d
exceedance_threshold_2d_combined = pn.Row(exceedance_slider_2d, exceedance_input_2d)
fps_slider_2d = pn.widgets.IntSlider(name='2D FPS', start=1, end=10, value=2)
Altitude_slider = pn.widgets.IntSlider(name='Define Ash Altitude Level', start=0, end=15, value=4)
fps_slider_3d = pn.widgets.IntSlider(name='3D FPS (frame/second)', start=1, end=10, value=2)



nc_file_selector_3d = pn.widgets.Select(
    name="📂 Select Project Name to Load 3D and 2D Files",
    options=[], width=300, height=200, size=6
)

@capture_terminal_output
def process_zip(event=None):
    global last_selected_zip_path

    zip_paths = []
    uploaded_files = []

    if file_dropper.value:
        for filename, file_bytes in file_dropper.value.items():
            zip_path = os.path.join(MEDIA_DIR, filename)
            with open(zip_path, "wb") as f:
                f.write(file_bytes)
            zip_paths.append(zip_path)
            uploaded_files.append(filename)
            print(f"✅ file_dropper file saved: {zip_path}")
        status.object = f"✅ Processing {len(zip_paths)} file(s) from drop zone {[p for p in zip_paths]}"

    elif file_input.value and file_input.filename:
        zip_path = os.path.join(MEDIA_DIR, file_input.filename)
        with open(zip_path, "wb") as f:
            f.write(file_input.value)
        zip_paths.append(zip_path)
        uploaded_files.append(file_input.filename)
        status.object = f"✅ Processing uploaded file: {zip_path}"
        print(f"✅ file_input path: {zip_path}")

    else:
        default_path = os.path.join(MEDIA_DIR, "default_model.zip")
        if not os.path.exists(default_path):
            default_path = "default_model.zip"
        zip_paths.append(default_path)
        uploaded_files.append(os.path.basename(default_path))
        status.object = "ℹ️ Using default_model.zip"
        print(f"ℹ️ Default file used: {default_path}")

    print(f"📂 Uploaded ZIP files: {uploaded_files}")

    try:
        output_dir = os.path.join(".", "ash_output")
        animator_obj.clear()
        run_project_paths.clear()
        import gc; gc.collect()
        shutil.rmtree(output_dir, ignore_errors=True)
        os.makedirs(output_dir, exist_ok=True)
    except PermissionError:
        output_dir = os.path.join(tempfile.gettempdir(), "ash_output")
        os.makedirs(output_dir, exist_ok=True)

    try:
        processor = NAMEDataProcessor()
        processor.batch_process_zip(zip_paths, output_root="./ash_output", cleanup=True)
        paths_unzip_run = processor.list_run_output_folders(as_print=True)
        run_project_paths['run_name_path'] = paths_unzip_run

        animator_obj["3d"] = []
        animator_obj["2d"] = []
        file_list_3d, file_list_2d = [], []

        for path in run_project_paths['run_name_path']:
            path_3d = os.path.join(path, "3D")
            path_2d = os.path.join(path, "horizontal")

            for fp in sorted(glob.glob(os.path.join(path_3d, "*.nc"))):
                print(f"📂 Loading 3D file: {fp}")
                with xr.open_dataset(fp) as ds:
                    animator_obj["3d"].append(ds.load())
                file_list_3d.append(fp)

            for fp in sorted(glob.glob(os.path.join(path_2d, "*.nc"))):
                print(f"📂 Loading 2D file: {fp}")
                with xr.open_dataset(fp) as ds:
                    animator_obj["2d"].append(ds.load())
                file_list_2d.append(fp)

        # project_names = [os.path.basename(p) for p in run_project_paths['run_name_path']]
        # project_path_map = {name: p for name, p in zip(project_names, run_project_paths['run_name_path'])}
        project_names = [os.path.basename(p) for p in run_project_paths['run_name_path']]
        project_path_map = {name: p for name, p in zip(project_names, run_project_paths['run_name_path'])}

        run_project_paths['project_name_to_path'] = project_path_map

        with open(os.path.join(MEDIA_DIR, "project_path_map.json"), "w") as f:
            json.dump(project_path_map, f)

        nc_file_selector_3d.options = list(project_path_map.keys())

        with open(os.path.join(MEDIA_DIR, "last_run.txt"), "w") as f:
            f.write(",".join(zip_paths))

        status.object += f" | ✅ Loaded {len(animator_obj['3d'])} 3D & {len(animator_obj['2d'])} 2D datasets."
        update_media_tabs()

    except Exception as e:
        logging.exception("Error during ZIP processing")
        status.object = f"❌ Processing failed: {e}"


@capture_terminal_output
def restore_previous_session():
    update_media_tabs()
    try:
        state_file = os.path.join(MEDIA_DIR, "last_run.txt")
        project_map_file = os.path.join(MEDIA_DIR, "project_path_map.json")

        # if os.path.exists(state_file):
        #     with open(state_file) as f:
        #         zip_path = f.read().strip()
        #         if os.path.exists(zip_path):
        #             status.object = f"🔁 Restored previous session from {os.path.basename(zip_path)}"
                    
        # if os.path.exists(state_file):
        #     with open(state_file) as f:
        #         zip_path = f.read().strip()

        #         # Extract the project name from the ZIP file (or folder) name
        #         project_name = os.path.basename(zip_path).replace(".zip", "")

        #         if os.path.exists(zip_path):
        #             status.object = f"🔁 Restored previous session from {zip_path}"
        #         else:
        #             print(f"⚠️ Previous ZIP path '{zip_path}' not found.")


        if os.path.exists(project_map_file):
            with open(project_map_file, "r") as f:
                project_path_map = json.load(f)
                run_project_paths['project_name_to_path'] = project_path_map
                run_project_paths['run_name_path'] = list(project_path_map.values())

                if isinstance(project_path_map, dict):
                    nc_file_selector_3d.options = dict(project_path_map)
                    if project_path_map:
                            # Use only the project name (not full path)
                        first_project = list(project_path_map.keys())[0]
                        if first_project in nc_file_selector_3d.options:
                            nc_file_selector_3d.value = first_project
                            on_project_selected(SimpleNamespace(new=first_project))
                        else:
                            print(f"⚠️ Project '{first_project}' not found in options.")


            status.object = f"🔁 Restored previous session from {project_path_map}"

    except Exception as e:
        logging.exception("Error restoring previous session")
        status.object = f"⚠️ Could not restore previous session: {e}"


def on_project_selected(event):
    selected_project = event.new
    if not selected_project:
        return

    # Step 1: Resolve path from selector
    options = nc_file_selector_3d.options
    if isinstance(options, dict) and selected_project in options:
        selected_path = options[selected_project]
    elif isinstance(options, list) and selected_project in options:
        selected_path = run_project_paths['project_name_to_path'].get(selected_project)
    else:
        print(f"⚠️ Project '{selected_project}' not found in options.")
        return

    project_path_map_path = os.path.join(MEDIA_DIR, "project_path_map.json")

    try:
        # Step 2: Load or initialize path map
        if os.path.exists(project_path_map_path):
            with open(project_path_map_path, "r") as f:
                try:
                    project_path_map = json.load(f)
                except json.JSONDecodeError:
                    print("⚠️ Corrupt project_path_map.json, reinitializing.")
                    project_path_map = {}
        else:
            project_path_map = {}

        # Step 3: Only update if path is new or changed
        if selected_project in project_path_map:
            existing_path = project_path_map[selected_project]
            if existing_path == selected_path:
                print(f"🔁 Project '{selected_project}' already mapped to same path. No update needed.")
                return  # Skip writing file

        # Step 4: Update and save new path
        project_path_map[selected_project] = selected_path
        with open(project_path_map_path, "w") as f:
            json.dump(project_path_map, f, indent=4)

        print(f"📁 [Project Path Map Updated] ➤ '{selected_project}' mapped to '{selected_path}'")

    except Exception as e:
        print(f"❌ [Error Updating Project Path Map] ➤ {e}")

nc_file_selector_3d.param.watch(on_project_selected, 'value')



def handle_remove_readonly(func, path, exc):
    excvalue = exc[1]
    if func in (os.rmdir, os.remove, os.unlink) and excvalue.errno == errno.EACCES:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    else:
        raise

def reset_app(event=None):
    animator_obj.clear()
    file_input.value = None

    for k in list(animator_obj.keys()):
        datasets = animator_obj[k]
        if isinstance(datasets, list):
            for ds in datasets:
                try:
                    ds.close()
                except Exception:
                    pass

    for entry in os.listdir(MEDIA_DIR):
        full_path = os.path.join(MEDIA_DIR, entry)
        try:
            if os.path.isdir(full_path):
                shutil.rmtree(full_path, ignore_errors=False, onerror=handle_remove_readonly)
            else:
                os.remove(full_path)
        except Exception as e:
            print(f"⚠️ Could not delete {full_path}: {e}")

    for root, dirs, _ in os.walk(MEDIA_DIR, topdown=False):
        for d in dirs:
            dir_path = os.path.join(root, d)
            try:
                os.rmdir(dir_path)
            except OSError as e:
                print(f"⚠️ Could not remove empty folder {dir_path}: {e}")

    last_run = os.path.join(MEDIA_DIR, "last_run.txt")
    if os.path.exists(last_run):
        try:
            os.remove(last_run)
        except Exception as e:
            print(f"⚠️ Could not remove last_run.txt: {e}")

    map_path = os.path.join(MEDIA_DIR, "project_path_map.json")
    if os.path.exists(map_path):
        try:
            os.remove(map_path)
        except Exception as e:
            print(f"⚠️ Could not remove project_path_map.json: {e}")

    file_dropper.value = {}
    update_media_tabs()

    status.object = (""" 🔄 App has been reset: 
### 📌 Getting Started with NAME Model Output Simulation Visualization

#### ✅ Instructions:
- 🗂️ **Step 1 (Optional)**: Upload your own NAME Model Simulation output in `.ZIP` format  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;If no file is uploaded, default data from **Taal Volcano** will be used.

- ▶️ **Step 2 (Required)**: Click **`Process Zip`**  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;This will process either your uploaded file or the default dataset.

- 📥 **Step 3 (Optional)**: Click **`Download Plots and Data`** to export a sample `.ZIP` structure and results from the **Taal Volcano** simulation.
---
""")


def build_animator_3d():
    ds = animator_obj.get("3d", [])
    if not ds:
        raise ValueError("No 3D datasets found. Please process a ZIP file first.")
    lat_grid, lon_grid = xr.broadcast(ds[0]["latitude"], ds[0]["longitude"])
    return SimpleNamespace(
        datasets=ds,
        levels=ds[0].altitude.values,
        lats=ds[0]["latitude"].values,
        lons=ds[0]["longitude"].values,
        lat_grid=lat_grid.values,
        lon_grid=lon_grid.values,
    )

def build_animator_2d():
    ds = animator_obj.get("2d", [])
    if not ds:
        raise ValueError("No 2D datasets found. Please process a ZIP file first.")
    lat_grid, lon_grid = xr.broadcast(ds[0]["latitude"], ds[0]["longitude"])
    return SimpleNamespace(
        datasets=ds,
        lats=ds[0]["latitude"].values,
        lons=ds[0]["longitude"].values,
        lat_grid=lat_grid.values,
        lon_grid=lon_grid.values,
    )



@capture_terminal_output
def run_all_analysis():
    """
    Runs all main analysis functions in sequence.
    """
    # Re-process ZIP if needed
    #process_zip()
    
    # Generate 3D outputs
    plot_z_level()
    plot_vertical_profile()
    animate_all_altitude_profiles()
    
    
    # Generate 2D outputs
    plot_2d_field("air_concentration")
    plot_2d_field("dry_deposition_rate")
    plot_2d_field("wet_deposition_rate")
    
    # Generate probability analysis
    plot_3d_exceedance_maps()
    plot_2d_exceedance("air_concentration_probability")
    plot_2d_exceedance("dry_deposition_probability")
    plot_2d_exceedance("wet_deposition_probability")
    
    status.object = "✅ All analyses completed successfully!"






@capture_terminal_output
def plot_z_level():
    try:
        run_name_paths = run_project_paths['run_name_path']
        out = os.path.join(MEDIA_DIR, "3D")
        for p in run_name_paths:
            animator = os.path.join(p, "3D")
            os.makedirs(out, exist_ok=True)
            Plot_3DField_Data(
                animator, out, cmap_select.value,
                threshold_slider_3d.value, zoom_slider.value,
                basemap_mode=basemap_select.value
            ).plot_single_z_level(
                z_km=Altitude_slider.value,
                filename=f"ash_altitude{Altitude_slider.value}level.gif"
            )
            update_media_tabs()
        status.object = "✅ Z-Level animation created."
    except Exception as e:
        logging.exception("Error in plot_z_level")
        status.object = f"❌ Error in Z-Level animation: {e}"


@capture_terminal_output
def plot_vertical_profile():
    try:
        run_name_paths = run_project_paths['run_name_path']
        out = os.path.join(MEDIA_DIR, "3D")
        for p in run_name_paths:
            animator = os.path.join(p, "3D")
            os.makedirs(out, exist_ok=True)
            plotter = Plot_3DField_Data(
                animator, out, cmap_select.value, fps_slider_3d.value,
                threshold_slider_3d.value, zoom_level=zoom_slider.value,
                basemap_mode=basemap_select.value
            )
            plotter.plot_vertical_profile_at_time(
                Altitude_slider.value - 1,
                filename=f"T{Altitude_slider.value}_profile.gif"
            )
            update_media_tabs()
        status.object = "✅ Vertical profile animation created."
    except Exception as e:
        logging.exception("Error in plot_vertical_profile")
        status.object = f"❌ Error in vertical profile animation: {e}"

@capture_terminal_output
def animate_all_altitude_profiles():
    try:
        run_name_paths = run_project_paths['run_name_path']
        out = os.path.join(MEDIA_DIR, "3D")
        for p in run_name_paths:
            animator = os.path.join(p, "3D")
            os.makedirs(out, exist_ok=True)
            Plot_3DField_Data(
                animator, out, cmap_select.value,
                threshold_slider_3d.value, zoom_slider.value,
                basemap_mode=basemap_select.value
            ).animate_all_altitude_profiles()
            update_media_tabs()
        status.object = "✅ All altitude profile animations created."
    except Exception as e:
        logging.exception("Error in animate_all_altitude_profiles")
        status.object = f"❌ Error animating all altitude profiles: {e}"


@capture_terminal_output
def plot_2d_field(field):
    try:
        run_name_paths = run_project_paths['run_name_path']
        out = os.path.join(MEDIA_DIR, "2D")
        for p in run_name_paths:
            pf = os.path.join(p, "horizontal")
            os.makedirs(out, exist_ok=True)
            result = Plot_Horizontal_Data(
                pf, out, cmap_select.value, fps_slider_2d.value,
                include_metadata=True, threshold=threshold_slider_2d.value,
                zoom_width_deg=6.0, zoom_height_deg=6.0,
                zoom_level=zoom_slider.value,
                static_frame_export=True, basemap_mode=basemap_select.value
            ).plot_single_field_over_time(field, f"{field}.gif")
            status.object = result
            update_media_tabs()
        status.object = f"✅ 2D field `{field}` animation created."
    except Exception as e:
        logging.exception(f"Error in plot_2d_field: {field}")
        status.object = f"❌ Error in 2D field `{field}` animation: {e}"


@capture_terminal_output
def plot_3d_exceedance_maps():
    try:
        # out = os.path.join(MEDIA_DIR, "Probability_3D")
        # os.makedirs(out, exist_ok=True)
        
        threshold_val = exceedance_threshold_3d.value
        threshold_folder = f"Threshold_{threshold_val:.5f}".rstrip("0").rstrip(".")  # avoid trailing zeroes
        out = os.path.join(MEDIA_DIR, "Probability_3D", threshold_folder)
        os.makedirs(out, exist_ok=True)

        processor = ProbabilityProcessor(
            input_dir="ash_output",
            output_dir=out,
            time_limit=None,
            basemap_mode=basemap_select.value,
            basemap_zoom_level=zoom_slider.value
        )
        processor.load_simulation_files()

        processor.compute_probability("3D", "ash_concentration", "ash_concentration_probability", threshold=exceedance_threshold_3d.value)

        processor.generate_probability_gifs_for_all_levels(
            variable_name="ash_concentration_probability",
            threshold=exceedance_threshold_3d.value,
            log_scale=False,
            save_gif=True,
            output_dir=None,
            fps=2,
            plot_style='pcolormesh',
            cmap=cmap_select.value
        )

        update_media_tabs()
        status.object = "✅ 3D probability maps created."
    except Exception as e:
        logging.exception("Error in plot_3d_exceedance_maps")
        status.object = f"❌ 3D map error: {e}"

@capture_terminal_output
def plot_2d_exceedance(var):
    try:
        # out = os.path.join(MEDIA_DIR, "Probability_2D")
        # os.makedirs(out, exist_ok=True)
        
        threshold_val = exceedance_threshold_2d.value
        threshold_folder = f"Threshold_{threshold_val:.5f}".rstrip("0").rstrip(".")  # avoid trailing zeroes
        out = os.path.join(MEDIA_DIR, "Probability_2D", threshold_folder)
        os.makedirs(out, exist_ok=True)

        processor = ProbabilityProcessor(
            input_dir="ash_output",
            output_dir=out,
            time_limit=None,
            basemap_mode=basemap_select.value,
            basemap_zoom_level=zoom_slider.value
        )
        processor.load_simulation_files()

        mapping = {
            "air_concentration_probability": "air_concentration",
            "dry_deposition_probability": "dry_deposition_rate",
            "wet_deposition_probability": "wet_deposition_rate",
            "ash_concentration_probability": "ash_concentration",
        }
        init_var = mapping.get(var)
        if init_var is None:
            raise ValueError(f"Unknown variable: {var}")

        processor.compute_probability("Horizontal", init_var, var, threshold=exceedance_threshold_2d.value)

        processor.plot_probability_animation(
            variable_name=var,
            level_index=None,
            threshold=exceedance_threshold_2d.value,
            log_scale=False,
            save_gif=True,
            gif_path=None,
            fps=2,
            plot_style='pcolormesh',
            cmap=cmap_select.value
        )

        update_media_tabs()
        status.object = f"✅ 2D Probability Map for `{var}` created."
    except Exception as e:
        logging.exception(f"Error in 2D Probability Map: {var}")
        status.object = f"❌ 2D {var} error: {e}"

live_log_output = pn.pane.Markdown("📜 Log output will appear here...", height=250, sizing_mode="stretch_width")

def update_live_log():
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r") as f:
                lines = f.readlines()
            log_text = ''.join(lines[-40:]) or "📭 No logs yet."
            live_log_output.object = f"```\n{log_text}\n```"
        else:
            live_log_output.object = "⚠️ Log file not found."
    except Exception as e:
        live_log_output.object = f"❌ Failed to read log: {e}"

pn.state.add_periodic_callback(update_live_log, period=3000)

terminal_output_controls = pn.Row(clear_output_button)

def create_terminal_output_section():
    return [
        pn.Card(
            pn.Card(status, title="📢 Status", collapsible=False),
            terminal_output_controls,
            terminal_output,
            title="📟 Terminal Output",
            collapsible=True
        )
    ]




tab3d = pn.Column(
    threshold_slider_3d_combined, fps_slider_3d, Altitude_slider,
    pn.widgets.Button(name="🎞 Generate Ash concentration for user defined fixed z index through time", button_type="primary", on_click=lambda e: plot_z_level()),
    pn.widgets.Button(name="📈 Generate Ash concentration for all existing altitudes with fixed z index through time", button_type="primary", on_click=lambda e: plot_vertical_profile()),
    pn.widgets.Button(name="📊 Generate Ash concentration for all existing time indexs with fixed time index through altitude levels", button_type="primary", on_click=lambda e: animate_all_altitude_profiles())
)
tab3d.extend(create_terminal_output_section())

tab2d = pn.Column(
    threshold_slider_2d_combined, fps_slider_2d,
    pn.widgets.Button(name="🌫 Animate Air Concentration Rate", button_type="primary", on_click=lambda e: plot_2d_field("air_concentration")),
    pn.widgets.Button(name="🌧 Animate Dry Deposition Rate", button_type="primary", on_click=lambda e: plot_2d_field("dry_deposition_rate")),
    pn.widgets.Button(name="💧 Animate Wet Deposition Rate", button_type="primary", on_click=lambda e: plot_2d_field("wet_deposition_rate"))
)
tab2d.extend(create_terminal_output_section())

tab_exceedance = pn.Column(
    pn.pane.Markdown("## 📊 Probability Analysis"),
    pn.Card(pn.Column(exceedance_threshold_3d_combined,
        pn.widgets.Button(name="📍 3D Probability Animation", button_type="primary", on_click=lambda e: plot_3d_exceedance_maps())
    ), title="3D Probability"),

    pn.Spacer(height=5),

    pn.Card(pn.Column(exceedance_threshold_2d_combined,
        pn.widgets.Button(name="🌫 2D Air Concentration Rate Probability", button_type="primary", on_click=lambda e: plot_2d_exceedance("air_concentration_probability")),
        pn.widgets.Button(name="🌧 2D Dry Deposition Rate Probability", button_type="primary", on_click=lambda e: plot_2d_exceedance("dry_deposition_probability")),
        pn.widgets.Button(name="💧 2D Wet Deposition Rate Probability", button_type="primary", on_click=lambda e: plot_2d_exceedance("wet_deposition_probability")),
    ), title="2D Probability")
)
tab_exceedance.extend(create_terminal_output_section())




info_3d_card = pn.Card(
    pn.pane.Markdown("""\
## 🌋 3D Volcanic Ash Visualization

Visualize ash concentration at various altitudes using 3D model outputs.

### 🎞 What You Can Do:
- Generate animations for specific altitude levels
- Create vertical ash profiles over time
- Animate across all z-levels

### ⚙️ Key Controls:
- altitude layer in the model grid (Define Ash Altitude Level)
- Threshold filter to suppress low ash
- FPS, Colormap, Basemap settings

### 📁 Output:
- `.gif` animations saved in `media/3D/Threshold_x/`
"""),
    title="🧭 3D Field Help", sizing_mode="stretch_width"
)

info_2d_card = pn.Card(
    pn.pane.Markdown("""\
## 🌍 2D Horizontal Field Animation

Explore ground-level and surface ash behavior using horizontal model fields.

### 💨 Animations:
- Air Concentration 
- Dry/Wet Deposition rate

### ⚙️ Controls:
- 2D threshold slider
- FPS and zoom level
- Basemap options

### 📁 Output:
- Results saved in `media/2D`
"""),
    title="🧭 2D Field Help", sizing_mode="stretch_width"
)

info_prob_card = pn.Card(
    pn.pane.Markdown("""\
## 📘 Probability Processor Guide

The `ProbabilityProcessor` builds probabilistic maps from ensemble simulations.

### 🧠 How It Works:
- Computes probability that a variable (e.g., ash) ≥ threshold
- Applies binary masks across simulations
- Normalizes results into a probability field

### 🧪 Example:
If 7 of 10 simulations exceed `0.02 g/m³`, probability = `0.7`.

### 📁 Output:
- Saved as NetCDF + GIFs under `media/Probability_2D/` and `media/Probability_3D/`
"""),
    title="🧭 Probability Help", sizing_mode="stretch_width"
)

info_media_card = pn.Card(
    pn.pane.Markdown("""\
## 🖼 Media Viewer Guide

Browse and preview output files by folder and threshold.

### 📂 Features:
- Expand folders (e.g., 3D, 2D, Probability)
- Search, preview, and download

### 🔍 Tips:
- Use filters for fast lookup
- Click 🔄 “Load Files” to refresh listings
"""),
    title="🧭 Media Viewer Help", sizing_mode="stretch_width"
)

info_sidebar = pn.Column(
    info_3d_card,
    info_2d_card,
    info_prob_card,
    info_media_card,
    #sizing_mode="fixed",
    width=200, 
    scroll=True
)



def human_readable_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024: return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"

def generate_output_gallery(*base_folders):
    """
    Creates a professional, responsive output gallery with:
    - Nested Accordions for all subfolders
    - Search/filter
    - Pagination for large folders
    - Manual load button
    """
    preview_container = pn.Column(
        pn.pane.Markdown("""
### 🖼️ Output Gallery
- 🔄 Use "Load Files" to display file list
- 🔍 Use search box to filter files
- 👁 Click a file to preview
"""),
        sizing_mode="stretch_width",
        height=550,
    )

    def make_preview(file_path):
        ext = os.path.splitext(file_path)[1].lower()
        title = pn.pane.Markdown(f"### {os.path.basename(file_path)}")
        download_button = pn.widgets.FileDownload(
            file=file_path,
            filename=os.path.basename(file_path),
            label="⬇ Download",
            button_type="success",
            width=150,
        )
        if ext in [".gif", ".png", ".jpg", ".jpeg"]:
            content = pn.pane.Image(
                file_path,
                sizing_mode="stretch_width",
                height=450,
                link_url=file_path,
                embed=False,
            )
        else:
            try:
                with open(file_path, 'r', errors="ignore") as f:
                    text = f.read(2048)
                content = pn.pane.PreText(text, sizing_mode="stretch_width", height=450)
            except Exception:
                content = pn.pane.Markdown("*Unable to preview this file.*")

        return pn.Column(title, content, download_button, sizing_mode="stretch_width")

    top_level_accordions = []

    def create_folder_accordion(folder_path, relative_path=""):
        folder_items = []
        entries = sorted(os.listdir(folder_path))
        dirs = [e for e in entries if os.path.isdir(os.path.join(folder_path, e))]
        files = [e for e in entries if os.path.isfile(os.path.join(folder_path, e))]

        search_box = pn.widgets.TextInput(
            placeholder="🔍 Filter files...",
            width=250,
            name=""
        )
        page_slider = pn.widgets.IntSlider(
            name="Page",
            start=1,
            end=2,
            value=1,
            width=200
        )
        thumbnails_container = pn.Column()

        # Load button
        load_button = pn.widgets.Button(
            name="🔄 Load Files",
            button_type="success",
            width=120
        )

        def update_thumbnails(event=None):
            thumbs = []
            filtered_files = [f for f in files if search_box.value.lower() in f.lower()]

            if not filtered_files:
                thumbnails_container[:] = [pn.pane.Markdown("*No matching files.*")]
                return

            page_size = 50
            total_pages = max(1, (len(filtered_files) - 1) // page_size + 1)
            page_slider.start = 1
            page_slider.end = total_pages
            page_slider.value = min(page_slider.value, total_pages)

            start = (page_slider.value - 1) * page_size
            end = start + page_size
            current_files = filtered_files[start:end]

            for fname in current_files:
                full_path = os.path.join(folder_path, fname)
                size = os.path.getsize(full_path)

                row = pn.Row(
                    pn.pane.Markdown(
                        f"**{fname}** (*{human_readable_size(size)}*)",
                        width=300
                    ),
                    pn.widgets.Button(
                        name="👁 Preview",
                        button_type="primary",
                        width=90
                    ),
                    sizing_mode="stretch_width"
                )
                # Preview handler
                row[1].on_click(lambda e, path=full_path: preview_container.__setitem__(slice(None), [make_preview(path)]))
                thumbs.append(row)

            thumbnails_container[:] = [pn.Column(*thumbs, sizing_mode="stretch_width")]

        # Wire up handlers
        load_button.on_click(update_thumbnails)
        search_box.param.watch(update_thumbnails, "value")
        page_slider.param.watch(update_thumbnails, "value")

        if files:
            file_card = pn.Card(
                pn.Column(
                    pn.Row(search_box, load_button, sizing_mode="stretch_width"),
                    page_slider,
                    thumbnails_container,
                    sizing_mode="stretch_width"
                ),
                title=f"📁 Files in `{os.path.basename(relative_path) or os.path.basename(folder_path)}`",
                collapsible=True,
                collapsed=True,
                sizing_mode="stretch_width"
            )
            folder_items.append(file_card)

        for d in dirs:
            folder_items.append(create_folder_accordion(os.path.join(folder_path, d), os.path.join(relative_path, d)))

        return pn.Accordion(
            (
                f"📂 {os.path.basename(relative_path) or os.path.basename(folder_path)}",
                pn.Column(*folder_items, sizing_mode="stretch_width")
            ),
            sizing_mode="stretch_width"
        )

    # Top-level folders
    for base_folder in base_folders:
        full_base_path = os.path.join(MEDIA_DIR, base_folder)
        if os.path.isdir(full_base_path):
            acc = create_folder_accordion(full_base_path)
            top_level_accordions.append(acc)

    folders_column = pn.Column(
        *top_level_accordions,
        scroll=True,
        height=600,
        sizing_mode="stretch_width"
    )

    expand_button = pn.widgets.Button(
        name="🔼 Expand All",
        button_type="primary",
        width=120
    )
    collapse_button = pn.widgets.Button(
        name="🔽 Collapse All",
        button_type="primary",
        width=120
    )
    expand_button.on_click(lambda e: [setattr(acc, "active", list(range(len(acc.objects)))) for acc in top_level_accordions])
    collapse_button.on_click(lambda e: [setattr(acc, "active", []) for acc in top_level_accordions])

    return pn.Column(
        pn.Row(expand_button, collapse_button, sizing_mode="stretch_width"),
        pn.Row(preview_container, pn.Spacer(width=20), folders_column, sizing_mode="stretch_width"),
        sizing_mode="stretch_width"
    )


media_tab_2d = pn.Column(generate_output_gallery("2D"))
media_tab_3d = pn.Column(generate_output_gallery("3D"))
media_tab_statistical_3d = pn.Column(generate_output_gallery("Probability_3D"))
media_tab_statistical_2d = pn.Column(generate_output_gallery("Probability_2D"))

media_tab = pn.Tabs(
    ("2D Outputs", media_tab_2d),
    ("3D Outputs", media_tab_3d),
    ("📈 Statistical Plots 3D", media_tab_statistical_3d),
    ("📈 Statistical Plots 2D", media_tab_statistical_2d),
    sizing_mode='stretch_width'
)

def update_media_tabs():
    media_tab_2d.objects[:] = [generate_output_gallery("2D")]
    media_tab_3d.objects[:] = [generate_output_gallery("3D")]
   
    
    media_tab_statistical_3d[:] = [generate_output_gallery("Probability_3D")]
    media_tab_statistical_2d[:] = [generate_output_gallery("Probability_2D")]
    




help_tab = pn.Column(
    pn.pane.Markdown(
        object=open("DASHBOARD_README.md", encoding="utf-8").read()
        if os.path.exists("DASHBOARD_README.md") else "ℹ️ Help file not found."
    )
)

tabs = pn.Tabs(
    ("🧱 3D Field", tab3d),
    ("🌍 2D Field", tab2d),
    ("📊 Probability Maps", tab_exceedance),
    ("📁 Media Viewer", media_tab),
    ("❓ Help", help_tab)
)

sidebar = pn.Column(
    pn.pane.Markdown("## 🌋 NAME Ash Visualizer"),

    pn.Card(pn.Column(file_input, file_dropper, process_button, reset_button, run_all_button),
            title="📂 File Upload & Processing", collapsible=True),

    pn.Card(pn.Column(cmap_select, basemap_select, zoom_slider),
            title="🎨 Map & Visualization Settings", collapsible=True),

    pn.Card(pn.Column(nc_file_selector_3d),
            title="📁 Select Simulation", collapsible=True),

    pn.Card(pn.Column(download_button, log_link),
            title="📁 Downloads & Logs", collapsible=True),

    pn.pane.Markdown("© 2025 Dr. Mahmud Muhammad • [Email:](mailto:mahmud.muhammad@hotmail.com)")
)


restore_previous_session()
process_button.on_click(process_zip)
reset_button.on_click(reset_app)
run_all_button.on_click(lambda e: run_all_analysis())

# pn.template.BootstrapTemplate(
#     title="🌋 Volcanic Ash Dispersion Analysis & Visualization Software",
#     sidebar=sidebar,
#     main=[tabs],
#     collapsed_sidebar=False
# ).servable()

pn.template.BootstrapTemplate(
    title="🌋 Volcanic Ash Dispersion Analysis & Visualization Software",
    sidebar=sidebar,
    main=[
        pn.Row(
            tabs,
            pn.Spacer(width=10),
            info_sidebar
        )
    ],
    collapsed_sidebar=False
).servable()


