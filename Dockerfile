# Multi-stage, security-hardened Dockerfile for AI Data Analyst
# Base: Official Python 3.12 slim
FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies (curl for healthchecks, build-essential for any C-extensions)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create non-root system user and group
RUN groupadd -r appgroup && useradd -r -g appgroup -u 1000 -d /app -s /sbin/nologin appuser

# Set working directory
WORKDIR /app

# Copy dependency definition
COPY requirements.txt .

# Install dependencies into system Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code and sample data
COPY app/ ./app/
COPY sample_data/ ./sample_data/
COPY tests/ ./tests/
COPY pytest.ini .
COPY .env.example .

# Create directory for logs, cache, and exports with correct non-root permissions
RUN mkdir -p /app/logs /app/evals /app/exports && \
    chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose Streamlit default port
EXPOSE 8501

# Healthcheck to verify Streamlit server is alive
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Default command: Launch Streamlit web app
CMD ["streamlit", "run", "app/main.py", "--server.port=8501", "--server.address=0.0.0.0"]
