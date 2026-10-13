from datetime import datetime, date, timedelta
from app import db
from app.models import Subject, Assignment, Exam, SyllabusUnit, SyllabusTopic
from app.services.priority_engine import PriorityEngine

def test_priority_engine_ranking(app, user1):
    with app.app_context():
        sub = Subject(user_id=user1.id, code='CS201', name='DBMS')
        db.session.add(sub)
        db.session.flush()

        # Task 1: Due in 12 hours (High Priority + Urgent Deadline)
        asgn_urgent = Assignment(
            user_id=user1.id,
            subject_id=sub.id,
            title='Urgent Lab Report',
            due_date=datetime.utcnow() + timedelta(hours=12),
            priority='high',
            status='pending'
        )

        # Task 2: Due in 10 days (Low Priority)
        asgn_low = Assignment(
            user_id=user1.id,
            subject_id=sub.id,
            title='Casual Reading Task',
            due_date=datetime.utcnow() + timedelta(days=10),
            priority='low',
            status='pending'
        )

        # Exam approaching in 3 days for DBMS
        exam = Exam(
            user_id=user1.id,
            subject_id=sub.id,
            title='DBMS Midterm',
            exam_date=date.today() + timedelta(days=3)
        )

        # Topic needing revision for that subject
        unit = SyllabusUnit(subject_id=sub.id, user_id=user1.id, unit_number=1, title='Unit 1')
        db.session.add(unit)
        db.session.flush()
        topic = SyllabusTopic(
            unit_id=unit.id,
            user_id=user1.id,
            title='BCNF Decomposition',
            status='needs_revision',
            confidence_score=1
        )

        db.session.add_all([asgn_urgent, asgn_low, exam, topic])
        db.session.commit()

        # Run Priority Engine
        ranked = PriorityEngine.get_ranked_study_priorities(user1.id)
        assert len(ranked) >= 2

        # Highest scored item must be either the urgent assignment or revision with exam in 3 days
        top_item = ranked[0]
        assert top_item['priority_level'] == 'high'
        assert top_item['score'] >= 70
        assert 'explanation' in top_item
        assert len(top_item['explanation']) > 5

        # Casual task should score lower than urgent task
        scores = {item['title']: item['score'] for item in ranked}
        assert scores['Urgent Lab Report'] > scores['Casual Reading Task']
