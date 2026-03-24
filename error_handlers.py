

import logging

from flask import jsonify, request
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)


def register_error_handlers(app) -> None:
    """Attach all error handlers to *app*."""

    @app.errorhandler(HTTPException)
    def handle_http_exception(e: HTTPException):
        """Handles expected HTTP errors (our APIError subclasses and Flask's own).
        Logged at WARNING – these are client-side mistakes, not server bugs."""
        logger.warning(
            "HTTP %s on %s %s – %s",
            e.code,
            request.method,
            request.path,
            e.description,
        )
        return (
            jsonify({
                "success": False,
                "data":    {},
                "errors":  [e.description],
            }),
            e.code,
        )

    @app.errorhandler(Exception)
    def handle_generic_exception(e: Exception):
        """Catch-all for unexpected exceptions. Full traceback is written to
        the log; client only receives a safe generic message."""
        logger.exception(
            "Unhandled %s on %s %s",
            type(e).__name__,
            request.method,
            request.path,
        )
        return (
            jsonify({
                "success": False,
                "data":    {},
                "errors":  [
                    "An unexpected internal error occurred. "
                    "Please try again or contact support."
                ],
            }),
            500,
        )
