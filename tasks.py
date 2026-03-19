from celeryWorker import app
import logging
import requests
import requests_oauthlib
import os

logger = logging.getLogger(__name__)


@app.task(bind=True)
def upload_image_task(self, file_path, tr_filename, src_fileext, tr_endpoint, OAuthObj):
    ses = requests_oauthlib.OAuth1(
        client_key=OAuthObj["consumer_key"],
        client_secret=OAuthObj["consumer_secret"],
        resource_owner_key=OAuthObj["key"],
        resource_owner_secret=OAuthObj["secret"]
    )
    self.update_state(state='PROGRESS', meta={'current': 0, 'total': 100})

    # API Parameter to get CSRF Token
    csrf_param = {
        "action": "query",
        "meta": "tokens",
        "format": "json"
    }

    try:
        response = requests.get(url=tr_endpoint, params=csrf_param, auth=ses, timeout=30)
        response.raise_for_status()
        csrf_token = response.json()["query"]["tokens"]["csrftoken"]
    except Exception as e:
        logger.error("upload_image_task: failed to fetch CSRF token from %s: %s", tr_endpoint, e)
        return {"success": False, "data": {}, "errors": ["Failed to get upload token"]}

    self.update_state(state='PROGRESS', meta={'current': 25, 'total': 100})

    # API Parameter to upload the file
    upload_param = {
        "action": "upload",
        "filename": tr_filename + "." + src_fileext,
        "format": "json",
        "token": csrf_token,
        "ignorewarnings": 1
    }

    # Read the file for POST request
    try:
        with open(file_path, 'rb') as f:
            file = {'file': f}
            response = requests.post(url=tr_endpoint, files=file, data=upload_param, auth=ses, timeout=120).json()
    except Exception as e:
        logger.error("upload_image_task: file upload POST failed for %s: %s", file_path, e)
        return {"success": False, "data": {}, "errors": ["Upload request failed"]}

    self.update_state(state='PROGRESS', meta={'current': 75, 'total': 100})

    # Try block to get Link and URL
    try:
        wikifile_url = response["upload"]["imageinfo"]["descriptionurl"]
        file_link = response["upload"]["imageinfo"]["url"]
    except KeyError:
        logger.error("upload_image_task: unexpected upload response structure: %s", response)
        return {"success": False, "data": {}, "errors": ["Upload failed"]}

    self.update_state(state='PROGRESS', meta={'current': 100, 'total': 100})

    return {
        "wikipage_url": wikifile_url,
        "file_link": file_link
    }
