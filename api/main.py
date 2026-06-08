import sys
import os
import sqlite3
import pandas as pd
import geopandas as gpd
from dotenv import load_dotenv

# Load Gemini API Key
load_dotenv()

# Ensure internal folders are discoverable
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from explainability.explainer import generate_explanation

def run_nightly_triage():
    data_path = "sample_data"
    dfs = []

    # 1. Detect and load files
    if os.path.exists(data_path):
        for f in os.listdir(data_path):
            file_path = os.path.join(data_path, f)
            try:
                if f.endswith('.csv'):
                    dfs.append(pd.read_csv(file_path))
                elif f.endswith(('.json', '.geojson')):
                    dfs.append(gpd.read_file(file_path))
            except Exception as e:
                print(f"Skipping {f} due to error: {e}")

    if not dfs: return {"status": "success", "high_risk_zones_processed": 0}
    
    # 2. Combine data and safely extract coordinates
    df = pd.concat(dfs, ignore_index=True)
    
    # Safely convert to GeoDataFrame if geometry exists
    if 'geometry' in df.columns:
        gdf = gpd.GeoDataFrame(df, geometry='geometry')
        # Use .representative_point() to get coordinates from Polygons OR Points safely
        df['lat'] = gdf.geometry.representative_point().y
        df['lon'] = gdf.geometry.representative_point().x
    
    # 3. SQLite setup (rest remains standard)
    conn = sqlite3.connect("mock_utility.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS triage_results (junction_id TEXT, zone_id TEXT, risk_score REAL, lat REAL, lon REAL, explanation TEXT, work_order TEXT, status TEXT)")
    cursor.execute("DELETE FROM triage_results")
    
    # 4. Process
    processed_count = 0
    for idx, row in df.iterrows():
        zone = str(row.get('zone_id', f'Zone-{idx}'))
        junction = str(row.get('junction_id', f'Asset-{idx}'))
        reason = str(row.get('anomaly_reason', 'Anomaly detected.'))
        
        try: risk = float(row.get('risk_score', 0.85))
        except: risk = 0.85
        try: lat = float(row.get('lat', 42.28))
        except: lat = 42.28
        try: lon = float(row.get('lon', -71.22))
        except: lon = -71.22
        
        if risk > 0.5:
            try:
                ai_result = generate_explanation(zone, risk, reason)
                explanation_text = ai_result.get('ui_explanation_text', 'Explanation unavailable.')
                work_order_text = ai_result.get('work_order_draft', 'Draft unavailable.')
            except:
                explanation_text = f"Anomaly: {reason}"
                work_order_text = f"Investigate {zone}."
            
            cursor.execute("INSERT INTO triage_results VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING')",
                           (junction, zone, risk, lat, lon, explanation_text, work_order_text))
            processed_count += 1
            
    conn.commit()
    conn.close()

    # 5. Cleanup
    if os.path.exists(data_path):
        for f in os.listdir(data_path):
            try: os.remove(os.path.join(data_path, f))
            except: pass
    
    return {"status": "success", "high_risk_zones_processed": processed_count}