from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from app.models import (
    Subject, Assignment, TimetableEvent, Exam,
    StudyPlan, PlannedSession, StudySession
)
from app.services.analytics_service import AnalyticsService
from app.services.priority_engine import PriorityEngine

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
def landing():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    return render_template('landing.html')


@dashboard_bp.route('/dashboard')
@login_required
def index():
    user_id = current_user.id
    today = date.today()
    day_of_week = today.weekday() # 0 = Monday

    # 1. Today's Timetable Classes
    today_classes = TimetableEvent.query.filter_by(
        user_id=user_id,
        day_of_week=day_of_week
    ).order_by(TimetableEvent.start_time).all()

    # 2. Upcoming Examinations
    upcoming_exams = Exam.query.filter(
        Exam.user_id == user_id,
        Exam.exam_date >= today
    ).order_by(Exam.exam_date).limit(4).all()

    # 3. Pending & Overdue Assignments
    now = datetime.utcnow()
    pending_assignments = Assignment.query.filter(
        Assignment.user_id == user_id,
        Assignment.status != 'completed'
    ).order_by(Assignment.due_date).limit(5).all()

    overdue_assignments = [a for a in pending_assignments if a.is_overdue]

    # 4. Today's Active Study Plan
    today_plan = StudyPlan.query.filter_by(
        user_id=user_id,
        start_date=today,
        is_active=True
    ).first()

    today_planned_sessions = []
    if today_plan:
        today_planned_sessions = today_plan.sessions.all()

    # 5. Smart Study Recommendations (from Priority Engine)
    top_recommendations = PriorityEngine.get_ranked_study_priorities(user_id, limit=3)

    # 6. High-level Metrics
    metrics = AnalyticsService.get_dashboard_metrics(user_id)

    # 7. Recent Focus Sessions (Completed today)
    recent_sessions = StudySession.query.filter(
        StudySession.user_id == user_id,
        StudySession.is_completed == True
    ).order_by(StudySession.started_at.desc()).limit(3).all()

    # Active Subjects for quick-select
    subjects = Subject.query.filter_by(user_id=user_id).all()

    return render_template(
        'dashboard/index.html',
        today=today,
        today_classes=today_classes,
        upcoming_exams=upcoming_exams,
        pending_assignments=pending_assignments,
        overdue_assignments=overdue_assignments,
        today_plan=today_plan,
        today_planned_sessions=today_planned_sessions,
        top_recommendations=top_recommendations,
        metrics=metrics,
        recent_sessions=recent_sessions,
        subjects=subjects
    )
