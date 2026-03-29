#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, request, session, jsonify, render_template
from flask_mwoauth import MWOAuth
from flask_migrate import Migrate
from utils import download_image, get_localized_wikitext, getHeader, process_upload, _fetch_csrf_token, success_response, error_response, safe_delete_temp_file
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

from globalExceptions import (
    APIRequestError,
    AuthenticationError,
    FileNotFoundOnWikiError,
    ImageDownloadError,
    OAuthConfigError,
    UploadError,
    WikitextProcessingError,
    CSRFTokenError,
)
from logger import get_logger
log = get_logger(__name__)


# Configure logging
# logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# app = Flask(__name__)
app = Flask(
    __name__,
    template_folder='frontend/build',
    static_folder='frontend/build/static'
)

# Load configuration from YAML file
__dir__ = os.path.dirname(__file__)
_config_path = os.path.join(__dir__, "config.yaml")
# app.config.update(yaml.safe_load(open(os.path.join(__dir__, 'config.yaml'))))

try:
    with open(_config_path) as _fh:
        app.config.update(yaml.safe_load(_fh))
except FileNotFoundError:
    raise RuntimeError(f"config.yaml not found at {_config_path!r}")
except yaml.YAMLError as exc:
    raise RuntimeError(f"config.yaml is malformed: {exc}") from exc
 

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
    
log.info("Flask app starting", extra={"env": ENV, "base_url": BASE_URL})

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


# def success_response(data: dict = None, status: int = 200):
#     """Standardised success envelope: {success, data}"""
#     return jsonify({"success": True, "data": data or {}}), status
 
 
# def error_response(message: str, status: int = 500, error_type: str = None):
#     body = {"success": False, "error": message}
#     if error_type:
#         body["error_type"] = error_type
#     return jsonify(body), status


@app.route('/index', methods=['GET'])
@app.route("/")
def index():
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def upload():
    
    data = request.get_json(silent=True)
    if not data:
        return error_response("Request body must be JSON", 400, "InvalidRequest")
    
    if request.method == 'POST':
        # data = request.get_json()
        src_url = urllib.parse.unquote(data.get('srcUrl'))
        match = re.findall(r"(\w+)\.(\w+)\.org/wiki/", src_url)
        
        if not match:
            return error_response("Could not parse source URL", 400, "InvalidRequest")

        src_project = match[0][1]
        src_lang = match[0][0]
        src_filename = src_url.split('/')[-1]
        src_fileext = src_filename.split('.')[-1]

        # Downloading the source file and getting saved file name
        # downloaded_filename = download_image(src_project, src_lang, src_filename)
        
        try:
            downloaded_filename = download_image(src_project, src_lang, src_filename)
            
        except FileNotFoundOnWikiError as exc:
            log.warning("Source file not found on wiki",
                        extra={"src_filename": exc.src_filename})
            return error_response(str(exc), 404, "FileNotFoundOnWikiError")
        
        except ImageDownloadError as exc:
            log.error("Failed to download source image", exc_info=True,
                    extra={"src_filename": exc.src_filename})
            return error_response(str(exc), 502, "ImageDownloadError")
        
        except APIRequestError as exc:
            log.error("API error while fetching source image", exc_info=True,
                    extra={"url": exc.url, "status_code": exc.status_code})
            return error_response(str(exc), 502, "APIRequestError")

        # Getting Target Details
        # tr_project = data.get('trproject')
        # tr_lang = data.get('trlang')
        # tr_filename = data.get('trfilename')
        # tr_filename = urllib.parse.unquote(tr_filename)
        # tr_endpoint = "https://" + tr_lang + "." + tr_project + ".org/w/api.php"
        
        tr_project  = data.get("trproject")
        tr_lang     = data.get("trlang")
        tr_filename = urllib.parse.unquote(data.get("trfilename", ""))

        if not all([tr_project, tr_lang, tr_filename]):
            log.warning("Upload request missing target fields",
                        extra={"tr_project": tr_project, "tr_lang": tr_lang, "tr_filename": tr_filename})
            return error_response("Missing target project, language, or filename", 400, "InvalidRequest")

        tr_endpoint = f"https://{tr_lang}.{tr_project}.org/w/api.php"

        # Authenticate Session
        ses = authenticated_session()
        
        if ses is None:
            log.warning("Upload attempted without authentication")
            return error_response("Not authenticated", 401, "AuthenticationError")

        log.info("Downloading source file", extra={"src_filename": src_filename, "src_lang": src_lang})

        # Check whether we have enough data or not
        if None not in (downloaded_filename, tr_filename, src_fileext, ses):
            file_path = 'temp_images/' + downloaded_filename
            file_size = os.path.getsize(file_path)
            
            if file_size < 0:
                log.error("Downloaded file has invalid size", extra={"file_path": file_path, "file_size": file_size})
                safe_delete_temp_file(file_path)
                return error_response("Downloaded file is invalid", 502, "ImageDownloadError")

            if file_size < 50 * 1024 * 1024:  # 50 MB
                log.info("Processing upload synchronously", extra={"file_path": file_path, "tr_filename": tr_filename})
                
                # Process synchronously
                # resp = process_upload(file_path, tr_filename, src_fileext, tr_endpoint, ses)
                # if resp is None:
                #     return jsonify({"success": False, "data": {}, "errors": ["Upload failed"]}), 500
                
                try:
                    resp = process_upload(file_path, tr_filename, src_fileext, tr_endpoint, ses)
                
                except CSRFTokenError as exc:
                    log.error("CSRF token error during upload", exc_info=True)
                    return error_response(str(exc), 502, "CSRFTokenError")
                
                except UploadError as exc:
                    log.error("Upload failed", exc_info=True,
                            extra={"tr_filename": exc.filename, "reason": exc.reason})
                    return error_response(str(exc), 502, "UploadError")
                
                except APIRequestError as exc:
                    log.error("API error during upload", exc_info=True,
                            extra={"url": exc.url, "status_code": exc.status_code})
                    return error_response(str(exc), 502, "APIRequestError")

                resp["source"] = src_url
                log.info("Synchronous upload completed", extra={"tr_filename": tr_filename})
                return success_response(resp, 200)

                # return jsonify({
                #     "success": True,
                #     "data": resp,
                #     "errors": []
                # }), 200
            else:
                log.info("Processing upload asynchronously", extra={"file_path": file_path, "tr_filename": tr_filename})
                
                # Process asynchronously using Celery
                try:
                    OAuthObj = {
                        "consumer_key":    CONSUMER_KEY,
                        "consumer_secret": CONSUMER_SECRET,
                        "key":    session["mwoauth_access_token"]["key"],
                        "secret": session["mwoauth_access_token"]["secret"],
                    }
                except KeyError as exc:
                    log.error("OAuth session token missing for async upload", exc_info=True)
                    return error_response("OAuth session data is missing", 401, "AuthenticationError")
                
                task = upload_image_task.delay(file_path, tr_filename, src_fileext, tr_endpoint, OAuthObj)
                log.info("Async upload task queued", extra={"task_id": task.id, "tr_filename": tr_filename})
                return success_response({"task_id": task.id}, 202)
        else:
            # return jsonify({"success": False, "data": {}, "errors": ["Not enough data"]}), 400
            return error_response("Not enough data", 400)
    else:
        # return jsonify({"success": False, "data": {}, "errors": ["Invalid Request"]}), 400
        return error_response("Invalid Request", 400)


@app.route('/api/preference', methods = ['GET', 'POST'])
def preference():

    if request.method == 'GET':
        user = db_user()
        
        log.info("Fetching user preferences",
                 extra={"username": MW_OAUTH.get_current_user(True)})
        
        return success_response({
            "project":               user.pref_project          if user else "wikipedia",
            "lang":                  user.pref_language         if user else "en",
            "skip_upload_selection": user.skip_upload_selection if user else False,
        })

        # user_project = "wikipedia"
        # user_lang = "en"
        # skip_upload_selection = False

        # if user is not None:
        #     user_project = user.pref_project
        #     user_lang = user.pref_language
        #     skip_upload_selection = user.skip_upload_selection
            
        # return jsonify(
        #     {
        #         "success": True,
        #         "data": {
        #             "project": user_project,
        #             "lang": user_lang,
        #             "skip_upload_selection": skip_upload_selection
        #         },
        #         "error": []
        #     }), 200

    elif request.method == 'POST':
        # Get the data
        data = request.get_json(silent = True)
        if not data:
            log.warning("Preference POST received with no JSON body")
            return error_response("Request body must be JSON", 400, "InvalidRequest")
        
        project = data.get('project')
        lang = data.get('lang')
        skip_upload_selection = data.get('skip_upload_selection')

        # Add into database
        cur_username = MW_OAUTH.get_current_user(True)
        user = User.query.filter_by(username=cur_username).first()
        
        log.info("Saving user preferences", extra={"username": cur_username})

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
        except:
            db.session.rollback()
            log.error("Database error saving preferences", exc_info=True,
                      extra={"username": cur_username})
            return error_response("Database error saving preferences", 500, "DatabaseError")

    else:
        return error_response("Method not allowed", 400, "Invalid Request")


@app.route('/api/user_language', methods=['GET', 'POST'])
def languagePreference():
    if request.method == 'GET':
        user = db_user()
        
        log.info("Fetching language preference", extra={"username": MW_OAUTH.get_current_user(True)})
        return success_response({
            "user_language": user.user_language if user else "en"
        })

        # user_language = "en"  # Default language
        # if user is not None:
        #     user_language = user.user_language

        # return jsonify(
        #     {
        #         "success": True,
        #         "data": {
        #             "user_language": user_language
        #         },
        #         "error": []
        #     }), 200

    elif request.method == 'POST':
        data = request.get_json(silent=True)
        if not data:
            log.warning("Language preference POST received with no JSON body")
            return error_response("Request body must be JSON", 400, "InvalidRequest")
        
        user_language = data.get('user_language')

        cur_username = MW_OAUTH.get_current_user(True)
        
        log.info("Saving language preference",extra={"username": cur_username, "user_language": user_language})
        
        user = User.query.filter_by(username=cur_username).first()

        if user is None:
            user = User(username=cur_username, user_language=user_language)
            db.session.add(user)
        else:
            user.user_language = user_language

        try:
            db.session.commit()
            log.info("Language preference saved")
            # return jsonify({ "success": True, "data": {}, "errors": []}), 200
            return success_response()
        except:
            db.session.rollback()
            log.error("Database error saving language preference")
            return error_response("Database error saving language preference", 500, "DatabaseError")
            # return jsonify({ "success": False, "data": {}, "errors": ["Database Error"]}), 500

    else:
        # return jsonify({ "success": False, "data": {}, "errors": ["Invalid Request"]}), 400
        return error_response("Method not allowed", 405, "InvalidRequest")


@app.route('/api/get_wikitext', methods=['GET'])
def get_wikitext():
    src_lang = request.args.get('src_lang')
    src_project = request.args.get('src_project')
    src_filename = request.args.get('src_filename')
    tr_lang = request.args.get('tr_lang')

    # In any case, return the strings only with 200 status code
    if not all([src_lang, src_project, src_filename, tr_lang]):
        log.warning("get_wikitext called with missing parameters",
                    extra={"src_lang": src_lang, "src_project": src_project,
                           "src_filename": src_filename, "tr_lang": tr_lang})
        # return jsonify({"wikitext": ""}), 200
        return success_response({"wikitext": ""})

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
    log.info("Fetching wikitext",
             extra={"src_filename": src_filename, "tr_lang": tr_lang})
    try:
        response = requests.get(src_endpoint, params=content_params)
        response.raise_for_status()

        page_data = response.json().get("query", {}).get("pages", [])

        if page_data and page_data[0].get("revisions"):
            wikitext = page_data[0]["revisions"][0]["slots"]["main"]["content"]
            wikitext = get_localized_wikitext(wikitext, src_endpoint, tr_lang)

            # return jsonify({"wikitext": wikitext}), 200
            log.info("Wikitext fetched and localised successfully", 
                     extra={"src_filename": src_filename, "tr_lang": tr_lang})
            
            return success_response({"wikitext": wikitext})
        else:
            # return jsonify({"wikitext": ""}), 200
            return success_response({"wikitext": ""})
    except:
        # return jsonify({"wikitext": ""}), 200
        log.error("HTTP error fetching wikitext", exc_info=True,
                  extra={"src_endpoint": src_endpoint})
        return success_response({"wikitext": ""})
    


@app.route('/api/edit_page', methods=['POST'])
def editPage():
    if request.method == 'POST':
        data = request.get_json(silent=True)
        if not data:
            log.warning("edit_page received with no JSON body")
            return error_response("Request body must be JSON", 400, "InvalidRequest")
        
        targetUrl = data.get('targetUrl')
        content = data.get('content')
        
        if not targetUrl or content is None:
            log.warning("edit_page missing required fields", extra={"target_url": targetUrl,
                            "content_present": content is not None})
            return error_response("targetUrl and content are required", 400, "InvalidRequest")

        match = re.findall(r"(\w+)\.(\w+)\.org/wiki/", targetUrl)
        
        if not match:
            return error_response("Could not parse targetUrl", 400, "InvalidRequest")

        target_project = match[0][1]
        target_lang = match[0][0]
        target_filename = targetUrl.split('/')[-1]

        target_endpoint = "https://" + target_lang + "." + target_project + ".org/w/api.php"

        # Authenticate Session
        ses = authenticated_session()
        if ses is None:
            log.warning("edit_page attempted without authentication")
            return error_response("Not authenticated", 401, "AuthenticationError")

        # API Parameter to get CSRF Token
        # csrf_param = {
        #     "action": "query",
        #     "meta": "tokens",
        #     "format": "json"
        # }

        # response = requests.get(url=target_endpoint, params=csrf_param, auth=ses)
        # csrf_token = response.json()["query"]["tokens"]["csrftoken"]
        try:
            csrf_token = _fetch_csrf_token(target_endpoint, ses)
        except CSRFTokenError as exc:
            log.error("Could not obtain CSRF token", exc_info=True)
            return error_response(str(exc), 502, "CSRFTokenError")

        # API Parameters to edit the page
        edit_params = {
            "action": "edit",
            "title": "File:" + target_filename.split(':')[1],
            "token": csrf_token,
            "format": "json",
            "appendtext": content
        }

        log.info("Submitting page edit", extra={"target_filename": target_filename})
        
        # try:
        #     response = requests.post(url=target_endpoint, data=edit_params, auth=ses)
        #     response.raise_for_status()
            # if response.status_code == 200:
        #     return success_response()
            # else:
            #     return error_response("Edit Error", 500, "EditError")
        # except:
        #     log.error("Error occurred while submitting page edit", exc_info=True, extra={"target_filename": target_filename})
        #     return error_response("Error occurred while submitting page edit", 502, "EditError")
        try:
            response = requests.post(url=target_endpoint, data=edit_params, auth=ses)
            response.raise_for_status()
        except requests.HTTPError as exc:
            log.error("HTTP error editing page", exc_info=True)
            return error_response(str(exc), 502, "APIRequestError")
        except requests.RequestException as exc:
            log.error("Network error editing page", exc_info=True)
            return error_response(str(exc), 502, "APIRequestError")
        
        return success_response()

        # if response.status_code == 200:
        #     # return jsonify({ "success": True, "data": {}, "errors": []}), 200
        #     return success_response()
        # else:
        #     # return jsonify({ "success": False, "data": {}, "errors": ["Edit Error"]}), 500
        #     return error_response("Edit Error", 500, "EditError")

    else:
        return error_response("Method not allowed", 405, "InvalidRequest")


@app.route('/api/user', methods=['GET'])
def get_base_variables():
    # return jsonify({
    #     "logged": logged() is not None,
    #     "username": MW_OAUTH.get_current_user(True)
    # }), 200
    return success_response({
        "logged": logged() is not None,
        "username": MW_OAUTH.get_current_user(True)
    })


@app.route('/api/task_status/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """
    Endpoint to get the status and result of a Celery task.
    """
    try:
        task = AsyncResult(task_id, app=celery_app)
        status = task.status
    except Exception as exc:
        log.error("Could not retrieve task status", exc_info=True,
                  extra={"task_id": task_id})
        return error_response(f"Could not retrieve task status: {exc}", 500, "TaskLookupError")

    body = {"task_id": task_id, "status": status}
    
    if task.successful():
        body.update(task.result)
        
    elif task.failed():
        body["error"] = str(task.result)
        body["error_type"] = type(task.result).__name__

    return success_response(body)
    
    # task = AsyncResult(task_id, app=celery_app)
    # response = {
    #     "task_id": task_id,
    #     "status": task.status,
    #     "result": task.result if task.successful() else None,
    # }
    
    # If task failed, include error information
    # if task.failed():
    #     response["error"] = str(task.result)

    # return jsonify(response), 200
    # return success_response(response)


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


if __name__ == "__main__":
    app.run()
