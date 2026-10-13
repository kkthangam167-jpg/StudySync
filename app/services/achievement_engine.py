from datetime import datetime, date, timedelta
from app import db
from app.models import (
    User, Achievement, UserAchievement, StudySession,
    Assignment, SyllabusTopic, GroupMember, Notification
)

DEFAULT_ACHIEVEMENTS = [
    {
        'code': 'first_focus_session',
        'name': 'Focus Pioneer',
        'description': 'Completed your very first focus study session.',
        'icon': 'zap',
        'category': 'focus',
        'points': 50
    },
    {
        'code': 'five_focus_sessions',
        'name': 'Deep Worker',
        'description': 'Completed 5 focused study sessions.',
        'icon': 'target',
        'category': 'focus',
        'points': 100
    },
    {
        'code': 'first_assignment_done',
        'name': 'Task Crusher',
        'description': 'Successfully marked your first assignment as completed.',
        'icon': 'check-circle',
        'category': 'assignment',
        'points': 50
    },
    {
        'code': 'five_assignments_done',
        'name': 'Submission Master',
        'description': 'Completed 5 assignments ahead of or on deadline.',
        'icon': 'award',
        'category': 'assignment',
        'points': 150
    },
    {
        'code': 'topic_mastered',
        'name': 'Knowledge Seeker',
        'description': 'Achieved level 5/5 confidence on a syllabus topic.',
        'icon': 'book-open',
        'category': 'syllabus',
        'points': 50
    },
    {
        'code': 'five_topics_completed',
        'name': 'Syllabus Explorer',
        'description': 'Fully completed 5 syllabus topics.',
        'icon': 'compass',
        'category': 'syllabus',
        'points': 100
    },
    {
        'code': 'group_collaborator',
        'name': 'Study Buddy',
        'description': 'Joined or created a collaborative study group.',
        'icon': 'users',
        'category': 'collaboration',
        'points': 75
    },
    {
        'code': 'weekly_consistency',
        'name': 'Consistency Champion',
        'description': 'Studied on at least 3 distinct days this week.',
        'icon': 'calendar',
        'category': 'consistency',
        'points': 150
    }
]

class AchievementEngine:
    """
    Evaluates real student database records and awards verifiable achievement badges.
    """

    @classmethod
    def seed_default_achievements(cls):
        """Ensures the achievement catalog is populated in the database."""
        for ach in DEFAULT_ACHIEVEMENTS:
            existing = Achievement.query.filter_by(code=ach['code']).first()
            if not existing:
                new_ach = Achievement(
                    code=ach['code'],
                    name=ach['name'],
                    description=ach['description'],
                    icon=ach['icon'],
                    category=ach['category'],
                    points=ach['points']
                )
                db.session.add(new_ach)
        db.session.commit()

    @classmethod
    def evaluate_user_achievements(cls, user_id: int):
        """
        Scans student's real records to unlock newly earned badges.
        Returns newly unlocked achievements list.
        """
        cls.seed_default_achievements()
        newly_awarded = []

        # Current user achievements
        earned_codes = {ua.achievement.code for ua in UserAchievement.query.filter_by(user_id=user_id).all() if ua.achievement}

        # 1. Focus session counts
        focus_count = StudySession.query.filter_by(user_id=user_id, is_completed=True, session_type='focus').count()
        if focus_count >= 1 and 'first_focus_session' not in earned_codes:
            cls._award(user_id, 'first_focus_session', newly_awarded)
        if focus_count >= 5 and 'five_focus_sessions' not in earned_codes:
            cls._award(user_id, 'five_focus_sessions', newly_awarded)

        # 2. Assignment completions
        completed_asgn = Assignment.query.filter_by(user_id=user_id, status='completed').count()
        if completed_asgn >= 1 and 'first_assignment_done' not in earned_codes:
            cls._award(user_id, 'first_assignment_done', newly_awarded)
        if completed_asgn >= 5 and 'five_assignments_done' not in earned_codes:
            cls._award(user_id, 'five_assignments_done', newly_awarded)

        # 3. Syllabus progress
        mastered_topics = SyllabusTopic.query.filter_by(user_id=user_id, confidence_score=5).count()
        if mastered_topics >= 1 and 'topic_mastered' not in earned_codes:
            cls._award(user_id, 'topic_mastered', newly_awarded)

        completed_topics = SyllabusTopic.query.filter_by(user_id=user_id, status='completed').count()
        if completed_topics >= 5 and 'five_topics_completed' not in earned_codes:
            cls._award(user_id, 'five_topics_completed', newly_awarded)

        # 4. Collaboration
        group_count = GroupMember.query.filter_by(user_id=user_id).count()
        if group_count >= 1 and 'group_collaborator' not in earned_codes:
            cls._award(user_id, 'group_collaborator', newly_awarded)

        # 5. Weekly consistency (studied on 3 distinct days in last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_sessions = StudySession.query.filter(
            StudySession.user_id == user_id,
            StudySession.started_at >= seven_days_ago,
            StudySession.is_completed == True
        ).all()
        distinct_study_days = {s.started_at.date() for s in recent_sessions}
        if len(distinct_study_days) >= 3 and 'weekly_consistency' not in earned_codes:
            cls._award(user_id, 'weekly_consistency', newly_awarded)

        if newly_awarded:
            db.session.commit()

        return newly_awarded

    @classmethod
    def _award(cls, user_id: int, achievement_code: str, awarded_list: list):
        ach = Achievement.query.filter_by(code=achievement_code).first()
        if ach:
            ua = UserAchievement(user_id=user_id, achievement_id=ach.id)
            db.session.add(ua)
            awarded_list.append(ach)

            # Create notification
            notif = Notification(
                user_id=user_id,
                title=f"Achievement Unlocked: {ach.name}! 🏆",
                message=ach.description,
                notification_type='achievement',
                link_url='/achievements'
            )
            db.session.add(notif)
