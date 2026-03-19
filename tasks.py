from celeryWorker import app
import requests
import requests_oauthlib
import os
import logging
from exceptions import UploadError, MediaWikiAPIError, TaskError
from utils_helper import _safe_remove_temp

logger = logging.getLogger(__name__)

@app.task(bind=True)
def upload_image_task(self, file_path, tr_filename, src_fileext, tr_endpoint, OAuthObj):
    try:
        # Validate file exists
        if not os.path.exists(file_path):
            raise UploadError(f"File not found: {file_path}")

        ses = requests_oauthlib.OAuth1(
            client_key=OAuthObj["consumer_key"],
            client_secret=OAuthObj["consumer_secret"],
            resource_owner_key=OAuthObj["key"],
            resource_owner_secret=OAuthObj["secret"]
        )
        
        # Update task state
        try:
            self.update_state(state='PROGRESS', meta={'current': 0, 'total': 100})
        except Exception:
            pass  # Silently continue if update fails

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
        except (requests.exceptions.RequestException, KeyError) as e:
            logger.error("Failed to get CSRF token", exc_info=True, extra={
                "tr_endpoint": tr_endpoint,
                "error": str(e)
            })
            raise MediaWikiAPIError(f"Failed to get CSRF token: {str(e)}")

        try:
            self.update_state(state='PROGRESS', meta={'current': 25, 'total': 100})
        except Exception:
            pass

        # API Parameter to upload the file
        upload_param = {
            "action": "upload",
            "filename": tr_filename + "." + src_fileext,
            "format": "json",
            "token": csrf_token,
            "ignorewarnings": 1
        }

        try:
            with open(file_path, 'rb') as f:
                file = {'file': f}
                response = requests.post(url=tr_endpoint, files=file, data=upload_param, auth=ses, timeout=120)
                response.raise_for_status()
                result = response.json()
        except (IOError, requests.exceptions.RequestException) as e:
            logger.error("Upload request failed", exc_info=True, extra={
                "tr_endpoint": tr_endpoint,
                "tr_filename": tr_filename,
                "error": str(e)
            })
            raise UploadError(f"Upload request failed: {str(e)}")

        try:
            self.update_state(state='PROGRESS', meta={'current': 75, 'total': 100})
        except Exception:
            pass

        # Try block to get Link and URL
        try:
            wikifile_url = result["upload"]["imageinfo"]["descriptionurl"]
            file_link = result["upload"]["imageinfo"]["url"]
        except KeyError as e:
            logger.error("Missing expected keys in upload response", exc_info=True, extra={
                "response_keys": list(result.keys()) if isinstance(result, dict) else str(type(result))
            })
            raise UploadError("Upload response missing required data")

        try:
            self.update_state(state='PROGRESS', meta={'current': 100, 'total': 100})
        except Exception:
            pass

        logger.info("Upload task completed successfully", extra={
            "tr_filename": tr_filename,
            "wikifile_url": wikifile_url
        })

        return {
            "wikipage_url": wikifile_url,
            "file_link": file_link
        }
        
    except (UploadError, MediaWikiAPIError) as e:
        logger.error("Upload task failed with application error", exc_info=True, extra={
            "error_type": e.__class__.__name__,
            "error_message": str(e)
        })
        raise TaskError(f"Image upload failed: {str(e)}")
    except Exception as e:
        logger.exception("Unexpected error in upload task")
        raise TaskError(f"Unexpected error during upload: {str(e)}")
    finally:
        # Clean up temp file if it exists
        try:
            _safe_remove_temp(file_path)
            logger.debug("Cleaned up temporary file", extra={"file_path": file_path})
        except Exception as e:
            logger.warning("Failed to clean up temporary file", extra={
                "file_path": file_path,
                "error": str(e)
            })
