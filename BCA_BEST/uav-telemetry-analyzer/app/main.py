import json

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from app.services.parser import TelemetryParser
from app.services.analytics import TelemetryAnalytics
from app.services.ai_engine import AIEngine
import shutil
import os
import struct
import numpy as np
from pathlib import Path

app = FastAPI(title="UAV Telemetry Analyzer API")

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _build_combined_payload(analytics: TelemetryAnalytics, metrics: dict, ai_summary: str) -> bytes:
    if analytics.res.empty:
        raise RuntimeError("Synchronized telemetry table is empty")

    frame = analytics.res[["E_m", "N_m", "U_m", "v_g"]].replace([np.inf, -np.inf], np.nan).dropna()
    if frame.empty:
        raise RuntimeError("Telemetry payload is empty after cleanup")

    points = frame.to_numpy(dtype="<f4", copy=True)
    count = int(points.shape[0])
    
    binary_points = struct.pack("<I", count) + points.tobytes(order="C")

    metadata = {
        "filename": analytics.filename if hasattr(analytics, 'filename') else "telemetry.bin",
        "metrics": metrics,
        "ai_summary": ai_summary
    }
    json_bytes = json.dumps(metadata).encode("utf-8")
    json_length = len(json_bytes)

    header = struct.pack("<I", json_length)

    return header + json_bytes + binary_points


@app.post("/analyze/optimized")
async def analyze_telemetry_optimized(file: UploadFile = File(...)):
    safe_name = os.path.basename(file.filename)
    temp_path = DATA_DIR / safe_name
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        parser = TelemetryParser(str(temp_path))
        pos_data, imu_data = parser.parse()

        analytics = TelemetryAnalytics(pos_data, imu_data)
        metrics = analytics.get_stats()
        
        ai = AIEngine()
        ai_summary = await ai.get_flight_summary(metrics)
        
        payload = _build_combined_payload(analytics, metrics, ai_summary)
        
        return Response(content=payload, media_type="application/octet-stream")
        
    except Exception as e:

        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except PermissionError:
                pass



FRONTEND_DIR = Path(__file__).parent / "frontend_dist"

app.mount("/_nuxt", StaticFiles(directory=str(FRONTEND_DIR / "_nuxt")), name="nuxt_assets")
app.mount("/_fonts", StaticFiles(directory=str(FRONTEND_DIR / "_fonts")), name="fonts_assets")

@app.get("/favicon.ico")
async def favicon():
    return FileResponse(FRONTEND_DIR / "favicon.ico")

@app.get("/{catchall:path}")
async def serve_frontend(catchall: str):
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"error": "Frontend build not found"}