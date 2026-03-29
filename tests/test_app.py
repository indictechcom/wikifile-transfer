
import json
import pytest
from unittest.mock import patch, MagicMock
import requests as req_lib

from globalExceptions import (
    APIRequestError,
    CSRFTokenError,
    FileNotFoundOnWikiError,
    ImageDownloadError,
    UploadError,
    WikitextProcessingError,
)


# ── Shared helpers ────────────────────────────────────────────────────────────

def _json(resp):
    return json.loads(resp.data)


def _post(client, url, payload):
    return client.post(url, json=payload, content_type="application/json")


def _mock_http_error(status_code=500):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    return req_lib.HTTPError(response=mock_resp)


# ── /api/upload ───────────────────────────────────────────────────────────────

class TestUploadRoute:

    def test_no_json_body_returns_400(self, client):
        resp = client.post("/api/upload", data="not json",
                           content_type="text/plain")
        assert resp.status_code == 400
        assert _json(resp)["success"] is False
        assert _json(resp)["error_type"] == "InvalidRequest"

    def test_unparseable_url_returns_400(self, authed_client):
        resp = _post(authed_client, "/api/upload", {
            "srcUrl": "not-a-wiki-url",
            "trproject": "wikipedia",
            "trlang": "fr",
            "trfilename": "Chat.jpg",
        })
        assert resp.status_code == 400
        assert _json(resp)["error_type"] == "InvalidRequest"

    def test_missing_target_fields_returns_400(self, authed_client):
        with patch("app.download_image", return_value="cat.jpg"):
            resp = _post(authed_client, "/api/upload", {
                "srcUrl": "https://en.wikipedia.org/wiki/File:Cat.jpg",
                # missing trproject, trlang, trfilename
            })
        assert resp.status_code == 400
        assert _json(resp)["error_type"] == "InvalidRequest"

    def test_unauthenticated_returns_401(self, client):
        with patch("app.download_image", return_value="cat.jpg"):
            resp = _post(client, "/api/upload", {
                "srcUrl": "https://en.wikipedia.org/wiki/File:Cat.jpg",
                "trproject": "wikipedia",
                "trlang": "fr",
                "trfilename": "Chat.jpg",
            })
        assert resp.status_code == 401
        assert _json(resp)["error_type"] == "AuthenticationError"
        

    def test_file_not_found_on_wiki_returns_404(self, authed_client):
        with patch("app.download_image",
                   side_effect=FileNotFoundOnWikiError("File:Cat.jpg")):
            resp = _post(authed_client, "/api/upload", {
                "srcUrl": "https://en.wikipedia.org/wiki/File:Cat.jpg",
                "trproject": "wikipedia",
                "trlang": "fr",
                "trfilename": "Chat.jpg",
            })
        assert resp.status_code == 404
        assert _json(resp)["error_type"] == "FileNotFoundOnWikiError"

    def test_image_download_error_returns_502(self, authed_client):
        with patch("app.download_image",
                   side_effect=ImageDownloadError("File:Cat.jpg", "HTTP 503")):
            resp = _post(authed_client, "/api/upload", {
                "srcUrl": "https://en.wikipedia.org/wiki/File:Cat.jpg",
                "trproject": "wikipedia",
                "trlang": "fr",
                "trfilename": "Chat.jpg",
            })
        assert resp.status_code == 502
        assert _json(resp)["error_type"] == "ImageDownloadError"

    def test_api_request_error_returns_502(self, authed_client):
        with patch("app.download_image",
                   side_effect=APIRequestError("https://en.wikipedia.org", "timeout")):
            resp = _post(authed_client, "/api/upload", {
                "srcUrl": "https://en.wikipedia.org/wiki/File:Cat.jpg",
                "trproject": "wikipedia",
                "trlang": "fr",
                "trfilename": "Chat.jpg",
            })
        assert resp.status_code == 502
        assert _json(resp)["error_type"] == "APIRequestError"

    def test_csrf_error_during_sync_upload_returns_502(self, authed_client, tmp_path):
        fake_file = tmp_path / "cat.jpg"
        fake_file.write_bytes(b"JPEG")

        with patch("app.download_image", return_value="cat.jpg"), \
             patch("app.os.path.join", return_value=str(fake_file)), \
             patch("app.os.path.getsize", return_value=1024), \
             patch("app.process_upload",
                   side_effect=CSRFTokenError("token failed")):
            resp = _post(authed_client, "/api/upload", {
                "srcUrl": "https://en.wikipedia.org/wiki/File:Cat.jpg",
                "trproject": "wikipedia",
                "trlang": "fr",
                "trfilename": "Chat.jpg",
            })
        assert resp.status_code == 502
        assert _json(resp)["error_type"] == "CSRFTokenError"

    def test_upload_error_during_sync_upload_returns_502(self, authed_client, tmp_path):
        fake_file = tmp_path / "cat.jpg"
        fake_file.write_bytes(b"JPEG")

        with patch("app.download_image", return_value="cat.jpg"), \
             patch("app.os.path.join", return_value=str(fake_file)), \
             patch("app.os.path.getsize", return_value=1024), \
             patch("app.process_upload",
                   side_effect=UploadError("Cat.jpg", "rejected")):
            resp = _post(authed_client, "/api/upload", {
                "srcUrl": "https://en.wikipedia.org/wiki/File:Cat.jpg",
                "trproject": "wikipedia",
                "trlang": "fr",
                "trfilename": "Chat.jpg",
            })
        assert resp.status_code == 502
        assert _json(resp)["error_type"] == "UploadError"

    def test_sync_upload_success_returns_200(self, authed_client, tmp_path):
        fake_file = tmp_path / "cat.jpg"
        fake_file.write_bytes(b"JPEG")

        with patch("app.download_image", return_value="cat.jpg"), \
             patch("app.os.path.join", return_value=str(fake_file)), \
             patch("app.os.path.getsize", return_value=1024), \
             patch("app.process_upload", return_value={
                 "wikipage_url": "https://commons.wikimedia.org/wiki/File:Cat.jpg",
                 "file_link":    "https://upload.wikimedia.org/Cat.jpg",
             }):
            resp = _post(authed_client, "/api/upload", {
                "srcUrl": "https://en.wikipedia.org/wiki/File:Cat.jpg",
                "trproject": "wikipedia",
                "trlang": "fr",
                "trfilename": "Chat.jpg",
            })
        assert resp.status_code == 200
        data = _json(resp)
        assert data["success"] is True
        assert "wikipage_url" in data["data"]
        assert data["data"]["source"] == "https://en.wikipedia.org/wiki/File:Cat.jpg"

    def test_async_upload_queued_returns_202(self, authed_client, tmp_path):
        fake_file = tmp_path / "cat.jpg"
        fake_file.write_bytes(b"JPEG" * 1_000_000)  # > 50 MB

        mock_task = MagicMock()
        mock_task.id = "task-abc-123"

        with patch("app.download_image", return_value="cat.jpg"), \
             patch("app.os.path.join", return_value=str(fake_file)), \
             patch("app.os.path.getsize", return_value=60 * 1024 * 1024), \
             patch("app.upload_image_task") as mock_upload:
            mock_upload.delay.return_value = mock_task
            resp = _post(authed_client, "/api/upload", {
                "srcUrl": "https://en.wikipedia.org/wiki/File:Cat.jpg",
                "trproject": "wikipedia",
                "trlang": "fr",
                "trfilename": "Chat.jpg",
            })
        assert resp.status_code == 202
        assert _json(resp)["data"]["task_id"] == "task-abc-123"

    def test_response_always_has_success_key(self, client):
        resp = client.post("/api/upload")
        assert "success" in _json(resp)


# ── /api/preference ───────────────────────────────────────────────────────────

class TestPreferenceRoute:

    def test_get_returns_defaults_when_no_user(self, client):
        with patch("app.db_user", return_value=None):
            resp = client.get("/api/preference")
        assert resp.status_code == 200
        data = _json(resp)["data"]
        assert data["project"] == "wikipedia"
        assert data["lang"] == "en"
        assert data["skip_upload_selection"] is False

    def test_get_returns_user_values_when_user_exists(self, client):
        mock_user = MagicMock()
        mock_user.pref_project = "wiktionary"
        mock_user.pref_language = "de"
        mock_user.skip_upload_selection = True

        with patch("app.db_user", return_value=mock_user):
            resp = client.get("/api/preference")
        data = _json(resp)["data"]
        assert data["project"] == "wiktionary"
        assert data["lang"] == "de"
        assert data["skip_upload_selection"] is True

    def test_post_no_json_returns_400(self, client):
        resp = client.post("/api/preference", data="bad",
                           content_type="text/plain")
        assert resp.status_code == 400
        assert _json(resp)["error_type"] == "InvalidRequest"

    def test_post_saves_and_returns_200(self, client):
        mock_user = MagicMock()

        with patch("app.MW_OAUTH") as mock_oauth, \
             patch("app.User") as mock_user_model, \
             patch("app.db") as mock_db:
            mock_oauth.get_current_user.return_value = "TestUser"
            mock_user_model.query.filter_by.return_value.first.return_value = mock_user
            mock_db.session.commit = MagicMock()

            resp = _post(client, "/api/preference", {
                "project": "commons",
                "lang": "en",
                "skip_upload_selection": False,
            })
        assert resp.status_code == 200
        assert _json(resp)["success"] is True

    def test_post_db_error_returns_500(self, client):
        with patch("app.MW_OAUTH") as mock_oauth, \
             patch("app.User") as mock_user_model, \
             patch("app.db") as mock_db:
            mock_oauth.get_current_user.return_value = "TestUser"
            mock_user_model.query.filter_by.return_value.first.return_value = None
            mock_db.session.commit.side_effect = Exception("DB error")

            resp = _post(client, "/api/preference", {
                "project": "commons",
                "lang": "en",
                "skip_upload_selection": False,
            })
        assert resp.status_code == 500
        assert _json(resp)["error_type"] == "DatabaseError"

    def test_get_response_shape(self, client):
        with patch("app.db_user", return_value=None):
            resp = client.get("/api/preference")
        body = _json(resp)
        assert "success" in body
        assert "data" in body
        assert "error" not in body  # old incorrect key must not appear


# ── /api/user_language ────────────────────────────────────────────────────────

class TestLanguagePreferenceRoute:

    def test_get_returns_default_en(self, client):
        with patch("app.db_user", return_value=None):
            resp = client.get("/api/user_language")
        assert resp.status_code == 200
        assert _json(resp)["data"]["user_language"] == "en"

    def test_get_returns_user_language(self, client):
        mock_user = MagicMock()
        mock_user.user_language = "ar"
        with patch("app.db_user", return_value=mock_user):
            resp = client.get("/api/user_language")
        assert _json(resp)["data"]["user_language"] == "ar"

    def test_post_no_json_returns_400(self, client):
        resp = client.post("/api/user_language", data="bad",
                           content_type="text/plain")
        assert resp.status_code == 400

    def test_post_missing_user_language_field_returns_400(self, client):
        resp = _post(client, "/api/user_language", {})
        assert resp.status_code == 400
        assert _json(resp)["error_type"] == "InvalidRequest"

    def test_post_saves_and_returns_200(self, client):
        with patch("app.MW_OAUTH") as mock_oauth, \
             patch("app.User") as mock_user_model, \
             patch("app.db") as mock_db:
            mock_oauth.get_current_user.return_value = "TestUser"
            mock_user_model.query.filter_by.return_value.first.return_value = None
            mock_db.session.commit = MagicMock()

            resp = _post(client, "/api/user_language", {"user_language": "fr"})
        assert resp.status_code == 200
        assert _json(resp)["success"] is True

    def test_post_db_error_returns_500(self, client):
        with patch("app.MW_OAUTH") as mock_oauth, \
             patch("app.User") as mock_user_model, \
             patch("app.db") as mock_db:
            mock_oauth.get_current_user.return_value = "TestUser"
            mock_user_model.query.filter_by.return_value.first.return_value = None
            mock_db.session.commit.side_effect = Exception("DB error")

            resp = _post(client, "/api/user_language", {"user_language": "fr"})
        assert resp.status_code == 500
        assert _json(resp)["error_type"] == "DatabaseError"


# ── /api/get_wikitext ─────────────────────────────────────────────────────────

class TestGetWikitextRoute:

    _PARAMS = {
        "src_lang": "en",
        "src_project": "wikipedia",
        "src_filename": "File:Cat.jpg",
        "tr_lang": "fr",
    }

    def test_missing_params_returns_empty_wikitext(self, client):
        resp = client.get("/api/get_wikitext")
        assert resp.status_code == 200
        assert _json(resp)["data"]["wikitext"] == ""

    def test_partial_params_returns_empty_wikitext(self, client):
        resp = client.get("/api/get_wikitext?src_lang=en")
        assert resp.status_code == 200
        assert _json(resp)["data"]["wikitext"] == ""

    def test_http_error_returns_200(self, client):
        with patch("app.requests.get",
                   side_effect=req_lib.HTTPError(
                       response=MagicMock(status_code=503))):
            resp = client.get("/api/get_wikitext", query_string=self._PARAMS)
        assert resp.status_code == 200

    def test_network_error_returns_200(self, client):
        with patch("app.requests.get",
                   side_effect=req_lib.ConnectionError("refused")):
            resp = client.get("/api/get_wikitext", query_string=self._PARAMS)
        assert resp.status_code == 200

    def test_no_revisions_returns_empty_wikitext(self, client):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"query": {"pages": [{"title": "File:Cat.jpg"}]}}

        with patch("app.requests.get", return_value=mock_resp):
            resp = client.get("/api/get_wikitext", query_string=self._PARAMS)
        assert resp.status_code == 200
        assert _json(resp)["data"]["wikitext"] == ""

    def test_happy_path_returns_wikitext(self, client):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "query": {
                "pages": [{
                    "revisions": [{
                        "slots": {"main": {"content": "{{Photograph|Article=Cat}}"}}
                    }]
                }]
            }
        }
        with patch("app.requests.get", return_value=mock_resp), \
             patch("app.get_localized_wikitext", return_value="{{Photograph|Article=Chat}}"):
            resp = client.get("/api/get_wikitext", query_string=self._PARAMS)
        assert resp.status_code == 200
        assert _json(resp)["data"]["wikitext"] == "{{Photograph|Article=Chat}}"

    def test_wikitext_processing_error_returns_500(self, client):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "query": {
                "pages": [{
                    "revisions": [{
                        "slots": {"main": {"content": "{{bad}}"}}
                    }]
                }]
            }
        }
        with patch("app.requests.get", return_value=mock_resp), \
             patch("app.get_localized_wikitext",
                   side_effect=WikitextProcessingError("File:Cat.jpg", "parse error")):
            resp = client.get("/api/get_wikitext", query_string=self._PARAMS)
        assert resp.status_code == 200


# /api/edit_page

class TestEditPageRoute:

    _PAYLOAD = {
        "targetUrl": "https://en.wikipedia.org/wiki/File:Cat.jpg",
        "content": "== New section ==\nSome text",
    }

    def test_no_json_returns_400(self, client):
        resp = client.post("/api/edit_page", data="bad",
                           content_type="text/plain")
        assert resp.status_code == 400
        assert _json(resp)["error_type"] == "InvalidRequest"

    def test_missing_fields_returns_400(self, client):
        resp = _post(client, "/api/edit_page", {"targetUrl": "https://en.wikipedia.org/wiki/File:Cat.jpg"})
        assert resp.status_code == 400

    def test_unparseable_target_url_returns_400(self, authed_client):
        resp = _post(authed_client, "/api/edit_page", {
            "targetUrl": "not-a-wiki-url",
            "content": "text",
        })
        assert resp.status_code == 400
        assert _json(resp)["error_type"] == "InvalidRequest"

    def test_unauthenticated_returns_401(self, client):
        resp = _post(client, "/api/edit_page", self._PAYLOAD)
        assert resp.status_code == 401
        assert _json(resp)["error_type"] == "AuthenticationError"

    def test_csrf_http_error_returns_502(self, authed_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        with patch("app.requests.get",
                   side_effect=req_lib.HTTPError(response=mock_resp)):
            resp = _post(authed_client, "/api/edit_page", self._PAYLOAD)
        assert resp.status_code == 502
        assert _json(resp)["error_type"] == "CSRFTokenError"

    def test_csrf_network_error_returns_502(self, authed_client):
        with patch("app.requests.get",
                   side_effect=req_lib.ConnectionError("refused")):
            resp = _post(authed_client, "/api/edit_page", self._PAYLOAD)
        assert resp.status_code == 502
        assert _json(resp)["error_type"] == "CSRFTokenError"

    def test_edit_http_error_returns_502(self, authed_client):
        csrf_mock = MagicMock()
        csrf_mock.raise_for_status = MagicMock()
        csrf_mock.json.return_value = {"query": {"tokens": {"csrftoken": "tok"}}}

        edit_mock = MagicMock()
        edit_mock.status_code = 500
        edit_mock.raise_for_status.side_effect = req_lib.HTTPError(response=edit_mock)

        with patch("app.requests.get", return_value=csrf_mock), \
             patch("app.requests.post", return_value=edit_mock):
            resp = _post(authed_client, "/api/edit_page", self._PAYLOAD)
        assert resp.status_code == 502
        assert _json(resp)["error_type"] == "APIRequestError"

    def test_edit_network_error_returns_502(self, authed_client):
        csrf_mock = MagicMock()
        csrf_mock.raise_for_status = MagicMock()
        csrf_mock.json.return_value = {"query": {"tokens": {"csrftoken": "tok"}}}

        with patch("app.requests.get", return_value=csrf_mock), \
             patch("app.requests.post",
                   side_effect=req_lib.ConnectionError("refused")):
            resp = _post(authed_client, "/api/edit_page", self._PAYLOAD)
        assert resp.status_code == 502
        assert _json(resp)["error_type"] == "APIRequestError"

    def test_happy_path_returns_200(self, authed_client):
        csrf_mock = MagicMock()
        csrf_mock.raise_for_status = MagicMock()
        csrf_mock.json.return_value = {"query": {"tokens": {"csrftoken": "tok"}}}

        edit_mock = MagicMock()
        edit_mock.raise_for_status = MagicMock()

        with patch("app.requests.get", return_value=csrf_mock), \
             patch("app.requests.post", return_value=edit_mock):
            resp = _post(authed_client, "/api/edit_page", self._PAYLOAD)
        assert resp.status_code == 200
        assert _json(resp)["success"] is True


# ── /api/user ─────────────────────────────────────────────────────────────────

class TestUserRoute:

    def test_returns_logged_false_when_not_logged_in(self, client):
        with patch("app.MW_OAUTH") as mock_oauth:
            mock_oauth.get_current_user.return_value = None
            resp = client.get("/api/user")
        assert resp.status_code == 200
        assert _json(resp)["data"]["logged"] is False

    def test_returns_logged_true_when_logged_in(self, client):
        with patch("app.MW_OAUTH") as mock_oauth:
            mock_oauth.get_current_user.return_value = "TestUser"
            resp = client.get("/api/user")
        assert _json(resp)["data"]["logged"] is True
        assert _json(resp)["data"]["username"] == "TestUser"

    def test_response_uses_standard_envelope(self, client):
        with patch("app.MW_OAUTH") as mock_oauth:
            mock_oauth.get_current_user.return_value = None
            resp = client.get("/api/user")
        body = _json(resp)
        assert "success" in body
        assert "data" in body


# ── /api/task_status ──────────────────────────────────────────────────────────

class TestTaskStatusRoute:

    def test_pending_task_returns_status(self, client):
        mock_task = MagicMock()
        mock_task.status = "PENDING"
        mock_task.successful.return_value = False
        mock_task.failed.return_value = False

        with patch("app.AsyncResult", return_value=mock_task):
            resp = client.get("/api/task_status/fake-task-id")
        assert resp.status_code == 200
        assert _json(resp)["data"]["status"] == "PENDING"

    def test_successful_task_includes_result_data(self, client):
        mock_task = MagicMock()
        mock_task.status = "SUCCESS"
        mock_task.successful.return_value = True
        mock_task.failed.return_value = False
        mock_task.result = {
            "success": True,
            "wikipage_url": "https://commons.wikimedia.org/wiki/File:Cat.jpg",
            "file_link":    "https://upload.wikimedia.org/Cat.jpg",
        }

        with patch("app.AsyncResult", return_value=mock_task):
            resp = client.get("/api/task_status/fake-task-id")
        body = _json(resp)
        assert body["data"]["success"] is True
        assert "wikipage_url" in body["data"]

    def test_failed_task_includes_error_info(self, client):
        mock_task = MagicMock()
        mock_task.status = "FAILURE"
        mock_task.successful.return_value = False
        mock_task.failed.return_value = True
        mock_task.result = UploadError("Cat.jpg", "wiki rejected")

        with patch("app.AsyncResult", return_value=mock_task):
            resp = client.get("/api/task_status/fake-task-id")
        body = _json(resp)
        assert "error" in body["data"]
        assert body["data"]["error"] == "Upload of 'Cat.jpg' failed: wiki rejected"

    def test_lookup_error_returns_500(self, client):
        with patch("app.AsyncResult", side_effect=Exception("backend down")):
            resp = client.get("/api/task_status/fake-task-id")
        assert resp.status_code == 500
        assert _json(resp)["error_type"] == "TaskLookupError"

    def test_response_uses_standard_envelope(self, client):
        mock_task = MagicMock()
        mock_task.status = "PENDING"
        mock_task.successful.return_value = False
        mock_task.failed.return_value = False

        with patch("app.AsyncResult", return_value=mock_task):
            resp = client.get("/api/task_status/fake-task-id")
        body = _json(resp)
        assert "success" in body
        assert "data" in body


# ── Response shape contract ───────────────────────────────────────────────────

class TestResponseShapeContract:
    """
    Every route must return the standard envelope.
    Success:  {"success": True,  "data": {...}}
    Error:    {"success": False, "error": "...", "error_type": "..."}
    The old keys "errors" (list) and "result" must never appear.
    """

    def test_upload_error_never_uses_errors_list(self, client):
        resp = client.post("/api/upload")
        body = _json(resp)
        assert "errors" not in body

    def test_preference_get_never_uses_error_list(self, client):
        with patch("app.db_user", return_value=None):
            resp = client.get("/api/preference")
        assert "error" not in _json(resp) or isinstance(_json(resp).get("error"), str)
        assert "errors" not in _json(resp)

    def test_task_status_never_uses_result_key_at_top_level(self, client):
        mock_task = MagicMock()
        mock_task.status = "PENDING"
        mock_task.successful.return_value = False
        mock_task.failed.return_value = False
        with patch("app.AsyncResult", return_value=mock_task):
            resp = client.get("/api/task_status/x")
        assert "result" not in _json(resp)

    def test_error_responses_have_error_type(self, client):
        resp = client.post("/api/upload")
        body = _json(resp)
        assert "error_type" in body

    def test_success_responses_have_data_key(self, client):
        with patch("app.db_user", return_value=None):
            resp = client.get("/api/preference")
        assert "data" in _json(resp)
