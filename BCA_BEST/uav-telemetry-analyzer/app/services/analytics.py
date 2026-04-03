import numpy as np
import pandas as pd
import pyproj
from scipy.spatial.transform import Rotation
from scipy.integrate import cumulative_trapezoid
from scipy.signal import detrend
from ahrs.filters import Madgwick

#DataFrame["pos"] - gps data format [timeUS, lat, lon, alt]
#DataFrame["imu"] - imu data format [timeUS, a_x, a_y, a_z, g_x, g_y, g_z]

#createdData - format [time, x, y, h, v]

class TelemetryAnalytics:
    """Core mathematical analytics for flight logic."""
    def __init__(self, pos_data: pd.DataFrame, imu_data: pd.DataFrame):
        self.res = pd.DataFrame()
        self.pos_data = pos_data

        self.pos_data["timeS"] = self.pos_data["timeUS"]/1_000_000

        #converting deg to rad for haversine
        self.pos_data['lat_rad'] = np.deg2rad(self.pos_data['lat'])
        self.pos_data['lon_rad'] = np.deg2rad(self.pos_data['lon'])

        self.imu_data = imu_data
        self.imu_data["timeS"] = self.imu_data["timeUS"]/1_000_000

        #calculating sampling rate in Hz
        self.imu_sampling_rate_hertz = len(imu_data)/(imu_data['timeS'].iloc[-1] - imu_data['timeS'].iloc[0])
        self.pos_sampling_rate_hertz = len(pos_data)/(pos_data['timeS'].iloc[-1] - pos_data['timeS'].iloc[0])

        self._filter_gps_outliers()
        self._create_enu_cords()
        self._filter_enu_outliners_by_speed()

        self._haversine()
        self._calculate_gyro_quanterions()
        self._prepare_imu_acceleration()
        self._calculate_speed_vector()

        self._synchronize_imu_nearest()


    def _calculate_gyro_quanterions(self):
        #geting 3d array of gyro acceleration and dron acceleration
        gyr_array = self.imu_data[['g_x', 'g_y', 'g_z']].values
        acc_array = self.imu_data[['a_x', 'a_y', 'a_z']].values

        filter_madgwick = Madgwick(gyr=gyr_array, acc=acc_array, frequency=self.imu_sampling_rate_hertz)

        quaternions = filter_madgwick.Q

        #setting quanterion of rotation
        self.imu_data[['q_w', 'q_x', 'q_y', 'q_z']] = quaternions

    #rotates acceleration by quaterion and subtracts g
    def _prepare_imu_acceleration(self):
        qs = self.imu_data[['q_x', 'q_y', 'q_z', 'q_w']].values

        rotations = Rotation.from_quat(qs)

        acc_vectors = self.imu_data[['a_x', 'a_y', 'a_z']].to_numpy(copy=True)
        rotated_acc = rotations.apply(acc_vectors)

        self.imu_data[['a_x_global', 'a_y_global', 'a_z_global']] = rotated_acc
        self.imu_data['a_z_global'] -= 9.81

        self.imu_data['a_x_clean'] = detrend(self.imu_data['a_x_global'], type='linear')
        self.imu_data['a_y_clean'] = detrend(self.imu_data['a_y_global'], type='linear')
        self.imu_data['a_z_clean'] = detrend(self.imu_data['a_z_global'], type='linear')



    #integrates global acceleration for creating speed vector ( will be used to determine max horizontal and vertical speed)
    def _calculate_speed_vector(self):
        self.imu_data['v_x'] = cumulative_trapezoid(self.imu_data['a_x_clean'], self.imu_data['timeS'], initial=0)
        self.imu_data['v_y'] = cumulative_trapezoid(self.imu_data['a_y_clean'], self.imu_data['timeS'], initial=0)
        self.imu_data['v_z'] = cumulative_trapezoid(self.imu_data['a_z_clean'], self.imu_data['timeS'], initial=0)
        

        self.imu_data['v_h'] = np.sqrt(self.imu_data['v_x']**2 + self.imu_data['v_y']**2)
        self.imu_data['v_g'] = np.sqrt(self.imu_data['v_h']**2 + self.imu_data['v_z']**2)
        
    def _haversine(self):
        window = max(3, int(self.pos_sampling_rate_hertz * 0.5))
        lat_smooth = self.pos_data['lat_rad'].rolling(window=window, center=True, min_periods=1).mean()
        lon_smooth = self.pos_data['lon_rad'].rolling(window=window, center=True, min_periods=1).mean()

        R = 6371000.0  # Радіус Землі в метрах
        
        dlat = lat_smooth.diff()
        dlon = lon_smooth.diff()
        
        a = np.sin(dlat / 2.0)**2 + np.cos(lat_smooth.shift(1)) * np.cos(lat_smooth) * np.sin(dlon / 2.0)**2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
        
        self.pos_data['s'] = R * c

    def _synchronize_imu_nearest(self):
        pos = self.pos_data.sort_values("timeS")
        imu = self.imu_data.sort_values("timeS")

        self.res = pd.merge_asof(
            pos,
            imu,
            on="timeS",
            direction="nearest",
            tolerance=0.05,
        )

    #fixes gps errors
    #takes median of window (5s or 5el), then compare diff and if larger 0.005 (~500m at Ukraine's latitudes) removes it
    def _filter_gps_outliers(self):
        window = max(5, int(self.pos_sampling_rate_hertz * 5))
        
        rolling_lat = self.pos_data['lat'].rolling(window=window, center=True, min_periods=1).median()
        rolling_lon = self.pos_data['lon'].rolling(window=window, center=True, min_periods=1).median()
        
        lat_diff = np.abs(self.pos_data['lat'] - rolling_lat)
        lon_diff = np.abs(self.pos_data['lon'] - rolling_lon)
        
        mask = (lat_diff < 0.005) & (lon_diff < 0.005)
        
        old_len = len(self.pos_data)
        self.pos_data = self.pos_data[mask].reset_index(drop=True)

    #filters bad records by mesuring speed
    def _filter_enu_outliners_by_speed(self, max_speed_ms=120.0):
        dt = self.pos_data["timeS"].diff()
        de = self.pos_data["E_m"].diff()
        dn = self.pos_data["N_m"].diff()
        du = self.pos_data["U_m"].diff()

        speed = np.sqrt(de**2 + dn**2 + du**2) / dt

        mask = (speed < max_speed_ms) | (dt > 2.0)
        mask = mask.fillna(True)

        old_len = len(self.pos_data)
        self.pos_data = self.pos_data[mask].reset_index(drop=True)
    
    def _create_enu_cords(self):
        lat0 = self.pos_data['lat_rad'].iloc[0]
        lon0 = self.pos_data['lon_rad'].iloc[0]
        alt0 = self.pos_data['alt'].iloc[0]

        pipeline = (
            f"+proj=pipeline "
            f"+step +proj=cart +ellps=WGS84 "
            f"+step +proj=topocentric +ellps=WGS84 +lat_0={lat0} +lon_0={lon0} +h_0={alt0}"
        )
        
        transformer = pyproj.Transformer.from_pipeline(pipeline)

        e, n, u = transformer.transform(
            self.pos_data["lon_rad"].values,
            self.pos_data["lat_rad"].values,
            self.pos_data["alt"].values,
        )

        self.pos_data["E_m"] = e
        self.pos_data["N_m"] = n
        self.pos_data["U_m"] = u

    def get_stats(self) -> dict:
        max_speed = self.res['v_g'].max()
        max_vertical_speed = self.res['v_z'].max()
        max_horizontal_speed = np.sqrt(self.res['v_x']**2 + self.res['v_y']**2).max()

        max_acceleration = np.sqrt(self.res['a_x_global']**2 + self.res['a_y_global']**2 + self.res['a_z_global']**2).max()
        max_vertical_acceleration = self.res['a_z_global'].max()
        max_horizontal_acceleration = np.sqrt(self.res['a_x_global']**2 + self.res['a_y_global']**2).max()

        max_clean_acceleration = np.sqrt(self.res['a_x_clean']**2 + self.res['a_y_clean']**2 + self.res['a_z_clean']**2).max()
        max_vertical_clean_acceleration = self.res['a_z_clean'].max()
        max_horizontal_clean_acceleration = np.sqrt(self.res['a_x_clean']**2 + self.res['a_y_clean']**2).max()

        max_height = self.res['alt'].max()
        total_distance = self.res['s'].sum()

        total_time = self.res['timeS'].iloc[-1] - self.res['timeS'].iloc[0]
        return {
            "max_speed_ms": max_speed,
            "max_horizontal_speed_ms": max_horizontal_speed,
            "max_vertical_speed_ms": max_vertical_speed,
            "max_acceleration_ms2": max_acceleration,
            "max_horizontal_acceleration_ms2": max_horizontal_acceleration,
            "max_vertical_acceleration_ms2": max_vertical_acceleration,
            "max_clean_acceleration_ms2": max_clean_acceleration,
            "max_horizontal_clean_acceleration_ms2": max_horizontal_clean_acceleration,
            "max_vertical_clean_acceleration_ms2": max_vertical_clean_acceleration,
            "max_height_m": max_height,
            "total_distance_m": total_distance,
            "total_time_s": total_time
        }