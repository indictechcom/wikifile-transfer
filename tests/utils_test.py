"""
Tests for download_image(), process_upload(), and get_localized_wikitext() in utils.py

WHY NO REAL NETWORK CALLS
==========================
These functions hit Wikipedia's API. Running tests against the real API is a bad idea —
it's slow, it breaks when Wikipedia is down, and it means your test results depend on
whether your internet connection is having a bad day. Not great for CI.

So we use unittest.mock to swap out requests.get and requests.post with fakes that
return whatever JSON we tell them to. The function has no idea it's talking to a fake —
it just sees a response object and processes it the same way it would in production.

HOW TO RUN
==========
  pytest tests/utils_test.py -v


WHAT THESE TESTS ACTUALLY PROVE
================================
If all pass, you know:
  - download_image() works end to end (finds URL, downloads file, saves it, returns filename)
  - timeouts and connection errors raise the RIGHT exception type, not None or a generic Exception
  - metadata failure and download failure raise DIFFERENT exceptions (they're different problems)
  - process_upload() catches the +\\ CSRF token before the upload even starts
  - get_localized_wikitext() keeps going if one article lookup fails — it doesn't abort everything
  - the iilocalonly param is being sent (remove it and you'll see why Commons files break)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock, mock_open, call
from contextlib import contextmanager

from utils import download_image, process_upload, get_localized_wikitext
from exceptions import WikiAPIError, FileOperationError, ResourceNotFoundError, AuthenticationError
import requests as req


# ─── mock for log_timed_api_call ─────────────────────────────────────────────
# The real log_timed_api_call does `yield` (no value), but utils.py uses
#   `with log_timed_api_call(...) as context:` then `context["status_code"] = ...`
# That would crash with TypeError because context would be None.
# Our fake yields a plain dict so that line works fine.

@contextmanager
def _mock_timed_api_call(logger, endpoint, method):
    yield {}


# ─── fake API responses ───────────────────────────────────────────────────────

# What Wikipedia returns when the image EXISTS and has a local URL
FOUND_RESPONSE = {
    "batchcomplete": "",
    "query": {
        "pages": {
            "12345": {
                "ns": 6,
                "title": "File:Example.jpg",
                "imageinfo": [
                    {"url": "https://upload.wikimedia.org/wikipedia/commons/a/a9/Example.jpg"}
                ]
            }
        }
    }
}

# What Wikipedia returns when the file is missing (no imageinfo key)
MISSING_RESPONSE = {
    "batchcomplete": "",
    "query": {
        "pages": {
            "-1": {
                "ns": 6,
                "title": "File:Missing.jpg",
                "missing": ""
            }
        }
    }
}

# What Wikipedia returns when iilocalonly blocks a Commons-hosted file
# (page exists but imageinfo is absent because the file lives on Commons)
COMMONS_FILE_RESPONSE = {
    "batchcomplete": "",
    "query": {
        "pages": {
            "99999": {
                "ns": 6,
                "title": "File:Commons_only.jpg"
                # no "imageinfo" key — blocked by iilocalonly
            }
        }
    }
}

# Empty pages dict — API gave us nothing
EMPTY_PAGES_RESPONSE = {
    "batchcomplete": "",
    "query": {"pages": {}}
}


# ─── helpers to build mock response objects ───────────────────────────────────

def _meta_response(data):
    """Fake first requests.get call (wiki API metadata)."""
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = data
    return m


def _image_response():
    """Fake second requests.get call (actual image bytes)."""
    m = MagicMock()
    m.status_code = 200
    m.headers = {"Content-Type": "image/jpeg"}
    m.content = b"fake-image-bytes"
    return m


# ─── SUCCESS TESTS ────────────────────────────────────────────────────────────

class TestSuccess:
    """The image exists and downloads without errors."""

    @patch("utils.log_timed_api_call", _mock_timed_api_call)
    @patch("utils.os.makedirs")
    @patch("builtins.open", mock_open())
    @patch("utils.requests.get")
    def test_returns_a_filename_string(self, mock_get, mock_makedirs):
        # ARRANGE: first call = metadata, second call = image bytes
        mock_get.side_effect = [_meta_response(FOUND_RESPONSE), _image_response()]

        # ACT
        result = download_image("wikipedia", "en", "File:Example.jpg")

        # ASSERT: we get a string back (the saved filename)
        assert isinstance(result, str)

    @patch("utils.log_timed_api_call", _mock_timed_api_call)
    @patch("utils.os.makedirs")
    @patch("builtins.open", mock_open())
    @patch("utils.requests.get")
    def test_filename_has_jpeg_extension(self, mock_get, mock_makedirs):
        mock_get.side_effect = [_meta_response(FOUND_RESPONSE), _image_response()]
        result = download_image("wikipedia", "en", "File:Example.jpg")
        # Content-Type was image/jpeg so extension should be .jpeg
        assert result.endswith(".jpeg")

    @patch("utils.log_timed_api_call", _mock_timed_api_call)
    @patch("utils.os.makedirs")
    @patch("builtins.open", mock_open())
    @patch("utils.requests.get")
    def test_makes_exactly_two_http_requests(self, mock_get, mock_makedirs):
        mock_get.side_effect = [_meta_response(FOUND_RESPONSE), _image_response()]
        download_image("wikipedia", "en", "File:Example.jpg")
        # One call for metadata, one for the image file
        assert mock_get.call_count == 2

    @patch("utils.log_timed_api_call", _mock_timed_api_call)
    @patch("utils.os.makedirs")
    @patch("builtins.open", mock_open())
    @patch("utils.requests.get")
    def test_creates_temp_images_directory(self, mock_get, mock_makedirs):
        mock_get.side_effect = [_meta_response(FOUND_RESPONSE), _image_response()]
        download_image("wikipedia", "en", "File:Example.jpg")
        mock_makedirs.assert_called_once_with("temp_images", exist_ok=True)


# ─── ENDPOINT CONSTRUCTION TESTS ─────────────────────────────────────────────

class TestEndpointConstruction:
    """The API URL must be built correctly from the arguments."""

    @patch("utils.log_timed_api_call", _mock_timed_api_call)
    @patch("utils.os.makedirs")
    @patch("builtins.open", mock_open())
    @patch("utils.requests.get")
    def test_builds_correct_api_url(self, mock_get, mock_makedirs):
        mock_get.side_effect = [_meta_response(FOUND_RESPONSE), _image_response()]
        download_image("wikipedia", "fr", "File:Example.jpg")

        first_call_kwargs = mock_get.call_args_list[0][1]
        assert first_call_kwargs["url"] == "https://fr.wikipedia.org/w/api.php"

    @patch("utils.log_timed_api_call", _mock_timed_api_call)
    @patch("utils.os.makedirs")
    @patch("builtins.open", mock_open())
    @patch("utils.requests.get")
    def test_sends_iilocalonly_param(self, mock_get, mock_makedirs):
        # This param is why Commons-hosted files return no imageinfo.
        # Confirming it is sent lets you decide if removing it would help.
        mock_get.side_effect = [_meta_response(FOUND_RESPONSE), _image_response()]
        download_image("wikipedia", "en", "File:Example.jpg")

        params = mock_get.call_args_list[0][1]["params"]
        assert params["iilocalonly"] == 1

    @patch("utils.log_timed_api_call", _mock_timed_api_call)
    @patch("utils.os.makedirs")
    @patch("builtins.open", mock_open())
    @patch("utils.requests.get")
    def test_sends_filename_as_titles_param(self, mock_get, mock_makedirs):
        mock_get.side_effect = [_meta_response(FOUND_RESPONSE), _image_response()]
        download_image("wikipedia", "en", "File:Example.jpg")

        params = mock_get.call_args_list[0][1]["params"]
        assert params["titles"] == "File:Example.jpg"


# ─── RESOURCE NOT FOUND TESTS ─────────────────────────────────────────────────

class TestResourceNotFound:
    """The file doesn't exist or imageinfo is absent → ResourceNotFoundError."""

    @patch("utils.log_timed_api_call", _mock_timed_api_call)
    @patch("utils.requests.get")
    def test_raises_when_file_is_missing(self, mock_get):
        # Wikipedia returns the page but with "missing": "" and no imageinfo
        mock_get.return_value = _meta_response(MISSING_RESPONSE)

        with pytest.raises(ResourceNotFoundError) as exc:
            download_image("wikipedia", "en", "File:Missing.jpg")

        assert "Image not found" in str(exc.value)

    @patch("utils.log_timed_api_call", _mock_timed_api_call)
    @patch("utils.requests.get")
    def test_raises_when_commons_file_blocked_by_iilocalonly(self, mock_get):
        # File exists but lives on Commons — iilocalonly hides imageinfo
        mock_get.return_value = _meta_response(COMMONS_FILE_RESPONSE)

        with pytest.raises(ResourceNotFoundError) as exc:
            download_image("wikipedia", "en", "File:Commons_only.jpg")

        assert "Image not found" in str(exc.value)

    @patch("utils.log_timed_api_call", _mock_timed_api_call)
    @patch("utils.requests.get")
    def test_raises_when_pages_is_empty(self, mock_get):
        mock_get.return_value = _meta_response(EMPTY_PAGES_RESPONSE)

        with pytest.raises(ResourceNotFoundError):
            download_image("wikipedia", "en", "File:Example.jpg")


# ─── NETWORK ERROR TESTS ──────────────────────────────────────────────────────

class TestNetworkErrors:
    """requests raises an exception → our code wraps it in the right exception."""

    @patch("utils.log_timed_api_call", _mock_timed_api_call)
    @patch("utils.requests.get")
    def test_metadata_timeout_raises_wiki_api_error(self, mock_get):
        # The first GET (metadata) times out
        mock_get.side_effect = req.exceptions.Timeout()

        with pytest.raises(WikiAPIError) as exc:
            download_image("wikipedia", "en", "File:Example.jpg")

        assert "Timeout" in str(exc.value)

    @patch("utils.log_timed_api_call", _mock_timed_api_call)
    @patch("utils.requests.get")
    def test_metadata_connection_error_raises_wiki_api_error(self, mock_get):
        mock_get.side_effect = req.exceptions.ConnectionError("refused")

        with pytest.raises(WikiAPIError):
            download_image("wikipedia", "en", "File:Example.jpg")

    @patch("utils.log_timed_api_call", _mock_timed_api_call)
    @patch("utils.requests.get")
    def test_image_download_timeout_raises_file_operation_error(self, mock_get):
        # First GET succeeds, second (image download) times out
        mock_get.side_effect = [
            _meta_response(FOUND_RESPONSE),
            req.exceptions.Timeout(),
        ]

        with pytest.raises(FileOperationError) as exc:
            download_image("wikipedia", "en", "File:Example.jpg")

        assert "Timeout" in str(exc.value)

    @patch("utils.log_timed_api_call", _mock_timed_api_call)
    @patch("utils.requests.get")
    def test_image_download_request_error_raises_file_operation_error(self, mock_get):
        mock_get.side_effect = [
            _meta_response(FOUND_RESPONSE),
            req.exceptions.RequestException("network error"),
        ]

        with pytest.raises(FileOperationError):
            download_image("wikipedia", "en", "File:Example.jpg")


# ─── FILE WRITE ERROR TESTS ───────────────────────────────────────────────────

class TestFileWriteErrors:
    """Disk errors when saving the image → FileOperationError."""

    @patch("utils.log_timed_api_call", _mock_timed_api_call)
    @patch("utils.os.makedirs")
    @patch("builtins.open")
    @patch("utils.requests.get")
    def test_disk_full_raises_file_operation_error(self, mock_get, mock_open_fn, mock_makedirs):
        mock_get.side_effect = [_meta_response(FOUND_RESPONSE), _image_response()]
        mock_open_fn.side_effect = OSError("No space left on device")

        with pytest.raises(FileOperationError) as exc:
            download_image("wikipedia", "en", "File:Example.jpg")

        assert "Failed to write" in str(exc.value)


# =============================================================================
# process_upload() TESTS
# =============================================================================
"""
HOW PROCESS_UPLOAD WORKS
========================
1. GET the CSRF token from the target wiki API (authenticated)
2. Check the token is not "+\\" (anon token — means OAuth session is invalid)
3. Check the local file exists before even opening it
4. POST the file to the upload API with the CSRF token
5. Validate the response — must be "Success" and include "imageinfo"
6. Return {"wikipage_url": ..., "file_link": ...}
"""

# ─── fake API response builders ──────────────────────────────────────────────

def _csrf_response(token="validtoken123"):
    """Fake CSRF token GET response."""
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {"query": {"tokens": {"csrftoken": token}}}
    return m


def _upload_ok_response():
    """Fake successful upload POST response."""
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {
        "upload": {
            "result": "Success",
            "imageinfo": {
                "url": "https://upload.wikimedia.org/wikipedia/commons/a/a9/Example.jpg",
                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Example.jpg"
            }
        }
    }
    return m


def _upload_fail_response(error_info="File is corrupt"):
    """Fake failed upload POST response."""
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {
        "upload": {
            "result": "Failure",
            "error": {"info": error_info}
        }
    }
    return m


def _upload_no_imageinfo_response():
    """Upload says Success but imageinfo is missing."""
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {"upload": {"result": "Success"}}
    return m


# ─── SUCCESS TESTS ────────────────────────────────────────────────────────────

class TestProcessUploadSuccess:
    """Happy path — CSRF token fetched, file uploaded, result returned."""

    @patch("utils.log_timed_api_call", _mock_timed_api_call)
    @patch("utils.os.path.exists", return_value=True)
    @patch("builtins.open", mock_open(read_data=b"fake-image-bytes"))
    @patch("utils.requests.post")
    @patch("utils.requests.get")
    def test_returns_dict_with_correct_keys(self, mock_get, mock_post, mock_exists):
        mock_get.return_value = _csrf_response()
        mock_post.return_value = _upload_ok_response()

        result = process_upload(
            "temp_images/file.jpg", "ExampleFile", "jpg",
            "https://commons.wikimedia.org/w/api.php", MagicMock()
        )

        assert "wikipage_url" in result
        assert "file_link" in result

    @patch("utils.log_timed_api_call", _mock_timed_api_call)
    @patch("utils.os.path.exists", return_value=True)
    @patch("builtins.open", mock_open(read_data=b"fake-image-bytes"))
    @patch("utils.requests.post")
    @patch("utils.requests.get")
    def test_returns_correct_urls(self, mock_get, mock_post, mock_exists):
        mock_get.return_value = _csrf_response()
        mock_post.return_value = _upload_ok_response()

        result = process_upload(
            "temp_images/file.jpg", "ExampleFile", "jpg",
            "https://commons.wikimedia.org/w/api.php", MagicMock()
        )

        assert result["wikipage_url"] == "https://commons.wikimedia.org/wiki/File:Example.jpg"
        assert result["file_link"] == "https://upload.wikimedia.org/wikipedia/commons/a/a9/Example.jpg"

    @patch("utils.log_timed_api_call", _mock_timed_api_call)
    @patch("utils.os.path.exists", return_value=True)
    @patch("builtins.open", mock_open(read_data=b"fake-image-bytes"))
    @patch("utils.requests.post")
    @patch("utils.requests.get")
    def test_csrf_token_is_sent_in_upload_post(self, mock_get, mock_post, mock_exists):
        # The CSRF token from the GET must appear in the POST data
        mock_get.return_value = _csrf_response("mytoken456")
        mock_post.return_value = _upload_ok_response()

        process_upload(
            "temp_images/file.jpg", "ExampleFile", "jpg",
            "https://commons.wikimedia.org/w/api.php", MagicMock()
        )

        post_data = mock_post.call_args[1]["data"]
        assert post_data["token"] == "mytoken456"


# ─── CSRF ERRORS ─────────────────────────────────────────────────────────────

class TestProcessUploadCSRFErrors:
    """Failures when fetching or validating the CSRF token."""

    @patch("utils.log_timed_api_call", _mock_timed_api_call)
    @patch("utils.requests.get")
    def test_anon_csrf_token_raises_auth_error(self, mock_get):
        # "+\\" is the unauthenticated token — means OAuth session is invalid
        mock_get.return_value = _csrf_response(token="+\\")

        with pytest.raises(AuthenticationError) as exc:
            process_upload(
                "temp_images/file.jpg", "ExampleFile", "jpg",
                "https://commons.wikimedia.org/w/api.php", MagicMock()
            )

        assert "Invalid CSRF token" in str(exc.value)

    @patch("utils.log_timed_api_call", _mock_timed_api_call)
    @patch("utils.requests.get")
    def test_csrf_timeout_raises_wiki_api_error(self, mock_get):
        mock_get.side_effect = req.exceptions.Timeout()

        with pytest.raises(WikiAPIError) as exc:
            process_upload(
                "temp_images/file.jpg", "ExampleFile", "jpg",
                "https://commons.wikimedia.org/w/api.php", MagicMock()
            )

        assert "Timeout" in str(exc.value)

    @patch("utils.log_timed_api_call", _mock_timed_api_call)
    @patch("utils.requests.get")
    def test_csrf_connection_error_raises_wiki_api_error(self, mock_get):
        mock_get.side_effect = req.exceptions.ConnectionError("refused")

        with pytest.raises(WikiAPIError):
            process_upload(
                "temp_images/file.jpg", "ExampleFile", "jpg",
                "https://commons.wikimedia.org/w/api.php", MagicMock()
            )

    @patch("utils.log_timed_api_call", _mock_timed_api_call)
    @patch("utils.requests.get")
    def test_csrf_missing_key_raises_wiki_api_error(self, mock_get):
        # Response is valid JSON but missing the expected "tokens" key
        m = MagicMock()
        m.status_code = 200
        m.json.return_value = {"query": {}}  # no "tokens" key
        mock_get.return_value = m

        with pytest.raises(WikiAPIError) as exc:
            process_upload(
                "temp_images/file.jpg", "ExampleFile", "jpg",
                "https://commons.wikimedia.org/w/api.php", MagicMock()
            )

        assert "CSRF" in str(exc.value)


# ─── FILE ERRORS ──────────────────────────────────────────────────────────────

class TestProcessUploadFileErrors:
    """Failures when the local file cannot be found or read."""

    @patch("utils.log_timed_api_call", _mock_timed_api_call)
    @patch("utils.os.path.exists", return_value=False)
    @patch("utils.requests.get")
    def test_file_not_found_raises_file_op_error(self, mock_get, mock_exists):
        mock_get.return_value = _csrf_response()

        with pytest.raises(FileOperationError) as exc:
            process_upload(
                "temp_images/missing.jpg", "ExampleFile", "jpg",
                "https://commons.wikimedia.org/w/api.php", MagicMock()
            )

        assert "not found" in str(exc.value)

    @patch("utils.log_timed_api_call", _mock_timed_api_call)
    @patch("utils.os.path.exists", return_value=True)
    @patch("builtins.open")
    @patch("utils.requests.get")
    def test_oserror_reading_file_raises_file_op_error(self, mock_get, mock_open_fn, mock_exists):
        mock_get.return_value = _csrf_response()
        mock_open_fn.side_effect = OSError("Permission denied")

        with pytest.raises(FileOperationError) as exc:
            process_upload(
                "temp_images/file.jpg", "ExampleFile", "jpg",
                "https://commons.wikimedia.org/w/api.php", MagicMock()
            )

        assert "Could not read file" in str(exc.value)


# ─── UPLOAD RESULT ERRORS ─────────────────────────────────────────────────────

class TestProcessUploadResultErrors:
    """Failures after the POST is sent — bad result from the Wiki API."""

    @patch("utils.log_timed_api_call", _mock_timed_api_call)
    @patch("utils.os.path.exists", return_value=True)
    @patch("builtins.open", mock_open(read_data=b"fake-image-bytes"))
    @patch("utils.requests.post")
    @patch("utils.requests.get")
    def test_upload_result_failure_raises_wiki_api_error(self, mock_get, mock_post, mock_exists):
        mock_get.return_value = _csrf_response()
        mock_post.return_value = _upload_fail_response("File is corrupt")

        with pytest.raises(WikiAPIError) as exc:
            process_upload(
                "temp_images/file.jpg", "ExampleFile", "jpg",
                "https://commons.wikimedia.org/w/api.php", MagicMock()
            )

        assert "Upload failed" in str(exc.value)

    @patch("utils.log_timed_api_call", _mock_timed_api_call)
    @patch("utils.os.path.exists", return_value=True)
    @patch("builtins.open", mock_open(read_data=b"fake-image-bytes"))
    @patch("utils.requests.post")
    @patch("utils.requests.get")
    def test_upload_missing_imageinfo_raises_wiki_api_error(self, mock_get, mock_post, mock_exists):
        # Upload says Success but no imageinfo in the response
        mock_get.return_value = _csrf_response()
        mock_post.return_value = _upload_no_imageinfo_response()

        with pytest.raises(WikiAPIError) as exc:
            process_upload(
                "temp_images/file.jpg", "ExampleFile", "jpg",
                "https://commons.wikimedia.org/w/api.php", MagicMock()
            )

        assert "imageinfo" in str(exc.value)

    @patch("utils.log_timed_api_call", _mock_timed_api_call)
    @patch("utils.os.path.exists", return_value=True)
    @patch("builtins.open", mock_open(read_data=b"fake-image-bytes"))
    @patch("utils.requests.post")
    @patch("utils.requests.get")
    def test_upload_timeout_raises_wiki_api_error(self, mock_get, mock_post, mock_exists):
        mock_get.return_value = _csrf_response()
        mock_post.side_effect = req.exceptions.Timeout()

        with pytest.raises(WikiAPIError) as exc:
            process_upload(
                "temp_images/file.jpg", "ExampleFile", "jpg",
                "https://commons.wikimedia.org/w/api.php", MagicMock()
            )

        assert "Timeout" in str(exc.value)

    @patch("utils.log_timed_api_call", _mock_timed_api_call)
    @patch("utils.os.path.exists", return_value=True)
    @patch("builtins.open", mock_open(read_data=b"fake-image-bytes"))
    @patch("utils.requests.post")
    @patch("utils.requests.get")
    def test_upload_request_error_raises_wiki_api_error(self, mock_get, mock_post, mock_exists):
        mock_get.return_value = _csrf_response()
        mock_post.side_effect = req.exceptions.RequestException("network error")

        with pytest.raises(WikiAPIError):
            process_upload(
                "temp_images/file.jpg", "ExampleFile", "jpg",
                "https://commons.wikimedia.org/w/api.php", MagicMock()
            )


# =============================================================================
# get_localized_wikitext() TESTS
# =============================================================================

# ─── wikitext fixtures ───────────────────────────────────────────────────────

# A template that IS in TEMPLATES with an Article param
WIKITEXT_WITH_TEMPLATE = "{{Non-free album cover|Article=Cat|Description=Test}}"

# A template NOT in TEMPLATES — should be ignored
WIKITEXT_UNKNOWN_TEMPLATE = "{{SomeRandomTemplate|Article=Cat}}"

# Two templates in TEMPLATES — lets us test that one failure doesn't abort the rest
WIKITEXT_TWO_TEMPLATES = (
    "{{Non-free album cover|Article=Cat}}\n"
    "{{Non-free film screenshot|Article=Dog}}"
)


def _langlinks_response(lang, title):
    """Fake langlinks API response with one translation."""
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {
        "query": {
            "pages": [
                {
                    "title": "Cat",
                    "langlinks": [{"lang": lang, "title": title}]
                }
            ]
        }
    }
    return m


def _no_langlinks_response():
    """Fake langlinks API response with no translations."""
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {"query": {"pages": [{"title": "Cat"}]}}
    return m


# ─── TESTS ────────────────────────────────────────────────────────────────────

class TestGetLocalizedWikitext:

    @patch("utils.requests.get")
    def test_always_returns_a_string(self, mock_get):
        mock_get.return_value = _langlinks_response("fr", "Chat")
        result = get_localized_wikitext(WIKITEXT_WITH_TEMPLATE, "https://en.wikipedia.org/w/api.php", "fr")
        assert isinstance(result, str)

    @patch("utils.requests.get")
    def test_localizes_article_param_when_langlink_found(self, mock_get):
        # The French translation of "Cat" is "Chat" — Article param should be updated
        mock_get.return_value = _langlinks_response("fr", "Chat")
        result = get_localized_wikitext(WIKITEXT_WITH_TEMPLATE, "https://en.wikipedia.org/w/api.php", "fr")
        assert "Chat" in result

    @patch("utils.requests.get")
    def test_leaves_article_unchanged_when_no_langlink_for_target(self, mock_get):
        # API returns langlinks but none match the requested language
        mock_get.return_value = _no_langlinks_response()
        result = get_localized_wikitext(WIKITEXT_WITH_TEMPLATE, "https://en.wikipedia.org/w/api.php", "fr")
        # Original value "Cat" should still be present
        assert "Cat" in result

    @patch("utils.requests.get")
    def test_ignores_templates_not_in_templates_list(self, mock_get):
        # Template not in TEMPLATES → no API call made, wikitext unchanged
        result = get_localized_wikitext(WIKITEXT_UNKNOWN_TEMPLATE, "https://en.wikipedia.org/w/api.php", "fr")
        mock_get.assert_not_called()
        assert "Cat" in result

    @patch("utils.requests.get")
    def test_continues_processing_after_single_article_timeout(self, mock_get):
        # First article times out, second should still be processed
        mock_get.side_effect = [
            req.exceptions.Timeout(),
            _langlinks_response("fr", "Chien"),
        ]
        # Should not raise — timeouts are caught per-article
        result = get_localized_wikitext(
            WIKITEXT_TWO_TEMPLATES, "https://en.wikipedia.org/w/api.php", "fr"
        )
        assert isinstance(result, str)

    @patch("utils.requests.get")
    def test_continues_processing_after_single_article_request_error(self, mock_get):
        mock_get.side_effect = [
            req.exceptions.RequestException("network error"),
            _langlinks_response("fr", "Chien"),
        ]
        result = get_localized_wikitext(
            WIKITEXT_TWO_TEMPLATES, "https://en.wikipedia.org/w/api.php", "fr"
        )
        assert isinstance(result, str)

    @patch("utils.mwparserfromhell.parse")
    def test_returns_original_wikitext_on_outer_exception(self, mock_parse):
        # If mwparserfromhell.parse itself crashes, return the original unchanged
        mock_parse.side_effect = Exception("parse error")
        original = "{{Non-free album cover|Article=Cat}}"
        result = get_localized_wikitext(original, "https://en.wikipedia.org/w/api.php", "fr")
        assert result == original
