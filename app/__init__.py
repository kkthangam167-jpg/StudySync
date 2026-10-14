import os
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from dotenv import load_dotenv

# Explicitly ensure .env is loaded from project root
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
env_file = os.path.join(BASE_DIR, '.env')
if os.path.exists(env_file):
    load_dotenv(dotenv_path=env_file)
else:
    load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()

def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    from config import config_by_name
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_by_name.get(config_name, config_by_name['development']))

    # Ensure instance folder exists
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    # In production or Vercel serverless environments, verify persistent database URI or fall back to writable temp SQLite
    if config_name == 'production' or os.environ.get('VERCEL') == '1':
        import tempfile
        from config import get_database_uri
        db_uri = get_database_uri(default_filename=None)

        is_serverless = bool(os.environ.get('VERCEL') == '1' or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))
        is_unwritable_sqlite = bool(db_uri and db_uri.startswith('sqlite:///') and not db_uri.startswith('sqlite:///:memory:') and '/tmp/' not in db_uri and tempfile.gettempdir().replace('\\', '/') not in db_uri)

        if not db_uri or (is_serverless and is_unwritable_sqlite):
            tmp_db_file = os.path.join(tempfile.gettempdir(), 'studysync.db').replace('\\', '/')
            fallback_uri = f'sqlite:///{tmp_db_file}'
            app.logger.warning(
                "DATABASE_URL is not set or points to an unwritable local file on Vercel. "
                f"Falling back to temporary writable SQLite database at {fallback_uri}. "
                "For permanent data persistence on Vercel, please set DATABASE_URL (PostgreSQL) in your Vercel Project Settings."
            )
            app.config['SQLALCHEMY_DATABASE_URI'] = fallback_uri
        else:
            app.config['SQLALCHEMY_DATABASE_URI'] = db_uri

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    # Reverse proxy support for Vercel / Cloudflare
    try:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    except Exception:
        pass

    # Ensure database schema exists safely
    with app.app_context():
        try:
            db.create_all()
            from app.services.achievement_engine import AchievementEngine
            AchievementEngine.seed_default_achievements()
        except Exception as e:
            app.logger.warning(f"Database schema auto-init notice: {e}")

    # Register Models
    from app.models import (
        User, Subject, Assignment, TimetableEvent, Exam,
        SyllabusUnit, SyllabusTopic, StudyPlan, PlannedSession,
        StudySession, StudyGroup, GroupMember, GroupGoal, GroupTask,
        ChatConversation, ChatMessage, Achievement, UserAchievement, Notification
    )

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Register Blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.assignments import assignments_bp
    from app.routes.timetable import timetable_bp
    from app.routes.syllabus import syllabus_bp
    from app.routes.planner import planner_bp
    from app.routes.ai import ai_bp
    from app.routes.timer import timer_bp
    from app.routes.analytics import analytics_bp
    from app.routes.groups import groups_bp
    from app.routes.achievements import achievements_bp
    from app.routes.notifications import notifications_bp
    from app.routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(assignments_bp)
    app.register_blueprint(timetable_bp)
    app.register_blueprint(syllabus_bp)
    app.register_blueprint(planner_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(timer_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(groups_bp)
    app.register_blueprint(achievements_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(api_bp)

    # Security Headers
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        return response

    # Global context processor (e.g. unread notifications count, app name)
    @app.context_processor
    def inject_global_data():
        from flask_login import current_user
        unread_count = 0
        if current_user.is_authenticated:
            unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        return {
            'app_name': 'StudySync',
            'unread_notifications_count': unread_count
        }

    # Custom Error Handlers
    @app.errorhandler(404)
    def page_not_found(e):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Resource not found'}), 404
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Internal server error'}), 500
        return render_template('errors/500.html'), 500

    @app.errorhandler(403)
    def forbidden(e):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Forbidden access'}), 403
        return render_template('errors/403.html'), 403

    return app
