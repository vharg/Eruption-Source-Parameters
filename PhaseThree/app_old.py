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

import contextlib

pn.extension()

import tempfile

#MEDIA_DIR = os.environ.get("NAME_MEDIA_DIR", os.path.join(tempfile.gettempdir(), "name_media"))

MEDIA_DIR = os.path.abspath(os.path.join(".", "name_media"))
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
status = pn.pane.Markdown("### Upload a NAME Model ZIP to begin")
############




download_button = pn.widgets.FileDownload(
    label="⬇️ Download All Exports",
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
zoom_slider_3d = pn.widgets.IntSlider(name='3D Zoom Level', start=1, end=20, value=19)
cmap_select_3d = pn.widgets.Select(name='3D Colormap', options=["rainbow", "viridis", "plasma"])
fps_slider_3d = pn.widgets.IntSlider(name='3D FPS', start=1, end=10, value=2)
Altitude_slider = pn.widgets.IntSlider(name='Define Ash Altitude', start=1, end=15, value=1)

threshold_slider_2d = pn.widgets.FloatSlider(name='2D Threshold', start=0.0, end=1.0, step=0.01, value=0.005)
zoom_slider_2d = pn.widgets.IntSlider(name='2D Zoom Level', start=1, end=20, value=19)
fps_slider_2d = pn.widgets.IntSlider(name='2D FPS', start=1, end=10, value=2)
cmap_select_2d = pn.widgets.Select(name='2D Colormap', options=["rainbow", "viridis", "plasma"])

# ---------------- Core Functions ----------------

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

        # animator_obj["3d"] = [xr.open_dataset(fp).load()
        #                       for fp in sorted(glob.glob(os.path.join(output_dir, "3D", "*.nc")))]
        
        # animator_obj["3d"] = []
        # for fp in sorted(glob.glob(os.path.join(output_dir, "3D", "*.nc"))):
        #     with xr.open_dataset(fp) as ds:
        #         animator_obj["3d"].append(ds.load())
        animator_obj["3d"] = []
        for fp in sorted(glob.glob(os.path.join(output_dir, "3D", "*.nc"))):
            with xr.open_dataset(fp) as ds:
                animator_obj["3d"].append(ds.load())

        animator_obj["2d"] = []
        for fp in sorted(glob.glob(os.path.join(output_dir, "horizontal", "*.nc"))):
            with xr.open_dataset(fp) as ds:
                animator_obj["2d"].append(ds.load())

        
        # animator_obj["2d"] = [xr.open_dataset(fp).load()
        #                       for fp in sorted(glob.glob(os.path.join(output_dir, "horizontal", "*.nc")))]

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
    
    for folder in ["ash_output", "2D", "3D"]:
        shutil.rmtree(os.path.join(MEDIA_DIR, folder), ignore_errors=True)
    if os.path.exists(os.path.join(MEDIA_DIR, "last_run.txt")):
        os.remove(os.path.join(MEDIA_DIR, "last_run.txt"))
    update_media_tabs()
    

def restore_previous_session():
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
                update_media_tabs()
    except Exception as e:
        logging.exception("Error restoring previous session")
        status.object = f"⚠️ Could not restore previous session: {e}"

process_button.on_click(process_zip)
reset_button.on_click(reset_app)

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

def plot_z_level():
    try:
        animator = build_animator_3d()
        out = os.path.join(MEDIA_DIR, "3D")
        os.makedirs(out, exist_ok=True)
        Plot_3DField_Data(animator, out, cmap_select_3d.value,
                          threshold_slider_3d.value, zoom_slider_3d.value,
                          fps_slider_3d.value).plot_single_z_level(
                              Altitude_slider.value, f"ash_altitude{Altitude_slider.value}km_runTimes.gif")
        update_media_tabs()
        status.object = "✅ Z-Level animation created."
    except Exception as e:
        logging.exception("Error in plot_z_level")
        status.object = f"❌ Error in Z-Level animation: {e}"
        

def plot_vertical_profile():
    try:
        animator = build_animator_3d()
        out = os.path.join(MEDIA_DIR, "3D")
        os.makedirs(out, exist_ok=True)
        plotter = Plot_3DField_Data(animator, out, cmap_select_3d.value, fps_slider_3d.value,
                                    threshold_slider_3d.value, zoom_level=zoom_slider_3d.value,
                                    basemap_type='basemap')
        plotter.plot_vertical_profile_at_time(Altitude_slider.value - 1,
                                              filename=f"T{Altitude_slider.value - 1}_profile.gif")
        update_media_tabs()
        
        status.object = "✅ Vertical profile animation created."
    except Exception as e:
        logging.exception("Error in plot_vertical_profile")
        status.object = f"❌ Error in vertical profile animation: {e}"
        

def animate_all_altitude_profiles():
    try:
        
        animator = build_animator_3d()
        out = os.path.join(MEDIA_DIR, "3D")
        Plot_3DField_Data(animator, out, cmap_select_3d.value,
                          threshold_slider_3d.value, zoom_slider_3d.value).animate_all_altitude_profiles()
        update_media_tabs()
       
        status.object = "✅ All altitude profile animations created."
    except Exception as e:
        logging.exception("Error in animate_all_altitude_profiles")
        status.object = f"❌ Error animating all altitude profiles: {e}"


def export_jpg_frames():
    try:
         
        animator = build_animator_3d()
        out = os.path.join(MEDIA_DIR, "3D")
        status.object= Plot_3DField_Data(animator, out, cmap_select_3d.value,
                          threshold_slider_3d.value, zoom_slider_3d.value).export_frames_as_jpgs(include_metadata=True)
        update_media_tabs()
         
        status.object = "✅ JPG frames exported."
    except Exception as e:
        logging.exception("Error exporting JPG frames")
        status.object = f"❌ Error exporting JPG frames: {e}"
        

def plot_2d_field(field):
    try:
         
        animator = build_animator_2d()
        out = os.path.join(MEDIA_DIR, "2D")
        status.object= Plot_Horizontal_Data(animator, out, cmap_select_2d.value, fps_slider_2d.value,
                             include_metadata=True, threshold=threshold_slider_2d.value,
                             zoom_width_deg=6.0, zoom_height_deg=6.0,
                             zoom_level=zoom_slider_2d.value,
                             static_frame_export=True).plot_single_field_over_time(field, f"{field}.gif")
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



# ---------------- Layout ----------------

def human_readable_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024: return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"




def generate_output_gallery(base_folder):
    preview_container = pn.Column(width=640, height=550)
    preview_container.append(pn.pane.Markdown("👈 Click a thumbnail to preview"))
    folder_cards = []

    def make_preview(file_path):
        ext = os.path.splitext(file_path)[1].lower()
        title = pn.pane.Markdown(f"### {os.path.basename(file_path)}", width=640)
        download_button = pn.widgets.FileDownload(file=file_path, filename=os.path.basename(file_path),
                                                  label="⬇ Download", button_type="success", width=150)

        if ext in [".gif", ".png", ".jpg", ".jpeg"]:
            content = pn.pane.Image(file_path, width=640, height=450, sizing_mode="fixed")
        else:
            try:
                with open(file_path, 'r', errors="ignore") as f:
                    text = f.read(2048)
                content = pn.pane.PreText(text, width=640, height=450)
            except:
                content = pn.pane.Markdown("*Unable to preview this file.*")

        return pn.Column(title, content, download_button)

    grouped = defaultdict(list)
    for root, _, files in os.walk(os.path.join(MEDIA_DIR, base_folder)):
        for file in sorted(files):
            full_path = os.path.join(root, file)
            if not os.path.exists(full_path):
                continue
            rel_folder = os.path.relpath(root, os.path.join(MEDIA_DIR, base_folder))
            grouped[rel_folder].append(full_path)

    for folder, file_paths in sorted(grouped.items()):
        thumbnails = []
        for full_path in file_paths:
            filename = os.path.basename(full_path)
            ext = os.path.splitext(full_path)[1].lower()

            if ext in [".gif", ".png", ".jpg", ".jpeg"]:
                img = pn.pane.Image(full_path, width=140, height=100)
            else:
                img = pn.pane.Markdown("📄", width=140, height=100)

            view_button = pn.widgets.Button(name="👁", width=40, height=30, button_type="primary")

            def click_handler(path=full_path):
                def inner_click(event):
                    preview_container[:] = [make_preview(path)]
                return inner_click

            view_button.on_click(click_handler())

            overlay = pn.Column(pn.Row(pn.Spacer(width=90), view_button), img, width=160)
            label_md = pn.pane.Markdown(f"**{filename}**", width=140, height=35)
            thumb_card = pn.Column(overlay, label_md, width=160)
            thumbnails.append(thumb_card)

        folder_card = pn.Card(pn.GridBox(*thumbnails, ncols=2), title=f"📁 {folder}", width=400, collapsible=True)
        folder_cards.append(folder_card)

    folder_scroll = pn.Column(*folder_cards, scroll=True, height=600, width=420)
    return pn.Row(preview_container, pn.Spacer(width=20), folder_scroll)


def update_media_tabs():
    #status.object = "🔁 Refreshing media tabs..."
    media_tab_2d.objects[:] = [generate_output_gallery("2D")]
    media_tab_3d.objects[:] = [generate_output_gallery("3D")]
    

media_tab_2d = pn.Column(generate_output_gallery("2D"))
media_tab_3d = pn.Column(generate_output_gallery("3D"))

media_tab = pn.Tabs(
    ("2D Outputs", media_tab_2d),
    ("3D Outputs", media_tab_3d)
)


tab3d = pn.Column(
    threshold_slider_3d, zoom_slider_3d, fps_slider_3d, Altitude_slider, cmap_select_3d,
    pn.widgets.Button(name="🎞 Generate animation at selected altitude level", button_type="primary", on_click=lambda e: tab3d.append(plot_z_level())),
    pn.widgets.Button(name="📈 Generate vertical profile animation at time index", button_type="primary", on_click=lambda e: tab3d.append(plot_vertical_profile())),
    pn.widgets.Button(name="📊 Generate all altitude level animations", button_type="primary", on_click=lambda e: tab3d.append(animate_all_altitude_profiles())),
    pn.widgets.Button(name="🖼 Export all animation frames as JPG", button_type="primary", on_click=lambda e: tab3d.append(export_jpg_frames())),
)

tab2d = pn.Column(
    threshold_slider_2d, zoom_slider_2d, fps_slider_2d, cmap_select_2d,
    pn.widgets.Button(name="🌫 Animate Air Concentration", button_type="primary", on_click=lambda e: tab2d.append(plot_2d_field("air_concentration"))),
    pn.widgets.Button(name="🌧 Animate Dry Deposition Rate", button_type="primary", on_click=lambda e: tab2d.append(plot_2d_field("dry_deposition_rate"))),
    pn.widgets.Button(name="💧 Animate Wet Deposition Rate", button_type="primary", on_click=lambda e: tab2d.append(plot_2d_field("wet_deposition_rate"))),
)

help_tab = pn.Column(pn.pane.Markdown("""
## ❓ How to Use the NAME Ash Visualizer

This dashboard allows users to upload and visualize outputs from the NAME ash dispersion model.

### 🧭 Workflow
1. **Upload ZIP** containing NetCDF files from the NAME model.
2. Use **3D and 2D tabs** to configure and generate animations.
3. Use **Media Viewer** to preview and download results.

### 🧳 ZIP Structure
```
## 🗂 How Uploaded ZIP is Processed

```text
┌────────────────────────────────────────────┐
│           Uploaded ZIP (.zip)              │
│  (e.g. Taal_273070_20200112_scenario_*.zip)│
└────────────────────────────────────────────┘
                    │
                    ▼
      ┌───────────────────────────────┐
      │ Contains: raw .txt outputs    │
      │  - AQOutput_3DField_*.txt     │
      │  - AQOutput_horizontal_*.txt  │
      └───────────────────────────────┘
                    │
                    ▼
  ┌────────────────────────────────────────┐
  │   NAMEDataProcessor.batch_process_zip()│
  └────────────────────────────────────────┘
                    │
                    ▼
      ┌─────────────────────────────┐
      │   Converts to NetCDF files  │
      │     - ash_output/3D/*.nc    │
      │     - ash_output/horizontal/*.nc │
      └─────────────────────────────┘
                    │
                    ▼
   ┌─────────────────────────────────────┐
   │ View & animate in 3D/2D tabs        │
   │ Download results in Media Viewer    │
   └─────────────────────────────────────┘

```

### 📢 Tips
- Reset the app with 🔄 if needed.
- View logs if an error occurs.
- Outputs are temporary per session.
""", sizing_mode="stretch_width"))

tabs = pn.Tabs(
    ("🧱 3D Field", tab3d),
    ("🌍 2D Field", tab2d),
    ("📁 Media Viewer", media_tab),
    ("❓ Help", help_tab)
)

sidebar = pn.Column(
    pn.pane.Markdown("## 🌋 NAME Ash Visualizer", sizing_mode="stretch_width"),
    pn.Card(pn.Column(file_input, process_button, reset_button, sizing_mode="stretch_width"),
            title="📂 File Upload & Processing", collapsible=True, sizing_mode="stretch_width"),
    pn.Card(pn.Column(download_button, log_link, sizing_mode="stretch_width"),
            title="📁 Downloads & Logs", collapsible=True, sizing_mode="stretch_width"),
    pn.Card(status, title="📢 Status", collapsible=True, sizing_mode="stretch_width"),
    sizing_mode="stretch_width"
)

restore_previous_session()

pn.template.EditableTemplate(
    title="NAME Visualizer Dashboard",
    sidebar=sidebar,
    main=[tabs],
).servable()

 
 
# import glob
# import shutil
# import io
# import logging
# import panel as pn
# import xarray as xr
# import numpy as np
# from datetime import datetime
# from types import SimpleNamespace
# from collections import defaultdict
# from ash_animator.converter import NAMEDataProcessor
# from ash_animator.plot_3dfield_data import Plot_3DField_Data
# from ash_animator.plot_horizontal_data import Plot_Horizontal_Data
# from ash_animator import create_grid
# import os 

# pn.extension()

# # Setup local media directory
# MEDIA_DIR = os.path.abspath(os.path.join(".", "name_media"))
# os.makedirs(MEDIA_DIR, exist_ok=True)

# LOG_FILE = os.path.join(MEDIA_DIR, "app_errors.log")
# logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# animator_obj = {}

# # Widgets
# file_input = pn.widgets.FileInput(accept=".zip")
# process_button = pn.widgets.Button(name="📦 Process ZIP", button_type="primary")
# reset_button = pn.widgets.Button(name="🔄 Reset App", button_type="danger")
# status = pn.pane.Markdown("### Upload a NAME Model ZIP to begin")

# download_button = pn.widgets.FileDownload(
#     label="⬇️ Download All Exports",
#     filename="all_exports.zip",
#     button_type="success",
#     callback=lambda: io.BytesIO(
#         open(shutil.make_archive(
#             os.path.join(MEDIA_DIR, "all_exports").replace(".zip", ""),
#             "zip", MEDIA_DIR
#         ), 'rb').read()
#     )
# )

# log_link = pn.widgets.FileDownload(
#     label="🪵 View Error Log", file=LOG_FILE,
#     filename="app_errors.log", button_type="warning"
# )

# # 3D Sliders
# threshold_slider_3d = pn.widgets.FloatSlider(name='3D Threshold', start=0.0, end=1.0, step=0.05, value=0.1)
# zoom_slider_3d = pn.widgets.IntSlider(name='3D Zoom Level', start=1, end=20, value=19)
# fps_slider_3d = pn.widgets.IntSlider(name='3D FPS', start=1, end=10, value=2)
# Altitude_slider = pn.widgets.IntSlider(name='Ash Altitude (Index)', start=0, end=15, value=1)
# cmap_select_3d = pn.widgets.Select(name='3D Colormap', options=["viridis", "plasma", "rainbow"])

# # 2D Sliders
# threshold_slider_2d = pn.widgets.FloatSlider(name='2D Threshold', start=0.0, end=1.0, step=0.01, value=0.005)
# zoom_slider_2d = pn.widgets.IntSlider(name='2D Zoom Level', start=1, end=20, value=19)
# fps_slider_2d = pn.widgets.IntSlider(name='2D FPS', start=1, end=10, value=2)
# cmap_select_2d = pn.widgets.Select(name='2D Colormap', options=["viridis", "plasma", "rainbow"])

# # Live log viewer
# live_log_output = pn.pane.Markdown("📜 Log output will appear here...", height=250, sizing_mode="stretch_width")

# def update_live_log():
#     try:
#         if os.path.exists(LOG_FILE):
#             with open(LOG_FILE, "r") as f:
#                 lines = f.readlines()
#             log_text = ''.join(lines[-40:]) or "📭 No logs yet."
#             live_log_output.object = f"```\n{log_text}\n```"
#         else:
#             live_log_output.object = "⚠️ Log file not found."
#     except Exception as e:
#         live_log_output.object = f"❌ Failed to read log: {e}"

# pn.state.add_periodic_callback(update_live_log, period=3000)

# # Core Functions
# def process_zip(event=None):
#     try:
#         status.object = "📥 Reading ZIP input..."
#         logging.info("Started ZIP processing.")
#         if file_input.value:
#             zip_path = os.path.join(MEDIA_DIR, file_input.filename)
#             with open(zip_path, "wb") as f:
#                 f.write(file_input.value)
#         else:
#             zip_path = os.path.join(MEDIA_DIR, "default_model.zip")
#             if not os.path.exists(zip_path):
#                 status.object = "❌ No ZIP uploaded and default_model.zip not found."
#                 return
#         output_dir = os.path.join(MEDIA_DIR, "ash_output")
#         shutil.rmtree(output_dir, ignore_errors=True)
#         os.makedirs(output_dir, exist_ok=True)

#         processor = NAMEDataProcessor(output_root=output_dir)
#         processor.batch_process_zip(zip_path)

#         animator_obj["3d"] = []
#         for fp in sorted(glob.glob(os.path.join(output_dir, "3D", "*.nc"))):
#             with xr.open_dataset(fp) as ds:
#                 animator_obj["3d"].append(ds.load())

#         animator_obj["2d"] = []
#         for fp in sorted(glob.glob(os.path.join(output_dir, "horizontal", "*.nc"))):
#             with xr.open_dataset(fp) as ds:
#                 animator_obj["2d"].append(ds.load())

#         with open(os.path.join(MEDIA_DIR, "last_run.txt"), "w") as f:
#             f.write(zip_path)

#         status.object = f"✅ Loaded 3D: {len(animator_obj['3d'])} | 2D: {len(animator_obj['2d'])}"
#     except Exception as e:
#         logging.exception("ZIP processing error")
#         status.object = f"❌ Processing failed: {e}"

# def reset_app(event=None):
#     try:
#         status.object = "🔄 Resetting app..."
#         animator_obj.clear()
#         file_input.value = None
#         for folder in ["ash_output", "3D", "2D"]:
#             shutil.rmtree(os.path.join(MEDIA_DIR, folder), ignore_errors=True)
#         try:
#             os.remove(os.path.join(MEDIA_DIR, "last_run.txt"))
#         except:
#             pass
#         status.object = "✅ App reset."
#     except Exception as e:
#         logging.exception("Reset error")
#         status.object = f"❌ Reset failed: {e}"

# def restore_previous_session():
#     try:
#         state_file = os.path.join(MEDIA_DIR, "last_run.txt")
#         if os.path.exists(state_file):
#             with open(state_file) as f:
#                 zip_path = f.read().strip()
#             output_dir = os.path.join(MEDIA_DIR, "ash_output")

#             animator_obj["3d"] = []
#             for fp in sorted(glob.glob(os.path.join(output_dir, "3D", "*.nc"))):
#                 with xr.open_dataset(fp) as ds:
#                     animator_obj["3d"].append(ds.load())

#             animator_obj["2d"] = []
#             for fp in sorted(glob.glob(os.path.join(output_dir, "horizontal", "*.nc"))):
#                 with xr.open_dataset(fp) as ds:
#                     animator_obj["2d"].append(ds.load())

#             status.object = f"✅ Restored session: {os.path.basename(zip_path)}"
#     except Exception as e:
#         logging.exception("Restore error")
#         status.object = f"❌ Restore failed: {e}"

# def build_animator_3d():
#     ds = animator_obj["3d"]
#     attrs = ds[0].attrs
#     lons, lats, grid = create_grid(attrs)
#     return SimpleNamespace(
#         datasets=ds,
#         levels=ds[0].altitude.values,
#         lons=lons,
#         lats=lats,
#         lon_grid=grid[0],
#         lat_grid=grid[1],
#     )

# def build_animator_2d():
#     ds = animator_obj["2d"]
#     lat_grid, lon_grid = xr.broadcast(ds[0]["latitude"], ds[0]["longitude"])
#     return SimpleNamespace(
#         datasets=ds,
#         lats=ds[0]["latitude"].values,
#         lons=ds[0]["longitude"].values,
#         lat_grid=lat_grid.values,
#         lon_grid=lon_grid.values,
#     )

# # ---------------- Plot Functions ----------------
# def plot_z_level():
#     try:
#         animator = build_animator_3d()
#         out = os.path.join(MEDIA_DIR, "3D")
#         os.makedirs(out, exist_ok=True)
#         Plot_3DField_Data(animator, out, cmap_select_3d.value,
#                           threshold_slider_3d.value, zoom_slider_3d.value,
#                           fps_slider_3d.value).plot_single_z_level(
#                               Altitude_slider.value, f"ash_altitude{Altitude_slider.value}km_runTimes.gif")
#         update_media_tabs()
#         status.object = "✅ Z-Level animation created."
#     except Exception as e:
#         logging.exception("Error in plot_z_level")
#         status.object = f"❌ Error in Z-Level animation: {e}"

# def plot_vertical_profile():
#     try:
#         animator = build_animator_3d()
#         out = os.path.join(MEDIA_DIR, "3D")
#         os.makedirs(out, exist_ok=True)
#         plotter = Plot_3DField_Data(animator, out, cmap_select_3d.value, fps_slider_3d.value,
#                                     threshold_slider_3d.value, zoom_level=zoom_slider_3d.value,
#                                     basemap_type='basemap')
#         plotter.plot_vertical_profile_at_time(Altitude_slider.value - 1,
#                                               filename=f"T{Altitude_slider.value - 1}_profile.gif")
#         update_media_tabs()
#         status.object = "✅ Vertical profile animation created."
#     except Exception as e:
#         logging.exception("Error in plot_vertical_profile")
#         status.object = f"❌ Error in vertical profile animation: {e}"

# def animate_all_altitude_profiles():
#     try:
#         animator = build_animator_3d()
#         out = os.path.join(MEDIA_DIR, "3D")
#         Plot_3DField_Data(animator, out, cmap_select_3d.value,
#                           threshold_slider_3d.value, zoom_slider_3d.value).animate_all_altitude_profiles()
#         update_media_tabs()
#         status.object = "✅ All altitude profile animations created."
#     except Exception as e:
#         logging.exception("Error in animate_all_altitude_profiles")
#         status.object = f"❌ Error animating all altitude profiles: {e}"

# def export_jpg_frames():
#     try:
#         animator = build_animator_3d()
#         out = os.path.join(MEDIA_DIR, "3D")
#         Plot_3DField_Data(animator, out, cmap_select_3d.value,
#                           threshold_slider_3d.value, zoom_slider_3d.value, basemap_type="stock").export_frames_as_jpgs(include_metadata=True)
#         update_media_tabs()
#         status.object = "✅ JPG frames exported."
#     except Exception as e:
#         logging.exception("Error exporting JPG frames")
#         status.object = f"❌ Error exporting JPG frames: {e}"

# def plot_2d_field(field):
#     try:
#         animator = build_animator_2d()
#         out = os.path.join(MEDIA_DIR, "2D")
#         Plot_Horizontal_Data(animator, out, cmap_select_2d.value, fps_slider_2d.value,
#                              include_metadata=True, threshold=threshold_slider_2d.value,
#                              zoom_width_deg=6.0, zoom_height_deg=6.0,
#                              zoom_level=zoom_slider_2d.value,
#                              static_frame_export=True).plot_single_field_over_time(field, f"{field}.gif")
#         update_media_tabs()
#         status.object = f"✅ 2D field `{field}` animation created."
#     except Exception as e:
#         logging.exception(f"Error in plot_2d_field: {field}")
#         status.object = f"❌ Error in 2D field `{field}` animation: {e}"

# def human_readable_size(size):
#     for unit in ['B', 'KB', 'MB', 'GB']:
#         if size < 1024: return f"{size:.1f} {unit}"
#         size /= 1024
#     return f"{size:.1f} TB"

# # ---------------- Tabs ----------------
# def generate_output_gallery(base_folder):
#     preview_container = pn.Column(width=640, height=550)
#     preview_container.append(pn.pane.Markdown("👈 Click a thumbnail to preview"))
#     folder_cards = []

#     def make_preview(file_path):
#         ext = os.path.splitext(file_path)[1].lower()
#         title = pn.pane.Markdown(f"### {os.path.basename(file_path)}", width=640)
#         download_button = pn.widgets.FileDownload(file=file_path, filename=os.path.basename(file_path),
#                                                   label="⬇ Download", button_type="success", width=150)

#         if ext in [".gif", ".png", ".jpg", ".jpeg"]:
#             content = pn.pane.Image(file_path, width=640, height=450, sizing_mode="fixed")
#         else:
#             try:
#                 with open(file_path, 'r', errors="ignore") as f:
#                     text = f.read(2048)
#                 content = pn.pane.PreText(text, width=640, height=450)
#             except:
#                 content = pn.pane.Markdown("*Unable to preview this file.*")

#         return pn.Column(title, content, download_button)

#     grouped = defaultdict(list)
#     for root, _, files in os.walk(os.path.join(MEDIA_DIR, base_folder)):
#         for file in sorted(files):
#             full_path = os.path.join(root, file)
#             if not os.path.exists(full_path):
#                 continue
#             rel_folder = os.path.relpath(root, os.path.join(MEDIA_DIR, base_folder))
#             grouped[rel_folder].append(full_path)

#     for folder, file_paths in sorted(grouped.items()):
#         thumbnails = []
#         for full_path in file_paths:
#             filename = os.path.basename(full_path)
#             ext = os.path.splitext(full_path)[1].lower()

#             if ext in [".gif", ".png", ".jpg", ".jpeg"]:
#                 img = pn.pane.Image(full_path, width=140, height=100)
#             else:
#                 img = pn.pane.Markdown("📄", width=140, height=100)

#             view_button = pn.widgets.Button(name="👁", width=40, height=30, button_type="primary")

#             def click_handler(path=full_path):
#                 def inner_click(event):
#                     preview_container[:] = [make_preview(path)]
#                 return inner_click

#             view_button.on_click(click_handler())

#             overlay = pn.Column(pn.Row(pn.Spacer(width=90), view_button), img, width=160)
#             label_md = pn.pane.Markdown(f"**{filename}**", width=140, height=35)
#             thumb_card = pn.Column(overlay, label_md, width=160)
#             thumbnails.append(thumb_card)

#         folder_card = pn.Card(pn.GridBox(*thumbnails, ncols=2), title=f"📁 {folder}", width=400, collapsible=True)
#         folder_cards.append(folder_card)

#     folder_scroll = pn.Column(*folder_cards, scroll=True, height=600, width=420)
#     return pn.Row(preview_container, pn.Spacer(width=20), folder_scroll)

# def update_media_tabs():
#     media_tab_2d.objects[:] = [generate_output_gallery("2D")]
#     media_tab_3d.objects[:] = [generate_output_gallery("3D")]

# media_tab_2d = pn.Column(generate_output_gallery("2D"))
# media_tab_3d = pn.Column(generate_output_gallery("3D"))

# media_tab = pn.Tabs(
#     ("2D Outputs", media_tab_2d),
#     ("3D Outputs", media_tab_3d)
# )


# tab3d = pn.Column(
#     threshold_slider_3d, zoom_slider_3d, fps_slider_3d, Altitude_slider, cmap_select_3d,
#     pn.widgets.Button(name="🎞 Generate animation at selected altitude level", button_type="primary", on_click=lambda e: tab3d.append(plot_z_level())),
#     pn.widgets.Button(name="📈 Generate vertical profile animation at time index", button_type="primary", on_click=lambda e: tab3d.append(plot_vertical_profile())),
#     pn.widgets.Button(name="📊 Generate all altitude level animations", button_type="primary", on_click=lambda e: tab3d.append(animate_all_altitude_profiles())),
#     pn.widgets.Button(name="🖼 Export all animation frames as JPG", button_type="primary", on_click=lambda e: tab3d.append(export_jpg_frames())),
# )

# tab2d = pn.Column(
#     threshold_slider_2d, zoom_slider_2d, fps_slider_2d, cmap_select_2d,
#     pn.widgets.Button(name="🌫 Animate Air Concentration", button_type="primary", on_click=lambda e: tab2d.append(plot_2d_field("air_concentration"))),
#     pn.widgets.Button(name="🌧 Animate Dry Deposition Rate", button_type="primary", on_click=lambda e: tab2d.append(plot_2d_field("dry_deposition_rate"))),
#     pn.widgets.Button(name="💧 Animate Wet Deposition Rate", button_type="primary", on_click=lambda e: tab2d.append(plot_2d_field("wet_deposition_rate"))),
# )

# help_tab = pn.Column(pn.pane.Markdown("""
# ## ❓ How to Use the NAME Ash Visualizer

# This dashboard allows users to upload and visualize outputs from the NAME ash dispersion model.

# ### 🧭 Workflow
# 1. **Upload ZIP** containing NetCDF files from the NAME model.
# 2. Use **3D and 2D tabs** to configure and generate animations.
# 3. Use **Media Viewer** to preview and download results.

# ### 🧳 ZIP Structure
# ```
# ## 🗂 How Uploaded ZIP is Processed

# ```text
# ┌────────────────────────────────────────────┐
# │           Uploaded ZIP (.zip)              │
# │  (e.g. Taal_273070_20200112_scenario_*.zip)│
# └────────────────────────────────────────────┘
#                     │
#                     ▼
#       ┌───────────────────────────────┐
#       │ Contains: raw .txt outputs    │
#       │  - AQOutput_3DField_*.txt     │
#       │  - AQOutput_horizontal_*.txt  │
#       └───────────────────────────────┘
#                     │
#                     ▼
#   ┌────────────────────────────────────────┐
#   │   NAMEDataProcessor.batch_process_zip()│
#   └────────────────────────────────────────┘
#                     │
#                     ▼
#       ┌─────────────────────────────┐
#       │   Converts to NetCDF files  │
#       │     - ash_output/3D/*.nc    │
#       │     - ash_output/horizontal/*.nc │
#       └─────────────────────────────┘
#                     │
#                     ▼
#    ┌─────────────────────────────────────┐
#    │ View & animate in 3D/2D tabs        │
#    │ Download results in Media Viewer    │
#    └─────────────────────────────────────┘

# ```

# ### 📢 Tips
# - Reset the app with 🔄 if needed.
# - View logs if an error occurs.
# - Outputs are temporary per session.
# """, sizing_mode="stretch_width"))

# tabs = pn.Tabs(
#     ("🧱 3D Field", tab3d),
#     ("🌍 2D Field", tab2d),
#     ("📁 Media Viewer", media_tab),
#     ("❓ Help", help_tab)
# )

# sidebar = pn.Column(
#     pn.pane.Markdown("## 🌋 NAME Ash Visualizer", sizing_mode="stretch_width"),
#     pn.Card(pn.Column(file_input, process_button, reset_button, sizing_mode="stretch_width"),
#             title="📂 File Upload & Processing", collapsible=True, sizing_mode="stretch_width"),
#     pn.Card(pn.Column(download_button, log_link, sizing_mode="stretch_width"),
#             title="📁 Downloads & Logs", collapsible=True, sizing_mode="stretch_width"),
#     pn.Card(status, title="📢 Status", collapsible=True, sizing_mode="stretch_width"),
#     sizing_mode="stretch_width")

# restore_previous_session()

# pn.template.EditableTemplate(
#     title="NAME Visualizer Dashboard",
#     sidebar=sidebar,
#     main=[tabs],
# ).servable()
