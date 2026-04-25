"""
services/stats_service.py
=========================
Business logic for the Upload Analytics Dashboard.

All database queries use SQLAlchemy ORM; raw SQL is avoided.
Every public function returns a plain Python dict ready for JSON serialisation.
"""

from datetime import datetime, timedelta

from sqlalchemy import func, cast, Date

from model import db, UploadTask


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Return numerator / denominator, or *default* when denominator is zero."""
    if denominator == 0:
        return default
    return round(numerator / denominator, 2)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_upload_stats() -> dict:
    """
    Compute and return all upload analytics metrics in a single dict.

    Returns
    -------
    dict with keys:
        total_uploads, successful_uploads, failed_uploads, success_rate,
        average_upload_time, uploads_last_24h,
        status_distribution, file_type_distribution, daily_upload_trend
    """

    # ------------------------------------------------------------------
    # 1. Aggregate counts in a single round-trip query
    # ------------------------------------------------------------------
    # func.count() with filter is supported by SQLAlchemy on MySQL, PostgreSQL,
    # and SQLite via CASE-WHEN, so no database-specific code is needed.
    agg = db.session.query(
        func.count(UploadTask.id).label('total'),
        func.count(
            db.case((UploadTask.status == 'success', UploadTask.id))
        ).label('successful'),
        func.count(
            db.case((UploadTask.status == 'failed', UploadTask.id))
        ).label('failed'),
    ).one()  # always returns exactly one row

    total_uploads      = agg.total       or 0
    successful_uploads = agg.successful  or 0
    failed_uploads     = agg.failed      or 0

    # ------------------------------------------------------------------
    # 2. Success rate — guarded against division by zero
    # ------------------------------------------------------------------
    success_rate = _safe_divide(successful_uploads * 100, total_uploads)

    # ------------------------------------------------------------------
    # 3. Average upload duration (seconds)
    #    Only completed tasks with BOTH timestamps are included.
    # ------------------------------------------------------------------
    avg_seconds = _compute_average_upload_time()

    # ------------------------------------------------------------------
    # 4. Uploads in the last 24 hours
    # ------------------------------------------------------------------
    cutoff_24h = datetime.utcnow() - timedelta(hours=24)
    uploads_last_24h = (
        db.session.query(func.count(UploadTask.id))
        .filter(UploadTask.created_at >= cutoff_24h)
        .scalar()
    ) or 0

    # ------------------------------------------------------------------
    # 5. Status distribution — count per status value
    # ------------------------------------------------------------------
    status_rows = (
        db.session.query(UploadTask.status, func.count(UploadTask.id).label('count'))
        .group_by(UploadTask.status)
        .all()
    )
    status_distribution = {row.status: row.count for row in status_rows}

    # ------------------------------------------------------------------
    # 6. File-type distribution — group by file_type, skip NULLs
    # ------------------------------------------------------------------
    file_type_rows = (
        db.session.query(UploadTask.file_type, func.count(UploadTask.id).label('count'))
        .filter(UploadTask.file_type.isnot(None))
        .group_by(UploadTask.file_type)
        .order_by(func.count(UploadTask.id).desc())
        .all()
    )
    file_type_distribution = {row.file_type: row.count for row in file_type_rows}

    # ------------------------------------------------------------------
    # 7. Daily upload trend — last 7 days, grouped by calendar date (UTC)
    # ------------------------------------------------------------------
    daily_upload_trend = _compute_daily_trend(days=7)

    return {
        "total_uploads":        total_uploads,
        "successful_uploads":   successful_uploads,
        "failed_uploads":       failed_uploads,
        "success_rate":         success_rate,
        "average_upload_time":  avg_seconds,
        "uploads_last_24h":     uploads_last_24h,
        "status_distribution":  status_distribution,
        "file_type_distribution": file_type_distribution,
        "daily_upload_trend":   daily_upload_trend,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _compute_average_upload_time() -> float:
    """
    Return the mean upload duration in seconds across all completed tasks.

    We compute (completed_at - created_at) in Python rather than relying on
    database-specific DATEDIFF / TIMESTAMPDIFF so the service stays
    portable across MySQL, PostgreSQL, and SQLite.

    Only rows where BOTH timestamps are present are included.
    Returns 0.0 when no qualifying rows exist.
    """
    rows = (
        db.session.query(UploadTask.created_at, UploadTask.completed_at)
        .filter(
            UploadTask.completed_at.isnot(None),
            UploadTask.created_at.isnot(None),
        )
        .all()
    )

    if not rows:
        return 0.0

    total_seconds = sum(
        (row.completed_at - row.created_at).total_seconds()
        for row in rows
        if row.completed_at >= row.created_at  # guard against bad data
    )
    return round(total_seconds / len(rows), 2)


def _compute_daily_trend(days: int = 7) -> list:
    """
    Return a list of {date, count} dicts for the last *days* calendar days.

    The result always contains exactly *days* entries — days with zero uploads
    are included with count=0, ensuring the frontend chart has a consistent
    x-axis.

    Strategy
    --------
    Cast created_at to a DATE (UTC) and group by it, then fill gaps in Python.
    This is a single DB query + O(days) iteration, so it is efficient.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    rows = (
        db.session.query(
            cast(UploadTask.created_at, Date).label('day'),
            func.count(UploadTask.id).label('count'),
        )
        .filter(UploadTask.created_at >= cutoff)
        .group_by('day')
        .order_by('day')
        .all()
    )

    # Build a lookup {date_string -> count} from query results
    counts_by_date = {str(row.day): row.count for row in rows}

    # Generate the full date range and fill gaps with 0
    today = datetime.utcnow().date()
    trend = []
    for offset in range(days - 1, -1, -1):          # oldest → newest
        day = today - timedelta(days=offset)
        day_str = day.strftime('%Y-%m-%d')
        trend.append({
            "date":  day_str,
            "count": counts_by_date.get(day_str, 0),
        })

    return trend
