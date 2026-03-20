from celeryWorker import app
import requests
import requests_oauthlib
import os
import logging

# Set up logging with better configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def fail(task_self, message):
    """Helper function to standardize failure responses with proper state updates."""
    task_self.update_state(state='FAILURE', meta={'current': 100, 'total': 100})
    return {"success": False, "data": {}, "errors": [message]}

@app.task(bind=True)
def upload_image_task(self, file_path, tr_filename, src_fileext, tr_endpoint, OAuthObj):
    # Validate OAuth credentials first
    if not all(k in OAuthObj for k in ["consumer_key", "consumer_secret", "key", "secret"]):
        return fail(self, "Missing or invalid OAuth credentials")
    
    # Validate file exists before processing
    if not os.path.exists(file_path):
        return fail(self, "File not found")
    
    try:
        ses = requests_oauthlib.OAuth1(
            client_key=OAuthObj["consumer_key"],
            client_secret=OAuthObj["consumer_secret"],
            resource_owner_key=OAuthObj["key"],
            resource_owner_secret=OAuthObj["secret"]
        )
        self.update_state(state='PROGRESS', meta={'current': 0, 'total': 100})
        logger.info(f"Starting upload task | file={file_path} | endpoint={tr_endpoint}")
        
        # API Parameter to get CSRF Token
        csrf_param = {
            "action": "query",
            "meta": "tokens",
            "format": "json"
        }

        response = requests.get(url=tr_endpoint, params=csrf_param, auth=ses, timeout=30)
        response.raise_for_status()  # Raise exception for bad status codes
        
        # Store JSON data to avoid repeated parsing
        try:
            csrf_data = response.json()
            csrf_token = csrf_data["query"]["tokens"]["csrftoken"]
        except (ValueError, KeyError) as e:
            logger.error(f"Failed to parse CSRF token response: {e}")
            return fail(self, "Failed to obtain CSRF token")

        self.update_state(state='PROGRESS', meta={'current': 25, 'total': 100})
        logger.info("CSRF token obtained successfully")

        # API Parameter to upload the file
        upload_param = {
            "action": "upload",
            "filename": f"{tr_filename}.{src_fileext}",
            "format": "json",
            "token": csrf_token,
            "ignorewarnings": 1
        }

        # Read the file for POST request using with statement to prevent leaks
        try:
            with open(file_path, 'rb') as file_handle:
                files = {'file': file_handle}
                response = requests.post(url=tr_endpoint, files=files, data=upload_param, auth=ses, timeout=120)
                response.raise_for_status()
                
                # Store JSON data to avoid repeated parsing
                try:
                    upload_response = response.json()
                except ValueError as e:
                    logger.error(f"Failed to parse upload response as JSON: {e}")
                    return fail(self, "Invalid response from upload API")
        except IOError as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return fail(self, "Failed to read file for upload")

        self.update_state(state='PROGRESS', meta={'current': 75, 'total': 100})
        logger.info(f"Upload successful for file: {tr_filename}")

        # Basic response validation - check if upload key exists (more defensive)
        upload_data = upload_response.get("upload")
        if not upload_data:
            logger.error(f"Unexpected response structure: {upload_response}")
            return fail(self, "Upload failed - unexpected response structure")

        # Safely extract imageinfo and validate required fields (true defensive coding)
        imageinfo = upload_data.get("imageinfo")
        if not imageinfo:
            logger.error(f"Missing imageinfo in response: {upload_response}")
            return fail(self, "Upload failed - missing image info")

        wikifile_url = imageinfo.get("descriptionurl")
        file_link = imageinfo.get("url")

        if not wikifile_url or not file_link:
            logger.error(f"Incomplete image info in response: {upload_response}")
            return fail(self, "Upload failed - incomplete image info")

        self.update_state(state='PROGRESS', meta={'current': 100, 'total': 100})
        logger.info("Upload task completed successfully")

        return {
            "success": True,
            "data": {
                "wikipage_url": wikifile_url,
                "file_link": file_link
            },
            "errors": []
        }
    
    except requests.exceptions.Timeout as e:
        logger.error(f"Request timed out for endpoint {tr_endpoint}: {e}")
        return fail(self, "Request timed out")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed for endpoint {tr_endpoint}: {e}")
        return fail(self, "API request failed")
    except Exception as e:
        logger.exception("Unexpected error occurred")
        return fail(self, "Unexpected error occurred")
    finally:
        # Clean up temp file
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Cleaned up temp file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete temp file: {e}")