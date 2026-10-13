import pytest
from app import create_app, db
from app.models import User
from app.services.achievement_engine import AchievementEngine

@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        AchievementEngine.seed_default_achievements()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

@pytest.fixture
def user1(app):
    with app.app_context():
        u = User(
            username='student1',
            email='student1@test.edu',
            full_name='Student One',
            semester='Semester 4',
            daily_available_hours=3.5,
            preferred_study_hours='Evening (18:00 - 22:00)'
        )
        u.set_password('password123')
        db.session.add(u)
        db.session.commit()
        return db.session.get(User, u.id)

@pytest.fixture
def user2(app):
    with app.app_context():
        u = User(
            username='student2',
            email='student2@test.edu',
            full_name='Student Two',
            semester='Semester 4',
            daily_available_hours=4.0,
            preferred_study_hours='Evening (18:00 - 22:00)'
        )
        u.set_password('password456')
        db.session.add(u)
        db.session.commit()
        return db.session.get(User, u.id)

@pytest.fixture
def auth_client1(client, user1):
    client.post('/login', data={'login_id': 'student1', 'password': 'password123'}, follow_redirects=True)
    return client
