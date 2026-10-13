from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    semester = db.Column(db.String(20), default="Semester 4")
    program = db.Column(db.String(100), default="B.E. Computer Science & Engineering")
    
    # Study preferences
    preferred_study_hours = db.Column(db.String(50), default="Evening (18:00 - 22:00)")
    daily_available_hours = db.Column(db.Float, default=4.0)
    focus_duration_minutes = db.Column(db.Integer, default=25)
    short_break_minutes = db.Column(db.Integer, default=5)
    long_break_minutes = db.Column(db.Integer, default=15)
    
    # UI and Notifications
    theme_preference = db.Column(db.String(10), default='dark') # 'dark' or 'light'
    email_notifications = db.Column(db.Boolean, default=True)
    in_app_notifications = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships with cascade delete to guarantee complete data isolation & safe account deletion
    subjects = db.relationship('Subject', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    assignments = db.relationship('Assignment', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    timetable_events = db.relationship('TimetableEvent', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    exams = db.relationship('Exam', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    study_plans = db.relationship('StudyPlan', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    study_sessions = db.relationship('StudySession', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    chat_conversations = db.relationship('ChatConversation', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    user_achievements = db.relationship('UserAchievement', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    group_memberships = db.relationship('GroupMember', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'semester': self.semester,
            'program': self.program,
            'preferred_study_hours': self.preferred_study_hours,
            'daily_available_hours': self.daily_available_hours,
            'focus_duration_minutes': self.focus_duration_minutes,
            'theme_preference': self.theme_preference
        }

    def __repr__(self):
        return f'<User {self.username}>'
