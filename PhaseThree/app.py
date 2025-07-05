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


import contextlib
import sys
import matplotlib.pyplot as plt
import tempfile

# === Controls ===

auto_scroll_toggle = pn.widgets.Toggle(
    name="🔃 Auto-Scroll",
    value=True,
    button_type="success",
    sizing_mode="stretch_width",  # remove width
)


clear_output_button = pn.widgets.Button(
    name="🧹 Clear Output",
    button_type="danger",
    width=150
)

# === Output Area ===

terminal_output = pn.pane.HTML(
    "<pre id='log-content' class='debugger-pane'></pre>",
    #height=300,
    sizing_mode="stretch_width"
)



class LiveOutput(io.StringIO):
    def __init__(self, pane, max_length=10000):
        super().__init__()
        self.pane = pane
        self._buffer = ""
        self.max_length = max_length

    def write(self, msg):
        self._buffer += msg
        if len(self._buffer) > self.max_length:
            self._buffer = "...\n" + self._buffer[-self.max_length:]

        # Escape HTML
        safe_html = (
            self._buffer.replace("&", "&amp;")
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
        )

        # Always scroll to the bottom
        scroll_script = (
            "<script>var e = document.getElementById('log-content');"
            "if(e) e.scrollTop = e.scrollHeight;</script>"
        )

        self.pane.object = (
            f"<pre id='log-content' class='debugger-pane'>{safe_html}</pre>{scroll_script}"
        )

        return len(msg)

    def flush(self):
        pass
    
   


# === Clear Output Logic ===

def clear_terminal_output(event=None):
    terminal_output.object = (
        "<pre id='log-content' class='debugger-pane'></pre>"
    )
    output_buffer.truncate(0)
    output_buffer.seek(0)

clear_output_button.on_click(clear_terminal_output)

# === Capture Function Decorator ===

def capture_terminal_output(func):
    def wrapper(*args, **kwargs):
        live_output = LiveOutput(terminal_output)
        with contextlib.redirect_stdout(live_output), contextlib.redirect_stderr(live_output):
            try:
                func(*args, **kwargs)
            except Exception as e:
                print(f"❌ Exception: {e}")
    return wrapper

# === Control Panel Card ===

terminal_output_controls = pn.Row(
    
    clear_output_button,
    sizing_mode="stretch_width"
)

pn.extension('filedropper', raw_css=[  # Windows 11-style debugger terminal
    """
    .debugger-pane pre {
        background-color: #1f1f1f;
        color: #dcdcdc;
        font-family: 'Segoe UI Mono', Consolas, monospace;
        padding: 16px;
        border-radius: 12px;
        overflow-y: auto;
        max-height: 300px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
        margin: 0;
        white-space: pre-wrap;
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
    """
])


#############



#############3

# Terminal output buffer and panel display pane
output_buffer = io.StringIO()

# terminal_output = pn.pane.Str(
#     "Terminal output will appear here...",
#     height=300,
    
#     sizing_mode="stretch_both", scroll=True
# )

terminal_output = pn.pane.HTML(
    "<pre id='log-content' style='margin:0; font-family:monospace; white-space:pre-wrap;'>"
     "Live terminal output will appear here..."
     "</pre>",  # Start with empty content
    #height=300,

    sizing_mode="stretch_width",

    css_classes=["debugger-pane"]
)



MEDIA_DIR = os.path.abspath(os.path.join(".", "media"))
os.makedirs(MEDIA_DIR, exist_ok=True)

# Logging setup
LOG_FILE = os.path.join(MEDIA_DIR, "app_errors.log")
logging.basicConfig(filename=LOG_FILE, level=logging.ERROR,
                    format="%(asctime)s - %(levelname)s - %(message)s")

animator_obj = {}

# ---------------- Widgets ----------------
# Widgets
file_input = pn.widgets.FileInput(accept=".zip")


##################################################################
# Drop Zone for large zip files
file_dropper = pn.widgets.FileDropper(
    name="📂 Drag & Drop ZIP file here",
    multiple=True,
    #sizing_mode="stretch_both"
)

# Event listener to save file
def on_file_drop(event):
    file_data = event.new  # this is a dict: {filename: bytes}
    if file_data:
        for filename, file_bytes in file_data.items():  # iterate through any dropped file
            zip_path = os.path.join(MEDIA_DIR, filename)
            
            # Save the file
            with open(zip_path, "wb") as f:
                f.write(file_bytes)

            # Sync file_input
            file_input.filename = filename
            file_input.value = file_bytes

            # Print the file path
            print(f"✅ Uploaded file saved to: {zip_path}")

            # Also show in status
            status.object = f"📂 Uploaded file saved to: {zip_path}"


file_dropper.param.watch(on_file_drop, 'value')




# Sync file selector to file_input
last_selected_zip_path = None




########################################################


##################3
process_button = pn.widgets.Button(name="📦 Process ZIP", button_type="primary", )
                                   #sizing_mode="stretch_both")
reset_button = pn.widgets.Button(name="🔄 Reset App", button_type="danger", )
                                 #sizing_mode="stretch_both")

status = pn.pane.Markdown("""
### 📌 Getting Started with NAME Model Output Simulation Visualization

#### ✅ Instructions:

- 🗂️ **Step 1 (Optional)**: Upload your own NAME Model Simulation output in `.ZIP` format  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;If no file is uploaded, default data from **Taal Volcano** will be used.

- ▶️ **Step 2 (Required)**: Click **`Process Zip`**  
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;This will process either your uploaded file or the default dataset.

- 📥 **Step 3 (Optional)**: Click **`Download Plots and Data`** to export a sample `.ZIP` structure and results from the **Taal Volcano** simulation.

---
""")





############




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

threshold_slider_3d = pn.widgets.FloatSlider(name='3D Threshold  (g/m³)', start=0.0, end=1.0, step=0.05, value=0.1, format='0.0000')
fps_slider_3d = pn.widgets.IntSlider(name='3D FPS (frame/second)', start=1, end=10, value=2)
Altitude_slider = pn.widgets.IntSlider(name='Define Ash Altitude (km)', start=0, end=15, value=4)

threshold_slider_2d = pn.widgets.FloatSlider(name='2D Threshold (g/m³) or g / (m²·s) for deposition rates', start=0.0, end=1.0, step=0.01, value=0.005, format='0.0000')
fps_slider_2d = pn.widgets.IntSlider(name='2D FPS', start=1, end=10, value=2)

all_cmaps = plt.colormaps()
# Exceedance controls
exceedance_threshold_3d = pn.widgets.FloatSlider(name='3D Exceedance Threshold (g/m³)', start=0, end=1, step=0.00001, value=0.008, format='0.0000')
#exceedance_cmap_3d = pn.widgets.Select(name='3D Exceedance Colormap', options=sorted(all_cmaps), value='viridis')

exceedance_threshold_2d = pn.widgets.FloatSlider(name='2D Exceedance Threshold (g/m³)', start=0, end=1, step=0.00001, value=0.001, format='0.0000')
#exceedance_cmap_2d = pn.widgets.Select(name='2D Exceedance Colormap', options=["viridis", "plasma", "rainbow"])




# Create the Select widget with all colormaps
cmap_select = pn.widgets.Select(name='Colormap', options=sorted(all_cmaps), value='turbo')
#cmap_select = pn.widgets.Select(name='Colormap', options=["rainbow", "viridis", "plasma"])
basemap_select = pn.widgets.Select(name='Basemap Mode', options=["default","basemap", "stock", "contextily"])
zoom_slider = pn.widgets.IntSlider(name='Basemap Zoom Level', start=1, end=30, value=10)

run_all_button = pn.widgets.Button(
    name="🚀 Run ALL Analysis",
    button_type="primary",
    width=200
)

    
run_all_button.on_click(lambda e: run_all_analysis())



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
    export_jpg_frames()
    
    # Generate 2D outputs
    plot_2d_field("air_concentration")
    plot_2d_field("dry_deposition_rate")
    plot_2d_field("wet_deposition_rate")
    
    # Generate exceedance analysis
    plot_3d_exceedance_maps()
    plot_3d_avg_exceedance()
    plot_3d_all_levels()
    plot_2d_exceedance("air_concentration")
    plot_2d_exceedance("dry_deposition_rate")
    plot_2d_exceedance("wet_deposition_rate")
    
    status.object = "✅ All analyses completed successfully!"





# ---------------- Core Functions ----------------

@capture_terminal_output
def process_zip(event=None):
    global last_selected_zip_path
    zip_path = None

    # 🟢 1) Prioritize file_input
    if file_input.value and file_input.filename:
        zip_path = os.path.join(MEDIA_DIR, file_input.filename)
        with open(zip_path, "wb") as f:
            f.write(file_input.value)
        status.object = f"✅ Processing file_input: {zip_path}"
        print(f"✅ file_input path: {zip_path}")

    # 🟢 2) Fallback to file_dropper
    elif file_dropper.value:
        file_data = file_dropper.value
        for filename, file_bytes in file_data.items():
            zip_path = os.path.join(MEDIA_DIR, filename)
            with open(zip_path, "wb") as f:
                f.write(file_bytes)
            status.object = f"✅ Processing file_dropper file: {zip_path}"
            print(f"✅ file_dropper path: {zip_path}")
            break

 
    # 🟢 4) Fallback to default_model.zip
    else:
        zip_path = os.path.join(MEDIA_DIR, "default_model.zip")
        if not os.path.exists(zip_path):
            zip_path = "default_model.zip"
        status.object = f"ℹ️ Using default_model.zip"
        print(f"ℹ️ default_model path: {zip_path}")

    # ==================== Process the zip file ====================

    try:
        output_dir = os.path.join(".", "ash_output")

        # 🧹 Clear existing data
        animator_obj.clear()
        import gc; gc.collect()
        shutil.rmtree(output_dir, ignore_errors=True)
        os.makedirs(output_dir, exist_ok=True)

    except PermissionError:
        output_dir = os.path.join(tempfile.gettempdir(), "name_output")
        os.makedirs(output_dir, exist_ok=True)

    # 🎛️ Run your existing processing
    try:
        processor = NAMEDataProcessor()
        processor.batch_process_zip(zip_path, output_root=output_dir, cleanup=True)

        # 🧠 Load into animator_obj
        animator_obj["3d"] = []
        for fp in sorted(glob.glob(os.path.join(output_dir, "3D", "*.nc"))):
            with xr.open_dataset(fp) as ds:
                animator_obj["3d"].append(ds.load())

        animator_obj["2d"] = []
        for fp in sorted(glob.glob(os.path.join(output_dir, "horizontal", "*.nc"))):
            with xr.open_dataset(fp) as ds:
                animator_obj["2d"].append(ds.load())

        # Save the zip path so we can restore next time
        with open(os.path.join(MEDIA_DIR, "last_run.txt"), "w") as f:
            f.write(zip_path)

        status.object += f" | ✅ Loaded {len(animator_obj['3d'])} 3D & {len(animator_obj['2d'])} 2D datasets."
        update_media_tabs()

    except Exception as e:
        logging.exception("Error during ZIP processing")
        status.object = f"❌ Processing failed: {e}"




import errno
import stat

def handle_remove_readonly(func, path, exc):
    excvalue = exc[1]
    if func in (os.rmdir, os.remove, os.unlink) and excvalue.errno == errno.EACCES:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    else:
        raise

def reset_app(event=None):
    # Clear animator
    animator_obj.clear()
    file_input.value = None

    # Close datasets (prevent locks)
    for k in list(animator_obj.keys()):
        datasets = animator_obj[k]
        if isinstance(datasets, list):
            for ds in datasets:
                try:
                    ds.close()
                except Exception:
                    pass

    # Remove known and unknown folders
    for entry in os.listdir(MEDIA_DIR):
        full_path = os.path.join(MEDIA_DIR, entry)
        try:
            if os.path.isdir(full_path):
                shutil.rmtree(full_path, ignore_errors=False, onerror=handle_remove_readonly)
            else:
                os.remove(full_path)
        except Exception as e:
            print(f"⚠️ Could not delete {full_path}: {e}")

    # Remove any empty directories
    for root, dirs, _ in os.walk(MEDIA_DIR, topdown=False):
        for d in dirs:
            dir_path = os.path.join(root, d)
            try:
                os.rmdir(dir_path)
            except OSError as e:
                print(f"⚠️ Could not remove empty folder {dir_path}: {e}")

    # Remove last_run.txt
    last_run = os.path.join(MEDIA_DIR, "last_run.txt")
    if os.path.exists(last_run):
        try:
            os.remove(last_run)
        except Exception as e:
            print(f"⚠️ Could not remove last_run.txt: {e}")

    # Reset file dropper
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




@capture_terminal_output
def restore_previous_session():
    update_media_tabs()
    
    try:
        state_file = os.path.join(MEDIA_DIR, "last_run.txt")
        if os.path.exists(state_file):
            with open(state_file) as f:
                zip_path = f.read().strip()
            if os.path.exists(zip_path):
                try:
                    output_dir = os.path.join("./", "ash_output")
                    os.makedirs(output_dir, exist_ok=True)
                except PermissionError:
                    output_dir = os.path.join(tempfile.gettempdir(), "name_output")
                    os.makedirs(output_dir, exist_ok=True)

                animator_obj["3d"] = []
                for fp in sorted(glob.glob(os.path.join(output_dir, "3D", "*.nc"))):
                    with xr.open_dataset(fp) as ds:
                        animator_obj["3d"].append(ds.load())

                animator_obj["2d"] = []
                for fp in sorted(glob.glob(os.path.join(output_dir, "horizontal", "*.nc"))):
                    with xr.open_dataset(fp) as ds:
                        animator_obj["2d"].append(ds.load())

                status.object = f"🔁 Restored previous session from {os.path.basename(zip_path)}"
                
    except Exception as e:
        logging.exception("Error restoring previous session")
        status.object = f"⚠️ Could not restore previous session: {e}"



# ---------------- Animator Builders ----------------
def create_grid(attrs: dict):
    x_origin = float(attrs.get("x_origin"))
    y_origin = float(attrs.get("y_origin"))
    x_res = float(attrs.get("x_res"))
    y_res = float(attrs.get("y_res"))
    x_grid_size = int(attrs.get("x_grid_size"))
    y_grid_size = int(attrs.get("y_grid_size"))
    lons = np.round(
        np.linspace(x_origin, x_origin + (x_grid_size - 1) * x_res, x_grid_size), 6
    )
    lats = np.round(
        np.linspace(y_origin, y_origin + (y_grid_size - 1) * y_res, y_grid_size), 6
    )
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    
    return lon_grid, lat_grid, (lon_grid, lat_grid)

def build_animator_3d():
    ds = animator_obj["3d"]
    #attrs = ds[0].attrs
    
    #lons, lats, grid = create_grid(attrs)
    lat_grid, lon_grid = xr.broadcast(ds[0]["latitude"], ds[0]["longitude"])
    return SimpleNamespace(
        datasets=ds,
        levels=ds[0].altitude.values,
        lats=ds[0]["latitude"].values,
        lons=ds[0]["longitude"].values,
        lat_grid=lat_grid.values,
        lon_grid=lon_grid.values,
        
        # lons=lons,
        # lats=lats,
        # lon_grid=grid[0],
        # lat_grid=grid[1],
    )


def build_animator_2d():
    ds = animator_obj["2d"]
    lat_grid, lon_grid = xr.broadcast(ds[0]["latitude"], ds[0]["longitude"])
    return SimpleNamespace(
        datasets=ds,
        lats=ds[0]["latitude"].values,
        lons=ds[0]["longitude"].values,
        lat_grid=lat_grid.values,
        lon_grid=lon_grid.values,
    )

# ---------------- Plot Functions ----------------

@capture_terminal_output
def plot_z_level():
    try:
        animator = build_animator_3d()
        out = os.path.join(MEDIA_DIR, "3D")
        os.makedirs(out, exist_ok=True)
        Plot_3DField_Data(animator, out, cmap_select.value,
                          threshold_slider_3d.value, zoom_slider.value,
                          fps_slider_3d.value, basemap_mode=basemap_select.value).plot_single_z_level(
                              z_km=Altitude_slider.value, filename= f"ash_altitude{Altitude_slider.value}km_runTimes.gif")
        update_media_tabs()
        status.object = "✅ Z-Level animation created."
    except Exception as e:
        logging.exception("Error in plot_z_level")
        status.object = f"❌ Error in Z-Level animation: {e}"
        
@capture_terminal_output
def plot_vertical_profile():
    try:
        animator = build_animator_3d()
        out = os.path.join(MEDIA_DIR, "3D")
        os.makedirs(out, exist_ok=True)
        plotter = Plot_3DField_Data(animator, out, cmap_select.value, fps_slider_3d.value,
                                    threshold_slider_3d.value, zoom_level=zoom_slider.value,
                                     basemap_mode=basemap_select.value)
        plotter.plot_vertical_profile_at_time(Altitude_slider.value - 1,
                                              filename=f"T{Altitude_slider.value}_profile.gif")
        update_media_tabs()
        
        status.object = "✅ Vertical profile animation created."
    except Exception as e:
        logging.exception("Error in plot_vertical_profile")
        status.object = f"❌ Error in vertical profile animation: {e}"
        
@capture_terminal_output
def animate_all_altitude_profiles():
    try:
        
        animator = build_animator_3d()
        
        out = os.path.join(MEDIA_DIR, "3D")
        
        os.makedirs(out, exist_ok=True)
        
        Plot_3DField_Data(animator, out, cmap_select.value,
                          threshold_slider_3d.value, zoom_slider.value, basemap_mode=basemap_select.value).animate_all_altitude_profiles()
        
        update_media_tabs()
       
        status.object = "✅ All altitude profile animations created."
    except Exception as e:
        logging.exception("Error in animate_all_altitude_profiles")
        status.object = f"❌ Error animating all altitude profiles: {e}"

@capture_terminal_output
def export_jpg_frames():
    try:
         
        animator = build_animator_3d()
        out = os.path.join(MEDIA_DIR, "3D")
        os.makedirs(out, exist_ok=True)
        Plot_3DField_Data(animator, out, cmap_select.value,
                          threshold_slider_3d.value, zoom_slider.value, basemap_mode=basemap_select.value).export_frames_as_jpgs(include_metadata=True)
        update_media_tabs()
         
        status.object = "✅ JPG frames exported."
    except Exception as e:
        logging.exception("Error exporting JPG frames")
        status.object = f"❌ Error exporting JPG frames: {e}"
        
@capture_terminal_output
def plot_2d_field(field):
    try:
         
        animator = build_animator_2d()
        out = os.path.join(MEDIA_DIR, "2D")
        os.makedirs(out, exist_ok=True)
        
        status.object= Plot_Horizontal_Data(animator, out, cmap_select.value, fps_slider_2d.value,
                             include_metadata=True, threshold=threshold_slider_2d.value,
                             zoom_width_deg=6.0, zoom_height_deg=6.0,
                             zoom_level=zoom_slider.value,
                             static_frame_export=True, basemap_mode=basemap_select.value).plot_single_field_over_time(field, f"{field}.gif")
        update_media_tabs()
         
        status.object = f"✅ 2D field `{field}` animation created."
    except Exception as e:
        logging.exception(f"Error in plot_2d_field: {field}")
        status.object = f"❌ Error in 2D field `{field}` animation: {e}"


################

# # Live log viewer
live_log_output = pn.pane.Markdown("📜 Log output will appear here...", height=250, sizing_mode="stretch_width")#height=250,
                                   #sizing_mode="stretch_both")


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



#####################

# ========== Exceedance Plotting Functions ==========
@capture_terminal_output
def plot_3d_exceedance_maps():
    try:
        analyzer = AshExceedanceAnalyzer_3D("./ash_output/3D", threshold=exceedance_threshold_3d.value, cmap=cmap_select.value, 
                                            basemap_mode=basemap_select.value, zoom_level=zoom_slider.value)
        analyzer.prepare_data()
        analyzer.compute_bayesian_exceedance()
        out = os.path.join(MEDIA_DIR, "Exceedance_3D")
        os.makedirs(out, exist_ok=True)
        analyzer.plot_exceedance_maps(save_dir=out, contour_levels=10)
        update_media_tabs()
        status.object = "✅ 3D exceedance maps created."
    except Exception as e:
        logging.exception("Error in plot_3d_exceedance_maps")
        status.object = f"❌ 3D map error: {e}"
        
@capture_terminal_output
def plot_3d_avg_exceedance():
    try:
        analyzer = AshExceedanceAnalyzer_3D("./ash_output/3D", threshold=exceedance_threshold_3d.value, cmap=cmap_select.value, 
                                            basemap_mode=basemap_select.value, zoom_level=zoom_slider.value)
        analyzer.prepare_data()
        analyzer.compute_bayesian_exceedance()
        analyzer.compute_summary_bayesian_exceedance()
        out = os.path.join(MEDIA_DIR, "Exceedance_3D")
        analyzer.plot_summary_bayesian_exceedance(contour_levels=10, save_dir=out)
        update_media_tabs()
        status.object = "✅ 3D summary exceedance plotted."
    except Exception as e:
        logging.exception("Error in plot_summary_bayesian_exceedance")
        status.object = f"❌ 3D summary error: {e}"

@capture_terminal_output
def plot_3d_all_levels():
    try:
        analyzer = AshExceedanceAnalyzer_3D("./ash_output/3D", threshold=exceedance_threshold_3d.value, cmap=cmap_select.value, 
                                            basemap_mode=basemap_select.value, zoom_level=zoom_slider.value)
        analyzer.prepare_data()
        analyzer.compute_bayesian_exceedance()
        out = os.path.join(MEDIA_DIR, "Exceedance_3D")
        analyzer.plot_all_levels_contour(save_dir=out, contour_levels=10)
        update_media_tabs()
        status.object = "✅ 3D all-level contour plots created."
    except Exception as e:
        logging.exception("Error in plot_3d_all_levels")
        status.object = f"❌ 3D levels error: {e}"

@capture_terminal_output
def plot_2d_exceedance(var):
    try:
        analyzer = MultiFieldExceedanceAnalyzer_2D("./ash_output/horizontal", threshold=exceedance_threshold_2d.value, cmap=cmap_select.value, 
                                                   basemap_mode=basemap_select.value, zoom_level=zoom_slider.value)
        analyzer.prepare_data()
        analyzer.compute_bayesian_exceedance(variable=var)
        
        out = os.path.join(MEDIA_DIR, "Exceedance_2D")
        os.makedirs(out, exist_ok=True)
        analyzer.plot_exceedance_map(var=var, save_dir=out, contour_levels=10)
        
        update_media_tabs()
        status.object = f"✅ 2D exceedance map for `{var}` created."
    except Exception as e:
        logging.exception(f"Error in plot_2d_exceedance: {var}")
        status.object = f"❌ 2D {var} error: {e}"

# ---------------- Layout ----------------

def human_readable_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024: return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"




import os

def list_subfolders(parent_dir):
    """
    Returns absolute paths of all subfolders inside parent_dir.
    """
    return [
        os.path.join(parent_dir, name)
        for name in os.listdir(parent_dir)
        if os.path.isdir(os.path.join(parent_dir, name))
    ]




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






media_tab_2d = pn.Column( generate_output_gallery("2D"))
media_tab_3d = pn.Column(generate_output_gallery("3D"))

media_tab_statistical_3d = pn.Column(generate_output_gallery("Exceedance_3D"), )

media_tab_statistical_2d = pn.Column( generate_output_gallery("Exceedance_2D"), )

media_tab = pn.Tabs(
    ("2D Outputs", media_tab_2d),
    ("3D Outputs", media_tab_3d),
    ("📈 Statistical Plots 3D Outputs", media_tab_statistical_3d), ("📈 Statistical Plots 2D Outputs", media_tab_statistical_2d),
sizing_mode='stretch_width') 


# ---------------- Gallery Update ----------------

def update_media_tabs():
    media_tab_2d.objects[:] = [generate_output_gallery("2D")]
    media_tab_3d.objects[:] = [generate_output_gallery("3D")]
   
    
    media_tab_statistical_3d[:] = [generate_output_gallery("Exceedance_3D")]
    media_tab_statistical_2d[:] = [generate_output_gallery("Exceedance_2D")]
    
   
    
# ---------------- Layout & Tabs ----------------

tab_exceedance = pn.Column(
    pn.pane.Markdown("## 📊 Bayesian Probability Analysis"),
    pn.Card(pn.Column(exceedance_threshold_3d,
        pn.widgets.Button(name="📍 3D Exceedance threshold Probability maps at each altitud seperate plots", button_type="primary", on_click=lambda e: plot_3d_exceedance_maps()),
        pn.widgets.Button(name="📉 3D Exceedance thresold summary(Mean,Max)probability maps for all altitudes", button_type="primary", on_click=lambda e: plot_3d_avg_exceedance()),
        pn.widgets.Button(name="📊 3D Exceedance threshold Probability maps at each altitud combined single plot", button_type="primary", on_click=lambda e: plot_3d_all_levels())
    ), title="3D Exceedance"),

    pn.Spacer(height=5),

    pn.Card(pn.Column(exceedance_threshold_2d,
        pn.widgets.Button(name="🌫 2D: Air Concentration", button_type="primary", on_click=lambda e: plot_2d_exceedance("air_concentration")),
        pn.widgets.Button(name="🌧 2D: Dry Deposition", button_type="primary", on_click=lambda e: plot_2d_exceedance("dry_deposition_rate")),
        pn.widgets.Button(name="💧 2D: Wet Deposition", button_type="primary", on_click=lambda e: plot_2d_exceedance("wet_deposition_rate")),
    ), title="2D Exceedance")
)



tab3d = pn.Column(
    threshold_slider_3d, fps_slider_3d, Altitude_slider,
    pn.widgets.Button(name="🎞 Generate animation at selected altitude level", button_type="primary", on_click=lambda e: tab3d.append(plot_z_level())),
    pn.widgets.Button(name="📈 Generate vertical profile animation at time index", button_type="primary", on_click=lambda e: tab3d.append(plot_vertical_profile())),
    pn.widgets.Button(name="📊 Generate all altitude level animations", button_type="primary", on_click=lambda e: tab3d.append(animate_all_altitude_profiles())),
    pn.widgets.Button(name="🖼 Export all animation frames as JPG", button_type="primary", on_click=lambda e: tab3d.append(export_jpg_frames())),
)

tab2d = pn.Column(
    threshold_slider_2d, fps_slider_2d,
    pn.widgets.Button(name="🌫 Animate Air Concentration", button_type="primary", on_click=lambda e: tab2d.append(plot_2d_field("air_concentration"))),
    pn.widgets.Button(name="🌧 Animate Dry Deposition Rate", button_type="primary", on_click=lambda e: tab2d.append(plot_2d_field("dry_deposition_rate"))),
    pn.widgets.Button(name="💧 Animate Wet Deposition Rate", button_type="primary", on_click=lambda e: tab2d.append(plot_2d_field("wet_deposition_rate"))),
)




help_tab = pn.Column(
 pn.pane.Markdown(
        object=open("DASHBOARD_README.md", encoding="utf-8").read(),
        #sizing_mode="stretch_both"
    )
)

tabs = pn.Tabs(
    ("🧱 3D Field", tab3d),
    ("🌍 2D Field", tab2d),
    ("📊 Bayesian Probability Analysis", tab_exceedance),
    ("📁 Media Viewer", media_tab),
    ("❓ Help", help_tab), 
    #sizing_mode='stretch_both'
)



# Update the sidebar:
sidebar = pn.Column(
    pn.pane.Markdown("## 🌋 NAME Ash Visualizer"),
    pn.Card(pn.Column(file_input,file_dropper,        # new dropper
        process_button, reset_button, run_all_button ),
            title="📂 File Upload & Processing", collapsible=True),
    pn.Card(pn.Column(cmap_select, basemap_select, zoom_slider),
            title="🎨 Map & Visualization Settings", collapsible=True),
    pn.Card(pn.Column(download_button, log_link),
            title="📁 Downloads & Logs", collapsible=True),
     pn.pane.Markdown(
    "© 2025 Dr. Mahmud Muhammad • [Email:]mahmud.muhammad@hotmail.com",
    
    sizing_mode='stretch_both'
)
)

# Include this in the sidebar or main app layout
terminal_output_controls = pn.Row(
    clear_output_button
   
)

terminal_output_card = pn.Column(
    terminal_output_controls,
    terminal_output,
    sizing_mode='stretch_width'
)

def create_terminal_output_section():
    return [
        # pn.Card(terminal_output_controls, title="📟 Terminal Controls", collapsible=True),
        pn.Card(pn.Card(status, title="📢 Status", collapsible=False),terminal_output_controls, terminal_output, title="📟 Terminal Output", collapsible=True)
    ]




# Add separate instances
tab3d.extend(create_terminal_output_section())
tab2d.extend(create_terminal_output_section())
tab_exceedance.extend(create_terminal_output_section())

pn.config.raw_css.append("""
body {
    font-family: "Segoe UI", sans-serif;
}
""")


##########





# ---------------- App Start ----------------
restore_previous_session()
process_button.on_click(process_zip)
reset_button.on_click(reset_app)

# pn.template.MaterialTemplate(
#     title="NAME Model Visualization Dashboard",
#     sidebar=sidebar,
#     main=[tabs] 
    
# ).servable()

pn.template.BootstrapTemplate (
    title="🌋 Volcanic Ash Dispersion Analysis & Visualization Software",
    sidebar=sidebar,
    main=[tabs], collapsed_sidebar =False
   
).servable()
