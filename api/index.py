import os
import sys
import logging

# Ensure project root directory is accessible on Python's module path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

logger = logging.getLogger(__name__)

# Instantiate production application instance for Vercel Serverless Functions.
# Vercel's Python runtime discovers and serves the WSGI 'app' object.
try:
    from app import create_app
    app = create_app(os.environ.get('FLASK_ENV', 'production'))
except Exception as exc:
    logger.exception("CRITICAL: Failed to initialize StudySync application for Vercel: %s", exc)
    from flask import Flask, jsonify
    app = Flask(__name__)

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serverless_init_error_fallback(path):
        err_msg = str(exc)
        # Protect sensitive credentials from being reflected in responses
        if any(w in err_msg.lower() for w in ['password', 'secret', 'key']):
            err_msg = "Database or credentials configuration notice during startup."
        return jsonify({
            'status': 500,
            'error': 'Application Initialization Notice',
            'message': 'StudySync encountered an initialization error during serverless startup.',
            'details': err_msg,
            'recommendation': 'Please verify your DATABASE_URL environment variable in your Vercel Project Settings and check the Vercel Runtime Logs.'
        }), 500
