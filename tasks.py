from celeryWorker import app
import requests
import requests_oauthlib
import logging
import os

# logger
logger = logging.getLogger(__name__)


@app.task(bind=True)
def upload_image_task(self, file_path, tr_filename, src_fileext, tr_endpoint, OAuthObj):
    try:
        ses = requests_oauthlib.OAuth1(
            client_key=OAuthObj["consumer_key"],
            client_secret=OAuthObj["consumer_secret"],
            resource_owner_key=OAuthObj["key"],
            resource_owner_secret=OAuthObj["secret"]
        )

        self.update_state(state='PROGRESS', meta={'current': 0, 'total': 100})

        csrf_param = {
            "action": "query",
            "meta": "tokens",
            "format": "json"
        }

        response = requests.get(
            url=tr_endpoint,
            params=csrf_param,
            auth=ses,
            timeout=10
        )
        response.raise_for_status()

        csrf_token = response.json()["query"]["tokens"]["csrftoken"]

        self.update_state(state='PROGRESS', meta={'current': 25, 'total': 100})

        # file upload
        upload_param = {
            "action": "upload",
            "filename": tr_filename + "." + src_fileext,
            "format": "json",
            "token": csrf_token,
            "ignorewarnings": 1
        }

        with open(file_path, 'rb') as f:
            files = {'file': f}

            response = requests.post(
                url=tr_endpoint,
                files=files,
                data=upload_param,
                auth=ses,
                timeout=30
            )
            response.raise_for_status()
            response = response.json()

        self.update_state(state='PROGRESS', meta={'current': 75, 'total': 100})

        #response data
        try:
            wikifile_url = response["upload"]["imageinfo"]["descriptionurl"]
            file_link = response["upload"]["imageinfo"]["url"]
        except KeyError:
            logger.error(f"Invalid upload response: {response}")
            return {
                "success": False,
                "data": {},
                "errors": ["Upload failed: Invalid API response"]
            }

        #cleanup 
        try:
            os.remove(file_path)
        except Exception as e:
            logger.warning(f"Failed to delete temp file: {e}")

        self.update_state(state='PROGRESS', meta={'current': 100, 'total': 100})

        return {
            "wikipage_url": wikifile_url,
            "file_link": file_link
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {e}")

        try:
            os.remove(file_path)
        except Exception:
            pass

        return {
            "success": False,
            "data": {},
            "errors": ["Network error during upload"]
        }

    except Exception as e:
        logger.error(f"Unexpected error: {e}")

        try:
            os.remove(file_path)
        except Exception:
            pass

        return {
            "success": False,
            "data": {},
            "errors": ["Unexpected error occurred"]
        }
