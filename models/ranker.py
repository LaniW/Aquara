import xgboost as xgb
import pandas as pd

def score_zones(features_df: pd.DataFrame) -> pd.DataFrame:
    """Scores areas and returns top contributing features for the explainer."""
    
    # Features model will use
    cols_to_use = ['pipe_age_yrs', 'night_flow_anomaly', 'material_Cast Iron', 'material_PVC', 'material_Ductile Iron']
    X = features_df[cols_to_use].copy()
    
    # MOCK MODEL TRAINING: In production, load a pre-trained model
    # Target: 1 = Leak confirmed, 0 = No leak
    y_dummy = [1, 0, 0] 
    
    model = xgb.XGBClassifier(n_estimators=10, max_depth=3)
    model.fit(X, y_dummy)
    
    # Predict probabilities
    features_df['risk_score'] = model.predict_proba(X)[:, 1]
    
    # Extract top reasons mathematically (Mocking SHAP values/feature importance for simplicity)
    # In a real app, you'd calculate SHAP values per row to see exactly WHY a specific row flagged.
    def get_top_reasons(row):
        if row['night_flow_anomaly'] > 100:
            return {'primary': 'High night flow', 'secondary': f'Pipe age ({row["pipe_age_yrs"]} yrs)'}
        return {'primary': 'Standard wear', 'secondary': 'None'}
        
    features_df['raw_model_reasons'] = features_df.apply(get_top_reasons, axis=1)
    
    # Sort by highest risk
    ranked_df = features_df.sort_values(by='risk_score', ascending=False)
    return ranked_df