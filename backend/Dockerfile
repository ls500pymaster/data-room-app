FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy frontend package files
COPY ./frontend/package.json ./frontend/package-lock.json* ./

# Install frontend dependencies
# Use npm install instead of npm ci for more flexibility
RUN npm install --legacy-peer-deps

# Copy frontend source code
COPY ./frontend ./

# Build frontend for production
# REACT_APP_API_URL should be set in Render environment variables
# If not set, use empty string for relative paths (same domain)
ARG REACT_APP_API_URL
ENV REACT_APP_API_URL=${REACT_APP_API_URL:-}
RUN npm run build

# Backend stage
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install system dependencies and Poetry
RUN apt-get update && apt-get install -y curl build-essential && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir poetry==1.8.3

# Copy Poetry configs
COPY ./backend/pyproject.toml ./backend/poetry.lock* ./backend/

# Poetry settings (use system site-packages to avoid creating venv)
RUN poetry config virtualenvs.create false

# Install project dependencies
WORKDIR /app/backend
RUN poetry install --no-interaction --no-ansi --no-root
WORKDIR /app

# Copy application source code
COPY ./backend ./backend

# Copy built frontend from builder stage
COPY --from=frontend-builder /app/frontend/build ./frontend/build

ENV PYTHONPATH=/app

WORKDIR /app/backend

EXPOSE 8000

CMD ["sh", "-c", "poetry run alembic upgrade head && poetry run python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 ${UVICORN_RELOAD:+--reload}"]
