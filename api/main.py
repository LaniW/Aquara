import sys
import os
import sqlite3
import json
import pandas as pd
import geopandas as gpd

# Make dotenv optional so Cloud deployment doesn't crash
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from explainability.explainer import generate_explanation
except ImportError:
    def generate_explanation(zone, risk, reason):
        return {"ui_explanation_text": f"Anomaly: {reason}", "work_order_draft": f"Dispatch crew to {zone}."}


def _coerce_float(val):
    """Safely convert a value to float, returning None on failure."""
    try:
        f = float(val)
        return f if pd.notna(f) else None
    except (TypeError, ValueError):
        return None


def _pick(row, *keys):
    """Return the first non-null value found among the given keys."""
    for k in keys:
        v = row.get(k)
        if v is not None and not (isinstance(v, float) and pd.isna(v)) and str(v).strip() not in ('', 'nan', 'None'):
            return v
    return None


def run_nightly_triage():
    data_path = "sample_data"
    dfs = []

    if os.path.exists(data_path):
        files = [f for f in os.listdir(data_path) if not f.startswith('.')]
        if not files:
            return {"status": "empty", "processed": 0}

        for f in files:
            file_path = os.path.join(data_path, f)
            try:
                if f.endswith('.geojson'):
                    dfs.append(gpd.read_file(file_path))

                elif f.endswith('.json'):
                    with open(file_path, 'r') as json_file:
                        try:
                            raw_json = json.load(json_file)
                        except json.JSONDecodeError:
                            return {"status": "malformed_json", "processed": 0}
                    # Support {readings: [...]} envelope or bare array/object
                    if isinstance(raw_json, dict) and 'readings' in raw_json:
                        temp_df = pd.DataFrame(raw_json['readings'])
                        for meta_key in ('sensor_array', 'dataset_name', 'region'):
                            if meta_key in raw_json:
                                temp_df[meta_key] = raw_json[meta_key]
                    elif isinstance(raw_json, list):
                        temp_df = pd.DataFrame(raw_json)
                    else:
                        temp_df = pd.DataFrame([raw_json])
                    dfs.append(temp_df)

                else:
                    # .csv and .txt: both handled as CSV (header row aware)
                    dfs.append(pd.read_csv(file_path))

            except Exception as e:
                print(f"Skipping unreadable file {f}: {e}")

    if not dfs:
        return {"status": "unsuitable", "processed": 0}

    normalized_rows = []

    for table in dfs:
        table.columns = [str(c).lower().strip() for c in table.columns]

        for idx, row in table.iterrows():
            # ── ID fields ────────────────────────────────────────────────────
            junction_id = _pick(row,
                'location_code',  # London JSON, Sydney TXT, less_rows.csv
                'sensor_id', 'node_id', 'junction_id', 'asset_id', 'anomaly_id',
            )

            # Prefer an explicit zone column; fall back to composing Zone/Block/Pipe
            zone_id = _pick(row, 'zone_id', 'sensor_array', 'district', 'region', 'area')
            if not zone_id:
                parts = [_pick(row, 'zone'), _pick(row, 'block'), _pick(row, 'pipe')]
                parts = [str(p) for p in parts if p]
                zone_id = ' / '.join(parts) if parts else None

            if not junction_id:
                zone_label = str(zone_id) if zone_id else 'Grid'
                junction_id = f'{zone_label}-Node-{idx + 1}'

            # ── Numeric telemetry ─────────────────────────────────────────────
            lat = _coerce_float(_pick(row, 'lat', 'latitude'))
            lon = _coerce_float(_pick(row, 'lon', 'longitude'))
            flow_gpm = _coerce_float(_pick(row,
                'flow_rate_lmin',
                'flow_gallons_per_min', 'flow_gpm', 'flow',
            ))
            db_level = _coerce_float(_pick(row, 'db_level', 'db', 'decibels'))

            # ── Risk / reason ─────────────────────────────────────────────────
            risk_score     = _coerce_float(_pick(row, 'risk_score', 'score', 'leak_probability'))
            anomaly_reason = _pick(row, 'anomaly_reason', 'notes', 'reason', 'description', 'alert')
            classification = _pick(row, 'classification_guess', 'classification', 'class', 'label')
            leakage_flag   = _coerce_float(_pick(row, 'leakage_flag', 'leak_flag', 'flag'))

            normalized_rows.append({
                'junction_id':   junction_id,
                'zone_id':       zone_id,
                'risk_score':    risk_score,
                'anomaly_reason': anomaly_reason,
                'lat':           lat,
                'lon':           lon,
                'flow_gpm':      flow_gpm,
                'db_level':      db_level,
                'classification': classification,
                'leakage_flag':  leakage_flag,
                'pressure_psi':  _coerce_float(_pick(row, 'pressure_psi', 'pressure')),
            })

    # Pre-compute flow range once across all rows for relative scoring
    all_flows  = [r['flow_gpm'] for r in normalized_rows if r.get('flow_gpm') is not None]
    flow_min   = min(all_flows) if all_flows else None
    flow_max   = max(all_flows) if all_flows else None
    flow_range = (flow_max - flow_min) if (flow_min is not None and flow_max != flow_min) else None

    conn = sqlite3.connect("mock_utility.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS triage_results (junction_id TEXT, zone_id TEXT, risk_score REAL, lat REAL, lon REAL, explanation TEXT, work_order TEXT, status TEXT)")
    cursor.execute("DELETE FROM triage_results")
    processed_count = 0

    for idx, row in enumerate(normalized_rows):
        junction     = str(row['junction_id'])
        zone         = str(row['zone_id']) if row['zone_id'] else "System Grid"
        risk         = 0.15
        reason       = "Operational metrics within nominal boundaries."

        leakage_flag = row.get('leakage_flag')
        flow         = row.get('flow_gpm')
        db           = row.get('db_level')
        pressure     = row.get('pressure_psi')
        sig          = str(row.get('classification') or '').strip()
        anomaly_note = str(row.get('anomaly_reason') or '').strip()

        if leakage_flag == 1.0:
            # Explicit rupture flag — always critical
            risk   = 0.95
            reason = anomaly_note if anomaly_note else "Leakage flag set: pipeline rupture or confirmed breach."

        elif flow is not None:
            # Score relative to this dataset's own flow range so thresholds
            # adapt regardless of units (GPM, L/min, etc.)
            if flow_range:
                flow_norm = (flow - flow_min) / flow_range
            else:
                flow_norm = 0.5  # single unique value — treat as mid-range
            if flow_norm >= 0.75:
                risk, reason = 0.92, f"High flow rate relative to dataset: {flow:.1f} (top quartile)."
            elif flow_norm >= 0.40:
                risk, reason = 0.65, f"Elevated flow rate: {flow:.1f} (mid-range variance)."
            else:
                risk, reason = 0.22, f"Flow rate nominal: {flow:.1f} (lower range)."

        elif db is not None:
            if db > 75 or sig == "Continuous Hiss":
                risk, reason = 0.95, f"High-confidence structural hiss signature ({db} dB) detected."
            elif db >= 50:
                risk, reason = 0.72, f"Elevated acoustic profile ({db} dB): {sig or 'unclassified'}."
            else:
                risk, reason = 0.30, f"Baseline acoustics normal ({db} dB)."

        elif pressure is not None:
            if pressure < 30.0:
                risk, reason = 0.88, f"Critically low pressure detected: {pressure} PSI (baseline ~65 PSI)."
            elif pressure < 55.0:
                risk, reason = 0.62, f"Pressure anomaly: {pressure} PSI below normal baseline."
            else:
                risk, reason = 0.20, f"Pressure nominal: {pressure} PSI."

        else:
            pre_scored = row.get('risk_score')
            risk       = float(pre_scored) if pre_scored is not None else 0.85
            reason     = anomaly_note if anomaly_note else "Acoustic variance flagged in logs."

        # Coordinates — no hardcoded fallback; None stored if missing
        lat = row.get('lat')
        lon = row.get('lon')

        status_flag = "PENDING" if risk > 0.5 else "CLEAR"
        if risk > 0.5:
            try:
                ai_result        = generate_explanation(zone, risk, reason)
                explanation_text = ai_result.get('ui_explanation_text', 'Explanation metrics pending.')
                work_order_text  = ai_result.get('work_order_draft', 'Crew routing generation pending.')
            except Exception:
                explanation_text = f"Anomaly signature: {reason}"
                work_order_text  = f"Dispatch crew to {zone}."
        else:
            explanation_text = f"System profile baseline stable: {reason}"
            work_order_text  = "No deployment action required."

        cursor.execute(
            "INSERT INTO triage_results VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (junction, zone, risk, lat, lon, explanation_text, work_order_text, status_flag)
        )
        processed_count += 1

    conn.commit()
    conn.close()

    if os.path.exists(data_path):
        for f in os.listdir(data_path):
            try:
                os.remove(os.path.join(data_path, f))
            except Exception:
                pass

    return {"status": "success", "processed": processed_count}