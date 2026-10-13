from flask import Blueprint, render_template, jsonify, Response
from flask_login import login_required, current_user
from app.services.analytics_service import AnalyticsService

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/analytics')
@login_required
def index():
    user_id = current_user.id
    metrics = AnalyticsService.get_dashboard_metrics(user_id)
    return render_template('analytics/index.html', metrics=metrics)


@analytics_bp.route('/api/analytics/weekly-chart')
@login_required
def weekly_chart_data():
    data = AnalyticsService.get_weekly_study_chart_data(current_user.id)
    return jsonify(data)


@analytics_bp.route('/api/analytics/subject-chart')
@login_required
def subject_chart_data():
    data = AnalyticsService.get_subject_progress_chart_data(current_user.id)
    return jsonify(data)


@analytics_bp.route('/analytics/export-csv')
@login_required
def export_csv():
    csv_content = AnalyticsService.generate_csv_summary(current_user.id)
    filename = f"studysync_export_{current_user.username}.csv"
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
