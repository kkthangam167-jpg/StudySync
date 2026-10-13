from datetime import datetime, timedelta
from app import db
from app.models import Subject, Assignment

def test_user_data_isolation(client, user1, user2, app):
    # Setup data for user 1
    with app.app_context():
        sub1 = Subject(user_id=user1.id, code='CS201', name='User1 Secret Subject')
        db.session.add(sub1)
        db.session.flush()

        asgn1 = Assignment(
            user_id=user1.id,
            subject_id=sub1.id,
            title='User1 Private Assignment',
            due_date=datetime.utcnow() + timedelta(days=2),
            priority='high',
            status='pending'
        )
        db.session.add(asgn1)
        db.session.commit()
        asgn1_id = asgn1.id
        sub1_id = sub1.id

    # Log in as user 2
    client.post('/login', data={'login_id': user2.username, 'password': 'password456'}, follow_redirects=True)

    # 1. User 2 views assignments list -> must NOT see User 1's assignment
    res_list = client.get('/assignments')
    assert b"User1 Private Assignment" not in res_list.data

    # 2. User 2 attempts to toggle User 1's assignment status -> must return 404 (isolated)
    res_toggle = client.post(f'/assignments/{asgn1_id}/toggle-status')
    assert res_toggle.status_code == 404

    # 3. User 2 attempts to delete User 1's assignment -> must return 404
    res_delete = client.post(f'/assignments/{asgn1_id}/delete')
    assert res_delete.status_code == 404

    # Verify User 1's assignment is still intact
    with app.app_context():
        asgn_check = db.session.get(Assignment, asgn1_id)
        assert asgn_check is not None
        assert asgn_check.status == 'pending'
