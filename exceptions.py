#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Custom exception hierarchy for Wikifile Transfer application.
"""

from typing import Optional, Dict, Any


class AppError(Exception):
    """Base exception for all domain-specific application errors."""
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
    """Raised when client request data or parameters fail validation."""
    status_code = 400
    error_type = "ValidationError"


class AuthenticationError(AppError):
    """Raised when user authentication or OAuth verification fails."""
    status_code = 401
    error_type = "AuthenticationError"


class DownloadError(AppError):
    """Raised when downloading a media file from source wiki fails."""
    status_code = 502
    error_type = "DownloadError"


class UploadError(AppError):
    """Raised when uploading a media file to target wiki fails."""
    status_code = 502
    error_type = "UploadError"


class MediaWikiAPIError(AppError):
    """Raised when a remote MediaWiki API query or action returns an error."""
    status_code = 502
    error_type = "MediaWikiAPIError"


class DatabaseError(AppError):
    """Raised when a local database read, write, or transaction fails."""
    status_code = 500
    error_type = "DatabaseError"


class TaskError(AppError):
    """Raised when background Celery task processing encounters a fatal error."""
    status_code = 500
    error_type = "TaskError"
