from pymavlink import mavutil
import pandas as pd
from typing import Any

class TelemetryParser:
    """Parser for Ardupilot binary .bin files using Pymavlink."""
    def __init__(self, file_path: str):
        self.file_path = file_path

    def _pick_first(self, data: dict[str, Any], keys: tuple[str, ...]) -> float | None:
        for key in keys:
            value = data.get(key)
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return None

    def _extract_time_us(self, data: dict[str, Any]) -> int | None:
        time_us = self._pick_first(data, ("TimeUS", "timeUS", "time_us"))
        if time_us is not None:
            return int(time_us)

        time_ms = self._pick_first(data, ("TimeMS", "TimeMs", "timeMS", "time_ms"))
        if time_ms is not None:
            return int(time_ms * 1000)

        return None

    def _normalize_lat_lon(self, value: float, lon: bool = False) -> float:
        if abs(value) > (180.0 if lon else 90.0):
            return value / 1e7
        return value

    def _normalize_alt(self, value: float) -> float:
        if abs(value) > 50000:
            return value / 100.0
        return value

    def _extract_acc(self, data: dict[str, Any]) -> tuple[float, float, float] | None:
        accx = self._pick_first(data, ("AccX", "a_x", "XAcc"))
        accy = self._pick_first(data, ("AccY", "a_y", "YAcc"))
        accz = self._pick_first(data, ("AccZ", "a_z", "ZAcc"))
        if accx is not None and accy is not None and accz is not None:
            return (accx, accy, accz)

        xacc = self._pick_first(data, ("xacc", "XACC"))
        yacc = self._pick_first(data, ("yacc", "YACC"))
        zacc = self._pick_first(data, ("zacc", "ZACC"))
        if xacc is None or yacc is None or zacc is None:
            return None

        scale = 9.80665 / 1000.0
        return (xacc * scale, yacc * scale, zacc * scale)

    def _extract_gyr(self, data: dict[str, Any]) -> tuple[float, float, float] | None:
        gyrx = self._pick_first(data, ("GyrX", "g_x", "XGyro"))
        gyry = self._pick_first(data, ("GyrY", "g_y", "YGyro"))
        gyrz = self._pick_first(data, ("GyrZ", "g_z", "ZGyro"))
        if gyrx is not None and gyry is not None and gyrz is not None:
            return (gyrx, gyry, gyrz)

        xgyro = self._pick_first(data, ("xgyro", "XGYRO"))
        ygyro = self._pick_first(data, ("ygyro", "YGYRO"))
        zgyro = self._pick_first(data, ("zgyro", "ZGYRO"))
        if xgyro is None or ygyro is None or zgyro is None:
            return None

        scale = 1.0 / 1000.0
        return (xgyro * scale, ygyro * scale, zgyro * scale)
        
    def parse(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Parses DataFlash/MAVLink log into GPS and IMU tables."""
        connection = mavutil.mavlink_connection(self.file_path, dialect="ardupilotmega")

        gps_rows: list[dict[str, float | int]] = []
        imu_rows: list[dict[str, float | int]] = []

        try:
            while True:
                message = connection.recv_match(blocking=False)
                if message is None:
                    break

                if message.get_type() == "BAD_DATA":
                    continue

                data = message.to_dict()
                time_us = self._extract_time_us(data)
                if time_us is None:
                    continue

                lat_raw = self._pick_first(data, ("Lat", "lat", "LAT"))
                lon_raw = self._pick_first(data, ("Lng", "Lon", "lon", "LON"))
                alt_raw = self._pick_first(data, ("Alt", "alt", "ALT", "RelAlt", "AltMSL"))
                if lat_raw is not None and lon_raw is not None and alt_raw is not None:
                    lat = self._normalize_lat_lon(lat_raw, lon=False)
                    lon = self._normalize_lat_lon(lon_raw, lon=True)
                    alt = self._normalize_alt(alt_raw)
                    if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
                        gps_rows.append({"timeUS": time_us, "lat": lat, "lon": lon, "alt": alt})

                acc = self._extract_acc(data)
                gyr = self._extract_gyr(data)
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
        finally:
            close_method = getattr(connection, "close", None)
            if callable(close_method):
                close_method()

        if not gps_rows:
            raise RuntimeError("No GPS rows were extracted from log")
        if not imu_rows:
            raise RuntimeError("No IMU rows were extracted from log")

        pos_df = pd.DataFrame(gps_rows).sort_values("timeUS").drop_duplicates("timeUS")
        imu_df = pd.DataFrame(imu_rows).sort_values("timeUS").drop_duplicates("timeUS")

        if len(pos_df) < 2:
            raise RuntimeError("Not enough GPS points for analytics")
        if len(imu_df) < 2:
            raise RuntimeError("Not enough IMU points for analytics")

        return pos_df, imu_df
