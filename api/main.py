import sys
import os
import sqlite3
import json
import pandas as pd
import geopandas as gpd
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from explainability.explainer import generate_explanation
except ImportError:
    # Safe fallback if explainer module is missing or not built yet
    def generate_explanation(zone, risk, reason):
        return {"ui_explanation_text": f"Anomaly: {reason}", "work_order_draft": f"Dispatch crew to {zone}."}

def run_nightly_triage():
    data_path = "sample_data"
    dfs = []

    if os.path.exists(data_path):
        files = [f for f in os.listdir(data_path)]
        if not files:
            return {"status": "empty", "processed": 0}
            
        for f in files:
            file_path = os.path.join(data_path, f)
            try:
                if f.endswith('.csv'):
                    dfs.append(pd.read_csv(file_path))
                elif f.endswith('.geojson'):
                    dfs.append(gpd.read_file(file_path))
                elif f.endswith('.json'):
                    with open(file_path, 'r') as json_file:
                        try: raw_json = json.load(json_file)
                        except json.JSONDecodeError: return {"status": "malformed_json", "processed": 0}
                    
                    if isinstance(raw_json, dict) and 'readings' in raw_json:
                        temp_df = pd.DataFrame(raw_json['readings'])
                        if 'sensor_array' in raw_json: temp_df['sensor_array'] = raw_json['sensor_array']
                        dfs.append(temp_df)
                    else:
                        dfs.append(pd.read_json(file_path))
                elif f.endswith('.txt'):
                    with open(file_path, 'r') as txt_file:
                        lines = txt_file.readlines()
                    text_rows = []
                    for line in lines:
                        if line.strip() and not line.startswith('#'):
                            parts = [p.strip() for p in line.split(',')]
                            if len(parts) >= 4:
                                text_rows.append({
                                    'sensor_id': parts[0], 'zone_id': parts[1],
                                    'flow_gallons_per_min': float(parts[2]) if parts[2].replace('.','',1).isdigit() else None,
                                    'db_level': float(parts[3]) if parts[3].replace('.','',1).isdigit() else None,
                                    'latitude': float(parts[4]) if len(parts) > 4 and parts[4].replace('.','',1).isdigit() else None,
                                    'longitude': float(parts[5]) if len(parts) > 5 and parts[5].replace('.','',1).isdigit() else None
                                })
                    if text_rows: dfs.append(pd.DataFrame(text_rows))
            except Exception as e:
                print(f"Skipping unreadable file {f}: {e}")

    if not dfs: return {"status": "unsuitable", "processed": 0}
    normalized_rows = []
    
    for table in dfs:
        table.columns = [str(c).lower().strip() for c in table.columns]
        for idx, row in table.iterrows():
            junction_id = row.get('sensor_id', row.get('anomaly_id', row.get('asset_id', None)))
            zone_id = row.get('zone_id', row.get('sensor_array', row.get('district', None)))
            if junction_id is None or pd.isna(junction_id):
                zone_label = str(zone_id) if zone_id is not None and not pd.isna(zone_id) else "Grid"
                junction_id = f"{zone_label}-Node-{idx+1}"

            normalized_rows.append({
                'junction_id': junction_id, 'zone_id': zone_id,
                'risk_score': row.get('risk_score', row.get('score', row.get('leak_probability', None))),
                'anomaly_reason': row.get('anomaly_reason', row.get('reason', row.get('description', row.get('notes', None)))),
                'lat': row.get('lat', row.get('latitude', None)), 'lon': row.get('lon', row.get('longitude', None)),
                'flow_gpm': row.get('flow_gallons_per_min', None), 'db_level': row.get('db_level', None),
                'classification': row.get('classification_guess', None)
            })

    conn = sqlite3.connect("mock_utility.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS triage_results (junction_id TEXT, zone_id TEXT, risk_score REAL, lat REAL, lon REAL, explanation TEXT, work_order TEXT, status TEXT)")
    cursor.execute("DELETE FROM triage_results")
    processed_count = 0
    
    for idx, row in enumerate(normalized_rows):
        junction = str(row['junction_id'])
        zone = str(row['zone_id']) if row['zone_id'] is not None and not pd.isna(row['zone_id']) else "System Grid"
        risk = 0.15
        reason = "Operational metrics within nominal boundaries."
        
        # Determine risk based on Flow or Acoustics
        if row['flow_gpm'] is not None and not pd.isna(row['flow_gpm']):
            flow = float(row['flow_gpm'])
            if flow > 60.0: risk, reason = 0.92, f"Critical nocturnal flow surge identified: {flow} GPM."
            elif 40.0 <= flow <= 60.0: risk, reason = 0.68, f"Moderate system boundary variance detected: {flow} GPM."
            else: risk, reason = 0.22, f"Nocturnal minimum flow rates nominal: {flow} GPM."
        elif row['db_level'] is not None and not pd.isna(row['db_level']):
            db = float(row['db_level'])
            sig = str(row['classification']).strip()
            if db > 75 or sig == "Continuous Hiss": risk, reason = 0.95, f"High-confidence structural hiss signature ({db} dB) detected."
            elif 50 <= db <= 75: risk, reason = 0.72, f"Elevated local acoustic amplitude profile ({db} dB): {sig}."
            else: risk, reason = 0.30, f"Baseline sound frequencies tracking normally ({db} dB)."
        else:
            try: risk = float(row['risk_score']) if row['risk_score'] is not None and not pd.isna(row['risk_score']) else 0.85
            except: risk = 0.85
            reason = str(row['anomaly_reason']) if row['anomaly_reason'] is not None and not pd.isna(row['anomaly_reason']) else "Acoustic variance flagged in logs."

        try: lat = float(row['lat']) if row['lat'] is not None and not pd.isna(row['lat']) else 42.283
        except: lat = 42.283
        try: lon = float(row['lon']) if row['lon'] is not None and not pd.isna(row['lon']) else -71.226
        except: lon = -71.226
        
        status_flag = "PENDING" if risk > 0.5 else "CLEAR"
        if risk > 0.5:
            try:
                ai_result = generate_explanation(zone, risk, reason)
                explanation_text = ai_result.get('ui_explanation_text', 'Explanation metrics pending.')
                work_order_text = ai_result.get('work_order_draft', 'Crew routing generation pending.')
            except Exception:
                explanation_text, work_order_text = f"Anomaly signature: {reason}", f"Dispatch crew to {zone}."
        else:
            explanation_text, work_order_text = f"System profile baseline stable: {reason}", "No deployment action required."
            
        cursor.execute("INSERT INTO triage_results VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (junction, zone, risk, lat, lon, explanation_text, work_order_text, status_flag))
        processed_count += 1
            
    conn.commit()
    conn.close()
    if os.path.exists(data_path):
        for f in os.listdir(data_path):
            try: os.remove(os.path.join(data_path, f))
            except: pass
    return {"status": "success", "processed": processed_count}