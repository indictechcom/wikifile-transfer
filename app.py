#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from flask import send_from_directory
from flask import Flask, request, session, jsonify
from flask_mwoauth import MWOAuth
from flask_migrate import Migrate
from utils import download_image, get_localized_wikitext, getHeader, process_upload
from flask_cors import CORS
import requests_oauthlib
import requests
import os
import yaml
import re
import urllib.parse
from model import db, User
from celeryWorker import app as celery_app
from tasks import upload_image_task
from celery.result import AsyncResult
from logging_config import setup_logging, get_logger, log_timed_api_call
from exceptions import (
    ValidationError,
    WikiAPIError,
    FileOperationError,
    DatabaseError,
    AuthenticationError,
    UploadError,
    ResourceNotFoundError
)
from error_handlers import register_error_handlers, success_response

app = Flask(__name__)

# Load configuration from YAML file
__dir__ = os.path.dirname(__file__)
app.config.update(yaml.safe_load(open(os.path.join(__dir__, 'config.yaml'))))

# Get variables
ENV = app.config['ENV']
BASE_URL = app.config['OAUTH_MWURI']
CONSUMER_KEY = app.config['CONSUMER_KEY']
CONSUMER_SECRET = app.config['CONSUMER_SECRET']

# Now that ENV is known, set up logging correctly for this environment
setup_logging(env=ENV)
logger = get_logger(__name__)

# Enable CORS and Debugging in Dev mode
if ENV == 'dev':
    CORS(app, supports_credentials=True)
    app.config['DEBUG'] = True

# Create Database and Migration Object
db.init_app(app)
migrate = Migrate(app, db)

# Register MediaWiki OAuth blueprint
MW_OAUTH = MWOAuth(
    base_url=BASE_URL,
    consumer_key=CONSUMER_KEY,
    consumer_secret=CONSUMER_SECRET,
    user_agent=getHeader()['User-Agent']
)
app.register_blueprint(MW_OAUTH.bp)

# Wire custom exceptions to consistent JSON error responses
register_error_handlers(app)


@app.route('/index', methods=['GET'])
@app.route("/")
def serve():
    return send_from_directory("frontend/build", "index.html")

@app.route("/static/<path:path>")
def serve_static(path):
    return send_from_directory("frontend/build/static", path)


@app.route('/api/upload', methods=['POST'])
def upload():
    data = request.get_json()

    # Validate srcUrl is present and is a valid wiki URL
    src_url = data.get('srcUrl') if data else None
    if not src_url:
        raise ValidationError("srcUrl is required", field="srcUrl")
    src_url = urllib.parse.unquote(src_url)

    match = re.findall(r"(\w+)\.(\w+)\.org/wiki/", src_url)
    if not match:
        raise ValidationError("srcUrl must be a valid wiki URL", field="srcUrl")

    src_project = match[0][1]
    src_lang = match[0][0]
    src_filename = src_url.split('/')[-1]
    src_fileext = src_filename.split('.')[-1]

    # Download source file and raise if download fails
    downloaded_filename = download_image(src_project, src_lang, src_filename)
    if downloaded_filename is None:
        raise FileOperationError(
            "Failed to download source file",
            operation="download",
            file_path=src_filename
        )

    # Validate target wiki fields
    tr_project = data.get('trproject')
    tr_lang = data.get('trlang')
    tr_filename = data.get('trfilename')

    if not all([tr_project, tr_lang, tr_filename]):
        raise ValidationError("trproject, trlang, and trfilename are all required")

    tr_filename = urllib.parse.unquote(tr_filename)
    tr_endpoint = "https://" + tr_lang + "." + tr_project + ".org/w/api.php"

    # Require authenticated session before proceeding
    ses = authenticated_session()
    if ses is None:
        raise AuthenticationError("You must be logged in to upload files")

    file_path = 'temp_images/' + downloaded_filename
    file_size = os.path.getsize(file_path)

    if file_size < 50 * 1024 * 1024:  # files under 50 MB upload synchronously
        resp = process_upload(file_path, tr_filename, src_fileext, tr_endpoint, ses)
        if resp is None:
            raise UploadError("Upload to target wiki failed", upload_type="sync")

        resp["source"] = src_url
        return success_response(data=resp)

    else:
        # Files over 50 MB are queued as a Celery async task
        OAuthObj = {
            "consumer_key": CONSUMER_KEY,
            "consumer_secret": CONSUMER_SECRET,
            "key": session['mwoauth_access_token']['key'],
            "secret": session['mwoauth_access_token']['secret']
        }
        task = upload_image_task.delay(file_path, tr_filename, src_fileext, tr_endpoint, OAuthObj)
        return success_response(data={"task_id": task.id}, status_code=202)


@app.route('/api/preference', methods=['GET', 'POST'])
def preference():

    if request.method == 'GET':
        user = db_user()

        # Return defaults for unauthenticated users
        user_project = "wikipedia"
        user_lang = "en"
        skip_upload_selection = False

        if user is not None:
            user_project = user.pref_project
            user_lang = user.pref_language
            skip_upload_selection = user.skip_upload_selection

        return success_response(data={
            "project": user_project,
            "lang": user_lang,
            "skip_upload_selection": skip_upload_selection
        })

    elif request.method == 'POST':
        data = request.get_json()

        # Validate required fields before touching the database
        project = data.get('project') if data else None
        lang = data.get('lang') if data else None
        skip_upload_selection = data.get('skip_upload_selection') if data else None

        if not all([project, lang]):
            raise ValidationError("project and lang are required")

        # Only authenticated users can save preferences
        cur_username = MW_OAUTH.get_current_user(True)
        if not cur_username:
            raise AuthenticationError("You must be logged in to save preferences")

        user = User.query.filter_by(username=cur_username).first()

        if user is None:
            user = User(
                username=cur_username,
                pref_language=lang,
                pref_project=project,
                skip_upload_selection=skip_upload_selection
            )
            db.session.add(user)
        else:
            user.pref_language = lang
            user.pref_project = project
            user.skip_upload_selection = skip_upload_selection

        try:
            db.session.commit()
            return success_response()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to save preferences: {e}", exc_info=True)
            raise DatabaseError("Failed to save preferences", operation="commit")

    else:
        raise ValidationError("Only GET and POST requests are allowed on this endpoint")


@app.route('/api/user_language', methods=['GET', 'POST'])
def languagePreference():
    if request.method == 'GET':
        user = db_user()

        # Return default language for unauthenticated users
        user_language = "en"
        if user is not None:
            user_language = user.user_language

        return success_response(data={"user_language": user_language})

    elif request.method == 'POST':
        data = request.get_json()

        # Validate required field
        user_language = data.get('user_language') if data else None
        if not user_language:
            raise ValidationError("user_language is required", field="user_language")

        # Only authenticated users can save language preference
        cur_username = MW_OAUTH.get_current_user(True)
        if not cur_username:
            raise AuthenticationError("You must be logged in to save language preference")

        user = User.query.filter_by(username=cur_username).first()

        if user is None:
            user = User(username=cur_username, user_language=user_language)
            db.session.add(user)
        else:
            user.user_language = user_language

        try:
            db.session.commit()
            return success_response()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to save language preference: {e}", exc_info=True)
            raise DatabaseError("Failed to save language preference", operation="commit")

    else:
        raise ValidationError("Only GET and POST requests are allowed on this endpoint")


@app.route('/api/get_wikitext', methods=['GET'])
def get_wikitext():
    src_lang = request.args.get('src_lang')
    src_project = request.args.get('src_project')
    src_filename = request.args.get('src_filename')
    tr_lang = request.args.get('tr_lang')

    # Return empty wikitext when params are missing — UI handles this gracefully
    if not all([src_lang, src_project, src_filename, tr_lang]):
        return success_response(data={"wikitext": ""})

    src_endpoint = f"https://{src_lang}.{src_project}.org/w/api.php"
    content_params = {
        "action": "query",
        "format": "json",
        "prop": "revisions",
        "titles": src_filename,
        "formatversion": "2",
        "rvprop": "content",
        "rvslots": "main",
        "origin": "*"
    }

    try:
        with log_timed_api_call(logger, src_endpoint, "GET") as context:
            response = requests.get(src_endpoint, params=content_params, timeout=10)
            response.raise_for_status()
            context["status_code"] = response.status_code

        page_data = response.json().get("query", {}).get("pages", [])

        if page_data and page_data[0].get("revisions"):
            wikitext = page_data[0]["revisions"][0]["slots"]["main"]["content"]
            wikitext = get_localized_wikitext(wikitext, src_endpoint, tr_lang)
            return success_response(data={"wikitext": wikitext})
        else:
            return success_response(data={"wikitext": ""})

    except requests.exceptions.Timeout:
        raise WikiAPIError("MediaWiki API request timed out", api_endpoint=src_endpoint)
    except requests.exceptions.RequestException as e:
        raise WikiAPIError(f"MediaWiki API request failed: {str(e)}", api_endpoint=src_endpoint)


@app.route('/api/edit_page', methods=['POST'])
def editPage():
    data = request.get_json()

    # Validate required fields
    target_url = data.get('targetUrl') if data else None
    content = data.get('content') if data else None

    if not target_url:
        raise ValidationError("targetUrl is required", field="targetUrl")
    if content is None:
        raise ValidationError("content is required", field="content")

    match = re.findall(r"(\w+)\.(\w+)\.org/wiki/", target_url)
    if not match:
        raise ValidationError("targetUrl must be a valid wiki URL", field="targetUrl")

    target_project = match[0][1]
    target_lang = match[0][0]
    target_filename = target_url.split('/')[-1]
    target_endpoint = "https://" + target_lang + "." + target_project + ".org/w/api.php"

    # Require authenticated session before making any API calls
    ses = authenticated_session()
    if ses is None:
        raise AuthenticationError("You must be logged in to edit pages")

    csrf_param = {
        "action": "query",
        "meta": "tokens",
        "format": "json"
    }

    # Fetch CSRF token required by MediaWiki edit API
    try:
        with log_timed_api_call(logger, target_endpoint, "GET") as context:
            response = requests.get(url=target_endpoint, params=csrf_param, auth=ses, timeout=10)
            response.raise_for_status()
            context["status_code"] = response.status_code

        csrf_token = response.json()["query"]["tokens"]["csrftoken"]

        # +\ is what MediaWiki returns when OAuth session isn't recognized — HTTP is still 200
        if csrf_token == "+\\":
            raise AuthenticationError("Invalid CSRF token — OAuth session may have expired")

    except requests.exceptions.Timeout:
        raise WikiAPIError("Timed out fetching CSRF token", api_endpoint=target_endpoint)
    except (requests.exceptions.RequestException, KeyError) as e:
        raise WikiAPIError(f"Failed to get CSRF token: {str(e)}", api_endpoint=target_endpoint)

    edit_params = {
        "action": "edit",
        "title": "File:" + target_filename.split(':')[1],
        "token": csrf_token,
        "format": "json",
        "appendtext": content
    }

    # Submit the edit with a longer timeout for large content
    try:
        with log_timed_api_call(logger, target_endpoint, "POST") as context:
            response = requests.post(url=target_endpoint, data=edit_params, auth=ses, timeout=30)
            response.raise_for_status()
            context["status_code"] = response.status_code
    except requests.exceptions.Timeout:
        raise WikiAPIError("Timed out posting edit", api_endpoint=target_endpoint)
    except requests.exceptions.RequestException as e:
        raise WikiAPIError(f"Edit request failed: {str(e)}", api_endpoint=target_endpoint)

    return success_response()


@app.route('/api/user', methods=['GET'])
def get_base_variables():
    return success_response(data={
        "logged": logged() is not None,
        "username": MW_OAUTH.get_current_user(True)
    })


@app.route('/api/task_status/<task_id>', methods=['GET'])
def get_task_status(task_id):
    task = AsyncResult(task_id, app=celery_app)

    data = {
        "task_id": task_id,
        "status": task.status,
        "result": task.result if task.successful() else None,
    }

    if task.failed():
        data["error"] = str(task.result)

    return success_response(data=data)


def authenticated_session():
    if 'mwoauth_access_token' in session:
        auth = requests_oauthlib.OAuth1(
            client_key=CONSUMER_KEY,
            client_secret=CONSUMER_SECRET,
            resource_owner_key=session['mwoauth_access_token']['key'],
            resource_owner_secret=session['mwoauth_access_token']['secret']
        )
        return auth
    return None


def logged():
    return MW_OAUTH.get_current_user(True)


def db_user():
    username = logged()
    if username:
        return User.query.filter_by(username=username).first()
    return None


if __name__ == "__main__":
    app.run()
