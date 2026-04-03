from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
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


def _build_binary_payload(analytics: TelemetryAnalytics) -> bytes:
    if analytics.res.empty:
        raise RuntimeError("Synchronized telemetry table is empty")

    frame = analytics.res[["E_m", "N_m", "U_m", "v_g"]].replace([np.inf, -np.inf], np.nan).dropna()
    if frame.empty:
        raise RuntimeError("Telemetry payload is empty after cleanup")

    points = frame.to_numpy(dtype="<f4", copy=True)
    count = int(points.shape[0])
    return struct.pack("<I", count) + points.tobytes(order="C")


def _build_json_trajectory(analytics: TelemetryAnalytics) -> list[dict[str, float]]:
    if analytics.res.empty:
        return []

    frame = analytics.res[["E_m", "N_m", "U_m", "v_g"]].replace([np.inf, -np.inf], np.nan).dropna()
    trajectory: list[dict[str, float]] = []
    for row in frame.itertuples(index=False):
        trajectory.append(
            {
                "x": float(row[0]),
                "y": float(row[1]),
                "h": float(row[2]),
                "s": float(row[3]),
            }
        )
    return trajectory

@app.get("/")
async def root():
    return {"message": "UAV Telemetry Analyzer is running"}

@app.post("/analyze")
async def analyze_telemetry(file: UploadFile = File(...)):
    safe_name = os.path.basename(file.filename)
    temp_path = DATA_DIR / safe_name
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        # 1. Parse DataFlash .BIN file (Pymavlink)
        parser = TelemetryParser(str(temp_path))
        pos_data, imu_data = parser.parse()
        
        # 2. Run Analytics (Haversine, ENU, Trapezoidal Integration)
        analytics = TelemetryAnalytics(pos_data, imu_data)
        metrics = analytics.get_stats()
        trajectory = _build_json_trajectory(analytics)
        
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
        if temp_path.exists():
            try:
                temp_path.unlink()
            except PermissionError:
                pass


@app.post("/analyze/bin")
async def analyze_telemetry_bin(file: UploadFile = File(...)):
    safe_name = os.path.basename(file.filename)
    temp_path = DATA_DIR / safe_name
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        parser = TelemetryParser(str(temp_path))
        pos_data, imu_data = parser.parse()
        analytics = TelemetryAnalytics(pos_data, imu_data)
        payload = _build_binary_payload(analytics)
        return Response(content=payload, media_type="application/octet-stream")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except PermissionError:
                pass
