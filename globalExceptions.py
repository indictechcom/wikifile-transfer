"""
globalExceptions.py
Custom exception hierarchy for wikifile-transfer.
All application-level errors are raised from these classes

APIRequestError: HTTP request to a MediaWiki API fails
UploadError: API upload action fails
CSRFTokenError: Failure to retrieve a CSRF token from the API
FileNotFoundOnWikiError: Requested file does not exist on source wiki
WikitextProcessingError: Localizing or parsing wikitext fails
TempDirectoryError: Issues with creating or accessing the temporary image directory
MissingConfigError: Required configuration keys or environment variables are missing
FileTooLargeError: A file exceeds the size limit for uploads
InvalidConfigValueError: A configuration value is present but fails validation
BrokerConfigError: Celery broker URL is missing or malformed
AuthenticationError: OAuth authentication is rejected by the target wiki
OAuthConfigError: Required user OAuth credentials are missing or malformed
"""


class WikifileError(Exception):
    pass


class APIRequestError(WikifileError):

    def __init__(self, url: str, reason: str, status_code: int | None = None):
        self.url = url
        self.reason = reason
        self.status_code = status_code
        super().__init__(
            f"API request to {url!r} failed"
            + (f" (HTTP {status_code})" if status_code else "")
            + f": {reason}"
        )


class CSRFTokenError(WikifileError):
    pass


class UploadError(WikifileError):

    def __init__(self, filename: str, reason: str):
        self.filename = filename
        self.reason = reason
        super().__init__(f"Upload of {filename!r} failed: {reason}")


class ImageDownloadError(WikifileError):
    """Raised when an image cannot be downloaded from the source wiki."""

    def __init__(self, src_filename: str, reason: str):
        self.src_filename = src_filename
        self.reason = reason
        super().__init__(f"Could not download image {src_filename!r}: {reason}")


class FileNotFoundOnWikiError(WikifileError):

    def __init__(self, src_filename: str):
        self.src_filename = src_filename
        super().__init__(f"File not found on wiki: {src_filename!r}")


class OAuthConfigError(WikifileError):
    """Raised when required OAuth credentials are missing or malformed."""


class WikitextProcessingError(WikifileError):

    def __init__(self, src_filename: str, reason: str):
        self.src_filename = src_filename
        self.reason = reason
        super().__init__(f"Error processing wikitext for {src_filename!r}: {reason}")
        

class LocalFileReadError(WikifileError):
    """Raised when a local file cannot be opened or read from disk.

    Attributes:
        file_path: Absolute or relative path of the file that could not be read.
        reason: Human-readable description of the I/O failure.
    """

    def __init__(self, file_path: str, reason: str):
        self.file_path = file_path
        self.reason = reason
        super().__init__(f"Cannot read file {file_path!r}: {reason}")


class LocalFileWriteError(WikifileError):
    """Raised when a local file cannot be created or written to disk.

    Attributes:
        file_path: Path where the write was attempted.
        reason: Human-readable description of the I/O failure.
    """

    def __init__(self, file_path: str, reason: str):
        self.file_path = file_path
        self.reason = reason
        super().__init__(f"Cannot write file {file_path!r}: {reason}")


class TempDirectoryError(WikifileError):

    def __init__(self, directory: str, reason: str):
        self.directory = directory
        self.reason = reason
        super().__init__(f"Temp directory {directory!r} is unusable: {reason}")


class FileTooLargeError(WikifileError):

    def __init__(self, filename: str, size_bytes: int, max_bytes: int):
        self.filename = filename
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes
        super().__init__(
            f"File {filename!r} is {size_bytes:,} bytes, "
            f"which exceeds the {max_bytes:,}-byte limit"
        )


class UnsupportedFileTypeError(WikifileError):
    """Raised when a file's MIME type or extension is not permitted.

    Attributes:
        filename: Name of the rejected file.
        detected_type: MIME type or extension that was detected.
        allowed_types: Collection of permitted types.
    """

    def __init__(self, filename: str, detected_type: str, allowed_types: list[str]):
        self.filename = filename
        self.detected_type = detected_type
        self.allowed_types = allowed_types
        super().__init__(
            f"File {filename!r} has unsupported type {detected_type!r}. "
            f"Allowed: {', '.join(allowed_types)}"
        )


class MissingConfigError(WikifileError):

    def __init__(self, key: str, source: str = "environment"):
        self.key = key
        self.source = source
        super().__init__(f"Required config key {key!r} is missing from {source}")


class InvalidConfigValueError(WikifileError):
    
    def __init__(self, key: str, value: object, reason: str):
        self.key = key
        self.value = value
        self.reason = reason
        super().__init__(
            f"Config key {key!r} has invalid value {value!r}: {reason}"
        )


class BrokerConfigError(WikifileError):

    def __init__(self, broker_url: str, reason: str):
        self.broker_url = broker_url
        self.reason = reason
        super().__init__(f"Broker {broker_url!r} is not usable: {reason}")


class RateLimitError(WikifileError):
    """Raised when the MediaWiki API returns a rate-limit or throttle response.

    Attributes:
        endpoint: The API endpoint that issued the limit.
        retry_after: Seconds to wait before retrying, if provided by the server.
    """

    def __init__(self, endpoint: str, retry_after: int | None = None):
        self.endpoint = endpoint
        self.retry_after = retry_after
        msg = f"Rate limited by {endpoint!r}"
        if retry_after is not None:
            msg += f"; retry after {retry_after}s"
        super().__init__(msg)


class AuthenticationError(WikifileError):

    def __init__(self, endpoint: str, reason: str):
        self.endpoint = endpoint
        self.reason = reason
        super().__init__(
            f"Authentication rejected by {endpoint!r}: {reason}"
        )


class InsufficientPermissionsError(WikifileError):
    """Raised when the authenticated user lacks the rights to perform an action.

    Attributes:
        action: The action that was attempted (e.g. 'upload', 'edit').
        endpoint: The wiki API endpoint that rejected the action.
        required_right: The wiki user-right that is needed, if known.
    """

    def __init__(self, action: str, endpoint: str, required_right: str | None = None):
        self.action = action
        self.endpoint = endpoint
        self.required_right = required_right
        msg = f"Insufficient permissions to perform {action!r} on {endpoint!r}"
        if required_right:
            msg += f" (requires '{required_right}' right)"
        super().__init__(msg)

