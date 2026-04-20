"""
Tests for upload_image_task() in tasks.py


The mock self needs to have:
  - self.request.id       → fake task ID (used in log messages)
  - self.request.retries  → how many retries have happened so far
  - self.max_retries      → max allowed retries (3 in the real task)
  - self.update_state()   → no-op, we don't care about Celery state in tests
  - self.retry(exc=e)     → raises celery.exceptions.Retry (simulates scheduling a retry)

WHY TASKS NEVER RAISE
======================
Unlike utils.py, the task always returns a dict — it never raises.
The only exception is Retry, which Celery uses internally and must be re-raised.
So every test checks the RETURN VALUE, not raised exceptions.
(Except retry tests, which check that Retry is raised.)

HOW TO RUN
==========
  pytest tests/tasks_test.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock, mock_open
from contextlib import contextmanager
from celery.exceptions import Retry
import requests as req

from tasks import upload_image_task


# ─── mock for log_timed_api_call ──────────────────────────────────────────────
# tasks.py does:  with log_timed_api_call(logger, endpoint, method) as ctx:
#                     ctx["status_code"] = ...
# The real one yields a dict — our fake does the same so ctx["status_code"] works.

@contextmanager
def _mock_timed_api_call(logger, endpoint, method):
    yield {}


# ─── mock Celery self ─────────────────────────────────────────────────────────

def _make_self(retries=0, max_retries=3):
    """
    Builds a fake Celery task instance.
    retries=0 means this is the first attempt (no retries yet).
    Setting retries=max_retries simulates exhausted retries.
    """
    mock_self = MagicMock()
    mock_self.request.id = "test-task-id-123"
    mock_self.request.retries = retries
    mock_self.max_retries = max_retries
    # self.retry(exc=e) raises Retry in the real Celery — simulate that here
    mock_self.retry.side_effect = Retry()
    return mock_self


# ─── shared test data ─────────────────────────────────────────────────────────

VALID_OAUTH = {
    "consumer_key": "ck",
    "consumer_secret": "cs",
    "key": "k",
    "secret": "s"
}

TR_ENDPOINT = "https://commons.wikimedia.org/w/api.php"
FILE_PATH = "temp_images/test.jpg"
TR_FILENAME = "TestFile"
SRC_FILEEXT = "jpg"


# ─── fake API response builders ───────────────────────────────────────────────

def _csrf_response(token="validtoken123"):
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {"query": {"tokens": {"csrftoken": token}}}
    return m


def _upload_ok_response():
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {
        "upload": {
            "result": "Success",
            "imageinfo": {
                "url": "https://upload.wikimedia.org/wikipedia/commons/a/a9/Test.jpg",
                "descriptionurl": "https://commons.wikimedia.org/wiki/File:TestFile.jpg"
            }
        }
    }
    return m


def _upload_fail_response(error_info="File is corrupt"):
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
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {"upload": {"result": "Success"}}
    return m


# =============================================================================
# SUCCESS
# =============================================================================

class TestSuccess:
    """Full happy path — CSRF fetched, file uploaded, result validated."""

    @patch("tasks.log_timed_api_call", _mock_timed_api_call)
    @patch("tasks.os.path.getsize", return_value=1024)
    @patch("tasks.os.path.exists", return_value=True)
    @patch("builtins.open", mock_open(read_data=b"fake-bytes"))
    @patch("tasks.requests.post")
    @patch("tasks.requests.get")
    @patch("tasks.requests_oauthlib.OAuth1")
    def test_returns_success_true(self, mock_oauth, mock_get, mock_post, mock_exists, mock_size):
        mock_get.return_value = _csrf_response()
        mock_post.return_value = _upload_ok_response()

        result = upload_image_task(_make_self(), FILE_PATH, TR_FILENAME, SRC_FILEEXT, TR_ENDPOINT, VALID_OAUTH)

        assert result["success"] is True

    @patch("tasks.log_timed_api_call", _mock_timed_api_call)
    @patch("tasks.os.path.getsize", return_value=1024)
    @patch("tasks.os.path.exists", return_value=True)
    @patch("builtins.open", mock_open(read_data=b"fake-bytes"))
    @patch("tasks.requests.post")
    @patch("tasks.requests.get")
    @patch("tasks.requests_oauthlib.OAuth1")
    def test_returns_correct_urls(self, mock_oauth, mock_get, mock_post, mock_exists, mock_size):
        mock_get.return_value = _csrf_response()
        mock_post.return_value = _upload_ok_response()

        result = upload_image_task(_make_self(), FILE_PATH, TR_FILENAME, SRC_FILEEXT, TR_ENDPOINT, VALID_OAUTH)

        assert result["wikipage_url"] == "https://commons.wikimedia.org/wiki/File:TestFile.jpg"
        assert result["file_link"] == "https://upload.wikimedia.org/wikipedia/commons/a/a9/Test.jpg"

    @patch("tasks.log_timed_api_call", _mock_timed_api_call)
    @patch("tasks.os.path.getsize", return_value=1024)
    @patch("tasks.os.path.exists", return_value=True)
    @patch("builtins.open", mock_open(read_data=b"fake-bytes"))
    @patch("tasks.requests.post")
    @patch("tasks.requests.get")
    @patch("tasks.requests_oauthlib.OAuth1")
    def test_csrf_token_sent_in_upload(self, mock_oauth, mock_get, mock_post, mock_exists, mock_size):
        # The CSRF token from the GET must appear in the POST data
        mock_get.return_value = _csrf_response("mytoken999")
        mock_post.return_value = _upload_ok_response()

        upload_image_task(_make_self(), FILE_PATH, TR_FILENAME, SRC_FILEEXT, TR_ENDPOINT, VALID_OAUTH)

        post_data = mock_post.call_args[1]["data"]
        assert post_data["token"] == "mytoken999"


# =============================================================================
# MISSING / BAD OAUTH CREDENTIALS
# =============================================================================

class TestOAuthCredentials:
    """Task returns failure immediately when credentials are wrong — no network calls made."""

    def test_missing_all_keys_returns_failure(self):
        result = upload_image_task(_make_self(), FILE_PATH, TR_FILENAME, SRC_FILEEXT, TR_ENDPOINT, {})

        assert result["success"] is False
        assert "Missing OAuth credentials" in result["errors"][0]

    def test_missing_single_key_returns_failure(self):
        incomplete = {k: v for k, v in VALID_OAUTH.items() if k != "secret"}

        result = upload_image_task(_make_self(), FILE_PATH, TR_FILENAME, SRC_FILEEXT, TR_ENDPOINT, incomplete)

        assert result["success"] is False
        assert "secret" in result["errors"][0]

    @patch("tasks.requests_oauthlib.OAuth1")
    def test_oauth_session_creation_failure_returns_failure(self, mock_oauth):
        mock_oauth.side_effect = Exception("OAuth library error")

        result = upload_image_task(_make_self(), FILE_PATH, TR_FILENAME, SRC_FILEEXT, TR_ENDPOINT, VALID_OAUTH)

        assert result["success"] is False
        assert "Failed to create OAuth session" in result["errors"][0]


# =============================================================================
# CSRF TOKEN ERRORS
# =============================================================================

class TestCSRFErrors:
    """Failures when fetching or validating the CSRF token."""

    @patch("tasks.log_timed_api_call", _mock_timed_api_call)
    @patch("tasks.requests.get")
    @patch("tasks.requests_oauthlib.OAuth1")
    def test_anon_csrf_token_returns_failure_no_retry(self, mock_oauth, mock_get):
        # "+\" means OAuth session not recognized — should NOT retry, return immediately
        mock_get.return_value = _csrf_response(token="+\\")
        mock_self = _make_self(retries=0)

        result = upload_image_task(mock_self, FILE_PATH, TR_FILENAME, SRC_FILEEXT, TR_ENDPOINT, VALID_OAUTH)

        assert result["success"] is False
        assert "CSRF token" in result["errors"][0]
        # retry must NOT have been called — retrying with an expired token is pointless
        mock_self.retry.assert_not_called()

    @patch("tasks.log_timed_api_call", _mock_timed_api_call)
    @patch("tasks.requests.get")
    @patch("tasks.requests_oauthlib.OAuth1")
    def test_csrf_timeout_triggers_retry_when_retries_remain(self, mock_oauth, mock_get):
        mock_get.side_effect = req.exceptions.Timeout()
        mock_self = _make_self(retries=0, max_retries=3)

        with pytest.raises(Retry):
            upload_image_task(mock_self, FILE_PATH, TR_FILENAME, SRC_FILEEXT, TR_ENDPOINT, VALID_OAUTH)

        mock_self.retry.assert_called_once()

    @patch("tasks.log_timed_api_call", _mock_timed_api_call)
    @patch("tasks.requests.get")
    @patch("tasks.requests_oauthlib.OAuth1")
    def test_csrf_timeout_returns_failure_when_retries_exhausted(self, mock_oauth, mock_get):
        mock_get.side_effect = req.exceptions.Timeout()
        # retries == max_retries means no more retries left
        mock_self = _make_self(retries=3, max_retries=3)

        result = upload_image_task(mock_self, FILE_PATH, TR_FILENAME, SRC_FILEEXT, TR_ENDPOINT, VALID_OAUTH)

        assert result["success"] is False
        assert "Timeout" in result["errors"][0]

    @patch("tasks.log_timed_api_call", _mock_timed_api_call)
    @patch("tasks.requests.get")
    @patch("tasks.requests_oauthlib.OAuth1")
    def test_csrf_request_error_triggers_retry_when_retries_remain(self, mock_oauth, mock_get):
        mock_get.side_effect = req.exceptions.ConnectionError("refused")
        mock_self = _make_self(retries=0)

        with pytest.raises(Retry):
            upload_image_task(mock_self, FILE_PATH, TR_FILENAME, SRC_FILEEXT, TR_ENDPOINT, VALID_OAUTH)

    @patch("tasks.log_timed_api_call", _mock_timed_api_call)
    @patch("tasks.requests.get")
    @patch("tasks.requests_oauthlib.OAuth1")
    def test_csrf_missing_key_returns_failure_no_retry(self, mock_oauth, mock_get):
        # Response is valid JSON but missing expected keys — not a network error, don't retry
        m = MagicMock()
        m.status_code = 200
        m.json.return_value = {"query": {}}  # no "tokens" key
        mock_get.return_value = m
        mock_self = _make_self(retries=0)

        result = upload_image_task(mock_self, FILE_PATH, TR_FILENAME, SRC_FILEEXT, TR_ENDPOINT, VALID_OAUTH)

        assert result["success"] is False
        assert "CSRF" in result["errors"][0]
        mock_self.retry.assert_not_called()


# =============================================================================
# FILE ERRORS
# =============================================================================

class TestFileErrors:
    """Failures when the local file can't be found or read before upload."""

    @patch("tasks.log_timed_api_call", _mock_timed_api_call)
    @patch("tasks.os.path.exists", return_value=False)
    @patch("tasks.requests.get")
    @patch("tasks.requests_oauthlib.OAuth1")
    def test_file_not_found_returns_failure(self, mock_oauth, mock_get, mock_exists):
        mock_get.return_value = _csrf_response()

        result = upload_image_task(_make_self(), FILE_PATH, TR_FILENAME, SRC_FILEEXT, TR_ENDPOINT, VALID_OAUTH)

        assert result["success"] is False
        assert "not found" in result["errors"][0]

    @patch("tasks.log_timed_api_call", _mock_timed_api_call)
    @patch("tasks.os.path.getsize", return_value=1024)
    @patch("tasks.os.path.exists", return_value=True)
    @patch("builtins.open")
    @patch("tasks.requests.get")
    @patch("tasks.requests_oauthlib.OAuth1")
    def test_oserror_reading_file_returns_failure(self, mock_oauth, mock_get, mock_open_fn, mock_exists, mock_size):
        mock_get.return_value = _csrf_response()
        mock_open_fn.side_effect = OSError("Permission denied")

        result = upload_image_task(_make_self(), FILE_PATH, TR_FILENAME, SRC_FILEEXT, TR_ENDPOINT, VALID_OAUTH)

        assert result["success"] is False
        assert "Could not read file" in result["errors"][0]


# =============================================================================
# UPLOAD NETWORK ERRORS
# =============================================================================

class TestUploadNetworkErrors:
    """Network failures during the actual file upload POST."""

    @patch("tasks.log_timed_api_call", _mock_timed_api_call)
    @patch("tasks.os.path.getsize", return_value=1024)
    @patch("tasks.os.path.exists", return_value=True)
    @patch("builtins.open", mock_open(read_data=b"fake-bytes"))
    @patch("tasks.requests.post")
    @patch("tasks.requests.get")
    @patch("tasks.requests_oauthlib.OAuth1")
    def test_upload_timeout_triggers_retry_when_retries_remain(self, mock_oauth, mock_get, mock_post, mock_exists, mock_size):
        mock_get.return_value = _csrf_response()
        mock_post.side_effect = req.exceptions.Timeout()
        mock_self = _make_self(retries=0)

        with pytest.raises(Retry):
            upload_image_task(mock_self, FILE_PATH, TR_FILENAME, SRC_FILEEXT, TR_ENDPOINT, VALID_OAUTH)

        mock_self.retry.assert_called_once()

    @patch("tasks.log_timed_api_call", _mock_timed_api_call)
    @patch("tasks.os.path.getsize", return_value=1024)
    @patch("tasks.os.path.exists", return_value=True)
    @patch("builtins.open", mock_open(read_data=b"fake-bytes"))
    @patch("tasks.requests.post")
    @patch("tasks.requests.get")
    @patch("tasks.requests_oauthlib.OAuth1")
    def test_upload_timeout_returns_failure_when_retries_exhausted(self, mock_oauth, mock_get, mock_post, mock_exists, mock_size):
        mock_get.return_value = _csrf_response()
        mock_post.side_effect = req.exceptions.Timeout()
        mock_self = _make_self(retries=3, max_retries=3)

        result = upload_image_task(mock_self, FILE_PATH, TR_FILENAME, SRC_FILEEXT, TR_ENDPOINT, VALID_OAUTH)

        assert result["success"] is False
        assert "Timeout" in result["errors"][0]

    @patch("tasks.log_timed_api_call", _mock_timed_api_call)
    @patch("tasks.os.path.getsize", return_value=1024)
    @patch("tasks.os.path.exists", return_value=True)
    @patch("builtins.open", mock_open(read_data=b"fake-bytes"))
    @patch("tasks.requests.post")
    @patch("tasks.requests.get")
    @patch("tasks.requests_oauthlib.OAuth1")
    def test_upload_request_error_triggers_retry(self, mock_oauth, mock_get, mock_post, mock_exists, mock_size):
        mock_get.return_value = _csrf_response()
        mock_post.side_effect = req.exceptions.ConnectionError("network error")
        mock_self = _make_self(retries=0)

        with pytest.raises(Retry):
            upload_image_task(mock_self, FILE_PATH, TR_FILENAME, SRC_FILEEXT, TR_ENDPOINT, VALID_OAUTH)


# =============================================================================
# UPLOAD RESULT VALIDATION
# =============================================================================

class TestUploadResultValidation:
    """The POST succeeded but the wiki rejected the upload or returned unexpected data."""

    @patch("tasks.log_timed_api_call", _mock_timed_api_call)
    @patch("tasks.os.path.getsize", return_value=1024)
    @patch("tasks.os.path.exists", return_value=True)
    @patch("builtins.open", mock_open(read_data=b"fake-bytes"))
    @patch("tasks.requests.post")
    @patch("tasks.requests.get")
    @patch("tasks.requests_oauthlib.OAuth1")
    def test_upload_result_failure_returns_failure(self, mock_oauth, mock_get, mock_post, mock_exists, mock_size):
        mock_get.return_value = _csrf_response()
        mock_post.return_value = _upload_fail_response("File is corrupt")

        result = upload_image_task(_make_self(), FILE_PATH, TR_FILENAME, SRC_FILEEXT, TR_ENDPOINT, VALID_OAUTH)

        assert result["success"] is False
        assert "Upload failed" in result["errors"][0]
        assert "File is corrupt" in result["errors"][0]

    @patch("tasks.log_timed_api_call", _mock_timed_api_call)
    @patch("tasks.os.path.getsize", return_value=1024)
    @patch("tasks.os.path.exists", return_value=True)
    @patch("builtins.open", mock_open(read_data=b"fake-bytes"))
    @patch("tasks.requests.post")
    @patch("tasks.requests.get")
    @patch("tasks.requests_oauthlib.OAuth1")
    def test_upload_missing_imageinfo_returns_failure(self, mock_oauth, mock_get, mock_post, mock_exists, mock_size):
        # Wiki says "Success" but no imageinfo in response
        mock_get.return_value = _csrf_response()
        mock_post.return_value = _upload_no_imageinfo_response()

        result = upload_image_task(_make_self(), FILE_PATH, TR_FILENAME, SRC_FILEEXT, TR_ENDPOINT, VALID_OAUTH)

        assert result["success"] is False
        assert "imageinfo" in result["errors"][0]
