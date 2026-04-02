from pydantic import BaseModel
from typing import List, Dict, Optional

class TelemetryPoint(BaseModel):
    timestamp: float
    lat: float
    lon: float
    alt: float
    vx: float
    vy: float
    vz: float
    ax: float
    ay: float
    az: float
    roll: float
    pitch: float
    yaw: float

class FlightMetrics(BaseModel):
    max_horizontal_speed: float
    max_vertical_speed: float
    max_acceleration: float
    max_altitude_gain: float
    total_distance: float # Calculated via Haversine
    duration: float
    
class ENUCoordinate(BaseModel):
    e: float # East
    n: float # North
    u: float # Up
    color: Optional[str] = None # Based on speed/time

class FlightAnalysisResponse(BaseModel):
    filename: str
    metrics: FlightMetrics
    trajectory: List[ENUCoordinate]
    ai_summary: str
