# Multi-stage Dockerfile for Intelligent Logistics ETA Prediction System
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and application assets
COPY src/ ./src/
COPY dashboard/ ./dashboard/
COPY tests/ ./tests/
COPY docs/ ./docs/
COPY README.md .

# Create required runtime directories
RUN mkdir -p data/raw data/processed data/ground_truth data/exports models reports

EXPOSE 8000 8501

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
