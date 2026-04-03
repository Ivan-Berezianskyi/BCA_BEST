#!/usr/bin/env python3
"""Convert ArduPilot DataFlash log into UI-ready binary payload.

Output format (little-endian):
    u32 count
    repeated count times: [f32 x, f32 y, f32 h, f32 s]
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pymavlink import mavutil

# Allow running script from any working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.analytics import TelemetryAnalytics


def _pick_first(data: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _extract_time_us(data: dict[str, Any]) -> int | None:
    time_us = _pick_first(data, ("TimeUS", "timeUS", "time_us"))
    if time_us is not None:
        return int(time_us)

    time_ms = _pick_first(data, ("TimeMS", "TimeMs", "timeMS", "time_ms"))
    if time_ms is not None:
        return int(time_ms * 1000)

    return None


def _normalize_lat_lon(value: float, lon: bool = False) -> float:
    # DataFlash often stores GPS as int32 in degE7.
    if abs(value) > (180.0 if lon else 90.0):
        return value / 1e7
    return value


def _normalize_alt(value: float) -> float:
    # Some logs store altitude in centimeters.
    if abs(value) > 50000:
        return value / 100.0
    return value


def _extract_acc(data: dict[str, Any]) -> tuple[float, float, float] | None:
    accx = _pick_first(data, ("AccX", "a_x", "XAcc"))
    accy = _pick_first(data, ("AccY", "a_y", "YAcc"))
    accz = _pick_first(data, ("AccZ", "a_z", "ZAcc"))
    if accx is not None and accy is not None and accz is not None:
        return (accx, accy, accz)

    # MAVLink RAW_IMU xacc/yacc/zacc are typically milli-g.
    xacc = _pick_first(data, ("xacc", "XACC"))
    yacc = _pick_first(data, ("yacc", "YACC"))
    zacc = _pick_first(data, ("zacc", "ZACC"))
    if xacc is None or yacc is None or zacc is None:
        return None

    scale = 9.80665 / 1000.0
    return (xacc * scale, yacc * scale, zacc * scale)


def _extract_gyr(data: dict[str, Any]) -> tuple[float, float, float] | None:
    gyrx = _pick_first(data, ("GyrX", "g_x", "XGyro"))
    gyry = _pick_first(data, ("GyrY", "g_y", "YGyro"))
    gyrz = _pick_first(data, ("GyrZ", "g_z", "ZGyro"))
    if gyrx is not None and gyry is not None and gyrz is not None:
        return (gyrx, gyry, gyrz)

    # MAVLink RAW_IMU xgyro/ygyro/zgyro are typically millirad/s.
    xgyro = _pick_first(data, ("xgyro", "XGYRO"))
    ygyro = _pick_first(data, ("ygyro", "YGYRO"))
    zgyro = _pick_first(data, ("zgyro", "ZGYRO"))
    if xgyro is None or ygyro is None or zgyro is None:
        return None

    scale = 1.0 / 1000.0
    return (xgyro * scale, ygyro * scale, zgyro * scale)


def parse_ardupilot_log(log_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    connection = mavutil.mavlink_connection(str(log_path), dialect="ardupilotmega")

    gps_rows: list[dict[str, float | int]] = []
    imu_rows: list[dict[str, float | int]] = []

    while True:
        message = connection.recv_match(blocking=False)
        if message is None:
            break

        if message.get_type() == "BAD_DATA":
            continue

        data = message.to_dict()
        time_us = _extract_time_us(data)
        if time_us is None:
            continue

        lat_raw = _pick_first(data, ("Lat", "lat", "LAT"))
        lon_raw = _pick_first(data, ("Lng", "Lon", "lon", "LON"))
        alt_raw = _pick_first(data, ("Alt", "alt", "ALT", "RelAlt", "AltMSL"))

        if lat_raw is not None and lon_raw is not None and alt_raw is not None:
            lat = _normalize_lat_lon(lat_raw, lon=False)
            lon = _normalize_lat_lon(lon_raw, lon=True)
            alt = _normalize_alt(alt_raw)
            if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
                gps_rows.append({"timeUS": time_us, "lat": lat, "lon": lon, "alt": alt})

        acc = _extract_acc(data)
        gyr = _extract_gyr(data)
        if acc is not None and gyr is not None:
            imu_rows.append(
                {
                    "timeUS": time_us,
                    "a_x": acc[0],
                    "a_y": acc[1],
                    "a_z": acc[2],
                    "g_x": gyr[0],
                    "g_y": gyr[1],
                    "g_z": gyr[2],
                }
            )

    if not gps_rows:
        raise RuntimeError("No GPS rows were extracted from log.")
    if not imu_rows:
        raise RuntimeError("No IMU rows were extracted from log.")

    pos_df = pd.DataFrame(gps_rows).sort_values("timeUS").drop_duplicates("timeUS")
    imu_df = pd.DataFrame(imu_rows).sort_values("timeUS").drop_duplicates("timeUS")

    if len(pos_df) < 2:
        raise RuntimeError("Not enough GPS points for analytics (need at least 2).")
    if len(imu_df) < 2:
        raise RuntimeError("Not enough IMU points for analytics (need at least 2).")

    pos_df.to_csv("./pos.csv")
    imu_df.to_csv("./imu.csv")


    return pos_df, imu_df


def build_ui_payload(analytics: TelemetryAnalytics) -> pd.DataFrame:
    # TelemetryAnalytics currently resets `res` at the end of __init__,
    # so we explicitly rebuild synchronization here.

    if analytics.res.empty:
        raise RuntimeError("Synchronized telemetry table is empty.")

    data = analytics.res.copy()

    payload = pd.DataFrame(
        {
            "x": data["E_m"],
            "y": data["N_m"],
            "h": data["U_m"],
            "s": data["v_g"],
        }
    )

    payload = payload.replace([np.inf, -np.inf], np.nan).dropna()
    payload.to_csv("./out.csv")
    print(analytics.get_stats())

    if payload.empty:
        raise RuntimeError("Payload is empty after cleanup.")

    return payload


def write_ui_bin(payload: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    points = payload[["x", "y", "h", "s"]].to_numpy(dtype="<f4", copy=True)
    count = int(points.shape[0])

    with output_path.open("wb") as f:
        f.write(struct.pack("<I", count))
        f.write(points.tobytes(order="C"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert ArduPilot log (.BIN) to UI binary (u32 + repeated f32 x,y,h,s)."
    )
    parser.add_argument("input_log", type=Path, help="Path to ArduPilot DataFlash .BIN log")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("data/binaryfiles/ui_trajectory.bin"),
        help="Output path for UI .bin payload",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_log: Path = args.input_log
    output_path: Path = args.output

    if not input_log.exists():
        raise FileNotFoundError(f"Input log not found: {input_log}")

    pos_df, imu_df = parse_ardupilot_log(input_log)
    analytics = TelemetryAnalytics(pos_df, imu_df)
    analytics.res.to_csv("res_res.csv")
    payload = build_ui_payload(analytics)
    write_ui_bin(payload, output_path)

    print(f"Input log: {input_log}")
    print(f"GPS rows: {len(pos_df)}")
    print(f"IMU rows: {len(imu_df)}")
    print(f"Output points: {len(payload)}")
    print(f"Wrote: {output_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())