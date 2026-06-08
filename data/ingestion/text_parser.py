import os
from google import genai
from pydantic import BaseModel, Field

# Ensure you have your GOOGLE_API_KEY set in your environment variables
client = genai.Client()

class MaintenanceEvent(BaseModel):
    junction_id: str = Field(description="The ID of the junction or pipe segment")
    issue_type: str = Field(description="Nature of the issue, e.g., Leak, Corrosion")
    repair_action: str = Field(description="What action was taken by the crew")

class ExtractionResult(BaseModel):
    events: list[MaintenanceEvent]

def extract_work_orders_from_text(raw_text: str) -> dict:
    """Passes raw field notes to Gemini to extract structured maintenance data."""
    
    prompt = f"Extract all maintenance events from this field report:\n\n{raw_text}"
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": ExtractionResult,
        },
    )
    
    return response.text # Returns validated JSON string