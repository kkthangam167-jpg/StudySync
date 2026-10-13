import json
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import StudyPlan, PlannedSession, Subject
from app.services.priority_engine import PriorityEngine
from app.services.planner_engine import PlannerEngine
from app.services.rescheduler import ReschedulerEngine
from app.services.achievement_engine import AchievementEngine

planner_bp = Blueprint('planner', __name__)

@planner_bp.route('/planner')
@login_required
def index():
    user_id = current_user.id
    today = date.today()

    # Active study plan for today
    today_plan = StudyPlan.query.filter_by(
        user_id=user_id,
        start_date=today,
        is_active=True
    ).first()

    today_sessions = today_plan.sessions.all() if today_plan else []

    # Priority Engine ranked items
    priorities = PriorityEngine.get_ranked_study_priorities(user_id, limit=8)

    # Missed sessions eligible for rescheduling
    missed_sessions = ReschedulerEngine.find_missed_sessions(user_id)

    return render_template(
        'planner/index.html',
        today=today,
        today_plan=today_plan,
        today_sessions=today_sessions,
        priorities=priorities,
        missed_sessions=missed_sessions,
        user=current_user
    )


@planner_bp.route('/planner/generate-preview', methods=['POST'])
@login_required
def generate_preview():
    """Returns candidate study plan JSON for modal review before saving."""
    plan_type = request.form.get('plan_type', 'daily')
    target_date_str = request.form.get('target_date')
    custom_hours_str = request.form.get('available_hours')

    target_date = date.today()
    if target_date_str:
        try:
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    custom_hours = None
    if custom_hours_str:
        try:
            custom_hours = float(custom_hours_str)
        except ValueError:
            pass

    plan_candidate = PlannerEngine.generate_plan(
        user=current_user,
        plan_type=plan_type,
        target_date=target_date,
        custom_available_hours=custom_hours
    )

    return jsonify({'success': True, 'plan': plan_candidate})


@planner_bp.route('/planner/accept', methods=['POST'])
@login_required
def accept_plan():
    """Saves the previewed study plan into the database."""
    data = request.get_json() if request.is_json else None
    if not data and request.form.get('plan_data'):
        data = json.loads(request.form.get('plan_data'))

    if not data:
        flash('No plan data provided to accept.', 'danger')
        return redirect(url_for('planner.index'))

    plan = PlannerEngine.save_accepted_plan(current_user.id, data)
    flash(f"Study Plan for {plan.start_date.strftime('%b %d')} accepted and activated!", 'success')
    return redirect(url_for('planner.index'))


@planner_bp.route('/planner/session/<int:session_id>/toggle', methods=['POST'])
@login_required
def toggle_session(session_id):
    session = PlannedSession.query.filter_by(id=session_id, user_id=current_user.id).first_or_404()
    
    if session.status == 'completed':
        session.status = 'pending'
    else:
        session.status = 'completed'

    db.session.commit()
    AchievementEngine.evaluate_user_achievements(current_user.id)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({'success': True, 'status': session.status})

    flash(f"Session '{session.title}' marked as {session.status}!", 'info')
    return redirect(url_for('planner.index'))


@planner_bp.route('/planner/reschedule/preview', methods=['GET', 'POST'])
@login_required
def preview_reschedule():
    session_id = request.args.get('session_id') or request.form.get('session_id')
    if not session_id:
        return jsonify({'error': 'Missing session_id'}), 400

    proposal = ReschedulerEngine.propose_reschedule(int(session_id), current_user.id)
    return jsonify(proposal)


@planner_bp.route('/planner/reschedule/confirm', methods=['POST'])
@login_required
def confirm_reschedule():
    session_id = request.form.get('session_id')
    new_date = request.form.get('proposed_date')
    new_start = request.form.get('proposed_start_time')
    new_end = request.form.get('proposed_end_time')

    if not session_id or not new_date or not new_start or not new_end:
        flash('Incomplete reschedule parameters.', 'danger')
        return redirect(url_for('planner.index'))

    ReschedulerEngine.apply_reschedule(
        session_id=int(session_id),
        user_id=current_user.id,
        new_date_str=new_date,
        new_start_time=new_start,
        new_end_time=new_end
    )

    flash(f"Session successfully rescheduled to {new_date} ({new_start} - {new_end})!", 'success')
    return redirect(url_for('planner.index'))
