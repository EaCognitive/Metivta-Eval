"""
WSGI entry point for Render deployment
"""

from api.server import app

if __name__ == "__main__":
    app.run()
