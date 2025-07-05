
import numpy as np
from scipy.interpolate import griddata

def interpolate_grid(data, lon_grid, lat_grid, attrs=None):
    data = np.where(data < 0, 0, data)
    mask = data > 0
    if np.count_nonzero(mask) < 10:
        return np.full_like(data, np.nan)
    
    if attrs:
        lon_grid, lat_grid=create_grid(attrs)
    
    points = np.column_stack((lon_grid[mask], lat_grid[mask]))
    values = data[mask]
    
    
    
    grid_z = griddata(points, values, (lon_grid, lat_grid), method='linear')
    
    
    
    return np.where(grid_z < 0, 0, grid_z)




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
    return lon_grid, lat_grid