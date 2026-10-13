import secrets
from datetime import datetime
from app import db

class StudyGroup(db.Model):
    __tablename__ = 'study_groups'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    invite_code = db.Column(db.String(12), unique=True, nullable=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    creator = db.relationship('User', foreign_keys=[created_by])
    members = db.relationship('GroupMember', backref='group', lazy='dynamic', cascade='all, delete-orphan')
    goals = db.relationship('GroupGoal', backref='group', lazy='dynamic', cascade='all, delete-orphan')

    @classmethod
    def generate_code(cls):
        return secrets.token_hex(4).upper()

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'invite_code': self.invite_code,
            'created_by': self.created_by,
            'member_count': self.members.count(),
            'goal_count': self.goals.count(),
            'created_at': self.created_at.strftime('%Y-%m-%d')
        }


class GroupMember(db.Model):
    __tablename__ = 'group_members'

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('study_groups.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    role = db.Column(db.String(20), default='member') # 'admin', 'member'
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('group_id', 'user_id', name='unique_group_member'),
    )


class GroupGoal(db.Model):
    __tablename__ = 'group_goals'

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('study_groups.id', ondelete='CASCADE'), nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    target_date = db.Column(db.Date)
    is_completed = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tasks = db.relationship('GroupTask', backref='goal', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def progress_percentage(self):
        total = self.tasks.count()
        if total == 0:
            return 100 if self.is_completed else 0
        completed = self.tasks.filter_by(is_completed=True).count()
        return round((completed / total) * 100)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'target_date': self.target_date.strftime('%Y-%m-%d') if self.target_date else None,
            'is_completed': self.is_completed,
            'progress': self.progress_percentage,
            'task_count': self.tasks.count()
        }


class GroupTask(db.Model):
    __tablename__ = 'group_tasks'

    id = db.Column(db.Integer, primary_key=True)
    goal_id = db.Column(db.Integer, db.ForeignKey('group_goals.id', ondelete='CASCADE'), nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    assigned_to_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    is_completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime)

    assigned_user = db.relationship('User', foreign_keys=[assigned_to_user_id])

    def to_dict(self):
        return {
            'id': self.id,
            'goal_id': self.goal_id,
            'title': self.title,
            'is_completed': self.is_completed,
            'assigned_to': self.assigned_user.full_name if self.assigned_user else 'Unassigned'
        }
