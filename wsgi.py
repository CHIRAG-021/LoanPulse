"""WSGI entrypoint for production deployment of LoanPulse."""
import os
from src.app import create_app

# When running via WSGI server (Gunicorn), enforce production mode by default
target_env = os.getenv("WSGI_ENV") or os.getenv("FLASK_ENV")
if not target_env or target_env.lower() == "development":
    target_env = "production"

app = create_app(target_env.lower())

if __name__ == "__main__":
    app.run()
