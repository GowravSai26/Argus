# syntax=docker/dockerfile:1
FROM python:3.11.9-slim

# Prevents Python from writing .pyc files and buffers stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer caching)
COPY pyproject.toml ./
RUN pip install -e ".[dev]"

# Copy source code
COPY . .

# Create non-root user — never run as root in production
RUN adduser --disabled-password --gecos "" argus \
    && chown -R argus:argus /app
USER argus

EXPOSE 8000

# Health check — verifies the container is alive. Hosts like Render set $PORT.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://localhost:%s/health' % os.getenv('PORT', '8000'))"

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]