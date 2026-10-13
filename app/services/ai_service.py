import os
import re
import logging
from typing import Dict, Any, List, Optional
from datetime import date, datetime
from app.models import User, Exam, Assignment, SyllabusTopic, Subject

logger = logging.getLogger(__name__)

# Core System Instruction for StudySync AI Tutor
SYSTEM_INSTRUCTION = (
    "You are StudySync AI, an expert, encouraging, and clear academic companion for university students.\n\n"
    "CRITICAL ACADEMIC & BEHAVIORAL RULES:\n"
    "1. Academic Grounding: When student academic records (upcoming examinations, pending assignments, "
    "syllabus topics, and available hours) are provided below, use ONLY these verified records. "
    "NEVER invent, hallucinate, or assume deadlines, courses, or exam schedules that are not listed.\n"
    "2. Data Integrity: You cannot directly execute SQL commands or alter database records. "
    "If the student requests schedule modifications or study plan creation, formulate a clear proposal "
    "and advise them to confirm it in the StudySync Planner tab.\n"
    "3. Clarity & Structure: Provide structured explanations with clear Markdown headings, bullet points, "
    "and language-tagged code blocks (e.g. ```python, ```sql) where relevant.\n"
    "4. Pedagogical Guidance: Use the Feynman technique and relatable examples for complex engineering concepts. "
    "When creating quizzes, include clear solutions or hints.\n"
    "5. Safety & Privacy: Never request or display private credentials, passwords, or personal tokens."
)

class AIService:
    """
    Configurable AI Study Assistant service using the official Google GenAI SDK.
    Provides contextual academic grounding, strict privacy boundaries,
    and reliable fallbacks when API keys are unconfigured or quota is exhausted.
    """

    @staticmethod
    def get_api_key() -> str:
        """Reads GEMINI_API_KEY securely from environment variables or Flask app config."""
        env_key = os.environ.get('GEMINI_API_KEY')
        if env_key is not None:
            return env_key.strip()
        try:
            from flask import current_app, has_app_context
            if has_app_context() and current_app:
                key = current_app.config.get('GEMINI_API_KEY')
                if key:
                    return str(key).strip()
        except Exception:
            pass
        return ''

    @staticmethod
    def get_model_name() -> str:
        """Reads configured Gemini model name, defaulting to gemini-3.1-flash-lite."""
        env_model = os.environ.get('GEMINI_MODEL')
        model = ''
        if env_model is not None and env_model.strip():
            model = env_model.strip()
        else:
            try:
                from flask import current_app, has_app_context
                if has_app_context() and current_app:
                    m = current_app.config.get('GEMINI_MODEL')
                    if m:
                        model = str(m).strip()
            except Exception:
                pass
        if not model:
            model = 'gemini-3.1-flash-lite'

        # Automatically upgrade deprecated / unavailable model identifiers
        if model in ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-2.0-flash']:
            return 'gemini-3.1-flash-lite'
        return model

    @classmethod
    def is_configured(cls) -> bool:
        """Checks if a non-empty, non-placeholder API key is configured."""
        key = cls.get_api_key()
        return bool(key) and key.lower() not in ['your_gemini_api_key_here', 'placeholder', 'none', 'false']

    @classmethod
    def build_student_context(cls, user: User) -> str:
        """
        Builds a safe, minimized summary of the student's authorized academic commitments.
        Never includes passwords, personal tokens, or external private data.
        """
        context_parts = []
        context_parts.append(f"Student: {user.full_name} ({user.program}, {user.semester})")
        context_parts.append(f"Daily Available Study Time: {user.daily_available_hours} hours")
        context_parts.append(f"Preferred Study Hours Window: {user.preferred_study_hours}")

        # Enrolled subjects
        subjects = Subject.query.filter_by(user_id=user.id).all()
        if subjects:
            sub_lines = [f"- {s.code}: {s.name} ({s.syllabus_progress}% completed)" for s in subjects]
            context_parts.append("Enrolled Courses:\n" + "\n".join(sub_lines))

        # Upcoming exams
        exams = Exam.query.filter(Exam.user_id == user.id, Exam.exam_date >= date.today()).order_by(Exam.exam_date).limit(5).all()
        if exams:
            exam_lines = [
                f"- {e.title} ({e.subject.name if e.subject else 'General'}) on {e.exam_date.strftime('%b %d, %Y')} "
                f"({e.days_until} days remaining, Venue: {e.venue or 'TBA'})"
                for e in exams
            ]
            context_parts.append("Upcoming Exams:\n" + "\n".join(exam_lines))
        else:
            context_parts.append("Upcoming Exams: None scheduled currently in StudySync.")

        # Pending assignments
        assignments = Assignment.query.filter(
            Assignment.user_id == user.id,
            Assignment.status != 'completed'
        ).order_by(Assignment.due_date).limit(6).all()
        if assignments:
            asgn_lines = [
                f"- {a.title} ({a.subject.name if a.subject else 'General'}), Priority: {a.priority.upper()}, "
                f"Due: {a.due_date.strftime('%b %d, %Y at %H:%M')}, Est. Effort: {a.estimated_hours}h"
                for a in assignments
            ]
            context_parts.append("Pending Assignments:\n" + "\n".join(asgn_lines))
        else:
            context_parts.append("Pending Assignments: All assignments are completed!")

        # Syllabus topics requiring revision or attention
        topics = SyllabusTopic.query.filter(
            SyllabusTopic.user_id == user.id,
            (SyllabusTopic.status.in_(['needs_revision', 'not_started'])) | (SyllabusTopic.confidence_score <= 2)
        ).limit(6).all()
        if topics:
            top_lines = [
                f"- {t.title} ({t.unit.subject.name if t.unit and t.unit.subject else 'General'}), "
                f"Confidence: {t.confidence_score}/5, Status: {t.status}"
                for t in topics
            ]
            context_parts.append("Priority Topics to Revise:\n" + "\n".join(top_lines))

        return "\n\n".join(context_parts)

    @classmethod
    def generate_response(
        cls,
        user: User,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        use_academic_context: bool = True
    ) -> Dict[str, Any]:
        """
        Sends the request to Google Gemini API or provides an intelligent deterministic fallback.
        Ensures strict server-side processing, sanitization, and graceful error categorization.
        """
        if not cls.is_configured():
            return cls._fallback_response(
                user,
                user_message,
                reason="GEMINI_API_KEY is not configured. Running in StudySync offline academic mode."
            )

        api_key = cls.get_api_key()
        model_name = cls.get_model_name()

        try:
            from google import genai
            from google.genai import types
            from google.genai.errors import APIError

            client = genai.Client(api_key=api_key)

            # Assemble system instruction and student profile
            sys_instruction = SYSTEM_INSTRUCTION
            if use_academic_context:
                student_context = cls.build_student_context(user)
                sys_instruction += f"\n\n--- AUTHENTICATED STUDENT ACADEMIC PROFILE ---\n{student_context}"

            # Format multi-turn conversation contents
            contents = []
            if conversation_history:
                for msg in conversation_history[-8:]: # Keep last 8 messages for context
                    role = "user" if msg.get('sender') == 'user' else "model"
                    contents.append(f"{role.upper()}: {msg.get('content')}")
            contents.append(f"USER: {user_message}")
            full_prompt = "\n".join(contents)

            # Build candidate models list: start with configured model, then verified active models
            models_to_try = [model_name]
            for fallback_m in ['gemini-3.1-flash-lite', 'gemini-3-flash-preview', 'gemini-3.8-flash', 'gemini-3.5-flash']:
                if fallback_m not in models_to_try:
                    models_to_try.append(fallback_m)

            response_text = None
            active_model = model_name
            last_err = None

            for candidate_model in models_to_try:
                try:
                    response = client.models.generate_content(
                        model=candidate_model,
                        contents=full_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=sys_instruction,
                            temperature=0.7,
                            max_output_tokens=2048,
                        )
                    )
                    if response and response.text:
                        response_text = response.text.strip()
                        active_model = candidate_model
                        break
                except Exception as candidate_err:
                    last_err = candidate_err
                    err_str = str(candidate_err)
                    # If this model is deprecated (404/NOT_FOUND), temporarily unavailable (503/504),
                    # or quota is exhausted (429/RESOURCE_EXHAUSTED), continue to fallback models!
                    if any(code in err_str for code in ['404', 'NOT_FOUND', '503', '504', 'UNAVAILABLE', 'DEADLINE_EXCEEDED', '429', 'RESOURCE_EXHAUSTED', 'QUOTA']):
                        logger.warning(
                            f"Gemini model '{candidate_model}' unavailable ({type(candidate_err).__name__}). Trying fallback model..."
                        )
                        continue
                    # For auth or invalid API key errors, stop attempting other models
                    raise candidate_err

            if not response_text and last_err:
                raise last_err

            return {
                'success': True,
                'is_live': True,
                'content': response_text or "I received an empty response. Please try rephrasing your question.",
                'is_grounded': use_academic_context,
                'provider': f'Google Gemini API ({active_model})',
                'warning': None
            }

        except Exception as e:
            error_message = cls._classify_gemini_error(e, model_name)
            logger.error(f"Google GenAI API call failed: {error_message}")
            
            # Return safe fallback with clean, actionable explanation
            fallback = cls._fallback_response(user, user_message, reason=error_message)
            fallback['is_live'] = False
            fallback['provider'] = f'Google Gemini API (Fallback: {error_message})'
            return fallback

    @classmethod
    def _classify_gemini_error(cls, error: Exception, model_name: str) -> str:
        """Maps API exceptions to human-friendly diagnostic messages without leaking secrets."""
        err_str = str(error)
        api_key = cls.get_api_key()
        if api_key and api_key in err_str:
            err_str = err_str.replace(api_key, '[REDACTED_API_KEY]')
        
        # Check for Quota / Rate Limiting (HTTP 429)
        if '429' in err_str or 'RESOURCE_EXHAUSTED' in err_str or 'QUOTA_EXCEEDED' in err_str:
            return "Gemini API rate limit or quota exceeded. Please wait a moment before trying again."
            
        # Check for Invalid API Key (HTTP 400/403)
        if 'API_KEY_INVALID' in err_str or ('INVALID_ARGUMENT' in err_str and 'key' in err_str.lower()):
            return "Invalid Gemini API Key. Please verify your GEMINI_API_KEY in the .env file."
            
        # Check for Model Not Found / Deprecated (HTTP 404)
        if '404' in err_str or 'NOT_FOUND' in err_str or 'model' in err_str.lower():
            return f"Model '{model_name}' is not available or has been deprecated. Try setting GEMINI_MODEL=gemini-3.5-flash or gemini-3.8-flash."
            
        # Network / Connection timeouts
        if 'ConnectError' in type(error).__name__ or 'Timeout' in type(error).__name__ or 'nodename nor servname provided' in err_str:
            return "Network connection error reaching Google Gemini servers. Please check your internet connectivity."
            
        # General safe error representation
        clean_msg = re.sub(r'AIza[0-9A-Za-z-_]{10,}', '[REDACTED_API_KEY]', err_str)
        return f"Gemini API notice: {clean_msg[:120]}"

    @classmethod
    def _fallback_response(cls, user: User, user_message: str, reason: str) -> Dict[str, Any]:
        """
        Graceful fallback when Gemini API key is missing, invalid, or quota is exceeded.
        Provides deterministic academic guidance derived from the student's actual database records.
        """
        msg_lower = user_message.lower()
        content = ""

        if any(w in msg_lower for w in ['study today', 'what should i study', 'schedule', 'plan']):
            from app.services.priority_engine import PriorityEngine
            priorities = PriorityEngine.get_ranked_study_priorities(user.id, limit=3)
            
            if priorities:
                recs = "\n".join([f"1. **{p['title']}** ({p['subject_name']}) — *{p['explanation']}*" for p in priorities])
                content = (
                    f"### 📋 Recommended Study Focus for Today\n\n"
                    f"Based on your actual StudySync academic profile and upcoming deadlines:\n\n"
                    f"{recs}\n\n"
                    f"💡 *Tip: Open the **Study Planner** tab to generate a structured conflict-free study schedule!*"
                )
            else:
                content = (
                    "### 🌟 You're All Caught Up!\n\n"
                    "You have no overdue assignments or high-priority exam topics flagged right now. "
                    "This is an ideal time to explore ahead in your syllabus or review earlier units in the **Syllabus Tracker**."
                )

        elif any(w in msg_lower for w in ['exam', 'prepare', 'test', 'midterm', 'finals']):
            exams = Exam.query.filter(Exam.user_id == user.id, Exam.exam_date >= date.today()).order_by(Exam.exam_date).limit(3).all()
            if exams:
                ex_text = "\n".join([f"- **{e.title}**: {e.exam_date.strftime('%A, %B %d')} ({e.days_until} days remaining in {e.venue or 'TBA'})" for e in exams])
                content = (
                    f"### 🎯 Upcoming Examination Summary\n\n"
                    f"{ex_text}\n\n"
                    f"**Action Plan:**\n"
                    f"- Dedicate 45 minutes to past question papers.\n"
                    f"- Check off high-yield topics in your **Syllabus Tracker**."
                )
            else:
                content = "You have no upcoming exams registered in StudySync yet. Add your examination schedule in the **Timetable & Exams** tab to activate countdowns and revision alerts."

        elif any(w in msg_lower for w in ['assignment', 'deadline', 'task', 'homework']):
            assignments = Assignment.query.filter(Assignment.user_id == user.id, Assignment.status != 'completed').order_by(Assignment.due_date).limit(3).all()
            if assignments:
                asgn_text = "\n".join([f"- **{a.title}** ({a.subject.name if a.subject else 'General'}) — Due {a.due_date.strftime('%b %d, %H:%M')} (Priority: {a.priority.upper()})" for a in assignments])
                content = (
                    f"### 📝 Active Assignments Overview\n\n"
                    f"{asgn_text}\n\n"
                    f"💡 *Remember to mark tasks complete in the **Assignments** tab once submitted.*"
                )
            else:
                content = "Great job! All your assignments in StudySync are currently marked as completed."

        elif any(w in msg_lower for w in ['explain', 'what is', 'concept', 'normalization', 'algorithm', 'how does']):
            content = (
                f"### 📚 Academic Concept Assistant (Offline Mode)\n\n"
                f"You asked: *\"{user_message}\"*\n\n"
                f"To get live, in-depth AI explanations and code walkthroughs powered by Google Gemini, please add your `GEMINI_API_KEY` in your `.env` file.\n\n"
                f"**Quick Study Tip:** Breaking down complex computer science concepts using the **Feynman Technique** (explaining it in simple words without technical jargon) helps identify knowledge gaps fast!"
            )

        else:
            content = (
                f"### 👋 Hello, {user.full_name.split()[0]}!\n\n"
                f"I am your **StudySync Academic Assistant**. I can help you review your timetable, prioritize assignments, and guide your daily study plan.\n\n"
                f"Try asking:\n"
                f"- *\"What should I study today?\"*\n"
                f"- *\"How many days until my next exam?\"*\n"
                f"- *\"Which assignments need my immediate attention?\"*\n\n"
                f"*(Note: Live generative responses require a configured `GEMINI_API_KEY`. Running in intelligent offline mode).* "
            )

        return {
            'success': True,
            'is_live': False,
            'content': content,
            'is_grounded': True,
            'provider': 'StudySync Offline Intelligence',
            'warning': reason
        }
