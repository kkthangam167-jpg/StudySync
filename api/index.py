import os
import sys

# Ensure project root directory is accessible on Python's module path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app

# Instantiate production application instance for Vercel Serverless Functions.
# Vercel's Python runtime discovers and serves the WSGI 'app' object.
app = create_app(os.environ.get('FLASK_ENV', 'production'))
