#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Centralized Flask error handlers that turn raised exceptions into consistent JSON responses."""

from flask import jsonify
from werkzeug.exceptions import HTTPException
from exceptions import (
    WikifileTransferError,
    ValidationError,
    WikiAPIError,
    FileOperationError,
    DatabaseError,
    OAuthError,
    AuthenticationError,
    UploadError,
    ConfigurationError,
    TaskError,
    ResourceNotFoundError
)
from logging_config import get_logger

logger = get_logger(__name__)


# Builds the standard error JSON shape returned by all error handlers
def create_error_response(error_code, message, details=None, status_code=500):
    response = {
        "success": False,
        "data": {},
        "errors": [message],
        "error_details": {
            "code": error_code,
            "message": message,
        }
    }
    if details:
        response["error_details"]["details"] = details
    return jsonify(response), status_code


# Builds the standard success JSON shape returned by all successful routes
def success_response(data=None, message=None, status_code=200):
    response = {
        "success": True,
        "data": data or {},
        "errors": []
    }
    if message:
        response["message"] = message
    return jsonify(response), status_code


# Handles bad user input — returns 400
def handle_validation_error(error):
    logger.warning(f"Validation error: {error.message}")
    return create_error_response(
        error_code=error.error_code,
        message=error.message,
        details=error.details,
        status_code=400
    )


# Handles Wikipedia API failures including timeouts and connection errors — returns 502
def handle_wiki_api_error(error):
    logger.error(f"Wiki API error: {error.message}")
    return create_error_response(
        error_code=error.error_code,
        message=error.message,
        details=error.details,
        status_code=502
    )


# Handles file download, upload, or write failures — returns 500
def handle_file_operation_error(error):
    logger.error(f"File operation error: {error.message}")
    return create_error_response(
        error_code=error.error_code,
        message=error.message,
        details=error.details,
        status_code=500
    )


# Handles database failures — hides internal details from user for security
def handle_database_error(error):
    logger.error(f"Database error: {error.message}", exc_info=True)
    return create_error_response(
        error_code=error.error_code,
        message="A database error occurred. Please try again later.",
        details={"operation": error.details.get("operation")},
        status_code=500
    )


# Handles broken or expired OAuth tokens — returns 401
# Token EXISTS but is invalid — different from user never logging in
def handle_oauth_error(error):
    logger.error(f"OAuth error: {error.message}")
    return create_error_response(
        error_code=error.error_code,
        message="Authentication session is invalid. Please log in again.",
        details={},
        status_code=401
    )


# Handles unauthenticated requests — returns 401
# User has NO token at all, never logged in
def handle_authentication_error(error):
    logger.warning(f"Authentication error: {error.message}")
    return create_error_response(
        error_code=error.error_code,
        message=error.message,
        details=error.details,
        status_code=401
    )


# Handles failed wiki uploads — returns 500
def handle_upload_error(error):
    logger.error(f"Upload error: {error.message}")
    return create_error_response(
        error_code=error.error_code,
        message=error.message,
        details=error.details,
        status_code=500
    )


# Handles missing or invalid config — hides config details from user for security
def handle_configuration_error(error):
    logger.critical(f"Configuration error: {error.message}")
    return create_error_response(
        error_code=error.error_code,
        message="A configuration error occurred. Please contact the administrator.",
        details={},
        status_code=500
    )


# Handles Celery async task failures — returns 500
def handle_task_error(error):
    logger.error(f"Task error: {error.message}")
    return create_error_response(
        error_code=error.error_code,
        message=error.message,
        details=error.details,
        status_code=500
    )


# Handles missing images or files — returns 404
def handle_resource_not_found_error(error):
    logger.info(f"Resource not found: {error.message}")
    return create_error_response(
        error_code=error.error_code,
        message=error.message,
        details=error.details,
        status_code=404
    )


# Handles standard HTTP errors from werkzeug like 404, 405, etc
def handle_http_exception(error):
    logger.warning(f"HTTP exception: {error.code} - {error.description}")
    return create_error_response(
        error_code=f"HTTP_{error.code}",
        message=error.description,
        details={},
        status_code=error.code
    )


# Catches any unexpected exception not handled by a specific handler
def handle_generic_exception(error):
    logger.error(f"Unexpected error: {str(error)}", exc_info=True)
    return create_error_response(
        error_code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred. Please try again later.",
        details={},
        status_code=500
    )


# Registers all error handlers with the Flask app — call this once in app.py
def register_error_handlers(app):
    app.register_error_handler(ValidationError, handle_validation_error)
    app.register_error_handler(WikiAPIError, handle_wiki_api_error)
    app.register_error_handler(FileOperationError, handle_file_operation_error)
    app.register_error_handler(DatabaseError, handle_database_error)
    app.register_error_handler(OAuthError, handle_oauth_error)
    app.register_error_handler(AuthenticationError, handle_authentication_error)
    app.register_error_handler(UploadError, handle_upload_error)
    app.register_error_handler(ConfigurationError, handle_configuration_error)
    app.register_error_handler(TaskError, handle_task_error)
    app.register_error_handler(ResourceNotFoundError, handle_resource_not_found_error)
    app.register_error_handler(HTTPException, handle_http_exception)
    app.register_error_handler(Exception, handle_generic_exception)
    logger.info("Error handlers registered")


## What Changed — Only 3 Things
