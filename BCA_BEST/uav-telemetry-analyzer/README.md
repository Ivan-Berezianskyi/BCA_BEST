# UAV Telemetry Analyzer (Backend)

Система для автоматизованого розбору лог-файлів Ardupilot, 3D-візуалізації та AI-аналізу.

## 🚀 Функціонал
- **Data Parsing**: Використання `pymavlink` для витягування даних GPS (WGS-84) та IMU.
- **Math Analytics**:
  - Обчислення дистанції за формулою **Haversine**.
  - Розрахунок швидкості через **трапецієвидне інтегрування** прискорень.
  - Конвертація WGS-84 у локальну декартову систему **ENU**.
- **AI Engine**: Генерація автоматичних звітів про політ за допомогою LLM.
- **API**: FastAPI для інтеграції з фронтендом.

## 🏗️ Архітектура
- `app/services/parser.py`: Логіка роботи з бінарними логами (Ardupilot/Mavlink).
- `app/services/analytics.py`: Математичне ядро (ENU, Integration, Haversine).
- `app/services/ai_engine.py`: Інтерфейс для AI-висновків.

## 🛠️ Запуск
1. Встановіть залежності: `pip install -r requirements.txt`
2. Запустіть сервер: `uvicorn app.main:app --reload`
3. Через Docker: `docker-compose up --build`

## 📚 Теоретичне обґрунтування
- **ENU (East-North-Up)**: Кастомна система координат, необхідна для точного відображення траєкторії в метрах відносно точки старту.
- **Trapezoidal Integration**: Метод апроксимації інтеграла для отримання швидкості (v = ∫a dt).
- **Quaternions**: Для уникнення Gimbal Lock при аналізі орієнтації.

---
*Розроблено для BEST::HACKath0n 2026*
