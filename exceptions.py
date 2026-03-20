class WikifileError(Exception):
    """Base class for all Wikifile Transfer exceptions."""
    pass

class DownloadError(WikifileError):
    """Raised when an error occurs while downloading an image."""
    pass

class UploadError(WikifileError):
    """Raised when an error occurs while uploading an image to Wikimedia."""
    pass

class AuthenticationError(WikifileError):
    """Raised when authentication with Wikimedia fails."""
    pass
