from datetime import datetime, date
from app import db

class Subject(db.Model):
    __tablename__ = 'subjects'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    code = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    color = db.Column(db.String(20), default='#6366F1') # Brand accent color
    professor = db.Column(db.String(100))
    credits = db.Column(db.Integer, default=3)
    semester = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    assignments = db.relationship('Assignment', backref='subject', lazy='dynamic', cascade='all, delete-orphan')
    timetable_events = db.relationship('TimetableEvent', backref='subject', lazy='dynamic', cascade='all, delete-orphan')
    exams = db.relationship('Exam', backref='subject', lazy='dynamic', cascade='all, delete-orphan')
    syllabus_units = db.relationship('SyllabusUnit', backref='subject', lazy='dynamic', cascade='all, delete-orphan', order_by='SyllabusUnit.unit_number')
    study_sessions = db.relationship('StudySession', backref='subject', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def syllabus_progress(self):
        """Calculates syllabus completion percentage based on topic status."""
        total_topics = 0
        completed_topics = 0
        for unit in self.syllabus_units:
            for topic in unit.topics:
                total_topics += 1
                if topic.status == 'completed':
                    completed_topics += 1
                elif topic.status == 'learning':
                    completed_topics += 0.5
        if total_topics == 0:
            return 0
        return round((completed_topics / total_topics) * 100, 1)

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'color': self.color,
            'professor': self.professor,
            'credits': self.credits,
            'progress': self.syllabus_progress
        }


class Assignment(db.Model):
    __tablename__ = 'assignments'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.DateTime, nullable=False, index=True)
    estimated_hours = db.Column(db.Float, default=2.0)
    priority = db.Column(db.String(20), default='medium') # 'high', 'medium', 'low'
    status = db.Column(db.String(20), default='pending') # 'pending', 'in_progress', 'completed'
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def is_overdue(self):
        if self.status == 'completed':
            return False
        return self.due_date < datetime.utcnow()

    @property
    def days_remaining(self):
        delta = self.due_date - datetime.utcnow()
        return max(0, delta.days)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'subject_id': self.subject_id,
            'subject_name': self.subject.name if self.subject else 'General',
            'subject_color': self.subject.color if self.subject else '#6366F1',
            'title': self.title,
            'description': self.description,
            'due_date': self.due_date.strftime('%Y-%m-%d %H:%M'),
            'due_date_iso': self.due_date.isoformat(),
            'estimated_hours': self.estimated_hours,
            'priority': self.priority,
            'status': self.status,
            'is_overdue': self.is_overdue,
            'completed_at': self.completed_at.strftime('%Y-%m-%d %H:%M') if self.completed_at else None
        }


class TimetableEvent(db.Model):
    __tablename__ = 'timetable_events'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id', ondelete='SET NULL'), nullable=True, index=True)
    title = db.Column(db.String(100), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False) # 0=Monday, 6=Sunday
    start_time = db.Column(db.String(5), nullable=False) # '09:00'
    end_time = db.Column(db.String(5), nullable=False)   # '10:30'
    location = db.Column(db.String(100)) # e.g. 'Lab 3', 'Hall 204'
    event_type = db.Column(db.String(30), default='lecture') # 'lecture', 'lab', 'tutorial', 'seminar'
    is_recurring = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            'id': self.id,
            'subject_id': self.subject_id,
            'subject_name': self.subject.name if self.subject else self.title,
            'subject_color': self.subject.color if self.subject else '#3B82F6',
            'title': self.title,
            'day_of_week': self.day_of_week,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'location': self.location,
            'event_type': self.event_type
        }


class Exam(db.Model):
    __tablename__ = 'exams'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False) # e.g. "DBMS Mid-Semester Exam"
    exam_date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.String(5), default='10:00')
    end_time = db.Column(db.String(5), default='13:00')
    venue = db.Column(db.String(100))
    notes = db.Column(db.Text)
    weight_percentage = db.Column(db.Float, default=30.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def days_until(self):
        delta = self.exam_date - date.today()
        return delta.days

    def to_dict(self):
        return {
            'id': self.id,
            'subject_id': self.subject_id,
            'subject_name': self.subject.name if self.subject else '',
            'subject_code': self.subject.code if self.subject else '',
            'subject_color': self.subject.color if self.subject else '#8B5CF6',
            'title': self.title,
            'exam_date': self.exam_date.strftime('%Y-%m-%d'),
            'start_time': self.start_time,
            'end_time': self.end_time,
            'venue': self.venue,
            'notes': self.notes,
            'days_until': self.days_until
        }


class SyllabusUnit(db.Model):
    __tablename__ = 'syllabus_units'

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    unit_number = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)

    topics = db.relationship('SyllabusTopic', backref='unit', lazy='dynamic', cascade='all, delete-orphan', order_by='SyllabusTopic.order_index')

    @property
    def progress(self):
        topics_list = self.topics.all()
        if not topics_list:
            return 0
        completed = sum(1 for t in topics_list if t.status == 'completed')
        learning = sum(0.5 for t in topics_list if t.status == 'learning')
        return round(((completed + learning) / len(topics_list)) * 100, 1)


class SyllabusTopic(db.Model):
    __tablename__ = 'syllabus_topics'

    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey('syllabus_units.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    status = db.Column(db.String(30), default='not_started') # 'not_started', 'learning', 'completed', 'needs_revision'
    confidence_score = db.Column(db.Integer, default=3) # 1 (Low) to 5 (Mastered)
    notes = db.Column(db.Text)
    resource_url = db.Column(db.String(255))
    last_revised_at = db.Column(db.DateTime)
    order_index = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'unit_id': self.unit_id,
            'unit_title': self.unit.title if self.unit else '',
            'subject_name': self.unit.subject.name if self.unit and self.unit.subject else '',
            'title': self.title,
            'status': self.status,
            'confidence_score': self.confidence_score,
            'notes': self.notes,
            'resource_url': self.resource_url,
            'last_revised_at': self.last_revised_at.strftime('%Y-%m-%d') if self.last_revised_at else None
        }
