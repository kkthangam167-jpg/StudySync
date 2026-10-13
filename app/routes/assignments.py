from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Assignment, Subject, Notification
from app.services.achievement_engine import AchievementEngine

assignments_bp = Blueprint('assignments', __name__)

@assignments_bp.route('/assignments')
@login_required
def index():
    user_id = current_user.id
    query = Assignment.query.filter_by(user_id=user_id)

    # Filters
    subject_id = request.args.get('subject_id')
    if subject_id and subject_id.isdigit():
        query = query.filter_by(subject_id=int(subject_id))

    priority = request.args.get('priority')
    if priority in ['high', 'medium', 'low']:
        query = query.filter_by(priority=priority)

    status = request.args.get('status')
    if status in ['pending', 'in_progress', 'completed']:
        query = query.filter_by(status=status)

    search = request.args.get('q', '').strip()
    if search:
        query = query.filter(Assignment.title.ilike(f'%{search}%'))

    # Sort by due_date ascending by default
    sort_by = request.args.get('sort', 'due_date')
    if sort_by == 'priority':
        query = query.order_by(Assignment.priority.asc())
    elif sort_by == 'created':
        query = query.order_by(Assignment.created_at.desc())
    else:
        query = query.order_by(Assignment.due_date.asc())

    assignments = query.all()
    subjects = Subject.query.filter_by(user_id=user_id).all()

    # Check for deadlines approaching in < 24h to trigger in-app alerts
    now = datetime.utcnow()
    for asgn in assignments:
        if asgn.status != 'completed' and not asgn.is_overdue:
            diff_hours = (asgn.due_date - now).total_seconds() / 3600
            if 0 < diff_hours <= 24:
                # Check if notification already exists
                existing_notif = Notification.query.filter_by(
                    user_id=user_id,
                    title=f"Deadline Approaching: {asgn.title}"
                ).first()
                if not existing_notif:
                    db.session.add(Notification(
                        user_id=user_id,
                        title=f"Deadline Approaching: {asgn.title}",
                        message=f"Due in less than {int(diff_hours)} hours on {asgn.due_date.strftime('%b %d, %H:%M')}.",
                        notification_type='assignment_due',
                        link_url='/assignments'
                    ))
                    db.session.commit()

    return render_template(
        'assignments/index.html',
        assignments=assignments,
        subjects=subjects,
        selected_subject=subject_id,
        selected_priority=priority,
        selected_status=status,
        search_query=search
    )


@assignments_bp.route('/assignments/new', methods=['POST'])
@login_required
def create():
    title = request.form.get('title', '').strip()
    subject_id = request.form.get('subject_id')
    due_date_str = request.form.get('due_date')
    estimated_hours = request.form.get('estimated_hours', 2.0)
    priority = request.form.get('priority', 'medium')
    description = request.form.get('description', '').strip()

    if not title or not subject_id or not due_date_str:
        flash('Assignment title, subject, and deadline are required.', 'danger')
        return redirect(url_for('assignments.index'))

    # Verify subject ownership
    subject = Subject.query.filter_by(id=int(subject_id), user_id=current_user.id).first()
    if not subject:
        flash('Invalid subject selected.', 'danger')
        return redirect(url_for('assignments.index'))

    try:
        # Handle datetime-local input ('YYYY-MM-DDTHH:MM')
        if 'T' in due_date_str:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
        else:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d %H:%M')
    except ValueError:
        flash('Invalid due date format.', 'danger')
        return redirect(url_for('assignments.index'))

    try:
        est_h = max(0.5, float(estimated_hours))
    except ValueError:
        est_h = 2.0

    assignment = Assignment(
        user_id=current_user.id,
        subject_id=subject.id,
        title=title,
        description=description,
        due_date=due_date,
        estimated_hours=est_h,
        priority=priority if priority in ['high', 'medium', 'low'] else 'medium',
        status='pending'
    )
    db.session.add(assignment)
    db.session.commit()

    flash(f"Assignment '{title}' added successfully!", 'success')
    return redirect(url_for('assignments.index'))


@assignments_bp.route('/assignments/<int:assignment_id>/edit', methods=['POST'])
@login_required
def edit(assignment_id):
    asgn = Assignment.query.filter_by(id=assignment_id, user_id=current_user.id).first_or_404()

    asgn.title = request.form.get('title', asgn.title).strip()
    subject_id = request.form.get('subject_id')
    if subject_id:
        sub = Subject.query.filter_by(id=int(subject_id), user_id=current_user.id).first()
        if sub:
            asgn.subject_id = sub.id

    due_date_str = request.form.get('due_date')
    if due_date_str:
        try:
            if 'T' in due_date_str:
                asgn.due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
            else:
                asgn.due_date = datetime.strptime(due_date_str, '%Y-%m-%d %H:%M')
        except ValueError:
            pass

    asgn.priority = request.form.get('priority', asgn.priority)
    asgn.description = request.form.get('description', asgn.description).strip()
    
    try:
        asgn.estimated_hours = float(request.form.get('estimated_hours', asgn.estimated_hours))
    except ValueError:
        pass

    db.session.commit()
    flash(f"Assignment '{asgn.title}' updated successfully.", 'success')
    return redirect(url_for('assignments.index'))


@assignments_bp.route('/assignments/<int:assignment_id>/toggle-status', methods=['POST'])
@login_required
def toggle_status(assignment_id):
    asgn = Assignment.query.filter_by(id=assignment_id, user_id=current_user.id).first_or_404()
    
    new_status = request.form.get('status')
    if new_status in ['pending', 'in_progress', 'completed']:
        asgn.status = new_status
    else:
        asgn.status = 'completed' if asgn.status != 'completed' else 'pending'

    if asgn.status == 'completed':
        asgn.completed_at = datetime.utcnow()
    else:
        asgn.completed_at = None

    db.session.commit()
    AchievementEngine.evaluate_user_achievements(current_user.id)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({'success': True, 'status': asgn.status, 'completed_at': asgn.completed_at.strftime('%Y-%m-%d') if asgn.completed_at else None})

    flash(f"Assignment '{asgn.title}' marked as {asgn.status}!", 'info')
    return redirect(url_for('assignments.index'))


@assignments_bp.route('/assignments/<int:assignment_id>/delete', methods=['POST'])
@login_required
def delete(assignment_id):
    asgn = Assignment.query.filter_by(id=assignment_id, user_id=current_user.id).first_or_404()
    title = asgn.title
    db.session.delete(asgn)
    db.session.commit()
    flash(f"Assignment '{title}' deleted.", 'info')
    return redirect(url_for('assignments.index'))
