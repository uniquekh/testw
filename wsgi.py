"""
WSGI entry point for production deployment
Use with gunicorn for better performance and concurrency
"""
from api import app

if __name__ == "__main__":
    app.run()
