"""
Custom exception classes for Wikifile Transfer application.

This module defines application-level exceptions used throughout the
codebase for consistent error handling and clear error categorization.
"""


class WikifileError(Exception):
    """
    Base class for all Wikifile Transfer exceptions.
    
    All application-specific errors should inherit from this exception
    to allow for granular exception handling and logging.
    """
    pass


class DownloadError(WikifileError):
    """
    Raised when an error occurs while downloading an image from a source wiki.
    
    This exception is raised when:
    - The source file cannot be found in the wiki
    - The image URL is invalid or unreachable
    - Network errors occur during download
    - File I/O errors occur while saving the downloaded image
    """
    pass


class UploadError(WikifileError):
    """
    Raised when an error occurs while uploading an image to Wikimedia.
    
    This exception is raised when:
    - CSRF token cannot be fetched from target wiki
    - Network errors occur during upload
    - Wikimedia API rejects the upload
    - File I/O errors occur during upload process
    """
    pass


class AuthenticationError(WikifileError):
    """
    Raised when authentication with Wikimedia fails.
    
    This exception is raised when:
    - OAuth token is invalid or expired
    - User lacks required permissions
    - Authentication handshake fails
    """
    pass
