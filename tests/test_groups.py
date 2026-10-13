from app import db
from app.models import StudyGroup, GroupMember, GroupGoal

def test_study_group_creation_and_joining(client, user1, user2, app):
    # User 1 logs in and creates a group
    client.post('/login', data={'login_id': user1.username, 'password': 'password123'}, follow_redirects=True)
    res = client.post('/groups/new', data={
        'name': 'Algorithms Study Circle',
        'description': 'Mastering Graph algorithms'
    }, follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        group = StudyGroup.query.filter_by(name='Algorithms Study Circle').first()
        assert group is not None
        assert group.created_by == user1.id
        invite_code = group.invite_code
        group_id = group.id

        # Verify creator is admin
        m1 = GroupMember.query.filter_by(group_id=group_id, user_id=user1.id).first()
        assert m1.role == 'admin'

    # User 2 logs in and joins with invite code
    client.get('/logout', follow_redirects=True)
    client.post('/login', data={'login_id': user2.username, 'password': 'password456'}, follow_redirects=True)

    res_join = client.post('/groups/join', data={'invite_code': invite_code}, follow_redirects=True)
    assert res_join.status_code == 200
    assert b"Welcome to Algorithms Study Circle" in res_join.data

    with app.app_context():
        m2 = GroupMember.query.filter_by(group_id=group_id, user_id=user2.id).first()
        assert m2 is not None
        assert m2.role == 'member'

def test_unauthorized_group_access(client, user1, user2, app):
    with app.app_context():
        # Group owned by user1 only
        g = StudyGroup(name='Private Group', invite_code='SECRET99', created_by=user1.id)
        db.session.add(g)
        db.session.flush()
        db.session.add(GroupMember(group_id=g.id, user_id=user1.id, role='admin'))
        db.session.commit()
        g_id = g.id

    # User 2 tries to access group without being a member
    client.post('/login', data={'login_id': user2.username, 'password': 'password456'}, follow_redirects=True)
    res = client.get(f'/groups/{g_id}', follow_redirects=True)
    assert b"You do not have permission to view this group" in res.data
