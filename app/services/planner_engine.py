from datetime import datetime, date, timedelta, time
from typing import List, Dict, Any, Optional
from app import db
from app.models import (
    User, StudyPlan, PlannedSession, TimetableEvent, Exam,
    Assignment, SyllabusTopic
)
from app.services.priority_engine import PriorityEngine

class PlannerEngine:
    """
    Transparent study scheduling engine.
    Constructs conflict-free daily and weekly study sessions matching
    student available hours, timetable constraints, and priority tasks.
    """

    @staticmethod
    def _parse_preferred_hours(pref_str: str) -> tuple[time, time]:
        """Parses start and end times from preference string like 'Evening (18:00 - 22:00)'."""
        default_start = time(18, 0)
        default_end = time(22, 0)
        try:
            if '(' in pref_str and '-' in pref_str:
                time_part = pref_str.split('(')[1].split(')')[0]
                s_str, e_str = [t.strip() for t in time_part.split('-')]
                sh, sm = map(int, s_str.split(':'))
                eh, em = map(int, e_str.split(':'))
                return time(sh, sm), time(eh, em)
        except Exception:
            pass
        return default_start, default_end

    @staticmethod
    def _has_conflict(user_id: int, target_date: date, start_dt: datetime, end_dt: datetime) -> bool:
        """Checks if a proposed time slot conflicts with scheduled timetable events or exams."""
        day_of_week = target_date.weekday() # 0 = Monday
        s_time_str = start_dt.strftime('%H:%M')
        e_time_str = end_dt.strftime('%H:%M')

        # Check Timetable events
        events = TimetableEvent.query.filter_by(user_id=user_id, day_of_week=day_of_week).all()
        for ev in events:
            if not (e_time_str <= ev.start_time or s_time_str >= ev.end_time):
                return True

        # Check Exams on that date
        exams = Exam.query.filter_by(user_id=user_id, exam_date=target_date).all()
        for ex in exams:
            if not (e_time_str <= ex.start_time or s_time_str >= ex.end_time):
                return True

        return False

    @classmethod
    def generate_plan(
        cls,
        user: User,
        plan_type: str = 'daily',
        target_date: Optional[date] = None,
        custom_available_hours: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Generates a study plan candidate with detailed session breakdown and conflict checks.
        """
        if not target_date:
            target_date = date.today()

        available_hours = custom_available_hours or user.daily_available_hours or 3.0
        start_time_obj, end_time_obj = cls._parse_preferred_hours(user.preferred_study_hours or "Evening (18:00 - 22:00)")

        # Priority items
        ranked_items = PriorityEngine.get_ranked_study_priorities(user.id, limit=6)
        
        # Calculate timeline slots
        proposed_sessions = []
        current_dt = datetime.combine(target_date, start_time_obj)
        max_end_dt = datetime.combine(target_date, end_time_obj)
        
        # Total study capacity in minutes
        total_capacity_minutes = int(available_hours * 60)
        allocated_minutes = 0
        warnings = []

        if not ranked_items:
            warnings.append("No pending assignments or revision topics found. Added general academic study sessions.")
            # Fallback placeholder items
            ranked_items = [{
                'id': None,
                'type': 'general',
                'title': 'General Review & Reading',
                'subject_name': 'Core Study',
                'subject_color': '#6366F1',
                'estimated_hours': 1.5,
                'explanation': 'Self-directed revision and reading session.'
            }]

        item_idx = 0
        while allocated_minutes < total_capacity_minutes and current_dt < max_end_dt and item_idx < len(ranked_items):
            item = ranked_items[item_idx]
            session_duration = min(50, total_capacity_minutes - allocated_minutes) # 45-50 min focus block
            
            slot_end_dt = current_dt + timedelta(minutes=session_duration)
            if slot_end_dt > max_end_dt:
                session_duration = int((max_end_dt - current_dt).total_seconds() / 60)
                slot_end_dt = current_dt + timedelta(minutes=session_duration)

            if session_duration < 15:
                break

            # Conflict check
            conflict = cls._has_conflict(user.id, target_date, current_dt, slot_end_dt)
            if conflict:
                # Try skipping 30 mins
                current_dt += timedelta(minutes=30)
                continue

            # Add study session
            proposed_sessions.append({
                'title': item['title'],
                'subject_name': item.get('subject_name', 'General'),
                'subject_color': item.get('subject_color', '#6366F1'),
                'start_time': current_dt.strftime('%H:%M'),
                'end_time': slot_end_dt.strftime('%H:%M'),
                'duration_minutes': session_duration,
                'is_break': False,
                'reason': item.get('explanation', 'Priority academic item'),
                'assignment_id': item['id'] if item.get('type') == 'assignment' else None,
                'topic_id': item['id'] if item.get('type') == 'topic_revision' else None
            })
            allocated_minutes += session_duration
            current_dt = slot_end_dt

            # Insert a 10 min break if time allows
            if allocated_minutes + 10 <= total_capacity_minutes and current_dt + timedelta(minutes=10) < max_end_dt:
                break_end = current_dt + timedelta(minutes=10)
                proposed_sessions.append({
                    'title': 'Rest & Recharge Break ☕',
                    'subject_name': 'Break',
                    'subject_color': '#10B981',
                    'start_time': current_dt.strftime('%H:%M'),
                    'end_time': break_end.strftime('%H:%M'),
                    'duration_minutes': 10,
                    'is_break': True,
                    'reason': 'Cognitive recovery break between intensive focus sessions.',
                    'assignment_id': None,
                    'topic_id': None
                })
                current_dt = break_end

            item_idx += 1

        if allocated_minutes < total_capacity_minutes:
            diff_m = total_capacity_minutes - allocated_minutes
            if diff_m >= 30:
                warnings.append(f"Workload completed before filling your {available_hours}h target ({diff_m} min remaining).")

        return {
            'target_date': target_date.strftime('%Y-%m-%d'),
            'plan_type': plan_type,
            'target_hours': available_hours,
            'allocated_hours': round(allocated_minutes / 60.0, 1),
            'sessions': proposed_sessions,
            'warnings': warnings,
            'reasoning': f"Plan structured around {len(proposed_sessions)} timed blocks prioritizing upcoming deadlines and exam schedules."
        }

    @classmethod
    def save_accepted_plan(cls, user_id: int, plan_data: Dict[str, Any]) -> StudyPlan:
        """Persists the user-accepted study plan and individual sessions to the database."""
        target_date = datetime.strptime(plan_data['target_date'], '%Y-%m-%d').date()
        
        # Deactivate older active plans for the same date
        existing_plans = StudyPlan.query.filter_by(
            user_id=user_id,
            start_date=target_date,
            is_active=True
        ).all()
        for p in existing_plans:
            p.is_active = False

        plan = StudyPlan(
            user_id=user_id,
            title=f"{plan_data.get('plan_type', 'Daily').capitalize()} Plan - {target_date.strftime('%b %d, %Y')}",
            plan_type=plan_data.get('plan_type', 'daily'),
            start_date=target_date,
            end_date=target_date,
            target_hours=plan_data.get('allocated_hours', 3.0),
            is_active=True,
            generated_reason=plan_data.get('reasoning', '')
        )
        db.session.add(plan)
        db.session.flush()

        for s in plan_data.get('sessions', []):
            session = PlannedSession(
                plan_id=plan.id,
                user_id=user_id,
                title=s['title'],
                scheduled_date=target_date,
                start_time=s['start_time'],
                end_time=s['end_time'],
                duration_minutes=s['duration_minutes'],
                is_break=s.get('is_break', False),
                status='pending',
                notes=s.get('reason', ''),
                assignment_id=s.get('assignment_id'),
                topic_id=s.get('topic_id')
            )
            db.session.add(session)

        db.session.commit()
        return plan
