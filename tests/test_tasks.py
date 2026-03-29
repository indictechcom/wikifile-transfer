"""
test_tasks.py
Tests for tasks.py — upload_image_task and its helpers.

Uses task.apply() to run tasks synchronously in-process (no broker needed).
All HTTP calls and file I/O are mocked.
"""

import pytest
from unittest.mock import patch, MagicMock, mock_open
import requests

from globalExceptions import CSRFTokenError, OAuthConfigError, UploadError


VALID_OAUTH = {
    "consumer_key":    "ck",
    "consumer_secret": "cs",
    "key":             "tk",
    "secret":          "ts",
}

CSRF_RESPONSE = {
    "query": {"tokens": {"csrftoken": "test_token+\\"}}
}

UPLOAD_SUCCESS_RESPONSE = {
    "upload": {
        "imageinfo": {
            "descriptionurl": "https://commons.wikimedia.org/wiki/File:Cat.jpg",
            "url":            "https://upload.wikimedia.org/Cat.jpg",
        }
    }
}


def _mock_resp(json_data=None, status_code=200):
    m = MagicMock()
    m.status_code = status_code
    m.json.return_value = json_data or {}
    m.raise_for_status = MagicMock()
    if status_code >= 400:
        err = requests.HTTPError(response=m)
        m.raise_for_status.side_effect = err
    return m


# _build_oauth_session 

class TestBuildOAuthSession:
    def test_raises_oauth_config_error_on_missing_keys(self):
        from tasks import _build_oauth_session
        incomplete = {"consumer_key": "ck"}
        with pytest.raises(OAuthConfigError, match="missing required keys"):
            _build_oauth_session(incomplete)

    def test_raises_oauth_config_error_when_all_keys_missing(self):
        from tasks import _build_oauth_session
        with pytest.raises(OAuthConfigError):
            _build_oauth_session({})

    def test_returns_oauth1_on_valid_config(self):
        import requests_oauthlib
        from tasks import _build_oauth_session
        result = _build_oauth_session(VALID_OAUTH)
        assert isinstance(result, requests_oauthlib.OAuth1)

    def test_partial_keys_reports_missing(self):
        from tasks import _build_oauth_session
        with pytest.raises(OAuthConfigError) as exc_info:
            _build_oauth_session({"consumer_key": "ck", "consumer_secret": "cs"})
        assert "key" in str(exc_info.value) or "secret" in str(exc_info.value)



# Upload_image_task

class TestUploadImageTask:

    def _run(self, file_path="temp_images/test.jpg", tr_filename="Cat",
             src_fileext="jpg", tr_endpoint="https://commons.wikimedia.org/w/api.php",
             oauth=None):
        from tasks import upload_image_task
        return upload_image_task.apply(
            args=[file_path, tr_filename, src_fileext, tr_endpoint, VALID_OAUTH if oauth is None else oauth]
        )

    # OAuth failures
    
    def test_missing_oauth_keys_returns_error_result(self):
        result = self._run(oauth={})
        assert result.result["success"] is False
        assert result.result["error_type"] == "OAuthConfigError"

    def test_missing_oauth_does_not_raise_exception(self):
        result = self._run(oauth={})
        assert result.successful()

    # CSRF token failures

    def test_csrf_failure_returns_error_result(self):
        csrf_resp = _mock_resp(status_code=403)
        with patch("utils.requests.get", return_value=csrf_resp):
            result = self._run()
        assert result.result["success"] is False
        assert result.result["error_type"] == "CSRFTokenError"

    def test_csrf_network_error_returns_error_result(self):
        with patch("utils.requests.get",
                   side_effect=requests.ConnectionError("refused")):
            result = self._run()
        assert result.result["success"] is False
        assert result.result["error_type"] == "CSRFTokenError"

    # File not found

    def test_local_file_not_found_returns_error_result(self):
        csrf_resp = _mock_resp(CSRF_RESPONSE)
        with patch("utils.requests.get", return_value=csrf_resp), \
             patch("builtins.open", side_effect=FileNotFoundError("no file")):
            result = self._run(file_path="/nonexistent/file.jpg")
        assert result.result["success"] is False
        assert result.result["error_type"] == "UploadError"

    def test_local_file_not_found_message_contains_path(self):
        csrf_resp = _mock_resp(CSRF_RESPONSE)
        with patch("utils.requests.get", return_value=csrf_resp), \
             patch("builtins.open", side_effect=FileNotFoundError("no file")):
            result = self._run(file_path="/nonexistent/file.jpg")
        assert "nonexistent" in result.result["error"]

    # HTTP errors during upload

    def test_http_error_during_upload_returns_error_result(self):
        csrf_resp = _mock_resp(CSRF_RESPONSE)
        upload_resp = _mock_resp(status_code=500)
        with patch("utils.requests.get", return_value=csrf_resp), \
             patch("builtins.open", mock_open(read_data=b"data")), \
             patch("tasks.requests.post", return_value=upload_resp):
            result = self._run()
        assert result.result["success"] is False
        assert result.result["error_type"] == "UploadError"

    def test_http_error_403_during_upload_returns_error_result(self):
        csrf_resp = _mock_resp(CSRF_RESPONSE)
        upload_resp = _mock_resp(status_code=403)
        with patch("utils.requests.get", return_value=csrf_resp), \
             patch("builtins.open", mock_open(read_data=b"data")), \
             patch("tasks.requests.post", return_value=upload_resp):
            result = self._run()
        assert result.result["success"] is False

    # Unexpected API response structure

    def test_missing_imageinfo_returns_error_result(self):
        csrf_resp = _mock_resp(CSRF_RESPONSE)
        bad_upload = _mock_resp({"upload": {"result": "Failure"}})
        with patch("utils.requests.get", return_value=csrf_resp), \
             patch("builtins.open", mock_open(read_data=b"data")), \
             patch("tasks.requests.post", return_value=bad_upload):
            result = self._run()
        assert result.result["success"] is False
        assert result.result["error_type"] == "UploadError"

    def test_api_error_info_included_in_message(self):
        csrf_resp = _mock_resp(CSRF_RESPONSE)
        bad_upload = _mock_resp({
            "error": {"info": "You do not have permission to upload files."}
        })
        with patch("utils.requests.get", return_value=csrf_resp), \
             patch("builtins.open", mock_open(read_data=b"data")), \
             patch("tasks.requests.post", return_value=bad_upload):
            result = self._run()
        assert "permission" in result.result["error"]

    # Happy path

    def test_happy_path_returns_success_true(self):
        csrf_resp = _mock_resp(CSRF_RESPONSE)
        upload_resp = _mock_resp(UPLOAD_SUCCESS_RESPONSE)
        with patch("utils.requests.get", return_value=csrf_resp), \
             patch("builtins.open", mock_open(read_data=b"data")), \
             patch("tasks.requests.post", return_value=upload_resp):
            result = self._run()
        assert result.result["success"] is True

    def test_happy_path_returns_wikipage_url(self):
        csrf_resp = _mock_resp(CSRF_RESPONSE)
        upload_resp = _mock_resp(UPLOAD_SUCCESS_RESPONSE)
        with patch("utils.requests.get", return_value=csrf_resp), \
             patch("builtins.open", mock_open(read_data=b"data")), \
             patch("tasks.requests.post", return_value=upload_resp):
            result = self._run()
        assert result.result["data"]["wikipage_url"] == "https://commons.wikimedia.org/wiki/File:Cat.jpg"

    def test_happy_path_returns_file_link(self):
        csrf_resp = _mock_resp(CSRF_RESPONSE)
        upload_resp = _mock_resp(UPLOAD_SUCCESS_RESPONSE)
        with patch("utils.requests.get", return_value=csrf_resp), \
             patch("builtins.open", mock_open(read_data=b"data")), \
             patch("tasks.requests.post", return_value=upload_resp):
            result = self._run()
        assert result.result["data"]["file_link"] == "https://upload.wikimedia.org/Cat.jpg"

    def test_happy_path_task_state_is_success(self):
        csrf_resp = _mock_resp(CSRF_RESPONSE)
        upload_resp = _mock_resp(UPLOAD_SUCCESS_RESPONSE)
        with patch("utils.requests.get", return_value=csrf_resp), \
             patch("builtins.open", mock_open(read_data=b"data")), \
             patch("tasks.requests.post", return_value=upload_resp):
            result = self._run()
        assert result.successful()

    # Result is always a plain dict

    def test_error_result_is_plain_dict_not_flask_response(self):
        result = self._run(oauth={})
        assert isinstance(result.result, dict)
        assert not hasattr(result.result, "status_code")

    def test_success_result_is_plain_dict(self):
        csrf_resp = _mock_resp(CSRF_RESPONSE)
        upload_resp = _mock_resp(UPLOAD_SUCCESS_RESPONSE)
        with patch("utils.requests.get", return_value=csrf_resp), \
             patch("builtins.open", mock_open(read_data=b"data")), \
             patch("tasks.requests.post", return_value=upload_resp):
            result = self._run()
        assert isinstance(result.result, dict)
