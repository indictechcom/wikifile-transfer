#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, request, session, jsonify, render_template, has_request_context
from flask_mwoauth import MWOAuth
from flask_migrate import Migrate
from flask_cors import CORS
from logging.config import dictConfig
import logging
import sys
import requests_oauthlib
import requests
import os
import yaml
import re
import urllib.parse
from model import db, User
from celeryWorker import app as celery_app
from tasks import upload_image_task, upload_task_item
from celery.result import AsyncResult
from utils import download_image, get_localized_wikitext, getHeader, process_upload, process_task_item

# Configure logging
class RequestFormatter(logging.Formatter):
    def format(self, record):
        if has_request_context():
            record.url = request.base_url
        else:
            record.url = "Background Task/App Context"
        return super().format(record)

dictConfig({
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            '()': RequestFormatter,
            'format': '[%(asctime)s] %(url)s\n%(levelname)s in %(module)s: %(message)s',
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'stream': sys.stdout,
            'formatter': 'default'
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/app.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 5,
            'formatter': 'default'
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console', 'file']
    }
})

app = Flask(__name__)

# Load configuration from YAML file
__dir__ = os.path.dirname(__file__)
config_path = os.path.join(__dir__, 'config.yaml')
if not os.path.exists(config_path):
    config_path = os.path.join(__dir__, 'config.yaml.bak')
with open(config_path) as f:
    app.config.update(yaml.safe_load(f))

# Get variables
ENV = app.config['ENV']
BASE_URL = app.config['OAUTH_MWURI']
API_ENDPOINT = BASE_URL + '/api.php'
CONSUMER_KEY = app.config['CONSUMER_KEY']
CONSUMER_SECRET = app.config['CONSUMER_SECRET']

# Enable CORS and Debugging in Dev mode
if ENV == 'dev':
    CORS(app, supports_credentials=True)
    app.config['DEBUG'] = True

# Create Database and Migration Object
db.init_app(app)
migrate = Migrate(app, db)

# Register blueprint to app
MW_OAUTH = MWOAuth(
    base_url=BASE_URL,
    consumer_key=CONSUMER_KEY,
    consumer_secret=CONSUMER_SECRET,
    user_agent= getHeader()['User-Agent']
)
app.register_blueprint(MW_OAUTH.bp)


@app.before_request
def log_request_info():
    app.logger.info(f"Processing request: {request.method} {request.path}")


@app.route('/index', methods=['GET'])
@app.route("/")
def index():
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload():
    if request.method == 'POST':
        app.logger.info("Initiating single file upload process")
        data = request.get_json()
        src_url = urllib.parse.unquote(data.get('srcUrl'))

        try:
            match = re.findall(r"(\w+)\.(\w+)\.org/wiki/", src_url)
            src_project = match[0][1]
            src_lang = match[0][0]
        except IndexError:
            app.logger.warning(f"Invalid source URL provided: {src_url}")
            return jsonify({"success": False, "data": {}, "errors": ["Invalid source URL"]}), 400

        src_filename = src_url.split('/')[-1]
        src_fileext = src_filename.split('.')[-1]

        # Downloading the source file and getting saved file name
        downloaded_filename = download_image(src_project, src_lang, src_filename)

        # Getting Target Details
        tr_project = data.get('trproject')
        tr_lang = data.get('trlang')
        tr_filename = data.get('trfilename')
        tr_filename = urllib.parse.unquote(tr_filename)
        tr_endpoint = "https://" + tr_lang + "." + tr_project + ".org/w/api.php"

        # Authenticate Session
        ses = authenticated_session()

        # Check whether we have enough data or not
        if None not in (downloaded_filename, tr_filename, src_fileext, ses):
            file_path = 'temp_images/' + downloaded_filename
            file_size = os.path.getsize(file_path)

            if file_size < 50 * 1024 * 1024:  # 50 MB
                app.logger.info(f"Processing file synchronously: {tr_filename} ({file_size} bytes) to {tr_lang}.{tr_project}")
                # Process synchronously
                resp = process_upload(file_path, tr_filename, src_fileext, tr_endpoint, ses)
                if resp is None:
                    app.logger.error(f"Synchronous upload failed for {tr_filename} to {tr_lang}.{tr_project}")
                    return jsonify({"success": False, "data": {}, "errors": ["Upload failed"]}), 500

                resp["source"] = src_url
                app.logger.info(f"Upload successful for {tr_filename} to {tr_lang}.{tr_project}")
                return jsonify({
                    "success": True,
                    "data": resp,
                    "errors": []
                }), 200
            else:
                app.logger.info(f"File size {file_size} exceeds 50MB, dispatching to Celery: {tr_filename} to {tr_lang}.{tr_project}")
                # Process asynchronously using Celery
                OAuthObj = {
                    "consumer_key": CONSUMER_KEY,
                    "consumer_secret": CONSUMER_SECRET,
                    "key": session['mwoauth_access_token']['key'],
                    "secret": session['mwoauth_access_token']['secret']
                }
                task = upload_image_task.delay(file_path, tr_filename, src_fileext, tr_endpoint, OAuthObj)
                app.logger.info(f"Dispatched async upload task {task.id} for {tr_filename} to {tr_lang}.{tr_project}")
                return jsonify({"success": True, "task_id": task.id}), 202
        else:
            app.logger.warning("Upload failed: Missing required data parameters or unauthorized session")
            return jsonify({"success": False, "data": {}, "errors": ["Not enough data"]}), 400
    else:
        return jsonify({"success": False, "data": {}, "errors": ["Invalid Request"]}), 400


@app.route('/api/upload_multi', methods=['POST'])
def upload_multi():
    if request.method == 'POST':
        app.logger.info("Initiating multi-file upload process")
        data = request.get_json()
        src_url = urllib.parse.unquote(data.get('srcUrl', ''))
        match = re.findall(r"(\w+)\.(\w+)\.org/wiki/", src_url)

        if not match:
            app.logger.warning(f"Invalid source URL provided: {src_url}")
            return jsonify({"status": "FAILURE", "errors": ["Invalid source URL"]}), 400

        src_project = match[0][1]
        src_lang = match[0][0]
        src_filename = src_url.split('/')[-1]
        src_fileext = src_filename.split('.')[-1]

        # Downloading the source file and getting saved file name
        downloaded_filename = download_image(src_project, src_lang, src_filename)

        # Getting Target Details
        tr_project = data.get('trproject')
        tasks = data.get('tasks', [])

        # Authenticate Session
        ses = authenticated_session()

        # Check whether we have enough data or not
        if None not in (downloaded_filename, tr_project, src_fileext, ses) and len(tasks) > 0:
            file_path = 'temp_images/' + downloaded_filename
            file_size = os.path.getsize(file_path)
            num_transfers = len(tasks)

            # Process synchronously if only 1 target and file is lightweight
            if file_size < 50 * 1024 * 1024 and num_transfers == 1:
                task_item = tasks[0]
                lang = task_item.get("lang")

                app.logger.info(f"Processing single target multi-task synchronously: {lang}.{tr_project}")
                try:
                    resp = process_task_item(file_path, tr_project, task_item, src_fileext, ses)
                    app.logger.info(f"Multi-upload successful for {lang}.{tr_project}")
                    return jsonify({"status": "SUCCESS", "lang": lang, "data": {lang: resp}}), 200
                except Exception as e:
                    app.logger.error(f"Multi-upload synchronous failure for {lang}: {e}", exc_info=True)
                    return jsonify({"status": "FAILURE", "lang": lang, "errors": [str(e)]}), 500
            else:
                app.logger.info(f"Dispatching {num_transfers} multi-upload tasks to Celery")
                # Process asynchronously using Celery for multiple transfers
                OAuthObj = {
                    "consumer_key": CONSUMER_KEY,
                    "consumer_secret": CONSUMER_SECRET,
                    "key": session['mwoauth_access_token']['key'],
                    "secret": session['mwoauth_access_token']['secret']
                }

                pending_tasks = {}
                for task_item in tasks:
                    lang = task_item.get("lang")
                    task = upload_task_item.delay(file_path, tr_project, task_item, src_fileext, OAuthObj)
                    pending_tasks[lang] = task.id
                    app.logger.info(f"Dispatched async task {task.id} for {lang}.{tr_project}")

                return jsonify({"status": "PENDING", "tasks": pending_tasks}), 202
        else:
            app.logger.warning("Upload multi failed: Missing required data parameters or missing tasks")
            return jsonify({"status": "FAILURE", "errors": ["Not enough data or missing tasks"]}), 400
    else:
        return jsonify({"status": "FAILURE", "errors": ["Invalid Request"]}), 400


@app.route('/api/preference', methods = ['GET', 'POST'])
def preference():

    if request.method == 'GET':
        user = db_user()

        user_project = "wikipedia"
        user_lang = "en"
        skip_upload_selection = False

        if user is not None:
            user_project = user.pref_project
            user_lang = user.pref_language
            skip_upload_selection = user.skip_upload_selection

        return jsonify(
            {
                "success": True,
                "data": {
                    "project": user_project,
                    "lang": user_lang,
                    "skip_upload_selection": skip_upload_selection
                },
                "error": []
            }), 200

    elif request.method == 'POST':
        # Get the data
        data = request.get_json()
        project = data.get('project')
        lang = data.get('lang')
        skip_upload_selection = data.get('skip_upload_selection')

        # Add into database
        cur_username = MW_OAUTH.get_current_user(True)
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
            return jsonify({ "success": True, "data": {}, "errors": []}), 200
        except Exception as e:
            app.logger.error(f"Database error saving preference for {cur_username}: {e}", exc_info=True)
            db.session.rollback()
            return jsonify({ "success": False, "data": {}, "errors": ["Database Error"]}), 500

    else:
        return jsonify({ "success": False, "data": {}, "errors": ["Invalid Request"]}), 400


@app.route('/api/user_language', methods=['GET', 'POST'])
def languagePreference():
    if request.method == 'GET':
        user = db_user()

        user_language = "en"  # Default language
        if user is not None:
            user_language = user.user_language

        return jsonify(
            {
                "success": True,
                "data": {
                    "user_language": user_language
                },
                "error": []
            }), 200

    elif request.method == 'POST':
        data = request.get_json()
        user_language = data.get('user_language')

        cur_username = MW_OAUTH.get_current_user(True)
        user = User.query.filter_by(username=cur_username).first()

        if user is None:
            user = User(username=cur_username, user_language=user_language)
            db.session.add(user)
        else:
            user.user_language = user_language

        try:
            db.session.commit()
            return jsonify({ "success": True, "data": {}, "errors": []}), 200
        except Exception as e:
            app.logger.error(f"Database error saving language preference for {cur_username}: {e}", exc_info=True)
            db.session.rollback()
            return jsonify({ "success": False, "data": {}, "errors": ["Database Error"]}), 500

    else:
        return jsonify({ "success": False, "data": {}, "errors": ["Invalid Request"]}), 400


@app.route('/api/get_wikitext', methods=['GET'])
def get_wikitext():
    src_lang = request.args.get('src_lang')
    src_project = request.args.get('src_project')
    src_filename = request.args.get('src_filename')
    tr_lang = request.args.get('tr_lang')

    # In any case, return the strings only with 200 status code
    if not all([src_lang, src_project, src_filename, tr_lang]):
        return jsonify({"wikitext": ""}), 200

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
        response = requests.get(src_endpoint, params=content_params, headers=getHeader())
        response.raise_for_status()

        page_data = response.json().get("query", {}).get("pages", [])

        if page_data and page_data[0].get("revisions"):
            wikitext = page_data[0]["revisions"][0]["slots"]["main"]["content"]
            wikitext = get_localized_wikitext(wikitext, src_endpoint, tr_lang)

            return jsonify({"wikitext": wikitext}), 200
        else:
            return jsonify({"wikitext": ""}), 200
    except Exception as e:
        app.logger.error(f"Failed to fetch wikitext for {src_filename} from {src_lang}.{src_project}: {e}", exc_info=True)
        return jsonify({"wikitext": ""}), 200


@app.route('/api/edit_page', methods=['POST'])
def editPage():
    if request.method == 'POST':
        data = request.get_json()
        targetUrl = data.get('targetUrl')
        content = data.get('content')

        match = re.findall(r"(\w+)\.(\w+)\.org/wiki/", targetUrl)

        target_project = match[0][1]
        target_lang = match[0][0]
        target_filename = targetUrl.split('/')[-1]

        target_endpoint = "https://" + target_lang + "." + target_project + ".org/w/api.php"

        app.logger.info(f"Initiating page edit for {target_filename} on {target_lang}.{target_project}")

        # Authenticate Session
        ses = authenticated_session()

        # API Parameter to get CSRF Token
        csrf_param = {
            "action": "query",
            "meta": "tokens",
            "format": "json"
        }

        response = requests.get(url=target_endpoint, params=csrf_param, auth=ses, headers=getHeader())
        response.raise_for_status()
        csrf_token = response.json()["query"]["tokens"]["csrftoken"]

        # API Parameters to edit the page
        edit_params = {
            "action": "edit",
            "title": "File:" + target_filename.split(':')[1],
            "token": csrf_token,
            "format": "json",
            "appendtext": content
        }

        response = requests.post(url=target_endpoint, data=edit_params, auth=ses, headers=getHeader())
        resp_json = response.json()

        if response.status_code == 200 and "error" not in resp_json:
            app.logger.info(f"Successfully edited page {target_filename} on {target_lang}.{target_project}")
            return jsonify({ "success": True, "data": {}, "errors": []}), 200
        else:
            api_err = resp_json.get("error", {}).get("info", "Unknown API Error")
            app.logger.error(f"Edit failed for page {target_filename} on {target_lang}.{target_project}. API response: {api_err}")
            return jsonify({ "success": False, "data": {}, "errors": ["Edit Error"]}), 500

    else:
        return jsonify({ "success": False, "data": {}, "errors": ["Invalid Request"]}), 400


@app.route('/api/edit_article', methods=['POST'])
def editArticle():
    if request.method == 'POST':
        data = request.get_json()
        articleName = data.get('articleName')
        content = data.get('content')
        target_lang = data.get('lang')
        target_project = data.get('project')

        if not articleName or not target_lang or not target_project:
            app.logger.warning("Edit article failed: Missing required parameters")
            return jsonify({ "success": False, "data": {}, "errors": ["Missing parameters"]}), 400

        target_title = urllib.parse.unquote(articleName)

        target_endpoint = "https://" + target_lang + "." + target_project + ".org/w/api.php"
        ses = authenticated_session()

        app.logger.info(f"Initiating article edit for '{target_title}' on {target_lang}.{target_project}")

        # API Parameter to get CSRF Token
        csrf_param = {
            "action": "query",
            "meta": "tokens",
            "format": "json"
        }

        try:
            response = requests.get(url=target_endpoint, params=csrf_param, auth=ses, headers=getHeader())
            response.raise_for_status()
            csrf_token = response.json()["query"]["tokens"]["csrftoken"]

            # API Parameters to edit the page (replace wikitext entirely)
            edit_params = {
                "action": "edit",
                "title": target_title,
                "token": csrf_token,
                "format": "json",
                "text": content
            }

            response = requests.post(url=target_endpoint, data=edit_params, auth=ses, headers=getHeader())
            resp_json = response.json()

            if response.status_code == 200 and "error" not in resp_json:
                app.logger.info(f"Successfully edited article '{target_title}' on {target_lang}.{target_project}")
                return jsonify({ "success": True, "data": {}, "errors": []}), 200
            else:
                api_err = resp_json.get("error", {}).get("info", "Unknown Error")
                app.logger.error(f"Edit failed for article '{target_title}' on {target_lang}.{target_project}. API response: {api_err}")
                return jsonify({ "success": False, "data": {}, "errors": ["Edit Error: " + api_err]}), 500
        except Exception as e:
            app.logger.error(f"Edit article exception for '{target_title}' on {target_lang}.{target_project}: {e}", exc_info=True)
            return jsonify({ "success": False, "data": {}, "errors": [str(e)]}), 500

    else:
        return jsonify({ "success": False, "data": {}, "errors": ["Invalid Request"]}), 400


@app.route('/api/user', methods=['GET'])
def get_base_variables():
    return jsonify({
        "logged": logged() is not None,
        "username": MW_OAUTH.get_current_user(True)
    }), 200


@app.route('/api/task_status/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """
    Endpoint to get the status and result of a Celery task.
    """
    task = AsyncResult(task_id, app=celery_app)

    status = task.status
    result = task.result if task.successful() else None
    error = None
    progress = 0

    if status == 'PROGRESS':
        progress = task.info.get('current', 0) if task.info else 0

    # Identify PARTIAL success requirement for the frontend
    # Triggers if file uploaded correctly, but wikitext fetch failed.
    if task.successful() and isinstance(result, dict):
        if result.get("wikitext_fetch_success") is False:
            status = "PARTIAL"
            error = "Upload completed, but failed to fetch the target article wikitext."

    if task.failed():
        error = str(task.result)

    response = {
        "task_id": task_id,
        "status": status,
        "result": result,
        "progress": progress
    }

    if error:
        response["error"] = error

    return jsonify(response), 200


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


def db_user():
    if logged():
        user = User.query.filter_by(username=MW_OAUTH.get_current_user(True)).first()
        return user
    else:
        return None


def logged():
    if MW_OAUTH.get_current_user(True) is not None:
        return MW_OAUTH.get_current_user(True)
    else:
        return None


@app.errorhandler(400)
def bad_request(e):
    app.logger.warning(f"400 Bad Request: {e}")
    return jsonify({"success": False, "data": {}, "errors": [e.description if hasattr(e, 'description') else "Bad Request"]}), 400

@app.errorhandler(404)
def not_found(e):
    app.logger.warning(f"404 Not Found: {request.base_url}")
    return jsonify({"success": False, "data": {}, "errors": ["Resource not found"]}), 404

@app.errorhandler(405)
def method_not_allowed(e):
    app.logger.warning(f"405 Method Not Allowed: {request.base_url}")
    return jsonify({"success": False, "data": {}, "errors": ["Method not allowed"]}), 405

@app.errorhandler(500)
def internal_error(e):
    app.logger.error(f"500 Internal Server Error: {e}", exc_info=True)
    return jsonify({"success": False, "data": {}, "errors": ["Internal server error"]}), 500

@app.errorhandler(Exception)
def unhandled_exception(e):
    app.logger.critical(f"Unhandled Exception: {e}", exc_info=True)
    return jsonify({"success": False, "data": {}, "errors": ["An unexpected error occurred"]}), 500

if __name__ == "__main__":
    app.run()
