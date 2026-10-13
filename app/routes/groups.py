from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import StudyGroup, GroupMember, GroupGoal, GroupTask, User, Notification
from app.services.achievement_engine import AchievementEngine

groups_bp = Blueprint('groups', __name__)

@groups_bp.route('/groups')
@login_required
def index():
    user_id = current_user.id
    memberships = GroupMember.query.filter_by(user_id=user_id).all()
    user_groups = [m.group for m in memberships if m.group]

    return render_template('groups/index.html', groups=user_groups)


@groups_bp.route('/groups/new', methods=['POST'])
@login_required
def create_group():
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()

    if not name:
        flash('Group name is required.', 'danger')
        return redirect(url_for('groups.index'))

    invite_code = StudyGroup.generate_code()
    group = StudyGroup(
        name=name,
        description=description,
        invite_code=invite_code,
        created_by=current_user.id
    )
    db.session.add(group)
    db.session.flush()

    # Add creator as admin
    membership = GroupMember(
        group_id=group.id,
        user_id=current_user.id,
        role='admin'
    )
    db.session.add(membership)
    db.session.commit()

    AchievementEngine.evaluate_user_achievements(current_user.id)
    flash(f"Study Group '{name}' created! Share Invite Code: {invite_code}", 'success')
    return redirect(url_for('groups.detail', group_id=group.id))


@groups_bp.route('/groups/join', methods=['POST'])
@login_required
def join_group():
    code = request.form.get('invite_code', '').strip().upper()
    if not code:
        flash('Please enter a valid invite code.', 'danger')
        return redirect(url_for('groups.index'))

    group = StudyGroup.query.filter_by(invite_code=code).first()
    if not group:
        flash('Invalid invite code. Group not found.', 'danger')
        return redirect(url_for('groups.index'))

    existing = GroupMember.query.filter_by(group_id=group.id, user_id=current_user.id).first()
    if existing:
        flash('You are already a member of this study group.', 'info')
        return redirect(url_for('groups.detail', group_id=group.id))

    membership = GroupMember(
        group_id=group.id,
        user_id=current_user.id,
        role='member'
    )
    db.session.add(membership)
    db.session.commit()

    AchievementEngine.evaluate_user_achievements(current_user.id)
    flash(f"Welcome to {group.name}!", 'success')
    return redirect(url_for('groups.detail', group_id=group.id))


@groups_bp.route('/groups/<int:group_id>')
@login_required
def detail(group_id):
    # Verify current user is a member
    membership = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if not membership:
        flash('You do not have permission to view this group.', 'danger')
        return redirect(url_for('groups.index'))

    group = db.get_or_404(StudyGroup, group_id)
    members = group.members.all()
    goals = group.goals.all()

    return render_template(
        'groups/detail.html',
        group=group,
        membership=membership,
        members=members,
        goals=goals
    )


@groups_bp.route('/groups/<int:group_id>/leave', methods=['POST'])
@login_required
def leave_group(group_id):
    membership = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first_or_404()
    group = membership.group
    db.session.delete(membership)
    db.session.commit()

    # If no members remain, delete group
    if group.members.count() == 0:
        db.session.delete(group)
        db.session.commit()

    flash(f"You have left '{group.name}'.", 'info')
    return redirect(url_for('groups.index'))


@groups_bp.route('/groups/<int:group_id>/goal/new', methods=['POST'])
@login_required
def create_goal(group_id):
    membership = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first_or_404()
    
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    target_date_str = request.form.get('target_date')

    if not title:
        flash('Goal title is required.', 'danger')
        return redirect(url_for('groups.detail', group_id=group_id))

    target_date = None
    if target_date_str:
        try:
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    goal = GroupGoal(
        group_id=group_id,
        title=title,
        description=description,
        target_date=target_date,
        created_by=current_user.id
    )
    db.session.add(goal)
    db.session.commit()

    flash(f"Group Goal '{title}' established!", 'success')
    return redirect(url_for('groups.detail', group_id=group_id))


@groups_bp.route('/groups/<int:group_id>/goal/<int:goal_id>/toggle', methods=['POST'])
@login_required
def toggle_goal(goal_id, group_id):
    GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first_or_404()
    goal = GroupGoal.query.filter_by(id=goal_id, group_id=group_id).first_or_404()
    goal.is_completed = not goal.is_completed
    db.session.commit()

    flash(f"Goal '{goal.title}' status updated!", 'info')
    return redirect(url_for('groups.detail', group_id=group_id))


@groups_bp.route('/groups/<int:group_id>/goal/<int:goal_id>/task/new', methods=['POST'])
@login_required
def create_task(group_id, goal_id):
    GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first_or_404()
    goal = GroupGoal.query.filter_by(id=goal_id, group_id=group_id).first_or_404()
    
    title = request.form.get('title', '').strip()
    assigned_to = request.form.get('assigned_to_user_id')

    if not title:
        flash('Task title is required.', 'danger')
        return redirect(url_for('groups.detail', group_id=group_id))

    assigned_id = int(assigned_to) if assigned_to and assigned_to.isdigit() else None

    task = GroupTask(
        goal_id=goal.id,
        title=title,
        assigned_to_user_id=assigned_id
    )
    db.session.add(task)
    db.session.commit()

    flash(f"Task '{title}' added to goal!", 'success')
    return redirect(url_for('groups.detail', group_id=group_id))


@groups_bp.route('/groups/<int:group_id>/task/<int:task_id>/toggle', methods=['POST'])
@login_required
def toggle_task(group_id, task_id):
    GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first_or_404()
    task = db.get_or_404(GroupTask, task_id)
    
    task.is_completed = not task.is_completed
    task.completed_at = datetime.utcnow() if task.is_completed else None
    db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({'success': True, 'is_completed': task.is_completed, 'goal_progress': task.goal.progress_percentage})

    flash(f"Task status updated!", 'info')
    return redirect(url_for('groups.detail', group_id=group_id))
