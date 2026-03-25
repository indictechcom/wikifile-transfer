#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
app.py – Flask application entry point for Wikifile-Transfer.

Responsibilities
----------------
* Bootstrap the Flask app, database, OAuth blueprint, and Celery connection.
* Configure structured, rotating file-based logging (see ``configure_logging``).
* Register centralised error handlers (see ``error_handlers.py``).
* Define all HTTP API endpoints with consistent request validation and error
  reporting using the custom exception hierarchy in ``exceptions.py``.
"""

import logging
import os
import re
import urllib.parse

import requests
import requests_oauthlib
import yaml
from celery.result import AsyncResult
from flask import Flask, jsonify, render_template, request, session
from flask_cors import CORS
from flask_migrate import Migrate
from flask_mwoauth import MWOAuth

from logging_config import configure_logging
from celeryWorker import app as celery_app
from error_handlers import register_error_handlers
from exceptions import (
    AuthenticationError,
    DatabaseError,
    DownloadError,
    ExternalAPIError,
    ValidationError,
)
from model import db, User
from tasks import upload_image_task
from utils import cleanup_temp_file, download_image, get_localized_wikitext, getHeader, process_upload

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

app = Flask(__name__)

# Load configuration from YAML file.
__dir__ = os.path.dirname(__file__)
app.config.update(yaml.safe_load(open(os.path.join(__dir__, "config.yaml"))))

# Get variables
ENV = app.config["ENV"]
BASE_URL = app.config["OAUTH_MWURI"]
API_ENDPOINT = BASE_URL + "/api.php"
CONSUMER_KEY = app.config["CONSUMER_KEY"]
CONSUMER_SECRET = app.config["CONSUMER_SECRET"]

# Enable CORS and debug mode in dev environment.
if ENV == "dev":
    CORS(app, supports_credentials=True)
    app.config["DEBUG"] = True

# Initialise structured logging now that DEBUG flag is known.
configure_logging(app)

# Create Database and Migration objects.
db.init_app(app)
migrate = Migrate(app, db)

# Register the MediaWiki OAuth blueprint.
MW_OAUTH = MWOAuth(
    base_url=BASE_URL,
    consumer_key=CONSUMER_KEY,
    consumer_secret=CONSUMER_SECRET,
    user_agent=getHeader()["User-Agent"],
)
app.register_blueprint(MW_OAUTH.bp)

# Register centralised error handlers (see error_handlers.py).
register_error_handlers(app)

logger.info("Wikifile-Transfer application initialised (ENV=%s)", ENV)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/index", methods=["GET"])
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/upload", methods=["POST"])
def upload():
    """
    Trigger a file transfer from a source wiki to a target wiki.

    For files under 50 MB the upload is handled synchronously.
    Larger files are handed off to a Celery worker and a ``task_id`` is
    returned so the client can poll ``/api/task_status/<task_id>``.
    """
    # --- Parse and validate request body ------------------------------------
    data = request.get_json()
    if not data:
        raise ValidationError("Request body must be JSON.")

    src_url = data.get("srcUrl")
    if not src_url:
        raise ValidationError("Missing required field: 'srcUrl'.")
    src_url = urllib.parse.unquote(src_url)

    match = re.findall(r"(\w+)\.(\w+)\.org/wiki/", src_url)
    if not match:
        raise ValidationError(
            "Could not parse source wiki from 'srcUrl'. "
            "Expected format: https://<lang>.<project>.org/wiki/…"
        )

    src_lang = match[0][0]
    src_project = match[0][1]
    src_filename = src_url.split("/")[-1]
    src_fileext = src_filename.split(".")[-1]

    tr_project = data.get("trproject")
    tr_lang = data.get("trlang")
    tr_filename = data.get("trfilename")

    if not all([tr_project, tr_lang, tr_filename]):
        raise ValidationError(
            "Missing one or more required fields: 'trproject', 'trlang', 'trfilename'."
        )

    tr_filename = urllib.parse.unquote(tr_filename)
    tr_endpoint = f"https://{tr_lang}.{tr_project}.org/w/api.php"

    # --- Authentication check -----------------------------------------------
    ses = _authenticated_session()
    if ses is None:
        raise AuthenticationError()

    # --- Download source file -----------------------------------------------
    logger.info(
        "Downloading source file '%s' from %s.%s", src_filename, src_lang, src_project
    )
    try:
        downloaded_filename = download_image(src_project, src_lang, src_filename)
    except DownloadError as e:
        # Translate the internal DownloadError into an HTTP 502 for the client.
        raise ExternalAPIError(str(e)) from e

    # --- Upload to target wiki ----------------------------------------------
    file_path = "temp_images/" + downloaded_filename
    file_size = os.path.getsize(file_path)

    if file_size < 50 * 1024 * 1024:  # 50 MB – process synchronously
        logger.info(
            "Uploading '%s' synchronously to %s.%s", tr_filename, tr_lang, tr_project
        )
        try:
            resp = process_upload(file_path, tr_filename, src_fileext, tr_endpoint, ses)
        finally:
            # Always delete the temp file, whether the upload succeeded or raised.
            cleanup_temp_file(file_path)
        resp["source"] = src_url
        logger.info("Synchronous upload succeeded: %s", resp.get("wikipage_url"))
        return jsonify({"success": True, "data": resp, "errors": []}), 200

    else:
        # Large file – dispatch to Celery worker. The task is responsible for
        # deleting the temp file once it finishes (success or failure).
        logger.info(
            "File exceeds 50 MB (%d bytes); dispatching async task for '%s'",
            file_size,
            tr_filename,
        )
        oauth_obj = {
            "consumer_key":    CONSUMER_KEY,
            "consumer_secret": CONSUMER_SECRET,
            "key":    session["mwoauth_access_token"]["key"],
            "secret": session["mwoauth_access_token"]["secret"],
        }
        task = upload_image_task.delay(
            file_path, tr_filename, src_fileext, tr_endpoint, oauth_obj
        )
        logger.info("Async upload task queued with id=%s", task.id)
        return jsonify({"success": True, "data": {"task_id": task.id}, "errors": []}), 202


@app.route("/api/preference", methods=["GET", "POST"])
def preference():
    """Get or update the authenticated user's upload preferences."""

    if request.method == "GET":
        user = _db_user()

        # Fall back to sensible defaults for unauthenticated / new users.
        project = user.pref_project if user else "wikipedia"
        lang    = user.pref_language if user else "en"
        skip    = user.skip_upload_selection if user else False

        return jsonify({
            "success": True,
            "data": {
                "project":              project,
                "lang":                 lang,
                "skip_upload_selection": skip,
            },
            "errors": [],
        }), 200

    elif request.method == "POST":
        data = request.get_json()
        if not data:
            raise ValidationError("Request body must be JSON.")

        project  = data.get("project")
        lang     = data.get("lang")
        skip     = data.get("skip_upload_selection")

        cur_username = MW_OAUTH.get_current_user(True)
        user = User.query.filter_by(username=cur_username).first()

        if user is None:
            user = User(
                username=cur_username,
                pref_language=lang,
                pref_project=project,
                skip_upload_selection=skip,
            )
            db.session.add(user)
        else:
            user.pref_language        = lang
            user.pref_project         = project
            user.skip_upload_selection = skip

        try:
            db.session.commit()
            logger.info("Preferences updated for user '%s'", cur_username)
            return jsonify({"success": True, "data": {}, "errors": []}), 200
        except Exception as e:
            db.session.rollback()
            raise DatabaseError(
                f"Failed to save preferences for '{cur_username}'."
            ) from e

    else:
        raise ValidationError("Method not allowed.")


@app.route("/api/user_language", methods=["GET", "POST"])
def language_preference():
    """Get or update the authenticated user's UI language preference."""

    if request.method == "GET":
        user = _db_user()
        user_language = user.user_language if user else "en"

        return jsonify({
            "success": True,
            "data":   {"user_language": user_language},
            "errors": [],
        }), 200

    elif request.method == "POST":
        data = request.get_json()
        if not data:
            raise ValidationError("Request body must be JSON.")

        user_language = data.get("user_language")
        if not user_language:
            raise ValidationError("Missing required field: 'user_language'.")

        cur_username = MW_OAUTH.get_current_user(True)
        user = User.query.filter_by(username=cur_username).first()

        if user is None:
            user = User(username=cur_username, user_language=user_language)
            db.session.add(user)
        else:
            user.user_language = user_language

        try:
            db.session.commit()
            logger.info("UI language updated to '%s' for user '%s'", user_language, cur_username)
            return jsonify({"success": True, "data": {}, "errors": []}), 200
        except Exception as e:
            db.session.rollback()
            raise DatabaseError(
                f"Failed to save language preference for '{cur_username}'."
            ) from e

    else:
        raise ValidationError("Method not allowed.")


@app.route("/api/get_wikitext", methods=["GET"])
def get_wikitext():
    """
    Fetch and optionally localise the wikitext for a source file.

    Returns ``{"wikitext": ""}`` on any failure – this endpoint is best-effort
    and should not block the upload flow.
    """
    src_lang     = request.args.get("src_lang")
    src_project  = request.args.get("src_project")
    src_filename = request.args.get("src_filename")
    tr_lang      = request.args.get("tr_lang")

    if not all([src_lang, src_project, src_filename, tr_lang]):
        # Missing params – silently return empty string so the UI degrades gracefully.
        return jsonify({"wikitext": ""}), 200

    src_endpoint = f"https://{src_lang}.{src_project}.org/w/api.php"
    content_params = {
        "action":        "query",
        "format":        "json",
        "prop":          "revisions",
        "titles":        src_filename,
        "formatversion": "2",
        "rvprop":        "content",
        "rvslots":       "main",
        "origin":        "*",
    }

    try:
        response = requests.get(src_endpoint, params=content_params)
        response.raise_for_status()

        page_data = response.json().get("query", {}).get("pages", [])

        if page_data and page_data[0].get("revisions"):
            wikitext = page_data[0]["revisions"][0]["slots"]["main"]["content"]
            wikitext = get_localized_wikitext(wikitext, src_endpoint, tr_lang)
            return jsonify({"wikitext": wikitext}), 200

        return jsonify({"wikitext": ""}), 200

    except Exception as e:
        # Log the real error for debugging but return a safe empty response so
        # the upload flow is not blocked by a wikitext-fetch failure.
        logger.warning(
            "Failed to fetch wikitext for '%s' from %s.%s: %s",
            src_filename, src_lang, src_project, e,
        )
        return jsonify({"wikitext": ""}), 200


@app.route("/api/edit_page", methods=["POST"])
def edit_page():
    """Append wikitext content to a file description page on a target wiki."""

    data = request.get_json()
    if not data:
        raise ValidationError("Request body must be JSON.")

    target_url = data.get("targetUrl")
    content    = data.get("content")

    if not target_url or content is None:
        raise ValidationError("Missing required fields: 'targetUrl' and 'content'.")

    match = re.findall(r"(\w+)\.(\w+)\.org/wiki/", target_url)
    if not match:
        raise ValidationError(
            "Could not parse target wiki from 'targetUrl'. "
            "Expected format: https://<lang>.<project>.org/wiki/…"
        )

    target_lang    = match[0][0]
    target_project = match[0][1]
    target_filename = target_url.split("/")[-1]
    target_endpoint = f"https://{target_lang}.{target_project}.org/w/api.php"

    ses = _authenticated_session()
    if ses is None:
        raise AuthenticationError()

    # Fetch a CSRF token from the target wiki.
    try:
        csrf_response = requests.get(
            url=target_endpoint,
            params={"action": "query", "meta": "tokens", "format": "json"},
            auth=ses,
        )
        csrf_response.raise_for_status()
        csrf_token = csrf_response.json()["query"]["tokens"]["csrftoken"]
    except (KeyError, Exception) as e:
        logger.error("Failed to obtain CSRF token from '%s': %s", target_endpoint, e)
        raise ExternalAPIError("Could not obtain CSRF token from target wiki.")

    # Submit the edit.
    edit_params = {
        "action":     "edit",
        "title":      "File:" + target_filename.split(":")[-1],
        "token":      csrf_token,
        "format":     "json",
        "appendtext": content,
    }

    try:
        edit_response = requests.post(
            url=target_endpoint, data=edit_params, auth=ses
        )
        edit_response.raise_for_status()
    except Exception as e:
        logger.error("Page edit request failed for '%s': %s", target_filename, e)
        raise ExternalAPIError("Edit request to target wiki failed.")

    logger.info("Successfully edited page '%s' on %s", target_filename, target_endpoint)
    return jsonify({"success": True, "data": {}, "errors": []}), 200


@app.route("/api/user", methods=["GET"])
def get_base_variables():
    """Return whether the current user is logged in and their username."""
    return jsonify({
        "logged":   _logged() is not None,
        "username": MW_OAUTH.get_current_user(True),
    }), 200


@app.route("/api/task_status/<task_id>", methods=["GET"])
def get_task_status(task_id: str):
    """
    Poll the status and result of an async Celery upload task.

    Returns one of the Celery task states (PENDING, PROGRESS, SUCCESS, FAILURE)
    along with the result payload on success or an error description on failure.
    """
    task = AsyncResult(task_id, app=celery_app)
    status = task.status  # PENDING | PROGRESS | SUCCESS | FAILURE

    # Determine what to put in "data" based on the task state:
    #   SUCCESS  → the dict returned by upload_image_task (wikipage_url, file_link)
    #   PROGRESS → progress meta dict e.g. {"current": 25, "total": 100}
    #   PENDING / FAILURE / other → None
    if status == "SUCCESS":
        data = task.result
    elif status == "PROGRESS":
        data = task.info  # task.info holds the meta passed to update_state()
    else:
        data = None

    errors = []
    if task.failed():
        # task.result holds the exception instance; convert to string for JSON.
        logger.error("Async task %s failed: %s", task_id, task.result)
        errors = [str(task.result)]

    return jsonify({
        "task_id": task_id,
        "status":  status,
        "data":    data,
        "errors":  errors,
    }), 200


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _authenticated_session():
    """
    Build an OAuth1 session from the stored access token.

    Returns ``None`` if the user is not logged in (no token in session).
    """
    if "mwoauth_access_token" not in session:
        return None

    return requests_oauthlib.OAuth1(
        client_key=CONSUMER_KEY,
        client_secret=CONSUMER_SECRET,
        resource_owner_key=session["mwoauth_access_token"]["key"],
        resource_owner_secret=session["mwoauth_access_token"]["secret"],
    )


def _db_user():
    """Return the ``User`` model instance for the current user, or ``None``."""
    if not _logged():
        return None
    return User.query.filter_by(username=MW_OAUTH.get_current_user(True)).first()


def _logged():
    """Return the current username if logged in, otherwise ``None``."""
    return MW_OAUTH.get_current_user(True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run()
