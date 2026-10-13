import os
from datetime import timedelta
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
env_file = os.path.join(BASE_DIR, '.env')
if os.path.exists(env_file):
    load_dotenv(dotenv_path=env_file)
else:
    load_dotenv()

class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'studysync-insecure-dev-secret-key-change-in-prod-2026')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # AI Assistant Configuration
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
    GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-3.1-flash-lite')
    
    # App Settings
    APP_NAME = "StudySync"
    ITEMS_PER_PAGE = 20

def get_database_uri(default_filename='studysync.db'):
    """Resolves database URI robustly across platforms, converting relative SQLite paths to absolute and postgres:// to postgresql://."""
    db_env = os.environ.get('DATABASE_URL')
    if db_env and db_env.strip():
        db_env = db_env.strip()
        # Normalizes legacy postgres:// scheme to postgresql:// for SQLAlchemy compatibility
        if db_env.startswith('postgres://'):
            return db_env.replace('postgres://', 'postgresql://', 1)
        if db_env.startswith('sqlite:///'):
            path_part = db_env[10:]
            if not os.path.isabs(path_part):
                abs_p = os.path.join(BASE_DIR, path_part).replace(os.sep, '/')
                return f"sqlite:///{abs_p}"
        return db_env
    if default_filename:
        abs_p = os.path.join(BASE_DIR, 'instance', default_filename).replace(os.sep, '/')
        return f"sqlite:///{abs_p}"
    return None

class DevelopmentConfig(Config):
    """Development configuration with SQLite (or DATABASE_URL if explicitly provided)."""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = get_database_uri('studysync.db')

class TestingConfig(Config):
    """Testing configuration with in-memory SQLite."""
    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SERVER_NAME = 'localhost'

class ProductionConfig(Config):
    """Production configuration for public cloud hosting (PostgreSQL via DATABASE_URL)."""
    DEBUG = False
    TESTING = False
    
    # Persistent PostgreSQL database configuration via DATABASE_URL
    SQLALCHEMY_DATABASE_URI = get_database_uri(default_filename=None)
    
    # Connection pool options optimized for serverless / persistent PostgreSQL (e.g. Supabase, Neon)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    
    # Cookie security
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
