# ingestion/gis_parser.py
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

def process_local_gis_triage(geojson_path: str, csv_path: str) -> pd.DataFrame:
    """
    Ingests local GIS boundary maps and raw coordinate files, performs 
    an air-gapped spatial join, and prepares data for the ranking engine.
    """
    # 1. Read the local service zone polygons
    # Geopandas parses the coordinate geometry directly from the local file
    zones_gdf = gpd.read_file(geojson_path)
    
    # 2. Read the raw anomaly coordinates from the flat file
    raw_anomalies_df = pd.read_csv(csv_path)
    
    # 3. Convert the flat file into a spatial GeoDataFrame
    # Creates true geometric Point objects out of the longitude and latitude numbers
    geometry = [Point(xy) for xy in zip(raw_anomalies_df.longitude, raw_anomalies_df.latitude)]
    anomalies_gdf = gpd.GeoDataFrame(raw_anomalies_df, geometry=geometry)
    
    # Crucial step: Ensure both data layers use the exact same Coordinate Reference System (CRS)
    # WGS84 (EPSG:4326) is the global standard for standard latitude/longitude coordinates
    anomalies_gdf.set_crs(epsg=4326, inplace=True)
    
    # 4. Perform the Local Spatial Join
    # 'predicate="within"' tells Python to find every anomaly Point that is physically 
    # located inside a service zone Polygon boundary
    joined_gdf = gpd.sjoin(anomalies_gdf, zones_gdf, how="left", predicate="within")
    
    # 5. Clean up the output for the UI dashboard
    # Identify anomalies that fell outside all known utility polygons (e.g., bad GPS data)
    joined_gdf['zone_id'] = joined_gdf['zone_id'].fillna('OUT_OF_BOUNDS')
    
    # Convert back to a standard pandas DataFrame to pass into the scoring model and UI
    final_df = pd.DataFrame(joined_gdf.drop(columns='geometry'))
    
    return final_df

# Quick local test verification loop
if __name__ == "__main__":
    import os
    
    # Create the sample files programmatically if running standalone
    os.makedirs("sample_data", exist_ok=True)
    
    # Test execution assuming files exist
    try:
        triage_table = process_local_gis_triage(
            geojson_path="sample_data/utility_zones.geojson", 
            csv_path="sample_data/detected_anomalies.csv"
        )
        print("\n--- Processed Local Spatial Join Outputs ---")
        print(triage_table[['anomaly_id', 'latitude', 'longitude', 'zone_id', 'pressure_zone_psi']])
    except Exception as e:
        print(f"To run this example, save the geojson and csv files to the paths above. Error: {e}")