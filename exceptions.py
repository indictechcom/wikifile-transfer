from werkzeug.exceptions import HTTPException

class WikifileTransferError(Exception):
    """
    Root exception for every error raised within Wikifile-Transfer.

    Catching this class catches *all* application-level errors, which is
    useful in Celery task wrappers and integration tests.
    """


# ---------------------------------------------------------------------------
# HTTP / API exceptions  (also subclass HTTPException for Flask routing)
# ---------------------------------------------------------------------------

class APIError(WikifileTransferError, HTTPException):
    """
    Base class for errors that must be returned as an HTTP response.

    Inherits from both ``WikifileTransferError`` (application family) and
    ``werkzeug.exceptions.HTTPException`` (Flask error-handler dispatch).

    Parameters
    ----------
    message : str
        Human-readable description included in the JSON error envelope.
    status_code : int
        HTTP status code to return to the client (default: 400).
    """

    def __init__(self, message: str, status_code: int = 400) -> None:
        # Initialise both parent classes explicitly to avoid MRO surprises.
        WikifileTransferError.__init__(self, message)
        self.code = status_code
        self.description = message

    def __str__(self) -> str:
        # Override HTTPException.__str__ which would prepend "NNN StatusText: ".
        # Returning just the description keeps str(err) == err.description,
        # which is the natural expectation for an application exception.
        return self.description


class ValidationError(APIError):
    """
    Raised when incoming request data fails validation.

    HTTP 422 Unprocessable Entity – the server understands the content type
    but the data itself is semantically invalid (e.g. missing required field,
    malformed URL).
    """

    def __init__(self, message: str = "Invalid or missing request data") -> None:
        super().__init__(message, status_code=422)


class NotFoundError(APIError):

    def __init__(self, message: str = "The requested resource was not found") -> None:
        super().__init__(message, status_code=404)


class AuthenticationError(APIError):

    def __init__(self, message: str = "Authentication required. Please log in.") -> None:
        super().__init__(message, status_code=401)


class UploadError(APIError):
    """
    Raised when a file upload to the target wiki is rejected or fails.

    HTTP 502 Bad Gateway – the upstream wiki returned an error or an
    unexpected response structure.
    """

    def __init__(self, message: str = "File upload to target wiki failed") -> None:
        super().__init__(message, status_code=502)


class ExternalAPIError(APIError):
    """
    Raised when a call to an external MediaWiki REST/Action API fails.

    HTTP 502 Bad Gateway – covers network errors, non-200 responses, and
    unexpected JSON shapes from upstream wikis.
    """

    def __init__(self, message: str = "External MediaWiki API request failed") -> None:
        super().__init__(message, status_code=502)


# ---------------------------------------------------------------------------
# Internal (non-HTTP) exceptions
# ---------------------------------------------------------------------------

class DownloadError(WikifileTransferError):
    """
    Raised when downloading a source file from a wiki fails.

    This is an *internal* error; callers are expected to catch it and either
    re-raise as an ``APIError`` subclass or log and return a safe response.
    """


class DatabaseError(WikifileTransferError):
    """
    Raised when a SQLAlchemy / database operation fails.

    Callers should roll back the session before raising this exception and
    avoid leaking raw SQLAlchemy messages to clients.
    """


class TaskError(WikifileTransferError):
    """
    Raised inside a Celery task when an unrecoverable error is encountered.

    The Celery task infrastructure catches this, logs the full traceback, and
    marks the task as FAILURE so the polling endpoint can report it correctly.
    """
