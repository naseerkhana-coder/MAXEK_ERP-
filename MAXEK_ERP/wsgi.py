"""WSGI entry point for production (Gunicorn / systemd)."""
from app import app

application = app
