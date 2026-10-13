from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required
from app import db
from app.models import Assignment, Subject, SyllabusTopic

api_bp = Blueprint('api', __name__)

@api_bp.route('/api/health')
def health_check():
    """Production health check endpoint."""
    try:
        # Verify database connection
        db.session.execute(db.text('SELECT 1'))
        return jsonify({
            'status': 'healthy',
            'application': 'StudySync',
            'database': 'connected'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500


@api_bp.route('/api/theme', methods=['POST'])
@login_required
def toggle_theme():
    """Updates user theme preference ('dark' or 'light')."""
    data = request.get_json() or {}
    new_theme = data.get('theme', 'dark')
    if new_theme in ['dark', 'light']:
        current_user.theme_preference = new_theme
        db.session.commit()
        return jsonify({'success': True, 'theme': new_theme})
    return jsonify({'error': 'Invalid theme'}), 400


@api_bp.route('/api/search')
@login_required
def global_search():
    """Universal search across student's assignments, subjects, and topics."""
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify({'results': []})

    user_id = current_user.id
    results = []

    # 1. Search Assignments
    assignments = Assignment.query.filter(
        Assignment.user_id == user_id,
        Assignment.title.ilike(f'%{query}%')
    ).limit(5).all()
    for a in assignments:
        results.append({
            'type': 'Assignment',
            'title': a.title,
            'subtitle': f"Due {a.due_date.strftime('%b %d')} • {a.status.capitalize()}",
            'url': f"/assignments?q={query}"
        })

    # 2. Search Subjects
    subjects = Subject.query.filter(
        Subject.user_id == user_id,
        (Subject.name.ilike(f'%{query}%')) | (Subject.code.ilike(f'%{query}%'))
    ).limit(5).all()
    for s in subjects:
        results.append({
            'type': 'Subject',
            'title': f"{s.code}: {s.name}",
            'subtitle': f"{s.credits} Credits • {s.syllabus_progress}% Completed",
            'url': f"/syllabus?subject_id={s.id}"
        })

    # 3. Search Topics
    topics = SyllabusTopic.query.filter(
        SyllabusTopic.user_id == user_id,
        SyllabusTopic.title.ilike(f'%{query}%')
    ).limit(5).all()
    for t in topics:
        results.append({
            'type': 'Topic',
            'title': t.title,
            'subtitle': f"{t.unit.subject.name if t.unit and t.unit.subject else ''} • Confidence: {t.confidence_score}/5",
            'url': f"/syllabus?subject_id={t.unit.subject_id if t.unit else ''}"
        })

    return jsonify({'results': results})
