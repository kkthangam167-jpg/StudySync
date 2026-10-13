from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import Achievement, UserAchievement
from app.services.achievement_engine import AchievementEngine

achievements_bp = Blueprint('achievements', __name__)

@achievements_bp.route('/achievements')
@login_required
def index():
    user_id = current_user.id
    AchievementEngine.seed_default_achievements()
    AchievementEngine.evaluate_user_achievements(user_id)

    all_achievements = Achievement.query.all()
    user_earned_records = UserAchievement.query.filter_by(user_id=user_id).all()
    
    earned_dict = {ua.achievement_id: ua.earned_at for ua in user_earned_records}
    total_points = sum(ua.achievement.points for ua in user_earned_records if ua.achievement)

    # Categorize
    achievements_data = []
    for ach in all_achievements:
        is_earned = ach.id in earned_dict
        achievements_data.append({
            'achievement': ach,
            'is_earned': is_earned,
            'earned_at': earned_dict.get(ach.id)
        })

    return render_template(
        'achievements/index.html',
        achievements=achievements_data,
        total_points=total_points,
        earned_count=len(user_earned_records),
        total_count=len(all_achievements)
    )
