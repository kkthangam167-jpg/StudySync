from datetime import datetime, date
from app import db

class StudyPlan(db.Model):
    __tablename__ = 'study_plans'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    plan_type = db.Column(db.String(20), default='daily') # 'daily', 'weekly'
    start_date = db.Column(db.Date, nullable=False, default=date.today)
    end_date = db.Column(db.Date, nullable=False, default=date.today)
    target_hours = db.Column(db.Float, default=4.0)
    is_active = db.Column(db.Boolean, default=True)
    generated_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sessions = db.relationship('PlannedSession', backref='plan', lazy='dynamic', cascade='all, delete-orphan', order_by='PlannedSession.start_time')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'plan_type': self.plan_type,
            'start_date': self.start_date.strftime('%Y-%m-%d'),
            'end_date': self.end_date.strftime('%Y-%m-%d'),
            'target_hours': self.target_hours,
            'is_active': self.is_active,
            'generated_reason': self.generated_reason,
            'session_count': self.sessions.count()
        }


class PlannedSession(db.Model):
    __tablename__ = 'planned_sessions'

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('study_plans.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id', ondelete='SET NULL'), nullable=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('syllabus_topics.id', ondelete='SET NULL'), nullable=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id', ondelete='SET NULL'), nullable=True)
    
    title = db.Column(db.String(150), nullable=False)
    scheduled_date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.String(5), nullable=False) # '18:00'
    end_time = db.Column(db.String(5), nullable=False)   # '19:00'
    duration_minutes = db.Column(db.Integer, default=60)
    is_break = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='pending') # 'pending', 'completed', 'missed', 'rescheduled'
    original_session_id = db.Column(db.Integer, nullable=True) # If rescheduled, points to ancestor
    notes = db.Column(db.Text)

    subject = db.relationship('Subject', backref='planned_sessions', lazy=True)
    topic = db.relationship('SyllabusTopic', backref='planned_sessions', lazy=True)
    assignment = db.relationship('Assignment', backref='planned_sessions', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'plan_id': self.plan_id,
            'title': self.title,
            'subject_id': self.subject_id,
            'subject_name': self.subject.name if self.subject else ('Break' if self.is_break else 'General'),
            'subject_color': self.subject.color if self.subject else ('#10B981' if self.is_break else '#6366F1'),
            'scheduled_date': self.scheduled_date.strftime('%Y-%m-%d'),
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration_minutes': self.duration_minutes,
            'is_break': self.is_break,
            'status': self.status,
            'notes': self.notes
        }


class StudySession(db.Model):
    """Actual focus timer session executed by the student."""
    __tablename__ = 'study_sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id', ondelete='SET NULL'), nullable=True)
    task_title = db.Column(db.String(150), default='Focus Session')
    session_type = db.Column(db.String(20), default='focus') # 'focus', 'short_break', 'long_break'
    duration_minutes = db.Column(db.Integer, default=25)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime)
    is_completed = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)

    def to_dict(self):
        return {
            'id': self.id,
            'subject_id': self.subject_id,
            'subject_name': self.subject.name if self.subject else 'General Study',
            'task_title': self.task_title,
            'session_type': self.session_type,
            'duration_minutes': self.duration_minutes,
            'started_at': self.started_at.strftime('%Y-%m-%d %H:%M'),
            'is_completed': self.is_completed
        }
