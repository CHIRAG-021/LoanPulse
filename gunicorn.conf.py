"""Gunicorn production server configuration for LoanPulse."""
import os

# Binding host and port (configurable via PORT environment variable)
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"

# Worker processes and threads per worker
workers = int(os.getenv("WEB_CONCURRENCY", "2"))
threads = int(os.getenv("PYTHON_THREADS", "2"))
worker_class = "gthread"

# Timeouts and keep-alive
timeout = int(os.getenv("GUNICORN_TIMEOUT", "60"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

# Logging to stdout/stderr for container log drivers & cloud logging
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")

# Process naming
proc_name = "loanpulse_gunicorn"
