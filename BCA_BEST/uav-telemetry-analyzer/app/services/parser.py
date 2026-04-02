from pymavlink import mavutil
import pandas as pd
import numpy as np

class TelemetryParser:
    """Parser for Ardupilot binary .bin files using Pymavlink.

    Витягує телеметричні дані з бінарних логів польотних контролерів на базі ArduPilot.
    Обробляє повідомлення GPS (координати WGS-84), IMU (прискорення, гіроскоп) та ATT (орієнтація).

    Формат даних:
    - GPS: координати Lat/Lng (degrees), Alt (m), Spd (m/s), VZ (m/s)
    - IMU: AccX/Y/Z (m/s²), GyrX/Y/Z (rad/s), sampling at ~1000Hz
    - ATT: Roll/Pitch/Yaw (degrees), оновлення ~50Hz
    """
    def __init__(self, file_path: str):
        self.file_path = file_path

    def parse(self) -> pd.DataFrame:
        """Parses GPS and IMU messages into a pandas DataFrame.

        Returns:
            pd.DataFrame з колонками:
                - timestamp: час у секундах від початку логу
                - lat, lon, alt: GPS координати (WGS-84)
                - vx, vy, vz: швидкості (vz з GPS, vx/vy розраховуються пізніше)
                - ax, ay, az: прискорення з IMU (m/s²)
                - roll, pitch, yaw: кути орієнтації (degrees)
        """
        # Відкриваємо бінарний лог через pymavlink
        mlog = mavutil.mavlink_connection(self.file_path)

        # Збираємо дані з різних типів повідомлень
        gps_data = []
        imu_data = []
        att_data = []

        print(f"Парсинг файлу: {self.file_path}")

        # Читаємо всі повідомлення з логу
        while True:
            msg = mlog.recv_match(blocking=False)
            if msg is None:
                break

            msg_type = msg.get_type()

            # GPS повідомлення - координати та швидкість
            if msg_type == 'GPS':
                gps_data.append({
                    'timestamp': msg.TimeUS / 1e6,  # конвертуємо мікросекунди в секунди
                    'lat': msg.Lat,
                    'lon': msg.Lng,
                    'alt': msg.Alt,
                    'gps_speed': msg.Spd,  # горизонтальна швидкість
                    'vz_gps': msg.VZ,       # вертикальна швидкість
                })

            # IMU повідомлення - прискорення та гіроскоп
            elif msg_type == 'IMU':
                imu_data.append({
                    'timestamp': msg.TimeUS / 1e6,
                    'ax': msg.AccX,
                    'ay': msg.AccY,
                    'az': msg.AccZ,
                    'gyr_x': msg.GyrX,
                    'gyr_y': msg.GyrY,
                    'gyr_z': msg.GyrZ,
                })

            # ATT повідомлення - орієнтація (Euler angles)
            elif msg_type == 'ATT':
                att_data.append({
                    'timestamp': msg.TimeUS / 1e6,
                    'roll': msg.Roll,
                    'pitch': msg.Pitch,
                    'yaw': msg.Yaw,
                })

        print(f"Зібрано: GPS={len(gps_data)}, IMU={len(imu_data)}, ATT={len(att_data)}")

        # Перетворюємо списки в DataFrame
        df_gps = pd.DataFrame(gps_data)
        df_imu = pd.DataFrame(imu_data)
        df_att = pd.DataFrame(att_data)

        # Об'єднуємо всі дані за часом (використовуємо GPS як базу)
        # GPS зазвичай оновлюється на ~5-10Hz, IMU на ~1000Hz, ATT на ~50Hz
        # Використовуємо метод merge_asof для злиття за найближчим часом
        df = df_gps.copy()

        # Додаємо IMU дані (інтерполюємо до GPS timestamps)
        if not df_imu.empty:
            df = pd.merge_asof(
                df.sort_values('timestamp'),
                df_imu.sort_values('timestamp'),
                on='timestamp',
                direction='nearest'
            )

        # Додаємо ATT дані (інтерполюємо до GPS timestamps)
        if not df_att.empty:
            df = pd.merge_asof(
                df.sort_values('timestamp'),
                df_att.sort_values('timestamp'),
                on='timestamp',
                direction='nearest'
            )

        # Заповнюємо пропущені значення (якщо є)
        df = df.ffill().bfill()

        # Переіменовуємо колонки для сумісності з моделлю
        df = df.rename(columns={
            'vz_gps': 'vz',
        })

        # Додаємо vx, vy (спочатку нулі, будуть розраховані в analytics)
        if 'vx' not in df.columns:
            df['vx'] = 0.0
        if 'vy' not in df.columns:
            df['vy'] = 0.0

        # Переставляємо колонки в правильному порядку
        expected_columns = ['timestamp', 'lat', 'lon', 'alt', 'vx', 'vy', 'vz',
                          'ax', 'ay', 'az', 'roll', 'pitch', 'yaw']

        # Додаємо відсутні колонки з нулями
        for col in expected_columns:
            if col not in df.columns:
                df[col] = 0.0

        df = df[expected_columns]

        print(f"Створено DataFrame: {len(df)} записів")
        return df
