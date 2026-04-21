"""
tests/test_exceptions.py – Unit tests for the custom exception hierarchy.

Covers:
  1. Inheritance chain  – every exception descends from WikifileTransferError.
  2. HTTP status codes  – APIError subclasses carry the right `.code`.
  3. werkzeug compat    – APIError subclasses are catchable as HTTPException.
  4. Message handling   – default and custom descriptions are preserved.
"""

import pytest
from werkzeug.exceptions import HTTPException

from exceptions import (
    APIError,
    AuthenticationError,
    DatabaseError,
    DownloadError,
    ExternalAPIError,
    NotFoundError,
    TaskError,
    UploadError,
    ValidationError,
    WikifileTransferError,
)


# ---------------------------------------------------------------------------
# 1. Inheritance chain
# ---------------------------------------------------------------------------

class TestInheritanceChain:
    """Every exception must ultimately descend from WikifileTransferError."""

    def test_api_error(self):
        assert issubclass(APIError, WikifileTransferError)

    def test_validation_error(self):
        assert issubclass(ValidationError, WikifileTransferError)

    def test_not_found_error(self):
        assert issubclass(NotFoundError, WikifileTransferError)

    def test_authentication_error(self):
        assert issubclass(AuthenticationError, WikifileTransferError)

    def test_upload_error(self):
        assert issubclass(UploadError, WikifileTransferError)

    def test_external_api_error(self):
        assert issubclass(ExternalAPIError, WikifileTransferError)

    def test_download_error(self):
        assert issubclass(DownloadError, WikifileTransferError)

    def test_database_error(self):
        assert issubclass(DatabaseError, WikifileTransferError)

    def test_task_error(self):
        assert issubclass(TaskError, WikifileTransferError)

    def test_api_subclasses_are_also_api_error(self):
        """ValidationError, NotFoundError, etc. must all be APIError."""
        for cls in (ValidationError, NotFoundError, AuthenticationError,
                    UploadError, ExternalAPIError):
            assert issubclass(cls, APIError), f"{cls.__name__} is not an APIError"


# ---------------------------------------------------------------------------
# 2. HTTP status codes
# ---------------------------------------------------------------------------

class TestHTTPStatusCodes:
    """APIError subclasses must expose the correct HTTP status via .code."""

    def test_api_error_default_400(self):
        assert APIError("oops").code == 400

    def test_api_error_custom_status(self):
        err = APIError("service unavailable", status_code=503)
        assert err.code == 503

    def test_validation_error_is_422(self):
        assert ValidationError().code == 422

    def test_not_found_error_is_404(self):
        assert NotFoundError().code == 404

    def test_authentication_error_is_401(self):
        assert AuthenticationError().code == 401

    def test_upload_error_is_502(self):
        assert UploadError().code == 502

    def test_external_api_error_is_502(self):
        assert ExternalAPIError().code == 502


# ---------------------------------------------------------------------------
# 3. werkzeug / Flask compatibility
# ---------------------------------------------------------------------------

class TestFlaskHTTPExceptionIntegration:
    """APIError subclasses must be catchable as werkzeug HTTPExceptions so
    Flask routes them to the correct error handler automatically."""

    def test_api_error_isinstance_http_exception(self):
        assert isinstance(APIError("msg"), HTTPException)

    def test_validation_error_isinstance_http_exception(self):
        assert isinstance(ValidationError(), HTTPException)

    @pytest.mark.parametrize("exc_cls", [
        ValidationError, NotFoundError, AuthenticationError,
        UploadError, ExternalAPIError,
    ])
    def test_can_catch_as_http_exception(self, exc_cls):
        with pytest.raises(HTTPException) as exc_info:
            raise exc_cls()
        assert exc_info.value.code == exc_cls().code

    def test_can_catch_all_as_wikifiletransfer_error(self):
        """Catching WikifileTransferError must intercept every app exception."""
        for exc_cls in (ValidationError, AuthenticationError, DownloadError,
                        DatabaseError, TaskError):
            with pytest.raises(WikifileTransferError):
                raise exc_cls()


# ---------------------------------------------------------------------------
# 4. Message handling
# ---------------------------------------------------------------------------

class TestMessageHandling:
    """Default and custom descriptions must be preserved correctly."""

    def test_api_error_stores_message_as_description(self):
        err = APIError("something went wrong")
        assert err.description == "something went wrong"

    def test_api_error_also_stores_as_str(self):
        err = APIError("fail")
        assert str(err) == "fail"

    def test_validation_error_custom_message(self):
        err = ValidationError("'srcUrl' is required")
        assert err.description == "'srcUrl' is required"

    def test_validation_error_default_message_is_informative(self):
        err = ValidationError()
        assert len(err.description) > 5  # Not blank

    def test_authentication_error_default_message_present(self):
        err = AuthenticationError()
        assert err.description  # truthy / non-empty

    def test_not_found_error_default_contains_not_found(self):
        err = NotFoundError()
        assert "not found" in err.description.lower()

    def test_task_error_preserves_message(self):
        err = TaskError("Redis connection refused")
        assert str(err) == "Redis connection refused"

    def test_download_error_preserves_message(self):
        err = DownloadError("HTTP 403 from upstream")
        assert str(err) == "HTTP 403 from upstream"
