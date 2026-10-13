import os
import sys
from dotenv import load_dotenv

# Ensure .env is explicitly loaded from the project directory before Flask initializes
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
env_file = os.path.join(BASE_DIR, '.env')
if os.path.exists(env_file):
    load_dotenv(dotenv_path=env_file)
else:
    load_dotenv()

import click
from app import create_app, db
from app.models import User
from app.services.achievement_engine import AchievementEngine

app = create_app(os.environ.get('FLASK_ENV', 'development'))

def do_init_db():
    with app.app_context():
        db.create_all()
        AchievementEngine.seed_default_achievements()
        print("[OK] Database tables initialized and achievements seeded successfully!")

def do_seed_demo():
    with app.app_context():
        db.create_all()
        AchievementEngine.seed_default_achievements()

        demo_user = User.query.filter_by(username="demo_student").first()
        if not demo_user:
            demo_user = User(
                username="demo_student",
                email="demo@studysync.edu",
                full_name="Alex Chen",
                semester="Semester 4",
                program="B.E. Computer Science & Engineering",
                preferred_study_hours="Evening (18:00 - 22:00)",
                daily_available_hours=4.0
            )
            demo_user.set_password("password123")
            db.session.add(demo_user)
            db.session.commit()
            print("[OK] Created demo user: 'demo_student' (password: 'password123')")
        else:
            print("[OK] Demo user 'demo_student' already exists.")

        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['_user_id'] = str(demo_user.id)
            client.post('/demo-seed', follow_redirects=True)
            print("[OK] Demo 2nd Year CSE academic coursework populated successfully!")

@app.cli.command("init-db")
def init_db_cli():
    """Initializes the database tables."""
    do_init_db()

@app.cli.command("seed-demo")
def seed_demo_cli():
    """Seeds a test demo student account with sample coursework."""
    do_seed_demo()

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'init-db':
        do_init_db()
    elif len(sys.argv) > 1 and sys.argv[1] == 'seed-demo':
        do_seed_demo()
    else:
        with app.app_context():
            db.create_all()
            AchievementEngine.seed_default_achievements()
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=True)
