from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import TimetableEvent, Exam, Subject

timetable_bp = Blueprint('timetable', __name__)

DAYS_OF_WEEK = [
    (0, 'Monday'),
    (1, 'Tuesday'),
    (2, 'Wednesday'),
    (3, 'Thursday'),
    (4, 'Friday'),
    (5, 'Saturday'),
    (6, 'Sunday'),
]

@timetable_bp.route('/timetable')
@login_required
def index():
    user_id = current_user.id
    events = TimetableEvent.query.filter_by(user_id=user_id).order_by(TimetableEvent.start_time).all()
    exams = Exam.query.filter_by(user_id=user_id).order_by(Exam.exam_date).all()
    subjects = Subject.query.filter_by(user_id=user_id).all()

    # Organize events by day of week
    timetable_by_day = {day_idx: [] for day_idx, _ in DAYS_OF_WEEK}
    for ev in events:
        timetable_by_day[ev.day_of_week].append(ev)

    return render_template(
        'timetable/index.html',
        days=DAYS_OF_WEEK,
        timetable_by_day=timetable_by_day,
        exams=exams,
        subjects=subjects,
        today_weekday=date.today().weekday()
    )


@timetable_bp.route('/timetable/event/new', methods=['POST'])
@login_required
def create_event():
    title = request.form.get('title', '').strip()
    subject_id = request.form.get('subject_id')
    day_of_week = int(request.form.get('day_of_week', 0))
    start_time = request.form.get('start_time', '').strip()
    end_time = request.form.get('end_time', '').strip()
    location = request.form.get('location', '').strip()
    event_type = request.form.get('event_type', 'lecture')

    if not title or not start_time or not end_time:
        flash('Title, start time, and end time are required.', 'danger')
        return redirect(url_for('timetable.index'))

    if start_time >= end_time:
        flash('Start time must be before end time.', 'danger')
        return redirect(url_for('timetable.index'))

    # Conflict detection check on same day
    existing_events = TimetableEvent.query.filter_by(
        user_id=current_user.id,
        day_of_week=day_of_week
    ).all()

    has_conflict = False
    conflicting_event = None
    for ev in existing_events:
        if not (end_time <= ev.start_time or start_time >= ev.end_time):
            has_conflict = True
            conflicting_event = ev
            break

    if has_conflict:
        flash(f"Conflict Warning: Overlaps with '{conflicting_event.title}' ({conflicting_event.start_time} - {conflicting_event.end_time}). Event not added.", 'warning')
        return redirect(url_for('timetable.index'))

    sub_id = int(subject_id) if subject_id and subject_id.isdigit() else None

    event = TimetableEvent(
        user_id=current_user.id,
        subject_id=sub_id,
        title=title,
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
        location=location,
        event_type=event_type,
        is_recurring=True
    )
    db.session.add(event)
    db.session.commit()

    flash(f"Class '{title}' added to timetable!", 'success')
    return redirect(url_for('timetable.index'))


@timetable_bp.route('/timetable/event/<int:event_id>/delete', methods=['POST'])
@login_required
def delete_event(event_id):
    ev = TimetableEvent.query.filter_by(id=event_id, user_id=current_user.id).first_or_404()
    db.session.delete(ev)
    db.session.commit()
    flash('Timetable class deleted.', 'info')
    return redirect(url_for('timetable.index'))


@timetable_bp.route('/exams')
@login_required
def exams_view():
    user_id = current_user.id
    exams = Exam.query.filter_by(user_id=user_id).order_by(Exam.exam_date).all()
    subjects = Subject.query.filter_by(user_id=user_id).all()
    return render_template(
        'timetable/exams.html',
        exams=exams,
        subjects=subjects
    )


@timetable_bp.route('/exams/new', methods=['POST'])
@login_required
def create_exam():
    title = request.form.get('title', '').strip()
    subject_id = request.form.get('subject_id')
    exam_date_str = request.form.get('exam_date')
    start_time = request.form.get('start_time', '10:00')
    end_time = request.form.get('end_time', '13:00')
    venue = request.form.get('venue', '').strip()
    notes = request.form.get('notes', '').strip()
    weight = request.form.get('weight_percentage', 30.0)

    fallback_url = request.referrer or url_for('timetable.exams_view')

    if not title or not subject_id or not exam_date_str:
        flash('Exam title, subject, and date are required.', 'danger')
        return redirect(fallback_url)

    try:
        exam_date = datetime.strptime(exam_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid exam date.', 'danger')
        return redirect(fallback_url)

    try:
        weight_val = float(weight)
    except ValueError:
        weight_val = 30.0

    exam = Exam(
        user_id=current_user.id,
        subject_id=int(subject_id),
        title=title,
        exam_date=exam_date,
        start_time=start_time,
        end_time=end_time,
        venue=venue,
        notes=notes,
        weight_percentage=weight_val
    )
    db.session.add(exam)
    db.session.commit()

    flash(f"Exam '{title}' scheduled! Countdown activated.", 'success')
    return redirect(fallback_url)


@timetable_bp.route('/exams/<int:exam_id>/delete', methods=['POST'])
@login_required
def delete_exam(exam_id):
    ex = Exam.query.filter_by(id=exam_id, user_id=current_user.id).first_or_404()
    db.session.delete(ex)
    db.session.commit()
    flash('Exam removed.', 'info')
    return redirect(request.referrer or url_for('timetable.exams_view'))
