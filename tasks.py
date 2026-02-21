import logging
import requests
import requests_oauthlib
from celeryWorker import app

logger = logging.getLogger(__name__)


@app.task(bind=True)
def upload_image_task(self, file_path, tr_filename, src_fileext, tr_endpoint, OAuthObj):
    ses = requests_oauthlib.OAuth1(
        client_key=OAuthObj["consumer_key"],
        client_secret=OAuthObj["consumer_secret"],
        resource_owner_key=OAuthObj["key"],
        resource_owner_secret=OAuthObj["secret"]
    )

    self.update_state(state="PROGRESS", meta={"current": 0, "total": 100})

    csrf_param = {
        "action": "query",
        "meta": "tokens",
        "format": "json"
    }

    try:
        response = requests.get(url=tr_endpoint, params=csrf_param, auth=ses, timeout=30)
        response.raise_for_status()
        csrf_token = response.json()["query"]["tokens"]["csrftoken"]
    except (KeyError, requests.RequestException) as e:
        logger.error("Failed to get CSRF token: %s", e)
        return {"success": False, "data": {}, "errors": ["Failed to get CSRF token"]}

    self.update_state(state="PROGRESS", meta={"current": 25, "total": 100})

    upload_param = {
        "action": "upload",
        "filename": tr_filename + "." + src_fileext,
        "format": "json",
        "token": csrf_token,
        "ignorewarnings": 1
    }

    try:
        with open(file_path, "rb") as f:
            response = requests.post(
                url=tr_endpoint,
                files={"file": f},
                data=upload_param,
                auth=ses,
                timeout=120
            ).json()
    except (OSError, requests.RequestException) as e:
        logger.error("Upload request failed: %s", e)
        return {"success": False, "data": {}, "errors": ["Upload request failed"]}

    self.update_state(state="PROGRESS", meta={"current": 75, "total": 100})

    try:
        wikifile_url = response["upload"]["imageinfo"]["descriptionurl"]
        file_link = response["upload"]["imageinfo"]["url"]
    except KeyError:
        logger.error("Unexpected upload response: %s", response)
        return {"success": False, "data": {}, "errors": ["Upload failed"]}

    self.update_state(state="PROGRESS", meta={"current": 100, "total": 100})

    return {
        "wikipage_url": wikifile_url,
        "file_link": file_link
    }
