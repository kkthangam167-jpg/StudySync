from datetime import date, timedelta
from app import db
from app.models import Subject, TimetableEvent, Exam

def test_timetable_and_conflict_detection(auth_client1, user1, app):
    # Add initial class: Monday 09:00 - 10:30
    res = auth_client1.post('/timetable/event/new', data={
        'title': 'DBMS Lecture',
        'day_of_week': 0,
        'start_time': '09:00',
        'end_time': '10:30',
        'location': 'Hall 101',
        'event_type': 'lecture'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"DBMS Lecture" in res.data

    # Attempt to add overlapping class on same day: Monday 10:00 - 11:30 (overlaps by 30 min)
    res_conflict = auth_client1.post('/timetable/event/new', data={
        'title': 'Algorithms Lecture',
        'day_of_week': 0,
        'start_time': '10:00',
        'end_time': '11:30',
        'location': 'Hall 102',
        'event_type': 'lecture'
    }, follow_redirects=True)
    assert b"Conflict Warning" in res_conflict.data

    with app.app_context():
        # Only 1 event must exist
        count = TimetableEvent.query.filter_by(user_id=user1.id, day_of_week=0).count()
        assert count == 1

def test_exam_creation_and_countdown(auth_client1, user1, app):
    with app.app_context():
        sub = Subject(user_id=user1.id, code='CS202', name='Algorithms')
        db.session.add(sub)
        db.session.commit()
        sub_id = sub.id

    exam_date = date.today() + timedelta(days=7)
    res = auth_client1.post('/exams/new', data={
        'title': 'Algorithms Midterm',
        'subject_id': sub_id,
        'exam_date': exam_date.strftime('%Y-%m-%d'),
        'start_time': '14:00',
        'end_time': '16:00',
        'venue': 'Auditorium A',
        'weight_percentage': '35.0'
    }, follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        ex = Exam.query.filter_by(user_id=user1.id, title='Algorithms Midterm').first()
        assert ex is not None
        assert ex.days_until == 7

def test_exams_page_view(auth_client1, user1, app):
    res = auth_client1.get('/exams')
    assert res.status_code == 200
    assert b"Examinations & Assessment Calendar" in res.data
