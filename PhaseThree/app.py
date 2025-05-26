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
from ash_animator import create_grid

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
    width=150
)

clear_output_button = pn.widgets.Button(
    name="🧹 Clear Output",
    button_type="danger",
    width=150
)

# === Output Area ===

terminal_output = pn.pane.HTML(
    "<pre id='log-content' class='debugger-pane'></pre>",
    height=300,
    sizing_mode="stretch_width"
)

# === Output Handler ===

# class LiveOutput(io.StringIO):
#     def __init__(self, pane, max_length=10000):
#         super().__init__()
#         self.pane = pane
#         self._buffer = ""
#         self.max_length = max_length

#     def write(self, msg):
#         self._buffer += msg
#         if len(self._buffer) > self.max_length:
#             self._buffer = "...\n" + self._buffer[-self.max_length:]

#         # Escape HTML
#         safe_html = (
#             self._buffer.replace("&", "&amp;")
#                         .replace("<", "&lt;")
#                         .replace(">", "&gt;")
#         )

#         scroll_script = (
#             "<script>var e = document.getElementById('log-content');"
#             "if(e) e.scrollTop = e.scrollHeight;</script>"
#             if auto_scroll_toggle.value else ""
#         )

#         self.pane.object = (
#             f"<pre id='log-content' class='debugger-pane'>{safe_html}</pre>{scroll_script}"
#         )

#         return len(msg)

#     def flush(self):
#         pass

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

pn.extension(raw_css=[  # Windows 11-style debugger terminal
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
    
#     sizing_mode="stretch_width", scroll=True
# )

terminal_output = pn.pane.HTML(
    "<pre id='log-content' style='margin:0; font-family:monospace; white-space:pre-wrap;'>"
     "Live terminal output will appear here..."
     "</pre>",  # Start with empty content
    height=300,

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
file_input = pn.widgets.FileInput(accept=".zip")
process_button = pn.widgets.Button(name="📦 Process ZIP", button_type="primary")
reset_button = pn.widgets.Button(name="🔄 Reset App", button_type="danger")

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

threshold_slider_3d = pn.widgets.FloatSlider(name='3D Threshold', start=0.0, end=1.0, step=0.05, value=0.1)
fps_slider_3d = pn.widgets.IntSlider(name='3D FPS', start=1, end=10, value=2)
Altitude_slider = pn.widgets.IntSlider(name='Define Ash Altitude', start=0, end=15, value=4)

threshold_slider_2d = pn.widgets.FloatSlider(name='2D Threshold', start=0.0, end=1.0, step=0.01, value=0.005)
fps_slider_2d = pn.widgets.IntSlider(name='2D FPS', start=1, end=10, value=2)


# Exceedance controls
exceedance_threshold_3d = pn.widgets.FloatSlider(name='3D Exceedance Threshold', start=0.001, end=1, step=0.001, value=0.008)
exceedance_cmap_3d = pn.widgets.Select(name='3D Exceedance Colormap', options=["viridis", "plasma", "rainbow"])

exceedance_threshold_2d = pn.widgets.FloatSlider(name='2D Exceedance Threshold', start=0.0001, end=1, step=0.0001, value=0.001)
exceedance_cmap_2d = pn.widgets.Select(name='2D Exceedance Colormap', options=["viridis", "plasma", "rainbow"])


all_cmaps = plt.colormaps()

# Create the Select widget with all colormaps
cmap_select = pn.widgets.Select(name='Colormap', options=sorted(all_cmaps), value='viridis')
#cmap_select = pn.widgets.Select(name='Colormap', options=["rainbow", "viridis", "plasma"])
basemap_select = pn.widgets.Select(name='Basemap Mode', options=["default","basemap", "stock", "contextily"])
zoom_slider = pn.widgets.IntSlider(name='Basemap Zoom Level', start=1, end=30, value=10)



# ---------------- Core Functions ----------------
@capture_terminal_output
def process_zip(event=None):
    if file_input.value:
        zip_path = os.path.join(MEDIA_DIR, file_input.filename)
        with open(zip_path, "wb") as f:
            f.write(file_input.value)
        status.object = "✅ ZIP uploaded and saved."
    else:
        zip_path = os.path.join(MEDIA_DIR, "default_model.zip")
        if not os.path.exists(zip_path):
            zip_path = "default_model.zip"  # fallback to local directory
        if not os.path.exists(zip_path):
            status.object = "❌ No ZIP uploaded and default_model.zip not found."
            return
        status.object = "📦 Using default_model.zip"


    try:
        output_dir = os.path.join("./", "ash_output")
        os.makedirs(output_dir, exist_ok=True)
    except PermissionError:
        output_dir = os.path.join(tempfile.gettempdir(), "name_output")
        os.makedirs(output_dir, exist_ok=True)
    shutil.rmtree(output_dir, ignore_errors=True)
    os.makedirs(output_dir, exist_ok=True)

    try:
        processor = NAMEDataProcessor(output_root=output_dir)
        processor.batch_process_zip(zip_path)

      
        animator_obj["3d"] = []
        for fp in sorted(glob.glob(os.path.join(output_dir, "3D", "*.nc"))):
            with xr.open_dataset(fp) as ds:
                animator_obj["3d"].append(ds.load())

        animator_obj["2d"] = []
        for fp in sorted(glob.glob(os.path.join(output_dir, "horizontal", "*.nc"))):
            with xr.open_dataset(fp) as ds:
                animator_obj["2d"].append(ds.load())


        with open(os.path.join(MEDIA_DIR, "last_run.txt"), "w") as f:
            f.write(zip_path)

       
        status.object += f" | ✅ Loaded 3D: {len(animator_obj['3d'])} & 2D: {len(animator_obj['2d'])}"
        update_media_tabs()
    except Exception as e:
        logging.exception("Error during ZIP processing")
        status.object = f"❌ Processing failed: {e}"


def reset_app(event=None):
    animator_obj.clear()
    file_input.value = None
    status.object = "🔄 App has been reset."
    
    for folder in ["ash_output", "2D", "3D", "Exceedance_3D", "Exceedance_2D"]:
        shutil.rmtree(os.path.join(MEDIA_DIR, folder), ignore_errors=True)
    if os.path.exists(os.path.join(MEDIA_DIR, "last_run.txt")):
        os.remove(os.path.join(MEDIA_DIR, "last_run.txt"))
    
    #restore_previous_session()
    update_media_tabs()




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


def build_animator_3d():
    ds = animator_obj["3d"]
    attrs = ds[0].attrs
    lons, lats, grid = create_grid(attrs)
    return SimpleNamespace(
        datasets=ds,
        levels=ds[0].altitude.values,
        lons=lons,
        lats=lats,
        lon_grid=grid[0],
        lat_grid=grid[1],
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



#####################

# ========== Exceedance Plotting Functions ==========
@capture_terminal_output
def plot_3d_exceedance_maps():
    try:
        analyzer = AshExceedanceAnalyzer_3D("./ash_output/3D", threshold=exceedance_threshold_3d.value, cmap=exceedance_cmap_3d.value, 
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
        analyzer = AshExceedanceAnalyzer_3D("./ash_output/3D", threshold=exceedance_threshold_3d.value, cmap=exceedance_cmap_3d.value, 
                                            basemap_mode=basemap_select.value, zoom_level=zoom_slider.value)
        analyzer.prepare_data()
        analyzer.compute_bayesian_exceedance()
        analyzer.compute_average_bayesian_exceedance()
        out = os.path.join(MEDIA_DIR, "Exceedance_3D")
        analyzer.plot_average_bayesian_exceedance(contour_levels=10, save_dir=out)
        update_media_tabs()
        status.object = "✅ 3D average exceedance plotted."
    except Exception as e:
        logging.exception("Error in plot_3d_avg_exceedance")
        status.object = f"❌ 3D average error: {e}"

@capture_terminal_output
def plot_3d_all_levels():
    try:
        analyzer = AshExceedanceAnalyzer_3D("./ash_output/3D", threshold=exceedance_threshold_3d.value, cmap=exceedance_cmap_3d.value, 
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
        analyzer = MultiFieldExceedanceAnalyzer_2D("./ash_output/horizontal", threshold=exceedance_threshold_2d.value, cmap=exceedance_cmap_2d.value, 
                                                   basemap_mode=basemap_select.value, zoom_level=zoom_slider.value)
        analyzer.prepare_data()
        analyzer.compute_bayesian_exceedance()
        
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







def generate_output_gallery(*base_folders):
    """
    Creates an interactive output gallery to preview and download files
    from one or more base folders. Each immediate subfolder is treated
    as its own category/folder section.

    Parameters:
        *base_folders (str): One or more folder names under MEDIA_DIR.

    Returns:
        pn.Row: A Panel layout with a preview pane and scrollable folder list.
    """
    preview_container = pn.Column(
    pn.pane.Markdown("""
### 🖼️ Output Gallery

- 🔄 **Refresh the browser** if thumbnails do not appear  
- 👈 **Click a thumbnail** on the left to preview the output
"""),
    width=640, height=550
)


    folder_cards = []

    def make_preview(file_path):
        ext = os.path.splitext(file_path)[1].lower()
        title = pn.pane.Markdown(f"### {os.path.basename(file_path)}", width=640)
        download_button = pn.widgets.FileDownload(
            file=file_path, filename=os.path.basename(file_path),
            label="⬇ Download", button_type="success", width=150
        )

        if ext in [".gif", ".png", ".jpg", ".jpeg"]:
            content = pn.pane.Image(file_path, width=640, height=450, sizing_mode="fixed")
        else:
            try:
                with open(file_path, 'r', errors="ignore") as f:
                    text = f.read(2048)
                content = pn.pane.PreText(text, width=640, height=450)
            except Exception:
                content = pn.pane.Markdown("*Unable to preview this file.*")

        return pn.Column(title, content, download_button)

    # Get all immediate subfolders as independent folders
    all_scan_folders = []
    for base_folder in base_folders:
        full_base_path = os.path.join(MEDIA_DIR, base_folder)
        if os.path.isdir(full_base_path):
            all_scan_folders.append(os.path.relpath(full_base_path, MEDIA_DIR))
            for entry in sorted(os.listdir(full_base_path)):
                subfolder_path = os.path.join(full_base_path, entry)
                if os.path.isdir(subfolder_path):
                    rel_subfolder = os.path.relpath(subfolder_path, MEDIA_DIR)
                    all_scan_folders.append(rel_subfolder)

    # Collect files under each scan folder (independent group)
    grouped = defaultdict(list)
    for folder in all_scan_folders:
        full_path = os.path.join(MEDIA_DIR, folder)
        for root, _, files in os.walk(full_path):
            for file in sorted(files):
                file_path = os.path.join(root, file)
                if os.path.exists(file_path):
                    grouped[folder].append(file_path)

    # Build UI for each folder
    sorted_folders = sorted(grouped.items())
    for idx, (folder, file_paths) in enumerate(sorted_folders):
        thumbnails = []

        for full_path in file_paths:
            filename = os.path.basename(full_path)
            ext = os.path.splitext(full_path)[1].lower()

            if ext in [".gif", ".png", ".jpg", ".jpeg"]:
                thumb = pn.pane.Image(full_path, width=140, height=100)
            else:
                thumb = pn.pane.Markdown("📄", width=140, height=100)

            view_button = pn.widgets.Button(name="👁", width=40, height=30, button_type="primary")

            def click_handler(path=full_path):
                def inner(event):
                    preview_container[:] = [make_preview(path)]
                return inner

            view_button.on_click(click_handler())

            overlay = pn.Column(
                pn.Row(pn.Spacer(width=90), view_button),
                thumb,
                width=160
            )
            label = pn.pane.Markdown(f"**{filename}**", width=140, height=35)
            thumb_card = pn.Column(overlay, label, width=160)
            thumbnails.append(thumb_card)

        is_expanded = idx == 0
        folder_card = pn.Card(
            pn.GridBox(*thumbnails, ncols=2),
            title=f"📁 {folder}",
            width=400,
            collapsible=True,
            collapsed=not is_expanded
        )
        folder_cards.append(folder_card)

    folder_scroll = pn.Column(*folder_cards, scroll=True, height=600, width=420)
    return pn.Row(preview_container, pn.Spacer(width=20), folder_scroll)



media_tab_2d = pn.Column(generate_output_gallery("2D"))
media_tab_3d = pn.Column(generate_output_gallery("3D"))
media_tab_statistical_3d = pn.Column(generate_output_gallery("Exceedance_3D"))
media_tab_statistical_2d = pn.Column( generate_output_gallery("Exceedance_2D"))

media_tab = pn.Tabs(
    ("2D Outputs", media_tab_2d),
    ("3D Outputs", media_tab_3d),
    ("📈 Statistical Plots 3D Outputs", media_tab_statistical_3d), ("📈 Statistical Plots 2D Outputs", media_tab_statistical_2d)
)


# ---------------- Gallery Update ----------------




def update_media_tabs():
    media_tab_2d.objects[:] = [generate_output_gallery("2D")]
    media_tab_3d.objects[:] = [generate_output_gallery("3D")]
    # media_tab_3d.objects[:] = [generate_output_gallery("3D/altitude_profiles")]
    # media_tab_3d.objects[:] = [generate_output_gallery("3D/z_levels")]
    # media_tab_3d.objects[:] = [generate_output_gallery("3D/frames")]
    
    media_tab_statistical_3d[:] = [generate_output_gallery("Exceedance_3D")]
    media_tab_statistical_2d[:] = [generate_output_gallery("Exceedance_2D")]
    
    #  # Trigger a browser reload using JavaScript injection
    # js_reload = pn.pane.HTML("<script>location.reload()</script>")
    #pn.Column(js_reload).servable()
    
    


# ---------------- Layout & Tabs ----------------

tab_exceedance = pn.Column(
    pn.pane.Markdown("## 📊 Bayesian Probability Analysis"),
    pn.Card(pn.Column(exceedance_threshold_3d,
        pn.widgets.Button(name="📍 3D Exceedance Maps For Each Altitud", button_type="primary", on_click=lambda e: plot_3d_exceedance_maps()),
        pn.widgets.Button(name="📉 3D Exceedance thresold for all Altitudes", button_type="primary", on_click=lambda e: plot_3d_avg_exceedance()),
        pn.widgets.Button(name="📊 3D All Level Contours", button_type="primary", on_click=lambda e: plot_3d_all_levels())
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
        sizing_mode="stretch_width"
    )
)

tabs = pn.Tabs(
    ("🧱 3D Field", tab3d),
    ("🌍 2D Field", tab2d),
    ("📊 Bayesian Probability Analysis", tab_exceedance),
    ("📁 Media Viewer", media_tab),
    ("❓ Help", help_tab), sizing_mode='stretch_width'
)



# Update the sidebar:
sidebar = pn.Column(
    pn.pane.Markdown("## 🌋 NAME Ash Visualizer"),
    pn.Card(pn.Column(file_input, process_button, reset_button),
            title="📂 File Upload & Processing", collapsible=True),
    pn.Card(pn.Column(cmap_select, basemap_select, zoom_slider),
            title="🎨 Map & Visualization Settings", collapsible=True),
    pn.Card(pn.Column(download_button, log_link),
            title="📁 Downloads & Logs", collapsible=True),
     pn.pane.Markdown(
    "© 2025 Dr. Mahmud Muhammad • [Email:]mahmud.muhammad@hotmail.com",
    
    sizing_mode='stretch_width'
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



pn.Accordion(
    ("3D Animations", pn.Column(
        threshold_slider_3d, fps_slider_3d, Altitude_slider,
        pn.widgets.Button(name="Generate Z-Level Animation", button_type="primary", on_click=lambda e: plot_z_level()),
        pn.widgets.Button(name="Generate Vertical Profile", button_type="primary", on_click=lambda e: plot_vertical_profile()),
        pn.widgets.Button(name="Generate All Altitude Profiles", button_type="primary", on_click=lambda e: animate_all_altitude_profiles()),
        pn.widgets.Button(name="Export JPG Frames", button_type="primary", on_click=lambda e: export_jpg_frames()),
    )),
    ("2D Animations", pn.Column(
        threshold_slider_2d, fps_slider_2d,
        pn.widgets.Button(name="Air Concentration", button_type="primary", on_click=lambda e: plot_2d_field("air_concentration")),
        pn.widgets.Button(name="Dry Deposition", button_type="primary", on_click=lambda e: plot_2d_field("dry_deposition_rate")),
        pn.widgets.Button(name="Wet Deposition", button_type="primary", on_click=lambda e: plot_2d_field("wet_deposition_rate")),
    )),
    sizing_mode="stretch_width"
)


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
