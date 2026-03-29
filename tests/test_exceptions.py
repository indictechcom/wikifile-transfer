

import pytest
from globalExceptions import (
    WikifileError,
    APIRequestError,
    CSRFTokenError,
    UploadError,
    ImageDownloadError,
    FileNotFoundOnWikiError,
    OAuthConfigError,
    WikitextProcessingError,
    LocalFileReadError,
    LocalFileWriteError,
    TempDirectoryError,
    FileTooLargeError,
    UnsupportedFileTypeError,
    MissingConfigError,
    InvalidConfigValueError,
    BrokerConfigError,
    RateLimitError,
    AuthenticationError,
    InsufficientPermissionsError,
)


# Base class

class TestWikifileError:
    def test_is_exception(self):
        exc = WikifileError("base error")
        assert isinstance(exc, Exception)

    def test_message(self):
        exc = WikifileError("something went wrong")
        assert str(exc) == "something went wrong"


# APIRequestError

class TestAPIRequestError:
    def test_subclass(self):
        exc = APIRequestError("https://example.org", "timeout")
        assert isinstance(exc, WikifileError)

    def test_attributes_stored(self):
        exc = APIRequestError("https://example.org", "timeout", status_code=503)
        assert exc.url == "https://example.org"
        assert exc.reason == "timeout"
        assert exc.status_code == 503

    def test_message_with_status_code(self):
        exc = APIRequestError("https://example.org", "not found", status_code=404)
        msg = str(exc)
        assert "https://example.org" in msg
        assert "404" in msg
        assert "not found" in msg

    def test_message_without_status_code(self):
        exc = APIRequestError("https://example.org", "network error")
        msg = str(exc)
        assert "https://example.org" in msg
        assert "network error" in msg
        assert "HTTP" not in msg

    def test_status_code_defaults_to_none(self):
        exc = APIRequestError("https://example.org", "reason")
        assert exc.status_code is None


# CSRFTokenError

class TestCSRFTokenError:
    def test_subclass(self):
        exc = CSRFTokenError("token fetch failed")
        assert isinstance(exc, WikifileError)

    def test_message(self):
        exc = CSRFTokenError("unexpected response")
        assert "unexpected response" in str(exc)


# UploadError

class TestUploadError:
    def test_subclass(self):
        exc = UploadError("image.png", "wiki rejected it")
        assert isinstance(exc, WikifileError)

    def test_attributes_stored(self):
        exc = UploadError("image.png", "wiki rejected it")
        assert exc.filename == "image.png"
        assert exc.reason == "wiki rejected it"

    def test_message_contains_filename_and_reason(self):
        exc = UploadError("photo.jpg", "file too large")
        assert "photo.jpg" in str(exc)
        assert "file too large" in str(exc)


# ImageDownloadError

class TestImageDownloadError:
    def test_subclass(self):
        exc = ImageDownloadError("File:Cat.jpg", "HTTP 404")
        assert isinstance(exc, WikifileError)

    def test_attributes_stored(self):
        exc = ImageDownloadError("File:Cat.jpg", "HTTP 404")
        assert exc.src_filename == "File:Cat.jpg"
        assert exc.reason == "HTTP 404"

    def test_message(self):
        exc = ImageDownloadError("File:Cat.jpg", "connection refused")
        assert "File:Cat.jpg" in str(exc)
        assert "connection refused" in str(exc)


# FileNotFoundOnWikiError

class TestFileNotFoundOnWikiError:
    def test_subclass(self):
        exc = FileNotFoundOnWikiError("File:Missing.png")
        assert isinstance(exc, WikifileError)

    def test_attribute_stored(self):
        exc = FileNotFoundOnWikiError("File:Missing.png")
        assert exc.src_filename == "File:Missing.png"

    def test_message(self):
        exc = FileNotFoundOnWikiError("File:Ghost.jpg")
        assert "File:Ghost.jpg" in str(exc)


# OAuthConfigError

class TestOAuthConfigError:
    def test_subclass(self):
        exc = OAuthConfigError("missing consumer_key")
        assert isinstance(exc, WikifileError)

    def test_message(self):
        exc = OAuthConfigError("missing consumer_key")
        assert "missing consumer_key" in str(exc)


# WikitextProcessingError

class TestWikitextProcessingError:
    def test_subclass(self):
        exc = WikitextProcessingError("File:Cat.jpg", "parse failed")
        assert isinstance(exc, WikifileError)

    def test_attributes_stored(self):
        exc = WikitextProcessingError("File:Cat.jpg", "parse failed")
        assert exc.src_filename == "File:Cat.jpg"
        assert exc.reason == "parse failed"

    def test_message(self):
        exc = WikitextProcessingError("File:Cat.jpg", "unexpected token")
        assert "File:Cat.jpg" in str(exc)
        assert "unexpected token" in str(exc)

    def test_single_string_raises_typeerror(self):
        """
        Passing only one arg should raise TypeError — this catches the
        signature mismatch bug where utils.py called it with a single string.
        """
        with pytest.raises(TypeError):
            WikitextProcessingError("Failed to parse wikitext: some error")


# LocalFileReadError

class TestLocalFileReadError:
    def test_subclass(self):
        exc = LocalFileReadError("/tmp/file.jpg", "permission denied")
        assert isinstance(exc, WikifileError)

    def test_attributes(self):
        exc = LocalFileReadError("/tmp/file.jpg", "permission denied")
        assert exc.file_path == "/tmp/file.jpg"
        assert exc.reason == "permission denied"

    def test_message(self):
        exc = LocalFileReadError("/tmp/file.jpg", "permission denied")
        assert "/tmp/file.jpg" in str(exc)
        assert "permission denied" in str(exc)


# LocalFileWriteError

class TestLocalFileWriteError:
    def test_subclass(self):
        exc = LocalFileWriteError("/tmp/out.jpg", "disk full")
        assert isinstance(exc, WikifileError)

    def test_attributes(self):
        exc = LocalFileWriteError("/tmp/out.jpg", "disk full")
        assert exc.file_path == "/tmp/out.jpg"
        assert exc.reason == "disk full"

    def test_message(self):
        exc = LocalFileWriteError("/tmp/out.jpg", "disk full")
        assert "/tmp/out.jpg" in str(exc)
        assert "disk full" in str(exc)


# TempDirectoryError

class TestTempDirectoryError:
    def test_subclass(self):
        exc = TempDirectoryError("/tmp/images", "not writable")
        assert isinstance(exc, WikifileError)

    def test_attributes(self):
        exc = TempDirectoryError("/tmp/images", "not writable")
        assert exc.directory == "/tmp/images"
        assert exc.reason == "not writable"

    def test_message(self):
        exc = TempDirectoryError("/tmp/images", "not writable")
        assert "/tmp/images" in str(exc)
        assert "not writable" in str(exc)


# FileTooLargeError

class TestFileTooLargeError:
    def test_subclass(self):
        exc = FileTooLargeError("big.jpg", 60_000_000, 52_428_800)
        assert isinstance(exc, WikifileError)

    def test_attributes(self):
        exc = FileTooLargeError("big.jpg", 60_000_000, 52_428_800)
        assert exc.filename == "big.jpg"
        assert exc.size_bytes == 60_000_000
        assert exc.max_bytes == 52_428_800

    def test_message_contains_sizes(self):
        exc = FileTooLargeError("big.jpg", 60_000_000, 52_428_800)
        msg = str(exc)
        assert "big.jpg" in msg
        assert "60,000,000" in msg
        assert "52,428,800" in msg


# UnsupportedFileTypeError

class TestUnsupportedFileTypeError:
    def test_subclass(self):
        exc = UnsupportedFileTypeError("file.exe", "application/x-msdownload", ["image/jpeg"])
        assert isinstance(exc, WikifileError)

    def test_attributes(self):
        exc = UnsupportedFileTypeError("file.exe", "application/x-msdownload", ["image/jpeg", "image/png"])
        assert exc.filename == "file.exe"
        assert exc.detected_type == "application/x-msdownload"
        assert exc.allowed_types == ["image/jpeg", "image/png"]

    def test_message(self):
        exc = UnsupportedFileTypeError("file.exe", "application/x-msdownload", ["image/jpeg"])
        msg = str(exc)
        assert "file.exe" in msg
        assert "application/x-msdownload" in msg
        assert "image/jpeg" in msg


# MissingConfigError

class TestMissingConfigError:
    def test_subclass(self):
        exc = MissingConfigError("REDIS_HOST")
        assert isinstance(exc, WikifileError)

    def test_default_source(self):
        exc = MissingConfigError("REDIS_HOST")
        assert exc.source == "environment"
        assert "REDIS_HOST" in str(exc)

    def test_custom_source(self):
        exc = MissingConfigError("REDIS_HOST", source="config.ini")
        assert exc.source == "config.ini"
        assert "config.ini" in str(exc)


# InvalidConfigValueError

class TestInvalidConfigValueError:
    def test_subclass(self):
        exc = InvalidConfigValueError("LOG_LEVEL", "VERBOSE", "not a valid level")
        assert isinstance(exc, WikifileError)

    def test_attributes(self):
        exc = InvalidConfigValueError("LOG_LEVEL", "VERBOSE", "not a valid level")
        assert exc.key == "LOG_LEVEL"
        assert exc.value == "VERBOSE"
        assert exc.reason == "not a valid level"

    def test_message(self):
        exc = InvalidConfigValueError("LOG_LEVEL", "VERBOSE", "not a valid level")
        msg = str(exc)
        assert "LOG_LEVEL" in msg
        assert "VERBOSE" in msg
        assert "not a valid level" in msg


# BrokerConfigError

class TestBrokerConfigError:
    def test_subclass(self):
        exc = BrokerConfigError("redis://bad-host:9999/0", "connection refused")
        assert isinstance(exc, WikifileError)

    def test_attributes(self):
        exc = BrokerConfigError("redis://bad-host:9999/0", "connection refused")
        assert exc.broker_url == "redis://bad-host:9999/0"
        assert exc.reason == "connection refused"

    def test_message(self):
        exc = BrokerConfigError("redis://bad-host:9999/0", "connection refused")
        msg = str(exc)
        assert "redis://bad-host:9999/0" in msg
        assert "connection refused" in msg


# RateLimitError

class TestRateLimitError:
    def test_subclass(self):
        exc = RateLimitError("https://en.wikipedia.org/w/api.php")
        assert isinstance(exc, WikifileError)

    def test_without_retry_after(self):
        exc = RateLimitError("https://en.wikipedia.org/w/api.php")
        assert exc.retry_after is None
        assert "en.wikipedia.org" in str(exc)
        assert "retry" not in str(exc)

    def test_with_retry_after(self):
        exc = RateLimitError("https://en.wikipedia.org/w/api.php", retry_after=30)
        assert exc.retry_after == 30
        assert "30" in str(exc)
        assert "retry" in str(exc)


# AuthenticationError

class TestAuthenticationError:
    def test_subclass(self):
        exc = AuthenticationError("https://commons.wikimedia.org", "invalid token")
        assert isinstance(exc, WikifileError)

    def test_attributes(self):
        exc = AuthenticationError("https://commons.wikimedia.org", "invalid token")
        assert exc.endpoint == "https://commons.wikimedia.org"
        assert exc.reason == "invalid token"

    def test_message(self):
        exc = AuthenticationError("https://commons.wikimedia.org", "invalid token")
        msg = str(exc)
        assert "commons.wikimedia.org" in msg
        assert "invalid token" in msg


# InsufficientPermissionsError

class TestInsufficientPermissionsError:
    def test_subclass(self):
        exc = InsufficientPermissionsError("upload", "https://en.wikipedia.org")
        assert isinstance(exc, WikifileError)

    def test_without_required_right(self):
        exc = InsufficientPermissionsError("upload", "https://en.wikipedia.org")
        assert exc.required_right is None
        assert "upload" in str(exc)
        assert "en.wikipedia.org" in str(exc)

    def test_with_required_right(self):
        exc = InsufficientPermissionsError("upload", "https://en.wikipedia.org", required_right="upload")
        assert exc.required_right == "upload"
        assert "upload" in str(exc)

    def test_attributes(self):
        exc = InsufficientPermissionsError("edit", "https://en.wikipedia.org", "editprotected")
        assert exc.action == "edit"
        assert exc.endpoint == "https://en.wikipedia.org"
        assert exc.required_right == "editprotected"
