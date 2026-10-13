from app import db
from app.models import Subject, SyllabusUnit, SyllabusTopic

def test_syllabus_progress_calculation(auth_client1, user1, app):
    with app.app_context():
        sub = Subject(user_id=user1.id, code='CS203', name='OS')
        db.session.add(sub)
        db.session.flush()

        unit = SyllabusUnit(subject_id=sub.id, user_id=user1.id, unit_number=1, title='Unit 1: Processes')
        db.session.add(unit)
        db.session.flush()

        # 2 topics: 1 completed, 1 learning -> (1 + 0.5) / 2 = 75%
        t1 = SyllabusTopic(unit_id=unit.id, user_id=user1.id, title='Process State', status='completed', confidence_score=5)
        t2 = SyllabusTopic(unit_id=unit.id, user_id=user1.id, title='Threads & Concurrency', status='learning', confidence_score=3)
        db.session.add_all([t1, t2])
        db.session.commit()

        sub_reloaded = db.session.get(Subject, sub.id)
        assert sub_reloaded.syllabus_progress == 75.0
        assert sub_reloaded.syllabus_units.first().progress == 75.0

def test_topic_revision_status_update(auth_client1, user1, app):
    with app.app_context():
        sub = Subject(user_id=user1.id, code='CS204', name='Networks')
        db.session.add(sub)
        db.session.flush()

        unit = SyllabusUnit(subject_id=sub.id, user_id=user1.id, unit_number=1, title='Unit 1')
        db.session.add(unit)
        db.session.flush()

        topic = SyllabusTopic(unit_id=unit.id, user_id=user1.id, title='Subnetting', status='not_started', confidence_score=2)
        db.session.add(topic)
        db.session.commit()
        topic_id = topic.id

    # Update to needs_revision
    res = auth_client1.post(f'/syllabus/topic/{topic_id}/update', data={
        'status': 'needs_revision',
        'confidence_score': '2'
    }, follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        t = db.session.get(SyllabusTopic, topic_id)
        assert t.status == 'needs_revision'
        assert t.confidence_score == 2
