from celeryWorker import app as celery_app
import requests
import requests_oauthlib
import os
import logging
from exceptions import UploadError
from logging_config import get_logger

# Task logger
logger = get_logger(__name__)

@celery_app.task(bind=True)
def upload_image_task(self, file_path, tr_filename, src_fileext, tr_endpoint, OAuthObj):
    ses = requests_oauthlib.OAuth1(
        client_key=OAuthObj["consumer_key"],
        client_secret=OAuthObj["consumer_secret"],
        resource_owner_key=OAuthObj["key"],
        resource_owner_secret=OAuthObj["secret"]
    )
    self.update_state(state='PROGRESS', meta={'current': 0, 'total': 100})
    
    try:
        # API Parameter to get CSRF Token
        csrf_param = {
            "action": "query",
            "meta": "tokens",
            "format": "json"
        }

        try:
            response = requests.get(url=tr_endpoint, params=csrf_param, auth=ses)
            response.raise_for_status()
            csrf_token = response.json()["query"]["tokens"]["csrftoken"]
        except Exception as e:
            raise UploadError(f"Failed to fetch CSRF token: {str(e)}")

        self.update_state(state='PROGRESS', meta={'current': 25, 'total': 100})

        # API Parameter to upload the file
        upload_param = {
            "action": "upload",
            "filename": tr_filename + "." + src_fileext,
            "format": "json",
            "token": csrf_token,
            "ignorewarnings": 1
        }

        # Read the file for POST request with proper handle closure
        try:
            with open(file_path, "rb") as f:
                file_data = {'file': f}     
                response_json = requests.post(url=tr_endpoint, files=file_data, data=upload_param, auth=ses).json()
        except Exception as e:
            raise UploadError(f"Upload connection failed: {str(e)}")

        self.update_state(state='PROGRESS', meta={'current': 75, 'total': 100})

        # Try block to get Link and URL
        try:
            wikifile_url = response_json["upload"]["imageinfo"]["descriptionurl"]
            file_link = response_json["upload"]["imageinfo"]["url"]
        except KeyError:
            error_info = response_json.get("error", {}).get("info", "Unknown Wikimedia error")
            raise UploadError(error_info)
                
        self.update_state(state='PROGRESS', meta={'current': 100, 'total': 100})

        return {
            "wikipage_url": wikifile_url,
            "file_link": file_link
        }
    except Exception as e:
        logger.error(f"Async task failed: {str(e)}")
        # Raise so Celery captures it as FAILURE
        raise e
    finally:
        # Guarantee that the file is removed from disk even if task crashes
        if os.path.exists(file_path):
            os.remove(file_path)
