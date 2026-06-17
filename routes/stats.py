"""
routes/stats.py
===============
Flask Blueprint that exposes the Upload Analytics Dashboard endpoint.

    GET /api/upload/stats

No authentication is required for stats (adjust if your project needs it).
"""

import logging

from flask import Blueprint, jsonify

from services.stats_service import get_upload_stats

logger = logging.getLogger(__name__)

# Blueprint is registered in app.py with url_prefix='/api/upload'
stats_bp = Blueprint('stats', __name__)


@stats_bp.route('/stats', methods=['GET'])
def upload_stats():
    """
    GET /api/upload/stats

    Returns aggregated upload analytics.

    Success response (200):
    {
        "status": "success",
        "data": {
            "total_uploads":          <int>,
            "successful_uploads":     <int>,
            "failed_uploads":         <int>,
            "success_rate":           <float>,   // percentage, 0-100
            "average_upload_time":    <float>,   // seconds
            "uploads_last_24h":       <int>,
            "status_distribution":    { "<status>": <count>, ... },
            "file_type_distribution": { "<ext>":    <count>, ... },
            "daily_upload_trend":     [
                { "date": "YYYY-MM-DD", "count": <int> },
                ...   // last 7 days, oldest first
            ]
        }
    }

    Error response (500):
    {
        "status": "error",
        "message": "<reason>"
    }
    """
    try:
        stats = get_upload_stats()
        return jsonify({"status": "success", "data": stats}), 200

    except Exception as exc:
        logger.exception("Failed to compute upload stats")
        return jsonify({"status": "error", "message": str(exc)}), 500
