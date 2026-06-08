import pandas as pd
from datetime import datetime

def engineer_features(gis_df: pd.DataFrame) -> pd.DataFrame:
    """Calculates risk factors like age and sustained night flow."""
    
    current_year = datetime.now().year
    
    # Calculate static features
    gis_df['pipe_age_yrs'] = current_year - gis_df['install_year']
    
    # Mocking Dynamic AMI Data (In production, group 15-min reads by zone)
    # e.g., calculating minimum night flow between 2 AM and 4 AM
    ami_flow_anomalies = {
        'Zone_A': 350.5, # High deviation from baseline (gal/hr)
        'Zone_B': 12.0   # Normal
    }
    
    # Merge dynamic signals with static data
    gis_df['night_flow_anomaly'] = gis_df['zone_id'].map(ami_flow_anomalies)
    
    # One-hot encode materials for XGBoost
    gis_df = pd.get_dummies(gis_df, columns=['material'])
    
    return gis_df