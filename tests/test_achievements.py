from datetime import datetime
from app import db
from app.models import StudySession, UserAchievement, Achievement
from app.services.achievement_engine import AchievementEngine

def test_real_achievement_unlock_and_no_duplicates(app, user1):
    with app.app_context():
        u = db.session.get(user1.__class__, user1.id)
        AchievementEngine.seed_default_achievements()

        # Before study session: no focus achievements
        ach1 = Achievement.query.filter_by(code='first_focus_session').first()
        assert UserAchievement.query.filter_by(user_id=u.id, achievement_id=ach1.id).first() is None

        # Log real completed focus session
        sess = StudySession(
            user_id=u.id,
            task_title='Algorithms Practice',
            session_type='focus',
            duration_minutes=25,
            started_at=datetime.utcnow(),
            is_completed=True
        )
        db.session.add(sess)
        db.session.commit()

        # Evaluate
        newly_awarded = AchievementEngine.evaluate_user_achievements(u.id)
        assert any(a.code == 'first_focus_session' for a in newly_awarded)

        # Check DB
        earned = UserAchievement.query.filter_by(user_id=u.id, achievement_id=ach1.id).count()
        assert earned == 1

        # Run evaluation again — must NOT duplicate
        second_run = AchievementEngine.evaluate_user_achievements(u.id)
        assert not any(a.code == 'first_focus_session' for a in second_run)
        assert UserAchievement.query.filter_by(user_id=u.id, achievement_id=ach1.id).count() == 1
