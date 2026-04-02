from fastapi import FastAPI, UploadFile, File, HTTPException
from app.services.parser import TelemetryParser
from app.services.analytics import TelemetryAnalytics
from app.services.ai_engine import AIEngine
import shutil
import os

app = FastAPI(title="UAV Telemetry Analyzer API")

@app.get("/")
async def root():
    return {"message": "UAV Telemetry Analyzer is running"}

@app.post("/analyze")
async def analyze_telemetry(file: UploadFile = File(...)):
    # Save temporary file
    temp_path = f"data/{file.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        # 1. Parse .bin file (Pymavlink)
        parser = TelemetryParser(temp_path)
        raw_data = parser.parse()
        
        # 2. Run Analytics (Haversine, ENU, Trapezoidal Integration)
        analytics = TelemetryAnalytics(raw_data)
        metrics = analytics.calculate_metrics()
        trajectory = analytics.get_enu_trajectory()
        
        # 3. AI Insight
        ai = AIEngine()
        ai_summary = await ai.get_flight_summary(metrics)
        
        return {
            "filename": file.filename,
            "metrics": metrics,
            "trajectory": trajectory,
            "ai_summary": ai_summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
