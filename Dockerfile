# Multi-stage Dockerfile
# Stage 1: Build React Admin Dashboard
FROM node:20-alpine AS frontend-builder
WORKDIR /app/admin_panel
COPY admin_panel/package*.json ./
RUN npm install
COPY admin_panel/ ./
RUN npm run build

# Stage 2: Python Backend & Bot
FROM python:3.12-slim AS runner
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy backend & bot source code
COPY config/ ./config/
COPY database/ ./database/
COPY game_engine/ ./game_engine/
COPY bot/ ./bot/
COPY backend/ ./backend/
COPY scripts/ ./scripts/

# Copy built frontend assets
COPY --from=frontend-builder /app/admin_panel/dist ./admin_panel/dist

# Ensure /app/data is writable for non-root containers (e.g. Hugging Face Spaces uid 1000)
RUN mkdir -p /app/data/backups && chmod -R 777 /app/data

# Expose FastAPI port (8000 local/Docker Compose, 7860 Hugging Face Spaces)
EXPOSE 8000 7860

# Run both Bot & API
CMD ["python", "scripts/run_all.py"]
