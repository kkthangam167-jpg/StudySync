#!/usr/bin/env python
"""
StudySync Production Database Initializer
-----------------------------------------
Safely initializes all database tables (SQLAlchemy models) and seeds
the system achievement catalog.

Does NOT seed demo accounts, create dummy user records, or modify existing data.
Safe to run against both local development (SQLite) and production (PostgreSQL).

Usage:
    python init_db.py
"""
import os
import sys

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv

env_file = os.path.join(BASE_DIR, '.env')
if os.path.exists(env_file):
    load_dotenv(dotenv_path=env_file)
else:
    load_dotenv()

from app import create_app, db
from app.services.achievement_engine import AchievementEngine


def init_database():
    config_name = os.environ.get('FLASK_ENV', 'development')
    # If DATABASE_URL is explicitly set to PostgreSQL, treat as production or development
    if os.environ.get('DATABASE_URL', '').startswith(('postgresql://', 'postgres://')):
        config_name = 'production'

    app = create_app(config_name)

    with app.app_context():
        raw_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        # Mask password in connection URI for clean logging
        masked_uri = raw_uri
        if '@' in raw_uri:
            try:
                prefix = raw_uri.split('@')[0]
                host_part = raw_uri.split('@')[1]
                scheme = prefix.split('://')[0]
                masked_uri = f"{scheme}://***:***@{host_part}"
            except Exception:
                masked_uri = "[PROTECTED_DATABASE_URI]"

        print(f"[*] Connecting to database: {masked_uri}")
        print("[*] Creating database tables if they do not exist...")
        db.create_all()
        print("[OK] Database tables verified / created successfully.")

        print("[*] Seeding default system achievements...")
        AchievementEngine.seed_default_achievements()
        print("[OK] System achievement catalog verified / seeded.")

        print("[SUCCESS] Database initialization completed safely!")


if __name__ == '__main__':
    init_database()
