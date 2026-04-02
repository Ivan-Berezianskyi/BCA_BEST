import struct
from typing import List

class BinaryExporter:
    """Exports trajectory data to binary format for efficient frontend rendering.

    Бінарний формат (little-endian):
    - Перші 4 байти: u32 - кількість точок траєкторії
    - Для кожної точки (16 байтів):
        - x (f32): East координата у метрах
        - y (f32): North координата у метрах
        - h (f32): Up (висота) у метрах
        - speed (f32): швидкість у м/с

    Загальний розмір файлу: 4 + (n_points * 16) байтів

    Переваги бінарного формату над JSON:
    - Компактність: ~4x менше розмір порівняно з JSON
    - Швидкість: парсинг у фронтенді через TypedArray (native)
    - Фіксована структура: передбачуваний формат для WebGL рендерингу

    Формат числових типів:
    - u32: unsigned int (0 до 4,294,967,295)
    - f32: 32-bit float IEEE 754 (∼7 знаків точності)
    """

    @staticmethod
    def export_to_binary(trajectory: List[dict]) -> bytes:
        """Converts ENU trajectory to binary format.

        Args:
            trajectory: список словників з ключами:
                - e: East (метри)
                - n: North (метри)
                - u: Up (метри)
                - speed: швидкість (м/с)

        Returns:
            bytes: бінарні дані у форматі little-endian
        """
        # Кількість точок
        n_points = len(trajectory)

        # Створюємо бінарний буфер
        # Формат: '<' означає little-endian
        # 'I' = unsigned int (4 байти)
        # 'f' = float (4 байти)
        binary_data = bytearray()

        # 1. Записуємо кількість точок (u32)
        binary_data.extend(struct.pack('<I', n_points))

        # 2. Записуємо кожну точку (4 × f32 = 16 байтів)
        for point in trajectory:
            x = float(point['e'])      # East
            y = float(point['n'])      # North
            h = float(point['u'])      # Up (висота)
            speed = float(point['speed'])

            # Пакуємо 4 float у little-endian формат
            binary_data.extend(struct.pack('<ffff', x, y, h, speed))

        return bytes(binary_data)

    @staticmethod
    def save_to_file(trajectory: List[dict], filepath: str):
        """Saves trajectory to binary file.

        Args:
            trajectory: ENU trajectory data
            filepath: шлях до вихідного файлу
        """
        binary_data = BinaryExporter.export_to_binary(trajectory)

        with open(filepath, 'wb') as f:
            f.write(binary_data)

        print(f"Експортовано {len(trajectory)} точок до {filepath}")
        print(f"Розмір файлу: {len(binary_data)} байтів")

    @staticmethod
    def validate_format(binary_data: bytes) -> bool:
        """Validates binary format structure.

        Args:
            binary_data: бінарні дані для перевірки

        Returns:
            True якщо формат валідний, False інакше
        """
        # Перевірка мінімального розміру (4 байти для кількості)
        if len(binary_data) < 4:
            return False

        # Читаємо кількість точок
        n_points = struct.unpack('<I', binary_data[:4])[0]

        # Перевірка, чи розмір відповідає формату
        expected_size = 4 + (n_points * 16)
        if len(binary_data) != expected_size:
            return False

        return True