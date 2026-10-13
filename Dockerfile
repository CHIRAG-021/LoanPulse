# ==============================================================================
# Production Dockerfile for LoanPulse
# ==============================================================================
FROM python:3.10-slim

# Set environment flags
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    PORT=8000

# Install minimal OS dependencies for psycopg2 and health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency specifications first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Create uploads directory and non-privileged user for security
RUN mkdir -p /app/uploads/documents && \
    useradd -m -u 1001 loanpulse && \
    chown -R loanpulse:loanpulse /app

USER loanpulse

# Expose standard application port
EXPOSE 8000

# Health check to ensure WSGI worker responsiveness
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Production startup using Gunicorn WSGI server
CMD ["gunicorn", "--config", "gunicorn.conf.py", "wsgi:app"]
