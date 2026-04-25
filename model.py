from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255))
    pref_project = db.Column(db.String(15))
    pref_language = db.Column(db.String(4))
    user_language = db.Column(db.String(4), default='en')
    skip_upload_selection = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return '<User %r>' % self.username


class UploadTask(db.Model):
    """
    Tracks every upload task dispatched to Celery.

    Fields
    ------
    task_id      : Celery task UUID (unique, indexed for fast lookups)
    status       : Current state — 'pending' | 'processing' | 'success' | 'failed'
    filename     : Target filename on the destination wiki
    file_type    : File extension (e.g. 'jpg', 'pdf', 'png'), lowercase, no dot
    created_at   : UTC timestamp when the task was created/queued
    completed_at : UTC timestamp when the task finished (success or failure); NULL while running
    """
    __tablename__ = 'upload_task'

    id           = db.Column(db.Integer, primary_key=True)
    task_id      = db.Column(db.String(36), unique=True, nullable=False, index=True)
    status       = db.Column(db.String(20), nullable=False, default='pending')
    filename     = db.Column(db.String(512), nullable=True)
    file_type    = db.Column(db.String(20), nullable=True)   # e.g. 'jpg', 'pdf'
    created_at   = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<UploadTask {self.task_id} status={self.status}>'