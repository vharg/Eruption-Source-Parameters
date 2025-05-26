
import numpy as np
from scipy.interpolate import griddata

def interpolate_grid(data, lon_grid, lat_grid):
    data = np.where(data < 0, np.nan, data)
    mask = data > 0
    if np.count_nonzero(mask) < 10:
        return np.full_like(data, np.nan)
    
    points = np.column_stack((lon_grid[mask], lat_grid[mask]))
    values = data[mask]
    grid_z = griddata(points, values, (lon_grid, lat_grid), method='cubic')
    return np.where(grid_z < 0, 0, grid_z)
