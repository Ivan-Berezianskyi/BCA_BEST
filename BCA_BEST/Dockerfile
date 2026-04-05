# ================================
# Stage 1: WASM Builder
# ================================
FROM rust:1.83-slim AS wasm-builder

# Install wasm-pack using pre-built binary (avoids edition2024 compilation issues)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    curl https://rustwasm.github.io/wasm-pack/installer/init.sh -sSf | sh && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /wasm-build

# Copy Rust WASM module source
COPY uav-telemetry-analyzer-ui/cords-optimizator/ .

# Build WASM module for web target
# Output: pkg/ directory with .wasm, .js, package.json
RUN wasm-pack build --target web --out-dir pkg

# ================================
# Stage 2: Frontend Builder
# ================================
FROM node:23-alpine AS frontend-builder

WORKDIR /frontend

# Copy workspace root package.json first (for workspace setup)
COPY uav-telemetry-analyzer-ui/package.json .

# Copy WASM pkg from Stage 1 to correct workspace location
# This creates cords-optimizator/pkg/ which is referenced in web/package.json
COPY --from=wasm-builder /wasm-build/pkg ./cords-optimizator/pkg

# Copy web application source
COPY uav-telemetry-analyzer-ui/web ./web

# Install all dependencies
# npm will resolve "cords-optimizator": "file:../cords-optimizator/pkg" from workspace
RUN npm install

# Build Nuxt 4 SPA
WORKDIR /frontend/web
RUN npm run build

# Output: .output/public/ directory with SPA files

# ================================
# Stage 3: Production Runtime
# ================================
FROM python:3.11-slim AS production

WORKDIR /app

# Install system dependencies
# - build-essential: required for pymavlink native compilation
# - curl: required for healthcheck
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        curl && \
    rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY uav-telemetry-analyzer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application code
COPY uav-telemetry-analyzer/ .

# Copy built frontend from Stage 2 to expected location
# Backend expects: Path(__file__).parent / "frontend_dist" = /app/app/frontend_dist/
COPY --from=frontend-builder /frontend/web/.output/public ./app/frontend_dist

# Create data directory for telemetry file uploads
RUN mkdir -p /app/data && chmod 755 /app/data

# Expose application port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Start FastAPI application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
