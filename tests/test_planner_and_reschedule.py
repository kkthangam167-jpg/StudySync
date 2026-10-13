from datetime import date, timedelta
from app import db
from app.models import Subject, Assignment, StudyPlan, PlannedSession
from app.services.planner_engine import PlannerEngine
from app.services.rescheduler import ReschedulerEngine

def test_planner_engine_generation(app, user1):
    with app.app_context():
        u = db.session.get(user1.__class__, user1.id)
        sub = Subject(user_id=u.id, code='CS201', name='DBMS')
        db.session.add(sub)
        db.session.flush()

        asgn = Assignment(
            user_id=u.id,
            subject_id=sub.id,
            title='Project Milestone',
            due_date=date.today() + timedelta(days=2),
            priority='high',
            status='pending'
        )
        db.session.add(asgn)
        db.session.commit()

        # Generate daily plan
        plan_dict = PlannerEngine.generate_plan(user=u, plan_type='daily', custom_available_hours=2.5)
        assert plan_dict['target_hours'] == 2.5
        assert len(plan_dict['sessions']) >= 1

        # Check that sessions have start/end times and break blocks
        has_break = any(s.get('is_break') for s in plan_dict['sessions'])
        # Save accepted plan
        saved_plan = PlannerEngine.save_accepted_plan(u.id, plan_dict)
        assert saved_plan.id is not None
        assert saved_plan.sessions.count() == len(plan_dict['sessions'])

def test_rescheduler_engine(app, user1):
    with app.app_context():
        u = db.session.get(user1.__class__, user1.id)
        # Create an active plan on yesterday
        yesterday = date.today() - timedelta(days=1)
        plan = StudyPlan(
            user_id=u.id,
            title='Yesterday Plan',
            start_date=yesterday,
            end_date=yesterday,
            target_hours=2.0,
            is_active=True
        )
        db.session.add(plan)
        db.session.flush()

        # Add a missed session on yesterday
        missed = PlannedSession(
            plan_id=plan.id,
            user_id=u.id,
            title='Missed Algorithms Review',
            scheduled_date=yesterday,
            start_time='18:00',
            end_time='19:00',
            duration_minutes=60,
            is_break=False,
            status='pending'
        )
        db.session.add(missed)
        db.session.commit()
        missed_id = missed.id

        # 1. Detection
        missed_list = ReschedulerEngine.find_missed_sessions(u.id)
        assert any(m.id == missed_id for m in missed_list)

        # 2. Proposal
        proposal = ReschedulerEngine.propose_reschedule(missed_id, u.id)
        assert proposal['original_session_id'] == missed_id
        assert proposal['proposed_date'] == (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
        assert proposal['proposed_start_time'] is not None

        # 3. Apply Reschedule
        rescheduled_obj = ReschedulerEngine.apply_reschedule(
            session_id=missed_id,
            user_id=u.id,
            new_date_str=proposal['proposed_date'],
            new_start_time=proposal['proposed_start_time'],
            new_end_time=proposal['proposed_end_time']
        )
        assert rescheduled_obj.original_session_id == missed_id
        assert '[Rescheduled]' in rescheduled_obj.title

        # Verify old session marked 'rescheduled' (audit preserved)
        old_refreshed = db.session.get(PlannedSession, missed_id)
        assert old_refreshed.status == 'rescheduled'
