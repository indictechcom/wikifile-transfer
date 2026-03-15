
"""Custom exceptions to replace bare except blocks and make error tracking clearer across the app."""


# Base class for all application errors
class WikifileTransferError(Exception):

    def __init__(self, message, error_code=None, details=None):
        self.message = message
        self.error_code = error_code or "GENERAL_ERROR"
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self):
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details
        }


# Raised when user input fails validation
class ValidationError(WikifileTransferError):

    def __init__(self, message, field=None, details=None):
        error_details = details or {}
        if field:
            error_details["field"] = field
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details=error_details
        )


# Raised when a MediaWiki API call fails
class WikiAPIError(WikifileTransferError):

    def __init__(self, message, api_endpoint=None, status_code=None, details=None):
        error_details = details or {}
        if api_endpoint:
            error_details["api_endpoint"] = api_endpoint
        if status_code:
            error_details["status_code"] = status_code
        super().__init__(
            message=message,
            error_code="WIKI_API_ERROR",
            details=error_details
        )


# Raised when a file download, write, or read operation fails
class FileOperationError(WikifileTransferError):

    def __init__(self, message, operation=None, file_path=None, details=None):
        error_details = details or {}
        if operation:
            error_details["operation"] = operation
        if file_path:
            error_details["file_path"] = file_path
        super().__init__(
            message=message,
            error_code="FILE_OPERATION_ERROR",
            details=error_details
        )


# Raised when a database operation fails
class DatabaseError(WikifileTransferError):

    def __init__(self, message, operation=None, details=None):
        error_details = details or {}
        if operation:
            error_details["operation"] = operation
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            details=error_details
        )


# Raised when an OAuth token is broken, expired, or rejected by the Wiki
class OAuthError(WikifileTransferError):

    def __init__(self, message, details=None):
        super().__init__(
            message=message,
            error_code="OAUTH_ERROR",
            details=details or {}
        )


# Raised when the user is not authenticated or the session is invalid
class AuthenticationError(WikifileTransferError):

    def __init__(self, message, details=None):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            details=details or {}
        )


# Raised when a file upload to the target Wiki fails
class UploadError(WikifileTransferError):

    def __init__(self, message, upload_type=None, details=None):
        error_details = details or {}
        if upload_type:
            error_details["upload_type"] = upload_type
        super().__init__(
            message=message,
            error_code="UPLOAD_ERROR",
            details=error_details
        )


# Raised when a required configuration key is missing or invalid
class ConfigurationError(WikifileTransferError):

    def __init__(self, message, config_key=None, details=None):
        error_details = details or {}
        if config_key:
            error_details["config_key"] = config_key
        super().__init__(
            message=message,
            error_code="CONFIGURATION_ERROR",
            details=error_details
        )


# Raised when a Celery async task fails
class TaskError(WikifileTransferError):

    def __init__(self, message, task_id=None, details=None):
        error_details = details or {}
        if task_id:
            error_details["task_id"] = task_id
        super().__init__(
            message=message,
            error_code="TASK_ERROR",
            details=error_details
        )


# Raised when a requested resource like an image or file does not exist
class ResourceNotFoundError(WikifileTransferError):

    def __init__(self, message, resource_type=None, resource_id=None, details=None):
        error_details = details or {}
        if resource_type:
            error_details["resource_type"] = resource_type
        if resource_id:
            error_details["resource_id"] = resource_id
        super().__init__(
            message=message,
            error_code="RESOURCE_NOT_FOUND",
            details=error_details
        )
