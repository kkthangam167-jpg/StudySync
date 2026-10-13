from datetime import datetime, date, timedelta
from typing import List, Dict, Any
from app.models import Assignment, Exam, SyllabusTopic, Subject

class PriorityEngine:
    """
    Deterministic rule-based recommendation engine for StudySync.
    Ranks academic tasks using a documented scoring formula:
    
    Total Score = Exam Proximity Score (0-50 pts)
                + Deadline Proximity Score (0-40 pts)
                + User Priority Weight (10-30 pts)
                + Revision Need Score (0-30 pts)
                + Overdue Penalty / Urgency Boost (25 pts)
                - High Effort Damping if time is limited
    """

    @staticmethod
    def calculate_assignment_score(assignment: Assignment) -> Dict[str, Any]:
        score = 0
        reasons = []
        now = datetime.utcnow()
        time_diff = assignment.due_date - now
        hours_remaining = time_diff.total_seconds() / 3600.0
        days_remaining = hours_remaining / 24.0

        # Overdue check
        if assignment.is_overdue:
            score += 45
            reasons.append("Task is OVERDUE and requires immediate completion.")
        elif hours_remaining <= 24:
            score += 40
            reasons.append(f"Due in less than 24 hours ({round(hours_remaining, 1)}h left).")
        elif days_remaining <= 3:
            score += 30
            reasons.append(f"Due in {int(days_remaining)} days.")
        elif days_remaining <= 7:
            score += 15
            reasons.append(f"Due within a week ({int(days_remaining)} days).")
        else:
            score += 5
            reasons.append(f"Due on {assignment.due_date.strftime('%b %d')}.")

        # User priority weight
        p_weights = {'high': 30, 'medium': 20, 'low': 10}
        p_val = p_weights.get(assignment.priority.lower(), 15)
        score += p_val
        reasons.append(f"Marked as {assignment.priority.upper()} priority (+{p_val} pts).")

        # Status adjustment
        if assignment.status == 'in_progress':
            score += 10
            reasons.append("Already in progress; finish to close out task.")

        # Priority label determination
        if score >= 70:
            level = "high"
        elif score >= 40:
            level = "medium"
        else:
            level = "low"

        return {
            'id': assignment.id,
            'type': 'assignment',
            'title': assignment.title,
            'subject_name': assignment.subject.name if assignment.subject else 'General',
            'subject_color': assignment.subject.color if assignment.subject else '#6366F1',
            'due_date': assignment.due_date.strftime('%b %d, %H:%M'),
            'score': round(score, 1),
            'priority_level': level,
            'estimated_hours': assignment.estimated_hours,
            'status': assignment.status,
            'explanation': " • ".join(reasons)
        }

    @staticmethod
    def calculate_topic_revision_score(topic: SyllabusTopic, upcoming_exams: List[Exam]) -> Dict[str, Any]:
        score = 0
        reasons = []

        # Find if this topic belongs to a subject with an upcoming exam
        subject = topic.unit.subject if topic.unit else None
        subject_id = subject.id if subject else None
        
        nearest_exam = None
        min_exam_days = 999
        if subject_id:
            for exam in upcoming_exams:
                if exam.subject_id == subject_id:
                    days = (exam.exam_date - date.today()).days
                    if 0 <= days < min_exam_days:
                        min_exam_days = days
                        nearest_exam = exam

        if nearest_exam:
            if min_exam_days <= 3:
                score += 50
                reasons.append(f"Exam '{nearest_exam.title}' is in {min_exam_days} days!")
            elif min_exam_days <= 7:
                score += 35
                reasons.append(f"Exam '{nearest_exam.title}' is in {min_exam_days} days.")
            elif min_exam_days <= 14:
                score += 20
                reasons.append(f"Exam '{nearest_exam.title}' approaching in {min_exam_days} days.")

        # Topic Status
        if topic.status == 'needs_revision':
            score += 30
            reasons.append("Flagged as 'Needs Revision'.")
        elif topic.status == 'not_started':
            score += 25
            reasons.append("Not started yet.")
        elif topic.status == 'learning':
            score += 20
            reasons.append("Currently in progress.")

        # Confidence Score (1=Low, 5=Mastered)
        if topic.confidence_score <= 2:
            score += 25
            reasons.append(f"Low self-assessed confidence ({topic.confidence_score}/5).")
        elif topic.confidence_score == 3:
            score += 10
            reasons.append("Medium confidence (3/5).")

        # Recency of revision
        if topic.last_revised_at:
            days_since = (datetime.utcnow() - topic.last_revised_at).days
            if days_since >= 14:
                score += 15
                reasons.append(f"Last revised {days_since} days ago.")
        else:
            score += 10
            reasons.append("Never revised yet.")

        if score >= 70:
            level = "high"
        elif score >= 40:
            level = "medium"
        else:
            level = "low"

        return {
            'id': topic.id,
            'type': 'topic_revision',
            'title': f"Revise: {topic.title}",
            'subject_name': subject.name if subject else 'General',
            'subject_color': subject.color if subject else '#8B5CF6',
            'unit_title': topic.unit.title if topic.unit else '',
            'score': round(score, 1),
            'priority_level': level,
            'confidence_score': topic.confidence_score,
            'estimated_hours': 1.0,
            'explanation': " • ".join(reasons) if reasons else "Routine revision item"
        }

    @classmethod
    def get_ranked_study_priorities(cls, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Gathers incomplete assignments and revision topics for the student,
        scores them deterministically, and returns them sorted by score desc.
        """
        # Active assignments
        assignments = Assignment.query.filter(
            Assignment.user_id == user_id,
            Assignment.status != 'completed'
        ).all()

        # Upcoming exams
        exams = Exam.query.filter(
            Exam.user_id == user_id,
            Exam.exam_date >= date.today()
        ).all()

        # Candidate topics (not completed, or needs revision, or low confidence)
        topics = SyllabusTopic.query.filter(
            SyllabusTopic.user_id == user_id,
            (SyllabusTopic.status != 'completed') | (SyllabusTopic.status == 'needs_revision') | (SyllabusTopic.confidence_score <= 2)
        ).limit(20).all()

        ranked_items = []

        for assignment in assignments:
            ranked_items.append(cls.calculate_assignment_score(assignment))

        for topic in topics:
            ranked_items.append(cls.calculate_topic_revision_score(topic, exams))

        # Sort by deterministic score descending
        ranked_items.sort(key=lambda x: x['score'], reverse=True)
        return ranked_items[:limit]
