from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import (
    User, Subject, Assignment, TimetableEvent, Exam,
    SyllabusUnit, SyllabusTopic, StudySession
)
from app.services.achievement_engine import AchievementEngine

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        full_name = request.form.get('full_name', '').strip()
        semester = request.form.get('semester', 'Semester 4')
        program = request.form.get('program', 'B.E. Computer Science & Engineering')

        # Validation
        if not username or not email or not password or not full_name:
            flash('All required fields must be filled.', 'danger')
            return render_template('auth/register.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return render_template('auth/register.html')

        if User.query.filter_by(username=username).first():
            flash('Username is already taken. Please choose another.', 'danger')
            return render_template('auth/register.html')

        if User.query.filter_by(email=email).first():
            flash('Email is already registered. Please log in.', 'danger')
            return render_template('auth/register.html')

        user = User(
            username=username,
            email=email,
            full_name=full_name,
            semester=semester,
            program=program
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # Seed initial achievements
        AchievementEngine.seed_default_achievements()

        login_user(user)
        flash(f'Welcome to StudySync, {user.full_name}! Your academic dashboard is ready.', 'success')
        return redirect(url_for('dashboard.index'))

    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        login_id = request.form.get('login_id', '').strip() # can be username or email
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        user = User.query.filter(
            (User.username == login_id) | (User.email == login_id.lower())
        ).first()

        if user and user.check_password(password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('dashboard.index')
            flash(f'Welcome back, {user.full_name}!', 'success')
            return redirect(next_page)

        flash('Invalid username/email or password.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out safely.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name', current_user.full_name).strip()
        current_user.semester = request.form.get('semester', current_user.semester).strip()
        current_user.program = request.form.get('program', current_user.program).strip()
        current_user.preferred_study_hours = request.form.get('preferred_study_hours', current_user.preferred_study_hours)
        
        try:
            avail_hours = float(request.form.get('daily_available_hours', current_user.daily_available_hours))
            current_user.daily_available_hours = max(1.0, min(12.0, avail_hours))
        except ValueError:
            pass

        try:
            focus_mins = int(request.form.get('focus_duration_minutes', current_user.focus_duration_minutes))
            current_user.focus_duration_minutes = max(15, min(90, focus_mins))
        except ValueError:
            pass

        current_user.theme_preference = request.form.get('theme_preference', current_user.theme_preference)
        current_user.in_app_notifications = bool(request.form.get('in_app_notifications'))

        db.session.commit()
        flash('Your profile and study preferences have been updated!', 'success')
        return redirect(url_for('auth.profile'))

    return render_template('auth/profile.html', user=current_user)


@auth_bp.route('/profile/delete-account', methods=['POST'])
@login_required
def delete_account():
    user = current_user
    db.session.delete(user)
    db.session.commit()
    logout_user()
    flash('Your account and all associated academic data have been permanently deleted.', 'info')
    return redirect(url_for('dashboard.landing'))


@auth_bp.route('/demo-seed', methods=['POST'])
@login_required
def seed_demo_data():
    """
    Populates realistic academic records for testing and demonstration
    specifically tailored for a 2nd year B.E. CSE student.
    """
    user_id = current_user.id

    # Create Subjects if not existing
    subjects_data = [
        {'code': 'CS201', 'name': 'Database Management Systems', 'color': '#6366F1', 'prof': 'Dr. Sharma'},
        {'code': 'CS202', 'name': 'Design & Analysis of Algorithms', 'color': '#EC4899', 'prof': 'Prof. Radhika'},
        {'code': 'CS203', 'name': 'Operating Systems', 'color': '#3B82F6', 'prof': 'Dr. Venkatesh'},
        {'code': 'CS204', 'name': 'Computer Networks', 'color': '#10B981', 'prof': 'Prof. Ananya'},
    ]

    created_subjects = {}
    for s_info in subjects_data:
        sub = Subject.query.filter_by(user_id=user_id, code=s_info['code']).first()
        if not sub:
            sub = Subject(
                user_id=user_id,
                code=s_info['code'],
                name=s_info['name'],
                color=s_info['color'],
                professor=s_info['prof'],
                credits=4,
                semester='Semester 4'
            )
            db.session.add(sub)
            db.session.flush()
        created_subjects[s_info['code']] = sub

    # Create Assignments
    today = datetime.utcnow()
    assignments_data = [
        {
            'sub': 'CS201',
            'title': 'SQL Schema & Normalization Lab Report',
            'due': today + timedelta(days=2),
            'hours': 3.0,
            'prio': 'high',
            'status': 'in_progress',
            'desc': 'Design 3NF schema for healthcare hospital management with BCNF proof.'
        },
        {
            'sub': 'CS202',
            'title': 'Dynamic Programming Knapsack Implementation',
            'due': today + timedelta(days=5),
            'hours': 2.5,
            'prio': 'high',
            'status': 'pending',
            'desc': 'Implement 0/1 knapsack in Python and analyze memoized recurrence relation.'
        },
        {
            'sub': 'CS203',
            'title': 'Process Scheduling Algorithm Simulation',
            'due': today + timedelta(days=8),
            'hours': 4.0,
            'prio': 'medium',
            'status': 'pending',
            'desc': 'Simulate Round Robin and Multi-Level Feedback Queue scheduling.'
        },
        {
            'sub': 'CS204',
            'title': 'TCP/UDP Socket Programming Assignment',
            'due': today - timedelta(days=1), # completed
            'hours': 2.0,
            'prio': 'medium',
            'status': 'completed',
            'desc': 'Client-server chat implementation using socket library.'
        }
    ]

    for a_info in assignments_data:
        existing = Assignment.query.filter_by(user_id=user_id, title=a_info['title']).first()
        if not existing:
            asgn = Assignment(
                user_id=user_id,
                subject_id=created_subjects[a_info['sub']].id,
                title=a_info['title'],
                description=a_info['desc'],
                due_date=a_info['due'],
                estimated_hours=a_info['hours'],
                priority=a_info['prio'],
                status=a_info['status'],
                completed_at=datetime.utcnow() if a_info['status'] == 'completed' else None
            )
            db.session.add(asgn)

    # Create Upcoming Exams
    exams_data = [
        {
            'sub': 'CS201',
            'title': 'DBMS Mid-Semester Exam',
            'date': date.today() + timedelta(days=6),
            'start': '10:00',
            'end': '12:00',
            'venue': 'Engineering Hall 302',
            'notes': 'Covers ER modeling, Relational Algebra, SQL, Normalization (1NF to BCNF).'
        },
        {
            'sub': 'CS202',
            'title': 'Algorithms Theory Examination',
            'date': date.today() + timedelta(days=12),
            'start': '14:00',
            'end': '16:00',
            'venue': 'CSE Auditorium',
            'notes': 'Greedy methods, Divide & Conquer, Dynamic Programming, and Graph Traversals.'
        }
    ]

    for ex in exams_data:
        existing = Exam.query.filter_by(user_id=user_id, title=ex['title']).first()
        if not existing:
            exam_obj = Exam(
                user_id=user_id,
                subject_id=created_subjects[ex['sub']].id,
                title=ex['title'],
                exam_date=ex['date'],
                start_time=ex['start'],
                end_time=ex['end'],
                venue=ex['venue'],
                notes=ex['notes'],
                weight_percentage=30.0
            )
            db.session.add(exam_obj)

    # Create Timetable Events (Monday to Friday)
    timetable_data = [
        {'sub': 'CS201', 'title': 'DBMS Lecture', 'day': 0, 's': '09:00', 'e': '10:30', 'loc': 'Hall 201', 'type': 'lecture'},
        {'sub': 'CS202', 'title': 'Algorithms Lecture', 'day': 0, 's': '11:00', 'e': '12:30', 'loc': 'Hall 204', 'type': 'lecture'},
        {'sub': 'CS203', 'title': 'OS Lab Session', 'day': 1, 's': '14:00', 'e': '16:30', 'loc': 'Linux Lab 2', 'type': 'lab'},
        {'sub': 'CS204', 'title': 'Computer Networks Lecture', 'day': 2, 's': '10:00', 'e': '11:30', 'loc': 'Hall 105', 'type': 'lecture'},
        {'sub': 'CS202', 'title': 'Algorithms Tutorial', 'day': 3, 's': '14:00', 'e': '15:30', 'loc': 'Seminar Hall', 'type': 'tutorial'},
        {'sub': 'CS201', 'title': 'DBMS Lab', 'day': 4, 's': '09:30', 'e': '12:30', 'loc': 'Database Lab 1', 'type': 'lab'}
    ]

    for tt in timetable_data:
        existing = TimetableEvent.query.filter_by(
            user_id=user_id,
            title=tt['title'],
            day_of_week=tt['day'],
            start_time=tt['s']
        ).first()
        if not existing:
            te = TimetableEvent(
                user_id=user_id,
                subject_id=created_subjects[tt['sub']].id,
                title=tt['title'],
                day_of_week=tt['day'],
                start_time=tt['s'],
                end_time=tt['e'],
                location=tt['loc'],
                event_type=tt['type'],
                is_recurring=True
            )
            db.session.add(te)

    # Create Syllabus Units & Topics for DBMS
    dbms_sub = created_subjects['CS201']
    unit1 = SyllabusUnit.query.filter_by(subject_id=dbms_sub.id, unit_number=1).first()
    if not unit1:
        unit1 = SyllabusUnit(
            subject_id=dbms_sub.id,
            user_id=user_id,
            unit_number=1,
            title='Unit 1: Relational Model & SQL',
            description='Relational schema, keys, relational algebra, SQL DDL/DML and joins.'
        )
        db.session.add(unit1)
        db.session.flush()

        # Topics
        topics = [
            {'title': 'ER Diagrams & Conversion to Tables', 'status': 'completed', 'conf': 4},
            {'title': 'Relational Algebra Operators', 'status': 'completed', 'conf': 5},
            {'title': 'Complex SQL Subqueries & Joins', 'status': 'learning', 'conf': 3},
        ]
        for idx, t in enumerate(topics):
            db.session.add(SyllabusTopic(
                unit_id=unit1.id,
                user_id=user_id,
                title=t['title'],
                status=t['status'],
                confidence_score=t['conf'],
                order_index=idx
            ))

    unit2 = SyllabusUnit.query.filter_by(subject_id=dbms_sub.id, unit_number=2).first()
    if not unit2:
        unit2 = SyllabusUnit(
            subject_id=dbms_sub.id,
            user_id=user_id,
            unit_number=2,
            title='Unit 2: Normalization & Functional Dependencies',
            description='FDs, 1NF, 2NF, 3NF, BCNF decomposition and losslessness.'
        )
        db.session.add(unit2)
        db.session.flush()

        topics = [
            {'title': 'Closure of Attributes & Canonical Cover', 'status': 'needs_revision', 'conf': 2},
            {'title': '3NF vs BCNF Decomposition Proofs', 'status': 'not_started', 'conf': 1},
        ]
        for idx, t in enumerate(topics):
            db.session.add(SyllabusTopic(
                unit_id=unit2.id,
                user_id=user_id,
                title=t['title'],
                status=t['status'],
                confidence_score=t['conf'],
                order_index=idx
            ))

    # Add realistic past focus sessions for analytics
    for i in range(1, 5):
        session_date = datetime.utcnow() - timedelta(days=i, hours=2)
        db.session.add(StudySession(
            user_id=user_id,
            subject_id=dbms_sub.id,
            task_title=f"Practice SQL & Algorithms block #{i}",
            session_type='focus',
            duration_minutes=45,
            started_at=session_date,
            ended_at=session_date + timedelta(minutes=45),
            is_completed=True
        ))

    db.session.commit()
    AchievementEngine.evaluate_user_achievements(user_id)
    flash('Sample academic data loaded successfully! Explore your dashboard, timetable, syllabus, and study planner.', 'success')
    return redirect(url_for('dashboard.index'))
