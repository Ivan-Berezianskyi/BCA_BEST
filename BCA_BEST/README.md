# UAV Telemetry Analyzer | Аналізатор Телеметрії БПЛА

<div align="center">

**BEST::HACKath0n 2026 Project**

*Професійна система аналізу телеметрії безпілотників з 3D-візуалізацією та AI-аналітикою*

</div>

---

## 🇺🇦 Українська версія

### 📋 Про проект

**UAV Telemetry Analyzer** — це повнофункціональна веб-система для детального аналізу польотних даних безпілотних літальних апаратів (БПЛА). Проект розроблено для BEST::HACKath0n 2026.

#### Ключові можливості:
- 📊 **3D-візуалізація траєкторії польоту** з інтерактивним Plotly.js
- 🤖 **AI-аналіз польоту** з генерацією детальних звітів (OpenAI GPT-4)
- 📈 **Розширена аналітика**: швидкість, висота, дистанція, орієнтація
- 🚀 **WebAssembly оптимізація** для обробки великих масивів даних
- 🎯 **Підтримка форматів**: ArduPilot `.bin`, Mavlink `.log`
- 🌐 **Сучасний UI** з темною темою та ефектами glassmorphism

### 🚀 Швидкий старт

#### Вимоги
- Docker (версія 20.10+)
- Docker Compose (версія 1.29+)

#### Запуск за 3 кроки

**1. Клонувати репозиторій:**
```bash
git clone <your-repo-url>
cd BCA_BEST
```

**2. Запустити контейнер:**
```bash
docker compose up --build
```

**3. Відкрити в браузері:**
```
http://localhost:8000
```

> **💡 Примітка**: Перша збірка займає ~7-10 хвилин (компіляція Rust, встановлення залежностей). Наступні збірки будуть швидшими завдяки кешуванню Docker.

#### ⚙️ Налаштування AI-аналізу (опціонально)

Для активації AI-аналізу польотів потрібен API-ключ OpenAI:

```bash
# Linux/macOS
export AI_API_KEY=sk-your-openai-key-here
docker compose up

# Windows (PowerShell)
$env:AI_API_KEY="sk-your-openai-key-here"
docker compose up
```

Або створіть файл `.env` в кореневій директорії:
```env
AI_API_KEY=sk-your-openai-key-here
```

### 🛠️ Технологічний стек

#### Backend
- **FastAPI** (Python 3.11) — сучасний веб-фреймворк
- **pymavlink** — парсинг ArduPilot/Mavlink логів
- **NumPy, Pandas, SciPy** — математичні обчислення
- **pyproj** — трансформація координат (WGS-84 → ECEF → ENU)
- **ahrs** — алгоритми орієнтації (Madgwick filter, кватерніони)

#### Frontend
- **Nuxt 4** (Vue 3.5) — мета-фреймворк для SPA
- **Tailwind CSS 4** — сучасний дизайн
- **Plotly.js** — 3D-візуалізація траєкторій
- **WebAssembly (Rust)** — клієнтська оптимізація координат

#### DevOps
- **Docker Multi-stage builds** — оптимізовані образи
- **Uvicorn** — високопродуктивний ASGI сервер

### 📐 Алгоритми обробки

1. **Трансформація координат**: WGS-84 (GPS) → ECEF → ENU (локальна система)
2. **Фільтрація GPS**: Медіанний фільтр з вікном 5 секунд
3. **Обчислення швидкості**: Трапецієподібна інтеграція з детрендінгом
4. **Орієнтація**: Quaternion-based обчислення (уникнення Gimbal Lock)
5. **Оптимізація траєкторії**: Алгоритм Ramer-Douglas-Peucker (WASM)

### 📊 Робочий процес

1. **Завантажте файл телеметрії** (.bin або .log)
2. **Перегляньте 3D-візуалізацію** траєкторії польоту
3. **Проаналізуйте метрики**: дистанція, середня/максимальна швидкість, висота
4. **Отримайте AI-звіт** про особливості польоту (якщо налаштовано API ключ)

### 🐳 Docker команди

```bash
# Запуск у фоновому режимі
docker compose up -d

# Перегляд логів
docker compose logs -f

# Зупинка
docker compose down

# Повне очищення (включаючи volumes)
docker compose down -v

# Перебудова після змін коду
docker compose up --build
```

### 🔍 Перевірка стану

```bash
# Статус контейнера
docker compose ps

# Healthcheck (має показати "healthy" після ~40 секунд)
docker inspect uav-telemetry-analyzer | grep Health -A 10
```

### 📁 Структура проекту

```
BCA_BEST/
├── uav-telemetry-analyzer/        # Backend (Python/FastAPI)
│   ├── app/
│   │   ├── main.py               # Entry point
│   │   ├── services/             # Парсинг, аналітика, AI
│   │   └── frontend_dist/        # Зібраний frontend (генерується)
│   └── requirements.txt
├── uav-telemetry-analyzer-ui/     # Frontend + WASM
│   ├── web/                      # Nuxt 4 додаток
│   │   ├── app/pages/index.vue   # Головна сторінка
│   │   └── app/composables/      # WASM інтеграція
│   └── cords-optimizator/        # Rust WASM модуль
│       └── src/lib.rs            # Douglas-Peucker алгоритм
├── Dockerfile                     # Multi-stage build
├── docker-compose.yml             # Оркестрація
└── README.md                      # Цей файл
```

### 🎓 Для розробників

#### Локальна розробка (без Docker)

**Backend:**
```bash
cd uav-telemetry-analyzer
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**WASM модуль:**
```bash
cd uav-telemetry-analyzer-ui/cords-optimizator
cargo install wasm-pack
wasm-pack build --target web --out-dir pkg
```

**Frontend:**
```bash
cd uav-telemetry-analyzer-ui
npm install
cd web
npm run dev
```

### 🐛 Усунення проблем

**Проблема**: Помилка `Cannot find module 'cords-optimizator'`
- **Рішення**: WASM модуль не зібрано. Використайте Docker або зберіть вручну (див. вище)

**Проблема**: Порт 8000 зайнятий
- **Рішення**: Змініть порт в `docker-compose.yml`: `"8080:8000"`

**Проблема**: Помилка `AI_API_KEY` в логах
- **Рішення**: Це не критично. AI-аналіз буде недоступний, але візуалізація працює

### 📞 Контакти

tg: @dmitriydima111

---

## 🇬🇧 English Version

### 📋 About

**UAV Telemetry Analyzer** is a comprehensive web-based system for detailed analysis of unmanned aerial vehicle (UAV) flight data. Developed for BEST::HACKath0n 2026.

#### Key Features:
- 📊 **3D Flight Trajectory Visualization** with interactive Plotly.js
- 🤖 **AI-Powered Flight Analysis** with detailed report generation (OpenAI GPT-4)
- 📈 **Advanced Analytics**: velocity, altitude, distance, orientation
- 🚀 **WebAssembly Optimization** for processing large datasets
- 🎯 **Format Support**: ArduPilot `.bin`, Mavlink `.log`
- 🌐 **Modern UI** with dark theme and glassmorphism effects

### 🚀 Quick Start

#### Requirements
- Docker (version 20.10+)
- Docker Compose (version 1.29+)

#### Launch in 3 Steps

**1. Clone the repository:**
```bash
git clone <your-repo-url>
cd BCA_BEST
```

**2. Start the container:**
```bash
docker compose up --build
```

**3. Open in browser:**
```
http://localhost:8000
```

> **💡 Note**: First build takes ~7-10 minutes (Rust compilation, dependency installation). Subsequent builds are faster thanks to Docker layer caching.

#### ⚙️ AI Analysis Setup (Optional)

To enable AI flight analysis, you need an OpenAI API key:

```bash
# Linux/macOS
export AI_API_KEY=sk-your-openai-key-here
docker compose up

# Windows (PowerShell)
$env:AI_API_KEY="sk-your-openai-key-here"
docker compose up
```

Or create a `.env` file in the root directory:
```env
AI_API_KEY=sk-your-openai-key-here
```

### 🛠️ Technology Stack

#### Backend
- **FastAPI** (Python 3.11) — modern web framework
- **pymavlink** — ArduPilot/Mavlink log parsing
- **NumPy, Pandas, SciPy** — mathematical computations
- **pyproj** — coordinate transformations (WGS-84 → ECEF → ENU)
- **ahrs** — orientation algorithms (Madgwick filter, quaternions)

#### Frontend
- **Nuxt 4** (Vue 3.5) — meta-framework for SPA
- **Tailwind CSS 4** — modern design system
- **Plotly.js** — 3D trajectory visualization
- **WebAssembly (Rust)** — client-side coordinate optimization

#### DevOps
- **Docker Multi-stage builds** — optimized images
- **Uvicorn** — high-performance ASGI server

### 📐 Processing Algorithms

1. **Coordinate Transformation**: WGS-84 (GPS) → ECEF → ENU (local frame)
2. **GPS Filtering**: Median filter with 5-second window
3. **Velocity Calculation**: Trapezoidal integration with detrending
4. **Orientation**: Quaternion-based computation (Gimbal Lock avoidance)
5. **Trajectory Optimization**: Ramer-Douglas-Peucker algorithm (WASM)

### 📊 Workflow

1. **Upload telemetry file** (.bin or .log)
2. **View 3D visualization** of flight trajectory
3. **Analyze metrics**: distance, average/max velocity, altitude
4. **Get AI report** on flight characteristics (if API key configured)

### 🐳 Docker Commands

```bash
# Run in background
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down

# Full cleanup (including volumes)
docker compose down -v

# Rebuild after code changes
docker compose up --build
```

### 🔍 Health Check

```bash
# Container status
docker compose ps

# Healthcheck (should show "healthy" after ~40 seconds)
docker inspect uav-telemetry-analyzer | grep Health -A 10
```

### 🎓 For Developers

#### Local Development (without Docker)

**Backend:**
```bash
cd uav-telemetry-analyzer
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**WASM Module:**
```bash
cd uav-telemetry-analyzer-ui/cords-optimizator
cargo install wasm-pack
wasm-pack build --target web --out-dir pkg
```

**Frontend:**
```bash
cd uav-telemetry-analyzer-ui
npm install
cd web
npm run dev
```

### 🐛 Troubleshooting

**Issue**: `Cannot find module 'cords-optimizator'` error
- **Solution**: WASM module not built. Use Docker or build manually (see above)

**Issue**: Port 8000 already in use
- **Solution**: Change port in `docker-compose.yml`: `"8080:8000"`

**Issue**: `AI_API_KEY` error in logs
- **Solution**: Not critical. AI analysis will be unavailable, but visualization works

### 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Browser                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Nuxt 4 SPA (Vue 3 + Tailwind + Plotly.js)         │  │
│  │  + WASM Module (cords-optimizator)                  │  │
│  └──────────────────────┬──────────────────────────────┘  │
└─────────────────────────┼──────────────────────────────────┘
                          │ HTTP (localhost:8000)
┌─────────────────────────▼──────────────────────────────────┐
│              FastAPI Backend (Python)                      │
│  ┌───────────────────┐  ┌─────────────────────────────┐  │
│  │ Static Files      │  │ API Endpoints               │  │
│  │ Serving           │  │ /analyze/optimized          │  │
│  │ (SPA)             │  │                             │  │
│  └───────────────────┘  └─────────┬───────────────────┘  │
│                                    │                       │
│  ┌─────────────────────────────────▼───────────────────┐  │
│  │            Services Layer                           │  │
│  │  • TelemetryParser (pymavlink)                     │  │
│  │  • TelemetryAnalytics (numpy, scipy, pyproj)      │  │
│  │  • AIEngine (OpenAI GPT-4-turbo)                  │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 📞 Contact

tg: @dmitriydima111

---

## 📄 License

This project was developed for BEST::HACKath0n 2026.

## 🙏 Acknowledgments

- ArduPilot community for telemetry format documentation
- Nuxt, Vue, and FastAPI teams for excellent frameworks
- Rust & wasm-pack for making WebAssembly accessible
