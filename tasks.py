from celeryWorker import app
import logging
import requests
import requests_oauthlib
import os
from utils import get_headers, cleanup_temp_file

logger = logging.getLogger(__name__)

@app.task(bind=True)
def upload_image_task(self, file_path, tr_filename, src_fileext, tr_endpoint, OAuthObj):
    try:
        ses = requests_oauthlib.OAuth1(
            client_key=OAuthObj["consumer_key"],
            client_secret= OAuthObj["consumer_secret"],
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

        response = requests.get(url=tr_endpoint, params=csrf_param, auth=ses, headers=get_headers(), timeout=30)
        response.raise_for_status()

        try:
            csrf_token = response.json()["query"]["tokens"]["csrftoken"]
        except KeyError:
            logger.error(f"Failed to get CSRF token from {tr_endpoint}")
            return {"success": False, "data": {}, "errors": ["Failed to get CSRF token"]}

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
        with open(file_path, 'rb') as file:
            response = requests.post(
                url = tr_endpoint,
                files = {'file': file},
                data = upload_param,
                auth = ses,
                headers = get_headers(),
                timeout=120
            )
        response.raise_for_status()
        result = response.json()

        self.update_state(state='PROGRESS', meta={'current': 75, 'total': 100})

        if "error" in result:
            logger.error(f"MediaWiki upload error: {result['error']}")
            return {"success": False, "data": {}, "errors": [result["error"].get("info", "Upload failed")]}

        # Try block to get Link and URL
        try:
            wikifile_url = result["upload"]["imageinfo"]["descriptionurl"]
            file_link = result["upload"]["imageinfo"]["url"]
        except KeyError:
            return {"success": False, "data": {}, "errors": ["Unexpected response from wiki"]}

        self.update_state(state='PROGRESS', meta={'current': 100, 'total': 100})

        return {
            "wikipage_url": wikifile_url,
            "file_link": file_link
        }
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error during upload tasks to {tr_endpoint}: {e}")
        return {"success": False, "data": {}, "errors": [f"Network error: {str(e)}"]}
    except Exception as e:
        logger.error(f"Unexpected error in upload task: {e}", exc_info=True)
        return {"success": False, "data": {}, "errors": [f"Unexpected error: {str(e)}"]}
    finally:
        cleanup_temp_file(file_path)


