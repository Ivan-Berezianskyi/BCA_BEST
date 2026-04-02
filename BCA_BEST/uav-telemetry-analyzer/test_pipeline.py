#!/usr/bin/env python3
"""
Тестовий скрипт для перевірки всього пайплайну обробки телеметрії
Запуск: python test_pipeline.py
"""

import sys
import os

# Додаємо шлях до app для імпорту
sys.path.insert(0, os.path.dirname(__file__))

from app.services.parser import TelemetryParser
from app.services.analytics import TelemetryAnalytics
from app.services.binary_exporter import BinaryExporter
import json


def main():
    print("=" * 60)
    print("Тестування пайплайну обробки телеметрії БПЛА")
    print("=" * 60)

    # Шлях до тестового файлу
    test_file = "data/binaryfiles/00000001.BIN"

    if not os.path.exists(test_file):
        print(f"❌ Файл {test_file} не знайдено!")
        return

    # Крок 1: Парсинг
    print("\n📝 КРОК 1: Парсинг бінарного логу")
    print("-" * 60)
    parser = TelemetryParser(test_file)
    raw_data = parser.parse()

    if raw_data.empty:
        print("❌ Парсинг не вдався - DataFrame порожній")
        return

    print(f"✅ Успішно розпарсено {len(raw_data)} записів")
    print(f"\nПерші 5 записів:")
    print(raw_data.head())

    # Крок 2: Аналітика
    print("\n📊 КРОК 2: Обчислення метрик")
    print("-" * 60)
    analytics = TelemetryAnalytics(raw_data)
    metrics = analytics.calculate_metrics()

    print("✅ Метрики розраховано:")
    print(f"  • Максимальна горизонтальна швидкість: {metrics['max_horizontal_speed']:.2f} м/с")
    print(f"  • Максимальна вертикальна швидкість: {metrics['max_vertical_speed']:.2f} м/с")
    print(f"  • Максимальне прискорення: {metrics['max_acceleration']:.2f} м/с²")
    print(f"  • Максимальний набір висоти: {metrics['max_altitude_gain']:.2f} м")
    print(f"  • Загальна дистанція (Haversine): {metrics['total_distance']:.2f} м")
    print(f"  • Тривалість польоту: {metrics['duration']:.2f} сек ({metrics['duration']/60:.2f} хв)")

    # Крок 3: Конвертація у ENU
    print("\n🌍 КРОК 3: Конвертація WGS-84 -> ENU")
    print("-" * 60)
    trajectory = analytics.get_enu_trajectory()

    if not trajectory:
        print("❌ Траєкторія порожня")
        return

    print(f"✅ Конвертовано {len(trajectory)} точок траєкторії")
    print(f"\nПерші 3 точки (ENU координати):")
    for i in range(min(3, len(trajectory))):
        point = trajectory[i]
        print(f"  {i+1}. E={point['e']:.2f}м, N={point['n']:.2f}м, U={point['u']:.2f}м, speed={point['speed']:.2f}м/с")

    # Крок 4: Експорт у бінарний формат
    print("\n💾 КРОК 4: Експорт у бінарний формат")
    print("-" * 60)
    output_file = "data/output/trajectory.bin"
    os.makedirs("data/output", exist_ok=True)

    BinaryExporter.save_to_file(trajectory, output_file)

    # Перевірка формату
    with open(output_file, 'rb') as f:
        binary_data = f.read()

    is_valid = BinaryExporter.validate_format(binary_data)
    print(f"✅ Формат {'валідний' if is_valid else 'невалідний'}")

    # Крок 5: Додатковий JSON експорт для читабельності
    print("\n📄 КРОК 5: Експорт метрик у JSON")
    print("-" * 60)
    json_output = {
        "filename": test_file,
        "metrics": metrics,
        "trajectory_points": len(trajectory),
        "sample_points": trajectory[:5] if len(trajectory) > 5 else trajectory
    }

    json_file = "data/output/analysis.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(json_output, f, indent=2, ensure_ascii=False)

    print(f"✅ JSON експортовано: {json_file}")

    print("\n" + "=" * 60)
    print("🎉 ТЕСТУВАННЯ ЗАВЕРШЕНО УСПІШНО!")
    print("=" * 60)


if __name__ == "__main__":
    main()
