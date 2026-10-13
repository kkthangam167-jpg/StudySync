from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Subject, SyllabusUnit, SyllabusTopic
from app.services.achievement_engine import AchievementEngine

syllabus_bp = Blueprint('syllabus', __name__)

@syllabus_bp.route('/syllabus')
@login_required
def index():
    user_id = current_user.id
    subjects = Subject.query.filter_by(user_id=user_id).all()

    # Active selected subject
    selected_subject_id = request.args.get('subject_id')
    selected_subject = None
    if selected_subject_id and selected_subject_id.isdigit():
        selected_subject = Subject.query.filter_by(id=int(selected_subject_id), user_id=user_id).first()
    
    if not selected_subject and subjects:
        selected_subject = subjects[0]

    units = []
    if selected_subject:
        units = selected_subject.syllabus_units.all()

    # Identify topics needing revision across all subjects
    needs_revision_topics = SyllabusTopic.query.filter_by(
        user_id=user_id,
        status='needs_revision'
    ).limit(8).all()

    return render_template(
        'syllabus/index.html',
        subjects=subjects,
        selected_subject=selected_subject,
        units=units,
        needs_revision_topics=needs_revision_topics
    )


@syllabus_bp.route('/subjects/new', methods=['POST'])
@login_required
def create_subject():
    code = request.form.get('code', '').strip().upper()
    name = request.form.get('name', '').strip()
    color = request.form.get('color', '#6366F1')
    professor = request.form.get('professor', '').strip()
    credits = int(request.form.get('credits', 3))

    if not code or not name:
        flash('Subject code and name are required.', 'danger')
        return redirect(url_for('syllabus.index'))

    sub = Subject(
        user_id=current_user.id,
        code=code,
        name=name,
        color=color,
        professor=professor,
        credits=credits,
        semester=current_user.semester
    )
    db.session.add(sub)
    db.session.commit()

    flash(f"Subject '{code}: {name}' created!", 'success')
    return redirect(url_for('syllabus.index', subject_id=sub.id))


@syllabus_bp.route('/subjects/<int:subject_id>/delete', methods=['POST'])
@login_required
def delete_subject(subject_id):
    sub = Subject.query.filter_by(id=subject_id, user_id=current_user.id).first_or_404()
    code = sub.code
    db.session.delete(sub)
    db.session.commit()
    flash(f"Subject '{code}' and all related records deleted.", 'info')
    return redirect(url_for('syllabus.index'))


@syllabus_bp.route('/syllabus/unit/new', methods=['POST'])
@login_required
def create_unit():
    subject_id = request.form.get('subject_id')
    unit_number = int(request.form.get('unit_number', 1))
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()

    subject = Subject.query.filter_by(id=int(subject_id), user_id=current_user.id).first_or_404()
    
    unit = SyllabusUnit(
        subject_id=subject.id,
        user_id=current_user.id,
        unit_number=unit_number,
        title=title,
        description=description
    )
    db.session.add(unit)
    db.session.commit()

    flash(f"Unit '{title}' added to {subject.code}!", 'success')
    return redirect(url_for('syllabus.index', subject_id=subject.id))


@syllabus_bp.route('/syllabus/topic/new', methods=['POST'])
@login_required
def create_topic():
    unit_id = request.form.get('unit_id')
    title = request.form.get('title', '').strip()
    notes = request.form.get('notes', '').strip()
    resource_url = request.form.get('resource_url', '').strip()

    unit = SyllabusUnit.query.filter_by(id=int(unit_id), user_id=current_user.id).first_or_404()
    
    topic = SyllabusTopic(
        unit_id=unit.id,
        user_id=current_user.id,
        title=title,
        status='not_started',
        confidence_score=3,
        notes=notes,
        resource_url=resource_url
    )
    db.session.add(topic)
    db.session.commit()

    flash(f"Topic '{title}' added!", 'success')
    return redirect(url_for('syllabus.index', subject_id=unit.subject_id))


@syllabus_bp.route('/syllabus/topic/<int:topic_id>/update', methods=['POST'])
@login_required
def update_topic(topic_id):
    topic = SyllabusTopic.query.filter_by(id=topic_id, user_id=current_user.id).first_or_404()

    new_status = request.form.get('status')
    if new_status in ['not_started', 'learning', 'completed', 'needs_revision']:
        topic.status = new_status

    confidence = request.form.get('confidence_score')
    if confidence and confidence.isdigit():
        topic.confidence_score = max(1, min(5, int(confidence)))

    notes = request.form.get('notes')
    if notes is not None:
        topic.notes = notes.strip()

    res_url = request.form.get('resource_url')
    if res_url is not None:
        topic.resource_url = res_url.strip()

    # If action is 'revised_now'
    if request.form.get('action') == 'revised_now':
        topic.last_revised_at = datetime.utcnow()
        if topic.status == 'needs_revision':
            topic.status = 'completed'

    db.session.commit()
    AchievementEngine.evaluate_user_achievements(current_user.id)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({
            'success': True,
            'topic': topic.to_dict(),
            'unit_progress': topic.unit.progress,
            'subject_progress': topic.unit.subject.syllabus_progress
        })

    flash(f"Topic '{topic.title}' updated!", 'success')
    return redirect(url_for('syllabus.index', subject_id=topic.unit.subject_id))


@syllabus_bp.route('/syllabus/topic/<int:topic_id>/delete', methods=['POST'])
@login_required
def delete_topic(topic_id):
    topic = SyllabusTopic.query.filter_by(id=topic_id, user_id=current_user.id).first_or_404()
    sub_id = topic.unit.subject_id
    db.session.delete(topic)
    db.session.commit()
    flash('Topic deleted.', 'info')
    return redirect(url_for('syllabus.index', subject_id=sub_id))
