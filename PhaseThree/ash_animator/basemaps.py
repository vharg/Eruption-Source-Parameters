import os
import hashlib
import tempfile
import contextily as ctx
from mpl_toolkits.basemap import Basemap
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from PIL import Image
import matplotlib.pyplot as plt

import warnings
from cartopy.io.shapereader import Reader
warnings.filterwarnings("ignore", category=UserWarning)


# Determine platform and fallback cache path
def get_cache_dir(app_name):
    if os.name == 'nt':
        return os.path.join(os.getenv('LOCALAPPDATA', tempfile.gettempdir()), f"{app_name}_cache")
    elif os.name == 'posix':
        home_dir = os.path.expanduser("~")
        if os.path.isdir(home_dir) and os.access(home_dir, os.W_OK):
            return os.path.join(home_dir, f".{app_name}_cache")
        else:
            return os.path.join(tempfile.gettempdir(), f"{app_name}_cache")
    else:
        return os.path.join(tempfile.gettempdir(), f"{app_name}_cache")


MEDIA_DIR = os.path.abspath(os.path.join(".", "basemaps_cache"))
os.makedirs(MEDIA_DIR, exist_ok=True)

# Logging setup
LOG_FILE = os.path.join(MEDIA_DIR, "app_errors.log")
# # Define cache directories
# CTX_TILE_CACHE_DIR = get_cache_dir("contextily")
# BASEMAP_TILE_CACHE_DIR = get_cache_dir("basemap")

BASEMAP_TILE_CACHE_DIR=MEDIA_DIR
CTX_TILE_CACHE_DIR=MEDIA_DIR


os.environ["XDG_CACHE_HOME"] = CTX_TILE_CACHE_DIR
os.makedirs(CTX_TILE_CACHE_DIR, exist_ok=True)
os.makedirs(BASEMAP_TILE_CACHE_DIR, exist_ok=True)

def draw_etopo_basemap(ax, mode="basemap", zoom=7):
    """
    Draws a high-resolution basemap background on the provided Cartopy GeoAxes.

    Parameters
    ----------
    ax : matplotlib.axes._subplots.AxesSubplot
        The matplotlib Axes object (with Cartopy projection) to draw the map background on.

    mode : str, optional
        The basemap mode to use:
        - "stock": Default stock image from Cartopy.
        - "contextily": Web tile background (CartoDB Voyager), with caching.
        - "basemap": High-resolution shaded relief using Basemap, with caching.
        Default is "basemap".

    zoom : int, optional
        Tile zoom level (only for "contextily"). Higher = more detail. Default is 7.

    Notes
    -----
    - Uses high resolution for Basemap (resolution='h') and saves figure at 300 DPI.
    - Cached images are reused using extent-based hashing to avoid re-rendering.
    - Basemap is deprecated; Cartopy with web tiles is recommended for new projects.
    """
    try:
        if mode == "stock":
            ax.stock_img()
            ax.add_feature(cfeature.LAND)
            ax.add_feature(cfeature.OCEAN)

        elif mode == "contextily":
            extent = ax.get_extent(crs=ccrs.PlateCarree())
            ax.set_extent(extent, crs=ccrs.PlateCarree())
            ctx.add_basemap(
                ax,
                crs=ccrs.PlateCarree(),
                source=ctx.providers.CartoDB.Voyager,
                zoom=zoom
            )

        elif mode == "basemap":
            extent = ax.get_extent(crs=ccrs.PlateCarree())
            extent_str = f"{extent[0]:.4f}_{extent[1]:.4f}_{extent[2]:.4f}_{extent[3]:.4f}"
            cache_key = hashlib.md5(extent_str.encode()).hexdigest()
            cache_file = os.path.join(BASEMAP_TILE_CACHE_DIR, f"{cache_key}_highres.png")

            if os.path.exists(cache_file):
                img = Image.open(cache_file)
                ax.imshow(img, extent=extent, transform=ccrs.PlateCarree(), origin='upper')
            else:
                fig_width, fig_height = 8, 6
                temp_fig, temp_ax = plt.subplots(figsize=(fig_width, fig_height),
                                                subplot_kw={'projection': ccrs.PlateCarree()})
                temp_ax.set_extent(extent, crs=ccrs.PlateCarree())

                # Use high resolution basemap
                m = Basemap(projection='cyl',
                            llcrnrlon=extent[0], urcrnrlon=extent[1],
                            llcrnrlat=extent[2], urcrnrlat=extent[3],
                            resolution='i', ax=temp_ax)
                m.shadedrelief()

                temp_ax.axis('off')  # Hide axis for clean image
                temp_fig.savefig(cache_file, dpi=300, bbox_inches='tight', pad_inches=0)
                plt.close(temp_fig)

                img = Image.open(cache_file)
                ax.imshow(img, extent=extent, transform=ccrs.PlateCarree(), origin='upper')

        elif mode == "default":
            ax.add_feature(cfeature.LAND)
            ax.add_feature(cfeature.OCEAN)
        # elif mode == "basemap":
        #     extent = ax.get_extent(crs=ccrs.PlateCarree())
        #     extent_str = f"{extent[0]:.4f}_{extent[1]:.4f}_{extent[2]:.4f}_{extent[3]:.4f}"
        #     cache_key = hashlib.md5(extent_str.encode()).hexdigest()
        #     cache_file = os.path.join(BASEMAP_TILE_CACHE_DIR, f"{cache_key}_highres.png")

        #     if os.path.exists(cache_file):
        #         img = Image.open(cache_file)
        #         ax.imshow(img, extent=extent, transform=ccrs.PlateCarree())
        #     else:
        #         temp_fig, temp_ax = plt.subplots(figsize=(12, 9),
        #                                          subplot_kw={'projection': ccrs.PlateCarree()})
        #         temp_ax.set_extent(extent, crs=ccrs.PlateCarree())

        #         m = Basemap(projection='cyl',
        #                     llcrnrlon=extent[0], urcrnrlon=extent[1],
        #                     llcrnrlat=extent[2], urcrnrlat=extent[3],
        #                     resolution='l', ax=temp_ax)
        #         m.shadedrelief()

        #         temp_fig.savefig(cache_file, dpi=300, bbox_inches='tight', pad_inches=0)
        #         plt.close(temp_fig)

                # img = Image.open(cache_file)
                # ax.imshow(img, extent=extent, transform=ccrs.PlateCarree())

        else:
            raise ValueError(f"Unsupported basemap mode: {mode}")

    except Exception as e:
        print(f"[Relief Error - {mode} mode]:", e)
        ax.add_feature(cfeature.LAND)
        ax.add_feature(cfeature.OCEAN)
