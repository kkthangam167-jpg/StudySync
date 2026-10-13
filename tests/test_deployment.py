import os
import re
from unittest.mock import patch
import pytest
from app import create_app
from config import get_database_uri, ProductionConfig
from app.services.ai_service import AIService


def test_database_uri_postgres_normalization():
    """Ensures legacy postgres:// URLs are automatically converted to postgresql://."""
    legacy_url = "postgres://student_user:strong_password@aws-0-us-east-1.pooler.supabase.com:6543/studysync_db"
    with patch.dict(os.environ, {'DATABASE_URL': legacy_url}):
        normalized = get_database_uri()
        assert normalized.startswith("postgresql://")
        assert "student_user:strong_password" in normalized
        assert "pooler.supabase.com:6543/studysync_db" in normalized


def test_database_uri_sqlite_local_handling():
    """Ensures local SQLite paths resolve to absolute paths under project root."""
    with patch.dict(os.environ, {'DATABASE_URL': 'sqlite:///instance/studysync.db'}):
        resolved = get_database_uri()
        assert resolved.startswith("sqlite:///")
        assert "instance/studysync.db" in resolved


def test_production_config_pool_options():
    """Ensures production configuration sets resilient serverless pool options."""
    assert ProductionConfig.SQLALCHEMY_ENGINE_OPTIONS.get('pool_pre_ping') is True
    assert ProductionConfig.SQLALCHEMY_ENGINE_OPTIONS.get('pool_recycle') == 300
    assert ProductionConfig.SESSION_COOKIE_SECURE is True
    assert ProductionConfig.SESSION_COOKIE_HTTPONLY is True


def test_production_config_requires_database_url():
    """Ensures create_app('production') fails fast if DATABASE_URL is not configured."""
    with patch.dict(os.environ, {'DATABASE_URL': ''}, clear=False):
        with pytest.raises(RuntimeError) as exc_info:
            create_app('production')
        assert "DATABASE_URL is not set" in str(exc_info.value)


def test_production_config_succeeds_with_database_url():
    """Ensures create_app('production') initializes correctly when DATABASE_URL is provided."""
    with patch.dict(os.environ, {'DATABASE_URL': 'sqlite:///:memory:'}):
        prod_app = create_app('production')
        assert prod_app is not None
        assert prod_app.config['DEBUG'] is False
        assert prod_app.config['TESTING'] is False


def test_vercel_entrypoint_exports_wsgi_app():
    """Ensures api/index.py exports a valid Flask WSGI application instance."""
    with patch.dict(os.environ, {'DATABASE_URL': 'sqlite:///:memory:'}):
        import api.index as vercel_entry
        assert hasattr(vercel_entry, 'app')
        assert vercel_entry.app is not None
        # Verify core blueprints are registered on the Vercel app
        blueprint_names = list(vercel_entry.app.blueprints.keys())
        expected_bps = ['auth', 'dashboard', 'assignments', 'timetable', 'syllabus', 'planner', 'ai', 'timer', 'api']
        for bp in expected_bps:
            assert bp in blueprint_names, f"Expected blueprint '{bp}' missing from Vercel entrypoint"


def test_static_asset_serving_on_app(app):
    """Ensures static CSS and JS assets are served with correct MIME types."""
    client = app.test_client()
    
    # CSS
    css_res = client.get('/static/css/style.css')
    assert css_res.status_code == 200
    assert 'text/css' in css_res.headers.get('Content-Type', '')

    # JS
    js_res = client.get('/static/js/main.js')
    assert js_res.status_code == 200
    assert 'javascript' in js_res.headers.get('Content-Type', '')


def test_health_check_endpoint(app):
    """Verifies production /api/health endpoint returns 200 healthy status."""
    client = app.test_client()
    res = client.get('/api/health')
    assert res.status_code == 200
    data = res.get_json()
    assert data['status'] == 'healthy'
    assert data['application'] == 'StudySync'
    assert data['database'] == 'connected'


def test_timer_routes_reachability(app):
    """Verifies that both /focus-timer and /timer redirect unauthenticated requests to login."""
    client = app.test_client()
    res1 = client.get('/focus-timer')
    assert res1.status_code == 302
    assert '/login' in res1.headers.get('Location', '')

    res2 = client.get('/timer')
    assert res2.status_code == 302
    assert '/login' in res2.headers.get('Location', '')


def test_ai_secrets_never_leaked_in_errors(app):
    """Verifies that any hypothetical API key is redacted from error messages."""
    secret_key = "AIzaSySecretTestKeyNotForProduction12345"
    with patch.dict(os.environ, {'GEMINI_API_KEY': secret_key}):
        err = Exception(f"HTTP 403 Forbidden with key {secret_key}: quota error")
        classified = AIService._classify_gemini_error(err, "gemini-3.5-flash")
        assert secret_key not in classified
        assert "[REDACTED_API_KEY]" in classified or "Gemini API" in classified
