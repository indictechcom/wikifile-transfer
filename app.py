#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, request, session, jsonify, render_template
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
import logging
from celeryWorker import app as celery_app
from tasks import upload_image_task
from celery.result import AsyncResult
from logger import initialize_logging_file, log_exception, log_info
from exceptions import (
    success_response,
    error_response,
    error_response_from_error,
    validation_error,
    authentication_error,
    file_handling_error,
)
# Configure logging
initialize_logging_file("./logs/wikifile_transfer.log")
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Load configuration from YAML file
__dir__ = os.path.dirname(__file__)
app.config.update(yaml.safe_load(open(os.path.join(__dir__, 'config.yaml'))))

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


@app.route('/index', methods=['GET'])
@app.route("/")
def index():
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload():
    if request.method == 'POST':
        data = request.get_json() or {}
        src_url = urllib.parse.unquote(data.get('srcUrl', ''))
        if not src_url:
            return error_response_from_error(validation_error("srcUrl is required"), status_code=400)

        match = re.findall(r"(\w+)\.(\w+)\.org/wiki/", src_url)
        if not match:
            return error_response_from_error(validation_error("Invalid source wiki URL"), status_code=400)

        src_project = match[0][1]
        src_lang = match[0][0]
        src_filename = src_url.split('/')[-1]
        src_fileext = src_filename.split('.')[-1]

        log_info("Processing upload for %s", src_filename)

        # Downloading the source file and getting saved file name
        download_result = download_image(src_project, src_lang, src_filename)

        # Getting Target Details
        tr_project = data.get('trproject')
        tr_lang = data.get('trlang')
        tr_filename = data.get('trfilename')
        if not all([tr_project, tr_lang, tr_filename]):
            return error_response_from_error(validation_error("trproject, trlang and trfilename are required"), status_code=400)

        tr_filename = urllib.parse.unquote(tr_filename)
        tr_endpoint = "https://" + tr_lang + "." + tr_project + ".org/w/api.php"

        # Authenticate Session
        ses = authenticated_session()

        # Check whether we have enough data or not
        if not download_result.get("ok"):
            log_exception("Download failed for %s", src_filename)
            return error_response_from_error(download_result.get("error"), status_code=500)

        if None not in (tr_filename, src_fileext, ses):
            downloaded_filename = download_result["data"].get("filename")
            if not downloaded_filename:
                return error_response_from_error(file_handling_error("Missing downloaded filename"), status_code=500)

            file_path = 'temp_images/' + downloaded_filename
            file_size = os.path.getsize(file_path)

            if file_size < 50 * 1024 * 1024:  # 50 MB
                # Process synchronously
                resp = process_upload(file_path, tr_filename, src_fileext, tr_endpoint, ses)
                if not resp.get("ok"):
                    return error_response_from_error(resp.get("error"), status_code=500)

                response_data = resp.get("data", {})
                response_data["source"] = src_url
                log_info("Upload results for %s: %s", tr_filename, response_data)

                return success_response(response_data, status_code=200)
            else:
                # Process asynchronously using Celery
                OAuthObj = {
                    "consumer_key": CONSUMER_KEY,
                    "consumer_secret": CONSUMER_SECRET,
                    "key": session['mwoauth_access_token']['key'],
                    "secret": session['mwoauth_access_token']['secret']
                }
                task = upload_image_task.delay(file_path, tr_filename, src_fileext, tr_endpoint, OAuthObj)
                
                log_info("Asynchronous upload initiated for %s", tr_filename)

                return success_response({"task_id": task.id}, status_code=202)
        else:
            log_exception("Not enough data for upload: %s", tr_filename)
            return error_response_from_error(validation_error("Not enough data for upload"), status_code=400)
    else:
        log_exception("Invalid request method for upload endpoint")
        return error_response("INVALID_REQUEST", "Invalid Request", status_code=400)


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
            log_info("Retrieved preferences for user %s: project=%s, language=%s, skip_upload_selection=%s", user.username, user_project, user_lang, skip_upload_selection)
            
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
            log_info("Preferences updated for user %s", cur_username)
            return jsonify({ "success": True, "data": {}, "errors": []}), 200
        except:
            db.session.rollback()
            log_exception("Failed to update preferences for user %s", cur_username)
            return jsonify({ "success": False, "data": {}, "errors": ["Database Error"]}), 500

    else:
        log_exception("Invalid request method for preference endpoint")
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
            log_info("User language updated for %s", cur_username)
            return jsonify({ "success": True, "data": {}, "errors": []}), 200
        except:
            db.session.rollback()
            log_exception("Failed to update user language for %s", cur_username)
            return jsonify({ "success": False, "data": {}, "errors": ["Database Error"]}), 500

    else:
        log_exception("Invalid request method for language preference endpoint")
        return jsonify({ "success": False, "data": {}, "errors": ["Invalid Request"]}), 400


@app.route('/api/get_wikitext', methods=['GET'])
def get_wikitext():
    src_lang = request.args.get('src_lang')
    src_project = request.args.get('src_project')
    src_filename = request.args.get('src_filename')
    tr_lang = request.args.get('tr_lang')
    log_info("Retrieving wikitext for %s (%s) -> %s", src_filename, src_lang, tr_lang)

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
        response = requests.get(src_endpoint, params=content_params)
        response.raise_for_status()

        page_data = response.json().get("query", {}).get("pages", [])

        if page_data and page_data[0].get("revisions"):
            wikitext = page_data[0]["revisions"][0]["slots"]["main"]["content"]
            wikitext = get_localized_wikitext(wikitext, src_endpoint, tr_lang)

            return jsonify({"wikitext": wikitext}), 200
        else:
            return jsonify({"wikitext": ""}), 200
    except:
        log_exception("Error occurred while retrieving wikitext for %s (%s) -> %s", src_filename, src_lang, tr_lang)
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


        # Authenticate Session
        ses = authenticated_session()

        # API Parameter to get CSRF Token
        csrf_param = {
            "action": "query",
            "meta": "tokens",
            "format": "json"
        }

        response = requests.get(url=target_endpoint, params=csrf_param, auth=ses)
        csrf_token = response.json()["query"]["tokens"]["csrftoken"]

        # API Parameters to edit the page
        edit_params = {
            "action": "edit",
            "title": "File:" + target_filename.split(':')[1],
            "token": csrf_token,
            "format": "json",
            "appendtext": content
        }

        response = requests.post(url=target_endpoint, data=edit_params, auth=ses)

        if response.status_code == 200:
            log_info("Page edited successfully for %s", target_filename)
            return jsonify({ "success": True, "data": {}, "errors": []}), 200
        else:
            log_exception("Failed to edit page for %s: %s", target_filename, response.text)
            return jsonify({ "success": False, "data": {}, "errors": ["Edit Error"]}), 500

    else:
        log_exception("Invalid request method for edit page endpoint")
        return jsonify({ "success": False, "data": {}, "errors": ["Invalid Request"]}), 400


@app.route('/api/user', methods=['GET'])
def get_base_variables():
    log_info("Retrieving base variables for user")
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
    response = {
        "task_id": task_id,
        "status": task.status,
        "result": task.result if task.successful() else None,
    }
    
    # If task failed, include error information
    if task.failed():
        response["error"] = str(task.result)
        log_exception("Task failed for %s: %s", task_id, response["error"])

    return jsonify(response), 200


def authenticated_session():
    if 'mwoauth_access_token' in session:
        auth = requests_oauthlib.OAuth1(
            client_key=CONSUMER_KEY,
            client_secret=CONSUMER_SECRET,
            resource_owner_key=session['mwoauth_access_token']['key'],
            resource_owner_secret=session['mwoauth_access_token']['secret']
        )
        log_info("Authenticated session created")
        return auth

    return None


def db_user():
    if logged():
        log_info("Retrieving user information for %s", MW_OAUTH.get_current_user(True))
        user = User.query.filter_by(username=MW_OAUTH.get_current_user(True)).first()
        return user
    else:
        log_info("No user logged in")
        return None


def logged():
    if MW_OAUTH.get_current_user(True) is not None:
        return MW_OAUTH.get_current_user(True)
    else:
        log_info("User is not logged in")
        return None


if __name__ == "__main__":
    app.run()
