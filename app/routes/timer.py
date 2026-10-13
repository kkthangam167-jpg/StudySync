from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import func
from app import db
from app.models import StudySession, Subject
from app.services.achievement_engine import AchievementEngine

timer_bp = Blueprint('timer', __name__)

@timer_bp.route('/focus-timer')
@timer_bp.route('/timer')
@login_required
def index():
    user_id = current_user.id
    today = date.today()
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    subjects = Subject.query.filter_by(user_id=user_id).all()

    # Today's focus minutes
    today_minutes = db.session.query(func.coalesce(func.sum(StudySession.duration_minutes), 0)).filter(
        StudySession.user_id == user_id,
        StudySession.is_completed == True,
        StudySession.session_type == 'focus',
        func.date(StudySession.started_at) == today
    ).scalar() or 0

    # Weekly focus minutes
    weekly_minutes = db.session.query(func.coalesce(func.sum(StudySession.duration_minutes), 0)).filter(
        StudySession.user_id == user_id,
        StudySession.is_completed == True,
        StudySession.session_type == 'focus',
        StudySession.started_at >= seven_days_ago
    ).scalar() or 0

    # Recent completed sessions
    recent_sessions = StudySession.query.filter_by(
        user_id=user_id
    ).order_by(StudySession.started_at.desc()).limit(8).all()

    return render_template(
        'timer/index.html',
        subjects=subjects,
        today_hours=round(today_minutes / 60.0, 1),
        weekly_hours=round(weekly_minutes / 60.0, 1),
        recent_sessions=recent_sessions,
        user=current_user
    )


@timer_bp.route('/api/timer/save-session', methods=['POST'])
@login_required
def save_session():
    data = request.get_json() or {}
    duration_minutes = int(data.get('duration_minutes', 25))
    subject_id = data.get('subject_id')
    task_title = data.get('task_title', 'Focus Session').strip()
    session_type = data.get('session_type', 'focus')
    notes = data.get('notes', '').strip()

    sub_id = int(subject_id) if subject_id and str(subject_id).isdigit() else None

    session = StudySession(
        user_id=current_user.id,
        subject_id=sub_id,
        task_title=task_title or 'Focus Session',
        session_type=session_type,
        duration_minutes=duration_minutes,
        started_at=datetime.utcnow() - timedelta(minutes=duration_minutes),
        ended_at=datetime.utcnow(),
        is_completed=True,
        notes=notes
    )
    db.session.add(session)
    db.session.commit()

    # Check for newly unlocked milestones
    new_achievements = AchievementEngine.evaluate_user_achievements(current_user.id)
    new_badges = [a.name for a in new_achievements]

    return jsonify({
        'success': True,
        'session_id': session.id,
        'new_achievements': new_badges
    })
