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

__all__ = [
    'auth_bp',
    'dashboard_bp',
    'assignments_bp',
    'timetable_bp',
    'syllabus_bp',
    'planner_bp',
    'ai_bp',
    'timer_bp',
    'analytics_bp',
    'groups_bp',
    'achievements_bp',
    'notifications_bp',
    'api_bp'
]
