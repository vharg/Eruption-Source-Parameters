
from geopy.geocoders import Nominatim
import numpy as np

def create_grid(attrs):
    x_origin = float(attrs["x_origin"])
    y_origin = float(attrs["y_origin"])
    x_res = float(attrs["x_res"])
    y_res = float(attrs["y_res"])
    x_grid_size = int(attrs["x_grid_size"])
    y_grid_size = int(attrs["y_grid_size"])

    lons = np.round(np.linspace(x_origin, x_origin + (x_grid_size - 1) * x_res, x_grid_size), 6)
    lats = np.round(np.linspace(y_origin, y_origin + (y_grid_size - 1) * y_res, y_grid_size), 6)
    return lons, lats, np.meshgrid(lons, lats)

def get_country_label(lat, lon):
    geolocator = Nominatim(user_agent="ash_animator")
    try:
        location = geolocator.reverse((lat, lon), language='en')
        return location.raw['address'].get('country', 'Unknown')
    except:
        return "Unknown"
