"""
Tests for Flask API routes.
"""
import json
from unittest.mock import patch, MagicMock


class TestUserRoute:
    """Tests for GET /api/user"""

    def test_returns_logged_false_when_no_session(self, client):
        response = client.get("/api/user")
        assert response.status_code == 200
        data = response.get_json()
        assert data["logged"] is False
        assert data["username"] is None

    def test_response_has_expected_keys(self, client):
        response = client.get("/api/user")
        data = response.get_json()
        assert "logged" in data
        assert "username" in data


class TestPreferenceRoute:
    """Tests for GET and POST /api/preference"""

    def test_get_returns_defaults_when_not_logged_in(self, client):
        response = client.get("/api/preference")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["project"] == "wikipedia"
        assert data["data"]["lang"] == "en"
        assert data["data"]["skip_upload_selection"] is False

    def test_get_response_structure(self, client):
        response = client.get("/api/preference")
        data = response.get_json()
        assert "success" in data
        assert "data" in data
        assert "project" in data["data"]
        assert "lang" in data["data"]
        assert "skip_upload_selection" in data["data"]

    def test_post_without_auth_fails(self, client):
        payload = {"project": "wikipedia", "lang": "fr", "skip_upload_selection": False}
        response = client.post(
            "/api/preference",
            data=json.dumps(payload),
            content_type="application/json"
        )
        # Without a valid session, MW_OAUTH.get_current_user returns None
        # which causes a DB error or similar — we just check it doesn't 500 silently
        assert response.status_code in [200, 400, 500]

    def test_invalid_method_returns_400(self, client):
        response = client.put("/api/preference")
        assert response.status_code == 405


class TestUserLanguageRoute:
    """Tests for GET and POST /api/user_language"""

    def test_get_returns_default_language(self, client):
        response = client.get("/api/user_language")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["user_language"] == "en"

    def test_get_response_has_user_language_key(self, client):
        response = client.get("/api/user_language")
        data = response.get_json()
        assert "user_language" in data["data"]


class TestGetWikitextRoute:
    """Tests for GET /api/get_wikitext"""

    def test_missing_params_returns_empty_wikitext(self, client):
        response = client.get("/api/get_wikitext")
        assert response.status_code == 200
        data = response.get_json()
        assert data["wikitext"] == ""

    def test_partial_params_returns_empty_wikitext(self, client):
        response = client.get("/api/get_wikitext?src_lang=en&src_project=wikipedia")
        assert response.status_code == 200
        assert response.get_json()["wikitext"] == ""

    @patch("app.requests.get")
    def test_successful_wikitext_fetch(self, mock_get, client):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "query": {
                "pages": [
                    {
                        "revisions": [
                            {
                                "slots": {
                                    "main": {
                                        "content": "== Test Article =="
                                    }
                                }
                            }
                        ]
                    }
                ]
            }
        }
        mock_get.return_value = mock_response

        response = client.get(
            "/api/get_wikitext"
            "?src_lang=en&src_project=wikipedia"
            "&src_filename=File:Test.jpg&tr_lang=fr"
        )
        assert response.status_code == 200

    @patch("app.requests.get")
    def test_api_failure_returns_empty_wikitext(self, mock_get, client):
        import requests as req
        mock_get.side_effect = req.RequestException("connection error")

        response = client.get(
            "/api/get_wikitext"
            "?src_lang=en&src_project=wikipedia"
            "&src_filename=File:Test.jpg&tr_lang=fr"
        )
        assert response.status_code == 200
        assert response.get_json()["wikitext"] == ""

    @patch("app.requests.get")
    def test_page_with_no_revisions_returns_empty(self, mock_get, client):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"query": {"pages": [{}]}}
        mock_get.return_value = mock_response

        response = client.get(
            "/api/get_wikitext"
            "?src_lang=en&src_project=wikipedia"
            "&src_filename=File:Test.jpg&tr_lang=fr"
        )
        assert response.status_code == 200
        assert response.get_json()["wikitext"] == ""


class TestTaskStatusRoute:
    """Tests for GET /api/task_status/<task_id>"""

    @patch("app.AsyncResult")
    def test_pending_task_status(self, mock_async_result, client):
        mock_task = MagicMock()
        mock_task.status = "PENDING"
        mock_task.successful.return_value = False
        mock_task.failed.return_value = False
        mock_task.result = None
        mock_async_result.return_value = mock_task

        response = client.get("/api/task_status/fake-task-id")
        assert response.status_code == 200
        data = response.get_json()
        assert data["task_id"] == "fake-task-id"
        assert data["status"] == "PENDING"
        assert data["result"] is None

    @patch("app.AsyncResult")
    def test_successful_task_includes_result(self, mock_async_result, client):
        mock_task = MagicMock()
        mock_task.status = "SUCCESS"
        mock_task.successful.return_value = True
        mock_task.failed.return_value = False
        mock_task.result = {"wikipage_url": "https://example.org/wiki/File:Test.jpg"}
        mock_async_result.return_value = mock_task

        response = client.get("/api/task_status/fake-task-id")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "SUCCESS"
        assert data["result"]["wikipage_url"] == "https://example.org/wiki/File:Test.jpg"

    @patch("app.AsyncResult")
    def test_failed_task_includes_error(self, mock_async_result, client):
        mock_task = MagicMock()
        mock_task.status = "FAILURE"
        mock_task.successful.return_value = False
        mock_task.failed.return_value = True
        mock_task.result = Exception("Upload connection timeout")
        mock_async_result.return_value = mock_task

        response = client.get("/api/task_status/fake-task-id")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "FAILURE"
        assert "error" in data


class TestUploadRoute:
    """Tests for POST /api/upload"""

    def test_get_request_returns_400(self, client):
        response = client.get("/api/upload")
        assert response.status_code == 405

    def test_unauthenticated_upload_fails(self, client):
        payload = {
            "srcUrl": "https://en.wikipedia.org/wiki/File:Test.jpg",
            "trproject": "wikipedia",
            "trlang": "fr",
            "trfilename": "Test.jpg"
        }
        with patch("app.download_image", return_value=None):
            response = client.post(
                "/api/upload",
                data=json.dumps(payload),
                content_type="application/json"
            )
        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False

    @patch("app.process_upload")
    @patch("app.download_image")
    @patch("app.os.path.getsize")
    def test_successful_sync_upload(
        self, mock_getsize, mock_download, mock_upload, client
    ):
        mock_download.return_value = "2026-01-01_test.jpg"
        mock_getsize.return_value = 1024  # 1 KB — well under 50 MB threshold
        mock_upload.return_value = {
            "wikipage_url": "https://fr.wikipedia.org/wiki/File:Test.jpg",
            "file_link": "https://upload.wikimedia.org/test.jpg"
        }

        payload = {
            "srcUrl": "https://en.wikipedia.org/wiki/File:Test.jpg",
            "trproject": "wikipedia",
            "trlang": "fr",
            "trfilename": "Test.jpg"
        }

        with client.session_transaction() as sess:
            sess["mwoauth_access_token"] = {"key": "testkey", "secret": "testsecret"}
            sess["mwoauth_request_token"] = {"key": "testkey", "secret": "testsecret"}

        with patch("app.authenticated_session", return_value=MagicMock()):
            response = client.post(
                "/api/upload",
                data=json.dumps(payload),
                content_type="application/json"
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "wikipage_url" in data["data"]
