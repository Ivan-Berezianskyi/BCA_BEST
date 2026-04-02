import numpy as np
import pandas as pd
import pyproj
from scipy.spatial.transform import Rotation
from scipy.integrate import cumulative_trapezoid
from ahrs.filters import Madgwick

#DataFrame["pos"] - gps data format [timeUS, lat, lon, alt]
#DataFrame["imu"] - imu data format [timeUS, a_x, a_y, a_z, g_x, g_y, g_z]

#createdData - format [time, x, y, h, v]

class TelemetryAnalytics:
    """Core mathematical analytics for flight logic."""
    def __init__(self, pos_data: pd.DataFrame, imu_data: pd.DataFrame):
        self.res = pd.DataFrame()
        self.pos_data = pos_data
        self.pos_data[['lat', 'lon', 'alt']] = self.pos_data[['lat', 'lon', 'alt']].replace(0.0, np.nan).ffill()

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

        print(1)
        self._calculate_gyro_quanterions()
        print(2)
        self._prepare_imu_acceleration()
        print(3)
        self._calculate_speed_vector()
        print(4)
        self._create_enu_cords()
        print(5)
        self._synchronize_imu_nearest()
        print(6)
        self.res["v"] = np.sqrt(np.pow(self.res["v_x"],2)+np.pow(self.res["v_y"],2)+np.pow(self.res["v_z"],2))


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

        self.imu_data['a_z_global'] -= 9.8

    #integrates global acceleration for creating speed vector ( will be used to determine max horizontal and vertical speed)
    def _calculate_speed_vector(self):
        self.imu_data['v_x'] = cumulative_trapezoid(self.imu_data['a_x_global'], self.imu_data['timeS'], initial=0)
        self.imu_data['v_y'] = cumulative_trapezoid(self.imu_data['a_y_global'], self.imu_data['timeS'], initial=0)
        self.imu_data['v_z'] = cumulative_trapezoid(self.imu_data['a_z_global'], self.imu_data['timeS'], initial=0)
        
    def _haversine(self, lat1, lon1, lat2, lon2):
        R = 6371000.0  # Earth radius in meters
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = np.sin(dlat / 2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0)**2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
        
        distance = R * c
        return distance

    def _synchronize_imu_nearest(self):
        pos = self.pos_data.sort_values("timeS")
        imu = self.imu_data.sort_values("timeS")

        self.res = pd.merge_asof(
            pos,
            imu,
            on="timeS",
            direction="nearest",   # або "backward" / "forward"
            tolerance=0.05,        # секунди — якщо IMU далі ніж 50мс → NaN
        )

    def _filter_gps_outliers(self):
        # Визначаємо розмір вікна для згладжування (~5 секунд)
        window = max(5, int(self.pos_sampling_rate_hertz * 5))
        
        # Знаходимо "нормальну" траєкторію через ковзну медіану
        rolling_lat = self.pos_data['lat'].rolling(window=window, center=True, min_periods=1).median()
        rolling_lon = self.pos_data['lon'].rolling(window=window, center=True, min_periods=1).median()
        
        # Рахуємо відхилення поточної точки від локальної медіани (в градусах)
        lat_diff = np.abs(self.pos_data['lat'] - rolling_lat)
        lon_diff = np.abs(self.pos_data['lon'] - rolling_lon)
        
        # 0.005 градуса — це приблизно 500 метрів. 
        # Якщо дрон "стрибнув" на >500м від своєї поточної траєкторії — це глітч.
        mask = (lat_diff < 0.005) & (lon_diff < 0.005)
        
        # Залишаємо тільки хороші точки і оновлюємо датафрейм
        old_len = len(self.pos_data)
        self.pos_data = self.pos_data[mask].reset_index(drop=True)
        
        print(f"Відфільтровано глітчів GPS: {old_len - len(self.pos_data)}")
    
    def _create_enu_cords(self):
        a = 6378137.0
        e_sq = 0.00669437999014

        # ---------------------------------------------------------
        # РОЗУМНИЙ ПОШУК ТОЧКИ ВІДЛІКУ (БЕЗ "ХОЛОДНОГО СТАРТУ")
        # ---------------------------------------------------------
        # 1. Знаходимо медіану всіх координат у радіанах (це центр нашого реального польоту)
        median_lat = self.pos_data['lat_rad'].median()
        median_lon = self.pos_data['lon_rad'].median()

        # 2. Відфільтровуємо аномалії. Залишаємо тільки ті точки, які знаходяться 
        # ближче ніж ~0.1 радіана (це приблизно 600 км) від медіани.
        # Це гарантовано відкине "нульові" острови та кеш з минулих польотів.
        valid_pos = self.pos_data[
            (np.abs(self.pos_data['lat_rad'] - median_lat) < 0.1) &
            (np.abs(self.pos_data['lon_rad'] - median_lon) < 0.1)
        ]

        # 3. Тепер безпечно беремо ПЕРШУ валідну точку як Origin для ENU
        lat0 = valid_pos['lat_rad'].iloc[0]
        lon0 = valid_pos['lon_rad'].iloc[0]
        alt0 = valid_pos['alt'].iloc[0]
        # ---------------------------------------------------------

        lat = self.pos_data['lat_rad']
        lon = self.pos_data['lon_rad']
        alt = self.pos_data['alt']

        # Крок 1: Перетворення WGS84 -> ECEF для всіх точок
        N = a / np.sqrt(1 - e_sq * np.sin(lat)**2)
        X = (N + alt) * np.cos(lat) * np.cos(lon)
        Y = (N + alt) * np.cos(lat) * np.sin(lon)
        Z = (N * (1 - e_sq) + alt) * np.sin(lat)

        # Перетворення WGS84 -> ECEF для точки відліку (Origin)
        N0 = a / np.sqrt(1 - e_sq * np.sin(lat0)**2)
        X0 = (N0 + alt0) * np.cos(lat0) * np.cos(lon0)
        Y0 = (N0 + alt0) * np.cos(lat0) * np.sin(lon0)
        Z0 = (N0 * (1 - e_sq) + alt0) * np.sin(lat0)

        # Вектор різниці в ECEF
        dX = X - X0
        dY = Y - Y0
        dZ = Z - Z0

        # Крок 2: Перетворення ECEF -> ENU
        sin_lat0 = np.sin(lat0)
        cos_lat0 = np.cos(lat0)
        sin_lon0 = np.sin(lon0)
        cos_lon0 = np.cos(lon0)

        self.pos_data['E_m'] = -sin_lon0 * dX + cos_lon0 * dY
        self.pos_data['N_m'] = -sin_lat0 * cos_lon0 * dX - sin_lat0 * sin_lon0 * dY + cos_lat0 * dZ
        self.pos_data['U_m'] = cos_lat0 * cos_lon0 * dX + cos_lat0 * sin_lon0 * dY + sin_lat0 * dZ
