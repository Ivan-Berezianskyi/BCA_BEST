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


class ScriptTelemetryAnalytics(TelemetryAnalytics):
    """TelemetryAnalytics variant with robust local ECEF->ENU conversion."""

    def _create_enu_cords(self):
        lat_deg = self.pos_data["lat"].to_numpy(dtype=np.float64)
        lon_deg = self.pos_data["lon"].to_numpy(dtype=np.float64)
        alt_m = self.pos_data["alt"].to_numpy(dtype=np.float64)

        lat = np.deg2rad(lat_deg)
        lon = np.deg2rad(lon_deg)

        # WGS84 ellipsoid constants.
        a = 6378137.0
        f = 1.0 / 298.257223563
        e2 = f * (2.0 - f)

        sin_lat = np.sin(lat)
        cos_lat = np.cos(lat)
        sin_lon = np.sin(lon)
        cos_lon = np.cos(lon)

        N = a / np.sqrt(1.0 - e2 * sin_lat**2)

        x = (N + alt_m) * cos_lat * cos_lon
        y = (N + alt_m) * cos_lat * sin_lon
        z = (N * (1.0 - e2) + alt_m) * sin_lat

        lat0 = lat[0]
        lon0 = lon[0]
        alt0 = alt_m[0]

        sin_lat0 = np.sin(lat0)
        cos_lat0 = np.cos(lat0)
        sin_lon0 = np.sin(lon0)
        cos_lon0 = np.cos(lon0)

        N0 = a / np.sqrt(1.0 - e2 * sin_lat0**2)
        x0 = (N0 + alt0) * cos_lat0 * cos_lon0
        y0 = (N0 + alt0) * cos_lat0 * sin_lon0
        z0 = (N0 * (1.0 - e2) + alt0) * sin_lat0

        dx = x - x0
        dy = y - y0
        dz = z - z0

        e = -sin_lon0 * dx + cos_lon0 * dy
        n = -sin_lat0 * cos_lon0 * dx - sin_lat0 * sin_lon0 * dy + cos_lat0 * dz
        u = cos_lat0 * cos_lon0 * dx + cos_lat0 * sin_lon0 * dy + sin_lat0 * dz

        self.pos_data["E_m"] = e
        self.pos_data["N_m"] = n
        self.pos_data["U_m"] = u

    def _synchronize_imu_nearest(self):
        pos_idx = self.pos_data.set_index("timeS")
        imu_idx = self.imu_data.set_index("timeS")

        # Avoid duplicate non-index columns during join.
        imu_idx = imu_idx.drop(columns=["timeUS"], errors="ignore")

        combined = pos_idx.join(imu_idx, how="outer")
        combined = combined.sort_index().interpolate(method="index")
        self.res = combined.dropna(subset=["lat"]).reset_index()


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
            "s": data["v"],
        }
    )

    payload = payload.replace([np.inf, -np.inf], np.nan).dropna()
    payload.to_csv("./out.csv")

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