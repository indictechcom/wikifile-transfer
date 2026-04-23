from celeryWorker import app
import requests
import requests_oauthlib
import os
import logging

logger = logging.getLogger(__name__)


def cleanup_temp_file(file_path):
    """Safely remove a temporary file."""
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.info("Cleaned up temp file: %s", file_path)
    except OSError as e:
        logger.warning("Failed to clean up temp file %s: %s", file_path, e)


@app.task(bind=True)
def upload_image_task(self, file_path, tr_filename, src_fileext, tr_endpoint, OAuthObj):
    file_handle = None
    try:
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

        response = requests.get(url=tr_endpoint, params=csrf_param, auth=ses)
        response.raise_for_status()
        token_data = response.json()

        # Validate CSRF token response
        try:
            csrf_token = token_data["query"]["tokens"]["csrftoken"]
        except KeyError:
            logger.error("Failed to retrieve CSRF token. Response: %s", token_data)
            return {"success": False, "data": {}, "errors": ["Failed to retrieve CSRF token"]}

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
        file_handle = open(file_path, 'rb')
        file = {'file': file_handle}

        response = requests.post(url=tr_endpoint, files=file, data=upload_param, auth=ses)
        response.raise_for_status()
        result = response.json()

        self.update_state(state='PROGRESS', meta={'current': 75, 'total': 100})

        # Check for MediaWiki API-level error
        if "error" in result:
            error_code = result["error"].get("code", "unknown")
            error_info = result["error"].get("info", "No details provided")
            logger.error("MediaWiki upload error: [%s] %s", error_code, error_info)
            return {"success": False, "data": {}, "errors": [f"MediaWiki error: {error_info}"]}

        # Try block to get Link and URL
        try:
            wikifile_url = result["upload"]["imageinfo"]["descriptionurl"]
            file_link = result["upload"]["imageinfo"]["url"]
        except KeyError:
            upload_result = result.get("upload", {}).get("result", "unknown")
            logger.error("Upload response missing expected fields. Result: %s, Full response: %s",
                         upload_result, result)
            return {"success": False, "data": {}, "errors": ["Upload failed — unexpected response from wiki"]}

        self.update_state(state='PROGRESS', meta={'current': 100, 'total': 100})

        return {
            "wikipage_url": wikifile_url,
            "file_link": file_link
        }

    except requests.RequestException as e:
        logger.error("Network error during async upload to %s: %s", tr_endpoint, e)
        return {"success": False, "data": {}, "errors": [f"Network error: {str(e)}"]}
    except Exception as e:
        logger.error("Unexpected error in upload task: %s", e, exc_info=True)
        return {"success": False, "data": {}, "errors": [f"Unexpected error: {str(e)}"]}
    finally:
        # Close file handle if opened
        if file_handle is not None:
            file_handle.close()
        # Clean up temp file
        cleanup_temp_file(file_path)
