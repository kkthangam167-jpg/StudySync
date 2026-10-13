from datetime import datetime, date, timedelta, time
from typing import List, Dict, Any, Optional
from app import db
from app.models import PlannedSession, StudyPlan, TimetableEvent, Exam, User

class ReschedulerEngine:
    """
    Intelligent Rescheduling Engine for missed study sessions.
    Finds conflict-free slots on subsequent days while preserving session audit history.
    """

    @classmethod
    def find_missed_sessions(cls, user_id: int) -> List[PlannedSession]:
        """Returns sessions whose scheduled date/time has passed but are still marked 'pending'."""
        today = date.today()
        now_time_str = datetime.utcnow().strftime('%H:%M')

        # Either past date and still pending, or today and end_time < current time
        past_date_sessions = PlannedSession.query.filter(
            PlannedSession.user_id == user_id,
            PlannedSession.status == 'pending',
            PlannedSession.is_break == False,
            PlannedSession.scheduled_date < today
        ).all()

        today_past_sessions = PlannedSession.query.filter(
            PlannedSession.user_id == user_id,
            PlannedSession.status == 'pending',
            PlannedSession.is_break == False,
            PlannedSession.scheduled_date == today,
            PlannedSession.end_time < now_time_str
        ).all()

        return past_date_sessions + today_past_sessions

    @classmethod
    def propose_reschedule(cls, session_id: int, user_id: int, target_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Proposes a new slot for a missed session on target_date (default: tomorrow).
        Checks for timetable and existing planned session conflicts.
        """
        session = PlannedSession.query.filter_by(id=session_id, user_id=user_id).first()
        if not session:
            return {'error': 'Session not found'}

        if not target_date:
            target_date = date.today() + timedelta(days=1)

        user = db.session.get(User, user_id)
        # Scan potential candidate slots (e.g. starting at 18:00, 19:00, 20:00, 21:00)
        duration_minutes = session.duration_minutes or 45
        day_of_week = target_date.weekday()

        candidate_hours = [18, 19, 20, 21, 16, 17]
        found_slot = None

        # Existing events on target date
        tt_events = TimetableEvent.query.filter_by(user_id=user_id, day_of_week=day_of_week).all()
        exams = Exam.query.filter_by(user_id=user_id, exam_date=target_date).all()
        existing_planned = PlannedSession.query.filter(
            PlannedSession.user_id == user_id,
            PlannedSession.scheduled_date == target_date,
            PlannedSession.status.in_(['pending', 'completed'])
        ).all()

        for h in candidate_hours:
            slot_start = time(h, 0)
            slot_end_dt = datetime.combine(target_date, slot_start) + timedelta(minutes=duration_minutes)
            slot_end = slot_end_dt.time()
            
            s_str = slot_start.strftime('%H:%M')
            e_str = slot_end.strftime('%H:%M')

            conflict = False
            # Check timetable
            for ev in tt_events:
                if not (e_str <= ev.start_time or s_str >= ev.end_time):
                    conflict = True
                    break
            if conflict:
                continue

            # Check exams
            for ex in exams:
                if not (e_str <= ex.start_time or s_str >= ex.end_time):
                    conflict = True
                    break
            if conflict:
                continue

            # Check existing planned sessions
            for ep in existing_planned:
                if not (e_str <= ep.start_time or s_str >= ep.end_time):
                    conflict = True
                    break
            if conflict:
                continue

            found_slot = (s_str, e_str)
            break

        if not found_slot:
            # Fallback slot with warning
            found_slot = ("21:00", "21:50")
            has_warning = True
            warning_msg = "Selected slot may overlap with other commitments. Please review."
        else:
            has_warning = False
            warning_msg = None

        return {
            'original_session_id': session.id,
            'title': session.title,
            'subject_name': session.subject.name if session.subject else 'General Study',
            'duration_minutes': session.duration_minutes,
            'original_date': session.scheduled_date.strftime('%Y-%m-%d'),
            'original_time': f"{session.start_time} - {session.end_time}",
            'proposed_date': target_date.strftime('%Y-%m-%d'),
            'proposed_start_time': found_slot[0],
            'proposed_end_time': found_slot[1],
            'has_warning': has_warning,
            'warning_msg': warning_msg
        }

    @classmethod
    def apply_reschedule(cls, session_id: int, user_id: int, new_date_str: str, new_start_time: str, new_end_time: str) -> PlannedSession:
        """Marks old session as 'rescheduled' and creates new session linked to original."""
        old_session = PlannedSession.query.filter_by(id=session_id, user_id=user_id).first_or_404()
        old_session.status = 'rescheduled'

        new_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()

        # Find or create active study plan for new date
        plan = StudyPlan.query.filter_by(user_id=user_id, start_date=new_date, is_active=True).first()
        if not plan:
            plan = StudyPlan(
                user_id=user_id,
                title=f"Plan - {new_date.strftime('%b %d, %Y')}",
                start_date=new_date,
                end_date=new_date,
                target_hours=3.0,
                is_active=True,
                generated_reason="Auto-created for rescheduled sessions"
            )
            db.session.add(plan)
            db.session.flush()

        rescheduled_session = PlannedSession(
            plan_id=plan.id,
            user_id=user_id,
            subject_id=old_session.subject_id,
            topic_id=old_session.topic_id,
            assignment_id=old_session.assignment_id,
            title=f"[Rescheduled] {old_session.title}",
            scheduled_date=new_date,
            start_time=new_start_time,
            end_time=new_end_time,
            duration_minutes=old_session.duration_minutes,
            is_break=False,
            status='pending',
            original_session_id=old_session.id,
            notes=f"Rescheduled from {old_session.scheduled_date.strftime('%Y-%m-%d')} ({old_session.start_time})"
        )
        db.session.add(rescheduled_session)
        db.session.commit()
        return rescheduled_session
