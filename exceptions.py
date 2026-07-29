#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Custom exception hierarchy for Wikifile-transfer application.
"""

from typing import Optional, Dict, Any


class AppError(Exception):
    """Base exception for all application errors."""
    status_code: int = 500
    error_type: str = "AppError"

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.error_type = self.__class__.__name__

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} status={self.status_code} message={self.message!r}>"


class ValidationError(AppError):
    """Raised when input validation fails."""
    status_code = 400
    error_type = "ValidationError"


class AuthenticationError(AppError):
    """Raised when authentication fails."""
    status_code = 401
    error_type = "AuthenticationError"


class UploadError(AppError):
    """Raised when file upload fails."""
    status_code = 502
    error_type = "UploadError"


class DownloadError(AppError):
    """Raised when file download fails."""
    status_code = 502
    error_type = "DownloadError"


class MediaWikiAPIError(AppError):
    """Raised when MediaWiki API calls fail."""
    status_code = 502
    error_type = "MediaWikiAPIError"


class DatabaseError(AppError):
    """Raised when database operations fail."""
    status_code = 500
    error_type = "DatabaseError"


class TaskError(AppError):
    """Raised when Celery task execution fails."""
    status_code = 500
    error_type = "TaskError"