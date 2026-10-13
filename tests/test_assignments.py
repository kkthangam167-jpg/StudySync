from datetime import datetime, timedelta
from app import db
from app.models import Subject, Assignment

def test_assignment_crud(auth_client1, user1, app):
    with app.app_context():
        sub = Subject(user_id=user1.id, code='CS201', name='DBMS')
        db.session.add(sub)
        db.session.commit()
        sub_id = sub.id

    due_str = (datetime.utcnow() + timedelta(days=3)).strftime('%Y-%m-%dT18:00')

    # Create
    res = auth_client1.post('/assignments/new', data={
        'title': 'SQL Normalization Lab',
        'subject_id': sub_id,
        'due_date': due_str,
        'estimated_hours': '3.0',
        'priority': 'high',
        'description': '3NF proof'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b"SQL Normalization Lab" in res.data

    with app.app_context():
        asgn = Assignment.query.filter_by(user_id=user1.id, title='SQL Normalization Lab').first()
        assert asgn is not None
        assert asgn.priority == 'high'
        assert asgn.status == 'pending'
        assert not asgn.is_overdue
        asgn_id = asgn.id

    # Toggle Status to completed
    res_toggle = auth_client1.post(f'/assignments/{asgn_id}/toggle-status', follow_redirects=True)
    assert res_toggle.status_code == 200

    with app.app_context():
        asgn_updated = db.session.get(Assignment, asgn_id)
        assert asgn_updated.status == 'completed'
        assert asgn_updated.completed_at is not None

    # Delete
    res_delete = auth_client1.post(f'/assignments/{asgn_id}/delete', follow_redirects=True)
    assert res_delete.status_code == 200
    with app.app_context():
        assert db.session.get(Assignment, asgn_id) is None
