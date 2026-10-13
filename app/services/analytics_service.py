import io
import csv
from datetime import datetime, date, timedelta
from typing import Dict, Any, List
from sqlalchemy import func
from app import db
from app.models import (
    User, StudySession, Assignment, Subject,
    SyllabusTopic, PlannedSession, UserAchievement
)

class AnalyticsService:
    """
    Computes academic performance and habit analytics using real student database records.
    """

    @classmethod
    def get_dashboard_metrics(cls, user_id: int) -> Dict[str, Any]:
        """Provides fast high-level aggregations for the Smart Dashboard."""
        today = date.today()
        seven_days_ago = datetime.utcnow() - timedelta(days=7)

        # Weekly focus time in minutes
        weekly_focus_minutes = db.session.query(func.coalesce(func.sum(StudySession.duration_minutes), 0)).filter(
            StudySession.user_id == user_id,
            StudySession.is_completed == True,
            StudySession.session_type == 'focus',
            StudySession.started_at >= seven_days_ago
        ).scalar() or 0

        # Today focus minutes
        today_focus_minutes = db.session.query(func.coalesce(func.sum(StudySession.duration_minutes), 0)).filter(
            StudySession.user_id == user_id,
            StudySession.is_completed == True,
            StudySession.session_type == 'focus',
            func.date(StudySession.started_at) == today
        ).scalar() or 0

        # Assignments
        total_assignments = Assignment.query.filter_by(user_id=user_id).count()
        completed_assignments = Assignment.query.filter_by(user_id=user_id, status='completed').count()
        pending_assignments = total_assignments - completed_assignments
        
        now = datetime.utcnow()
        overdue_assignments = Assignment.query.filter(
            Assignment.user_id == user_id,
            Assignment.status != 'completed',
            Assignment.due_date < now
        ).count()

        # Overall syllabus progress across all user subjects
        user_subjects = Subject.query.filter_by(user_id=user_id).all()
        if user_subjects:
            avg_syllabus_progress = round(sum(s.syllabus_progress for s in user_subjects) / len(user_subjects), 1)
        else:
            avg_syllabus_progress = 0.0

        # Achievements earned
        achievements_earned = UserAchievement.query.filter_by(user_id=user_id).count()

        return {
            'weekly_focus_hours': round(weekly_focus_minutes / 60.0, 1),
            'today_focus_hours': round(today_focus_minutes / 60.0, 1),
            'today_focus_minutes': int(today_focus_minutes),
            'total_assignments': total_assignments,
            'completed_assignments': completed_assignments,
            'pending_assignments': pending_assignments,
            'overdue_assignments': overdue_assignments,
            'avg_syllabus_progress': avg_syllabus_progress,
            'achievements_earned': achievements_earned,
            'active_subjects_count': len(user_subjects)
        }

    @classmethod
    def get_weekly_study_chart_data(cls, user_id: int) -> Dict[str, Any]:
        """Provides daily study hours for the past 7 days for Chart.js."""
        today = date.today()
        labels = []
        actual_hours = []
        planned_hours = []

        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            day_str = day.strftime('%a (%b %d)')
            labels.append(day_str)

            # Actual minutes
            actual_min = db.session.query(func.coalesce(func.sum(StudySession.duration_minutes), 0)).filter(
                StudySession.user_id == user_id,
                StudySession.is_completed == True,
                StudySession.session_type == 'focus',
                func.date(StudySession.started_at) == day
            ).scalar() or 0
            actual_hours.append(round(actual_min / 60.0, 1))

            # Planned minutes
            planned_min = db.session.query(func.coalesce(func.sum(PlannedSession.duration_minutes), 0)).filter(
                PlannedSession.user_id == user_id,
                PlannedSession.scheduled_date == day,
                PlannedSession.is_break == False
            ).scalar() or 0
            planned_hours.append(round(planned_min / 60.0, 1))

        return {
            'labels': labels,
            'actual_hours': actual_hours,
            'planned_hours': planned_hours
        }

    @classmethod
    def get_subject_progress_chart_data(cls, user_id: int) -> Dict[str, Any]:
        """Returns subject-wise syllabus progress and colors for bar/donut chart."""
        subjects = Subject.query.filter_by(user_id=user_id).all()
        labels = [s.code or s.name for s in subjects]
        progress_data = [s.syllabus_progress for s in subjects]
        colors = [s.color or '#6366F1' for s in subjects]

        return {
            'labels': labels,
            'data': progress_data,
            'colors': colors
        }

    @classmethod
    def generate_csv_summary(cls, user_id: int) -> str:
        """Generates a downloadable CSV text containing student study sessions and assignment records."""
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(['StudySync Academic Data Export'])
        writer.writerow(['Exported At', datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')])
        writer.writerow([])

        # Section 1: Study Sessions
        writer.writerow(['FOCUS STUDY SESSIONS'])
        writer.writerow(['ID', 'Subject', 'Task Title', 'Duration (min)', 'Started At', 'Completed'])
        sessions = StudySession.query.filter_by(user_id=user_id).order_by(StudySession.started_at.desc()).all()
        for s in sessions:
            writer.writerow([
                s.id,
                s.subject.name if s.subject else 'General',
                s.task_title,
                s.duration_minutes,
                s.started_at.strftime('%Y-%m-%d %H:%M'),
                s.is_completed
            ])

        writer.writerow([])
        # Section 2: Assignments
        writer.writerow(['ASSIGNMENTS & DEADLINES'])
        writer.writerow(['ID', 'Subject', 'Title', 'Due Date', 'Priority', 'Status', 'Completed At'])
        assignments = Assignment.query.filter_by(user_id=user_id).order_by(Assignment.due_date.asc()).all()
        for a in assignments:
            writer.writerow([
                a.id,
                a.subject.name if a.subject else 'General',
                a.title,
                a.due_date.strftime('%Y-%m-%d %H:%M'),
                a.priority,
                a.status,
                a.completed_at.strftime('%Y-%m-%d %H:%M') if a.completed_at else 'N/A'
            ])

        writer.writerow([])
        # Section 3: Syllabus Topics
        writer.writerow(['SYLLABUS PROGRESS'])
        writer.writerow(['ID', 'Subject', 'Unit', 'Topic Title', 'Status', 'Confidence (1-5)'])
        topics = SyllabusTopic.query.filter_by(user_id=user_id).all()
        for t in topics:
            writer.writerow([
                t.id,
                t.unit.subject.name if t.unit and t.unit.subject else 'N/A',
                t.unit.title if t.unit else 'N/A',
                t.title,
                t.status,
                t.confidence_score
            ])

        return output.getvalue()
