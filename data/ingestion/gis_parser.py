import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

def load_and_join_spatial_data():
    """
    Mock function: In production, load actual shapefiles or PostGIS tables.
    Returns a dataframe of pipe junctions with their corresponding zones.
    """
    # Mock pipe junctions
    junctions = pd.DataFrame({
        'junction_id': ['J-001', 'J-002', 'J-003'],
        'latitude': [42.28, 42.29, 42.27],
        'longitude': [-71.23, -71.24, -71.22],
        'material': ['Cast Iron', 'PVC', 'Ductile Iron'],
        'install_year': [1955, 1995, 1970]
    })
    
    # Convert to GeoDataFrame
    gdf_junctions = gpd.GeoDataFrame(
        junctions, 
        geometry=gpd.points_from_xy(junctions.longitude, junctions.latitude)
    )
    
    # In a real app, you would spatial-join this with Zone polygons
    # gdf_joined = gpd.sjoin(gdf_junctions, gdf_zones, how="left")
    
    # Mocking the joined output
    gdf_junctions['zone_id'] = ['Zone_A', 'Zone_A', 'Zone_B']
    return gdf_junctions