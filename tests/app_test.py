"""
Tests for Flask routes in app.py

STRATEGY
========
app.py has a module-level side effect that we must neutralize before the first
import: `from flask_mwoauth import MWOAuth` creates an MW_OAUTH object whose
`get_current_user()` method tests need to control.

We stub flask_mwoauth in sys.modules BEFORE importing app so that MW_OAUTH
becomes a MagicMock we can configure per-test. We keep MW_OAUTH.bp as a real
Flask Blueprint so that app.register_blueprint() does not fail.

After import we:
  - Override SQLALCHEMY_DATABASE_URI to SQLite in-memory (no MySQL needed)
  - Set TESTING=True so Flask propagates exceptions through registered handlers
  - Create all tables once per test module with db.create_all()

ROUTES COVERED
==============
  POST /api/upload           — validation, auth check, sync and async paths
  GET  /api/preference       — defaults for unauthenticated users
  POST /api/preference       — validation, auth, DB save + update
  GET  /api/user_language    — defaults for unauthenticated users
  POST /api/user_language    — validation, auth, DB save
  GET  /api/get_wikitext     — missing params, success, timeout
  POST /api/edit_page        — validation, auth, CSRF fetch, edit success
  GET  /api/user             — logged/username fields
  GET  /api/task_status/<id> — PENDING, SUCCESS, FAILURE states

HOW TO RUN
==========
  pytest tests/app_test.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import MagicMock, patch
from contextlib import contextmanager
from flask import Blueprint

# ─── Stub flask_mwoauth BEFORE importing app ──────────────────────────────────
# MW_OAUTH.bp must be a real Blueprint; everything else can be a MagicMock.
_fake_bp = Blueprint("mwoauth", __name__)
_mock_mwoauth_inst = MagicMock()
_mock_mwoauth_inst.bp = _fake_bp
_mock_mwoauth_mod = MagicMock()
_mock_mwoauth_mod.MWOAuth.return_value = _mock_mwoauth_inst
sys.modules.setdefault("flask_mwoauth", _mock_mwoauth_mod)

# ─── Now safe to import the Flask app ────────────────────────────────────────
from app import app as flask_app, MW_OAUTH  # noqa: E402
from model import db                         # noqa: E402


# ─── Shared mock for log_timed_api_call ──────────────────────────────────────
# app.py does:  with log_timed_api_call(logger, endpoint, method) as ctx:
#                   ctx["status_code"] = ...
# Our fake yields a dict so ctx["status_code"] works without a real logger.
@contextmanager
def _mock_timed(logger, endpoint, method):
    yield {}


# ─── Pytest fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """
    Flask test client backed by an in-memory SQLite DB.
    Created once per test module; DB tables are created on entry and dropped on exit.
    """
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"

    with flask_app.app_context():
        db.create_all()
        with flask_app.test_client() as c:
            yield c
        db.drop_all()


# ─── Auth helpers ─────────────────────────────────────────────────────────────

def _set_oauth_session(client):
    """Inject a fake OAuth token into the test client's session."""
    with client.session_transaction() as sess:
        sess["mwoauth_access_token"] = {"key": "fake_key", "secret": "fake_secret"}


def _clear_oauth_session(client):
    """Remove the OAuth token from the test client's session."""
    with client.session_transaction() as sess:
        sess.pop("mwoauth_access_token", None)


# ─── Shared data ──────────────────────────────────────────────────────────────

VALID_WIKI_URL = "https://en.wikipedia.org/wiki/File:Example.jpg"
VALID_UPLOAD_BODY = {
    "srcUrl": VALID_WIKI_URL,
    "trproject": "wikipedia",
    "trlang": "fr",
    "trfilename": "File%3AExample.jpg",
}


# =============================================================================
# POST /api/upload
# =============================================================================

class TestUploadValidation:
    """Input validation happens before any network call is made."""

    def test_no_body_returns_400(self, client):
        resp = client.post("/api/upload", json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["success"] is False
        assert data["error_details"]["code"] == "VALIDATION_ERROR"

    def test_missing_src_url_returns_400(self, client):
        resp = client.post("/api/upload", json={"trproject": "wikipedia"})
        assert resp.status_code == 400
        assert resp.get_json()["error_details"]["code"] == "VALIDATION_ERROR"

    def test_non_wiki_src_url_returns_400(self, client):
        resp = client.post("/api/upload", json={"srcUrl": "https://example.com/notawiki"})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error_details"]["code"] == "VALIDATION_ERROR"

    def test_download_failure_returns_500(self, client):
        # download_image returns None → FileOperationError → 500
        with patch("app.download_image", return_value=None):
            resp = client.post("/api/upload", json={"srcUrl": VALID_WIKI_URL})
        assert resp.status_code == 500
        assert resp.get_json()["success"] is False

    def test_missing_tr_fields_returns_400(self, client):
        # srcUrl valid, download succeeds, but target fields are all absent
        with patch("app.download_image", return_value="file.jpg"):
            resp = client.post("/api/upload", json={"srcUrl": VALID_WIKI_URL})
        assert resp.status_code == 400
        assert resp.get_json()["error_details"]["code"] == "VALIDATION_ERROR"


class TestUploadAuthentication:
    """Unauthenticated requests are rejected before touching the wiki API."""

    def test_no_session_returns_401(self, client):
        _clear_oauth_session(client)
        with patch("app.download_image", return_value="file.jpg"), \
             patch("app.authenticated_session", return_value=None):
            resp = client.post("/api/upload", json=VALID_UPLOAD_BODY)
        assert resp.status_code == 401
        assert resp.get_json()["error_details"]["code"] == "AUTHENTICATION_ERROR"


class TestUploadSuccess:
    """Successful upload — sync path (< 50 MB) and async path (≥ 50 MB)."""

    def test_small_file_returns_200_with_source(self, client):
        _set_oauth_session(client)
        upload_result = {
            "file_link": "https://upload.wikimedia.org/test.jpg",
            "wikipage_url": "https://commons.wikimedia.org/wiki/File:Example.jpg",
        }
        with patch("app.download_image", return_value="file.jpg"), \
             patch("app.authenticated_session", return_value=MagicMock()), \
             patch("app.os.path.getsize", return_value=1024), \
             patch("app.process_upload", return_value=upload_result):
            resp = client.post("/api/upload", json=VALID_UPLOAD_BODY)

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "source" in data["data"]
        assert data["data"]["source"] == VALID_WIKI_URL

    def test_large_file_returns_202_with_task_id(self, client):
        _set_oauth_session(client)
        mock_task = MagicMock()
        mock_task.id = "async-task-id-abc"
        with patch("app.download_image", return_value="file.jpg"), \
             patch("app.authenticated_session", return_value=MagicMock()), \
             patch("app.os.path.getsize", return_value=60 * 1024 * 1024), \
             patch("app.upload_image_task") as mock_upload_task:
            mock_upload_task.delay.return_value = mock_task
            resp = client.post("/api/upload", json=VALID_UPLOAD_BODY)

        assert resp.status_code == 202
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["task_id"] == "async-task-id-abc"


# =============================================================================
# GET /api/preference
# =============================================================================

class TestPreferenceGet:
    """Unauthenticated GET returns default project/language values."""

    def test_unauthenticated_returns_defaults(self, client):
        MW_OAUTH.get_current_user.return_value = None
        resp = client.get("/api/preference")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["project"] == "wikipedia"
        assert data["data"]["lang"] == "en"
        assert data["data"]["skip_upload_selection"] is False


# =============================================================================
# POST /api/preference
# =============================================================================

class TestPreferencePost:
    """Validation, auth enforcement, DB save and update."""

    def test_missing_project_returns_400(self, client):
        resp = client.post("/api/preference", json={"lang": "fr"})
        assert resp.status_code == 400
        assert resp.get_json()["success"] is False

    def test_missing_lang_returns_400(self, client):
        resp = client.post("/api/preference", json={"project": "wikipedia"})
        assert resp.status_code == 400

    def test_empty_body_returns_400(self, client):
        resp = client.post("/api/preference", json={})
        assert resp.status_code == 400

    def test_unauthenticated_returns_401(self, client):
        MW_OAUTH.get_current_user.return_value = None
        resp = client.post("/api/preference", json={"project": "wikipedia", "lang": "fr"})
        assert resp.status_code == 401
        assert resp.get_json()["error_details"]["code"] == "AUTHENTICATION_ERROR"

    def test_authenticated_save_returns_200(self, client):
        MW_OAUTH.get_current_user.return_value = "pref_user1"
        resp = client.post(
            "/api/preference",
            json={"project": "commons", "lang": "de", "skip_upload_selection": True},
        )
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

    def test_second_post_updates_existing_user(self, client):
        # Same user, different preferences — should UPDATE not INSERT a second row
        MW_OAUTH.get_current_user.return_value = "pref_user1"
        resp = client.post(
            "/api/preference",
            json={"project": "wiktionary", "lang": "es", "skip_upload_selection": False},
        )
        assert resp.status_code == 200

    def test_get_reflects_saved_preferences(self, client):
        # Save then read back — values must match what was saved
        MW_OAUTH.get_current_user.return_value = "pref_user2"
        client.post(
            "/api/preference",
            json={"project": "wikibooks", "lang": "it", "skip_upload_selection": False},
        )
        resp = client.get("/api/preference")
        data = resp.get_json()
        assert data["data"]["project"] == "wikibooks"
        assert data["data"]["lang"] == "it"


# =============================================================================
# GET /api/user_language
# =============================================================================

class TestUserLanguageGet:
    """Unauthenticated GET returns 'en' as the default language."""

    def test_unauthenticated_returns_en(self, client):
        MW_OAUTH.get_current_user.return_value = None
        resp = client.get("/api/user_language")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["user_language"] == "en"


# =============================================================================
# POST /api/user_language
# =============================================================================

class TestUserLanguagePost:
    """Validation, auth enforcement, and DB persistence."""

    def test_missing_user_language_returns_400(self, client):
        resp = client.post("/api/user_language", json={})
        assert resp.status_code == 400
        assert resp.get_json()["error_details"]["code"] == "VALIDATION_ERROR"

    def test_unauthenticated_returns_401(self, client):
        MW_OAUTH.get_current_user.return_value = None
        resp = client.post("/api/user_language", json={"user_language": "fr"})
        assert resp.status_code == 401

    def test_authenticated_save_returns_200(self, client):
        MW_OAUTH.get_current_user.return_value = "lang_user1"
        resp = client.post("/api/user_language", json={"user_language": "ja"})
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

    def test_get_reflects_saved_language(self, client):
        MW_OAUTH.get_current_user.return_value = "lang_user1"
        client.post("/api/user_language", json={"user_language": "ko"})
        resp = client.get("/api/user_language")
        data = resp.get_json()
        assert data["data"]["user_language"] == "ko"


# =============================================================================
# GET /api/get_wikitext
# =============================================================================

class TestGetWikitext:
    """Wikitext endpoint — missing params, success, and timeout paths."""

    def test_no_params_returns_empty_wikitext(self, client):
        resp = client.get("/api/get_wikitext")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["wikitext"] == ""

    def test_partial_params_returns_empty_wikitext(self, client):
        resp = client.get("/api/get_wikitext?src_lang=en&src_project=wikipedia")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["wikitext"] == ""

    def test_all_params_returns_localized_wikitext(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "query": {
                "pages": [{
                    "revisions": [{"slots": {"main": {"content": "== raw =="}}}]
                }]
            }
        }
        with patch("app.log_timed_api_call", _mock_timed), \
             patch("app.requests.get", return_value=mock_resp), \
             patch("app.get_localized_wikitext", return_value="== localized =="):
            resp = client.get(
                "/api/get_wikitext"
                "?src_lang=en&src_project=wikipedia"
                "&src_filename=File%3AExample.jpg&tr_lang=fr"
            )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["wikitext"] == "== localized =="

    def test_no_revisions_in_response_returns_empty(self, client):
        # Page exists but has no revision history
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"query": {"pages": [{}]}}
        with patch("app.log_timed_api_call", _mock_timed), \
             patch("app.requests.get", return_value=mock_resp):
            resp = client.get(
                "/api/get_wikitext"
                "?src_lang=en&src_project=wikipedia"
                "&src_filename=File%3AExample.jpg&tr_lang=fr"
            )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["wikitext"] == ""

    def test_api_timeout_returns_502(self, client):
        import requests as req
        with patch("app.log_timed_api_call", _mock_timed), \
             patch("app.requests.get", side_effect=req.exceptions.Timeout()):
            resp = client.get(
                "/api/get_wikitext"
                "?src_lang=en&src_project=wikipedia"
                "&src_filename=File%3AExample.jpg&tr_lang=fr"
            )
        assert resp.status_code == 502

    def test_api_connection_error_returns_502(self, client):
        import requests as req
        with patch("app.log_timed_api_call", _mock_timed), \
             patch("app.requests.get", side_effect=req.exceptions.ConnectionError("refused")):
            resp = client.get(
                "/api/get_wikitext"
                "?src_lang=en&src_project=wikipedia"
                "&src_filename=File%3AExample.jpg&tr_lang=fr"
            )
        assert resp.status_code == 502


# =============================================================================
# POST /api/edit_page
# =============================================================================

class TestEditPageValidation:
    """Input validation and auth check before any network call is made."""

    def test_missing_target_url_returns_400(self, client):
        resp = client.post("/api/edit_page", json={"content": "hello"})
        assert resp.status_code == 400
        assert resp.get_json()["error_details"]["code"] == "VALIDATION_ERROR"

    def test_missing_content_returns_400(self, client):
        resp = client.post("/api/edit_page", json={"targetUrl": VALID_WIKI_URL})
        assert resp.status_code == 400
        assert resp.get_json()["error_details"]["code"] == "VALIDATION_ERROR"

    def test_non_wiki_target_url_returns_400(self, client):
        resp = client.post(
            "/api/edit_page",
            json={"targetUrl": "https://notawiki.com/page", "content": "hello"},
        )
        assert resp.status_code == 400

    def test_unauthenticated_returns_401(self, client):
        with patch("app.authenticated_session", return_value=None):
            resp = client.post(
                "/api/edit_page",
                json={"targetUrl": VALID_WIKI_URL, "content": "hello"},
            )
        assert resp.status_code == 401
        assert resp.get_json()["error_details"]["code"] == "AUTHENTICATION_ERROR"

    def test_csrf_timeout_returns_502(self, client):
        import requests as req
        with patch("app.authenticated_session", return_value=MagicMock()), \
             patch("app.log_timed_api_call", _mock_timed), \
             patch("app.requests.get", side_effect=req.exceptions.Timeout()):
            resp = client.post(
                "/api/edit_page",
                json={"targetUrl": VALID_WIKI_URL, "content": "hello"},
            )
        assert resp.status_code == 502


class TestEditPageSuccess:
    """Successful edit — CSRF token fetched and edit POST accepted."""

    def test_valid_edit_returns_200(self, client):
        csrf_resp = MagicMock()
        csrf_resp.status_code = 200
        csrf_resp.raise_for_status.return_value = None
        csrf_resp.json.return_value = {"query": {"tokens": {"csrftoken": "validtoken"}}}

        post_resp = MagicMock()
        post_resp.status_code = 200
        post_resp.raise_for_status.return_value = None

        with patch("app.authenticated_session", return_value=MagicMock()), \
             patch("app.log_timed_api_call", _mock_timed), \
             patch("app.requests.get", return_value=csrf_resp), \
             patch("app.requests.post", return_value=post_resp):
            resp = client.post(
                "/api/edit_page",
                json={"targetUrl": VALID_WIKI_URL, "content": "hello"},
            )

        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

    def test_anon_csrf_token_returns_401(self, client):
        # MW returns "+\" when OAuth session is not recognized — treat as auth failure
        csrf_resp = MagicMock()
        csrf_resp.status_code = 200
        csrf_resp.raise_for_status.return_value = None
        csrf_resp.json.return_value = {"query": {"tokens": {"csrftoken": "+\\"}}}

        with patch("app.authenticated_session", return_value=MagicMock()), \
             patch("app.log_timed_api_call", _mock_timed), \
             patch("app.requests.get", return_value=csrf_resp):
            resp = client.post(
                "/api/edit_page",
                json={"targetUrl": VALID_WIKI_URL, "content": "hello"},
            )

        assert resp.status_code == 401


# =============================================================================
# GET /api/user
# =============================================================================

class TestUserEndpoint:
    """GET /api/user returns `logged` boolean and `username`."""

    def test_logged_out_returns_false_and_none(self, client):
        MW_OAUTH.get_current_user.return_value = None
        resp = client.get("/api/user")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["logged"] is False
        assert data["data"]["username"] is None

    def test_logged_in_returns_true_and_username(self, client):
        MW_OAUTH.get_current_user.return_value = "WikiUser123"
        resp = client.get("/api/user")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["logged"] is True
        assert data["data"]["username"] == "WikiUser123"


# =============================================================================
# GET /api/task_status/<task_id>
# =============================================================================

class TestTaskStatus:
    """GET /api/task_status/<id> reflects the Celery task state."""

    def test_pending_task_returns_correct_fields(self, client):
        mock_result = MagicMock()
        mock_result.status = "PENDING"
        mock_result.successful.return_value = False
        mock_result.failed.return_value = False
        mock_result.result = None

        with patch("app.AsyncResult", return_value=mock_result):
            resp = client.get("/api/task_status/pending-task-id")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["task_id"] == "pending-task-id"
        assert data["data"]["status"] == "PENDING"
        assert data["data"]["result"] is None

    def test_successful_task_includes_result(self, client):
        mock_result = MagicMock()
        mock_result.status = "SUCCESS"
        mock_result.successful.return_value = True
        mock_result.failed.return_value = False
        mock_result.result = {
            "file_link": "https://upload.wikimedia.org/test.jpg",
            "wikipage_url": "https://commons.wikimedia.org/wiki/File:Test.jpg",
        }

        with patch("app.AsyncResult", return_value=mock_result):
            resp = client.get("/api/task_status/success-task-id")

        data = resp.get_json()
        assert data["data"]["status"] == "SUCCESS"
        assert data["data"]["result"]["file_link"] == "https://upload.wikimedia.org/test.jpg"

    def test_failed_task_includes_error_field(self, client):
        mock_result = MagicMock()
        mock_result.status = "FAILURE"
        mock_result.successful.return_value = False
        mock_result.failed.return_value = True
        mock_result.result = Exception("upload failed")

        with patch("app.AsyncResult", return_value=mock_result):
            resp = client.get("/api/task_status/failed-task-id")

        data = resp.get_json()
        assert data["data"]["status"] == "FAILURE"
        assert "error" in data["data"]
        assert "upload failed" in data["data"]["error"]
