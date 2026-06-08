import json
from google import genai
from pydantic import BaseModel, Field

# The SDK automatically finds GEMINI_API_KEY in your .env file
client = genai.Client()

class ZoneExplanation(BaseModel):
    ui_explanation_text: str = Field(description="One sentence explaining the risk to a dispatcher.")
    work_order_draft: str = Field(description="Draft text for the field crew work order.")

def generate_explanation(zone_id: str, risk_score: float, anomaly_reason: str) -> dict:
    """Uses Gemini to translate local data patterns into human explanations."""
    
    prompt = f"""
    You are a water utility operations assistant. Explain why this zone is flagged for a leak.
    Zone: {zone_id}
    Risk Score: {risk_score:.2f}
    Primary Anomaly Detected: {anomaly_reason}
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": ZoneExplanation,
        },
    )
    
    return json.loads(response.text)