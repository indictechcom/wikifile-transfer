from celeryWorker import app
from utils import _fetch_csrf_token, success_response, error_response, safe_delete_temp_file
import requests
import requests_oauthlib
from globalExceptions import CSRFTokenError, UploadError, OAuthConfigError
from logger import get_logger
 
log = get_logger(__name__)

_REQUIRED_OAUTH_KEYS = ("consumer_key", "consumer_secret", "key", "secret")

def _build_oauth_session(oauth_obj: dict) -> requests_oauthlib.OAuth1:
    missing = [k for k in _REQUIRED_OAUTH_KEYS if not oauth_obj.get(k)]
    if missing:
        raise OAuthConfigError(
            f"OAuth config is missing required keys: {missing}"
        )
    return requests_oauthlib.OAuth1(
        client_key=oauth_obj["consumer_key"],
        client_secret=oauth_obj["consumer_secret"],
        resource_owner_key=oauth_obj["key"],
        resource_owner_secret=oauth_obj["secret"],
    )
    
    
# def _error_result(exc: Exception) -> dict:
    
#     return {
#         "success":    False,
#         "error_type": type(exc).__name__,
#         "error":      str(exc),
#         "data":       {},
#     }


# def _fetch_csrf_token(endpoint: str, auth) -> str:
#     try:
#         response = requests.get(
#             url=endpoint,
#             params={"action": "query", "meta": "tokens", "format": "json"},
#             auth=auth,
#             timeout=30,
#         )
#         response.raise_for_status()
#         return response.json()["query"]["tokens"]["csrftoken"]
    
#     except requests.HTTPError as exc:
#         raise CSRFTokenError(
#             f"HTTP error fetching CSRF token from {endpoint!r}: {exc}"
#         ) from exc
    
#     except requests.RequestException as exc:
#         raise CSRFTokenError(
#             f"Network error fetching CSRF token from {endpoint!r}: {exc}"
#         ) from exc
    
#     except (KeyError, ValueError) as exc:
#         raise CSRFTokenError(
#             f"Unexpected response format when fetching CSRF token from {endpoint!r}: {exc}"
#         ) from exc


@app.task(bind=True)
def upload_image_task(self, file_path, tr_filename, src_fileext, tr_endpoint, OAuthObj):
    
    try:
        ses = _build_oauth_session(OAuthObj)
    except OAuthConfigError as exc:
        log.error("OAuth configuration error", exc_info=True, extra={"task_id": self.request.id})
        return error_response(str(exc), error_type="OAuthConfigError")
        
    
    log.info(
        "Starting image upload",
        extra={"task_id": self.request.id, "file_path": file_path, "tr_filename": tr_filename},
    )
    
    self.update_state(state='PROGRESS', meta={'current': 0, 'total': 100})
    
    try:
        csrf_token = _fetch_csrf_token(tr_endpoint, ses)
    except CSRFTokenError as exc:
        log.error("Could not obtain CSRF token", exc_info=True, extra={"task_id": self.request.id})
        safe_delete_temp_file(file_path)
        return error_response(str(exc), error_type="CSRFTokenError")
 
    log.debug("CSRF token acquired", extra={"task_id": self.request.id})
    
    # API Parameter to get CSRF Token
    # csrf_param = {
    #     "action": "query",
    #     "meta": "tokens",
    #     "format": "json"
    # }

    # response = requests.get(url=tr_endpoint, params=csrf_param, auth=ses)
    # csrf_token = response.json()["query"]["tokens"]["csrftoken"]

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
    # file = {
    #     'file': open(file_path, 'rb')
    # }

    # response = requests.post(url=tr_endpoint, files=file, data=upload_param, auth=ses).json()
 
    try:
        with open(file_path, "rb") as fh:
            response = requests.post(
                url=tr_endpoint,
                files={"file": fh},
                data=upload_param,
                auth=ses,
                timeout=120,
            )
        response.raise_for_status()
        response_data = response.json()
        
    except FileNotFoundError as exc:
        log.error(
            "File to upload not found on disk",
            exc_info=True,
            extra={"task_id": self.request.id, "file_path": file_path},
        )
        return error_response(str(UploadError(tr_filename, f"Local file not found: {file_path}")), error_type="UploadError")
    
    except requests.HTTPError as exc:
        log.error(
            "HTTP error during upload",
            exc_info=True,
            extra={"task_id": self.request.id, "status_code": exc.response.status_code},
        )
        safe_delete_temp_file(file_path)
        return error_response(str(UploadError(tr_filename, str(exc))), error_type="UploadError")
    
    except requests.RequestException as exc:
        log.error("Network error during upload", exc_info=True, extra={"task_id": self.request.id})
        safe_delete_temp_file(file_path)
        raise self.retry(exc=exc)

    self.update_state(state='PROGRESS', meta={'current': 75, 'total': 100})

    # Try block to get Link and URL
    try:
        wikifile_url = response_data["upload"]["imageinfo"]["descriptionurl"]
        file_link = response_data["upload"]["imageinfo"]["url"]
        
    except KeyError as exc:
        api_error = (
            response_data.get("error", {}).get("info")
            or response_data.get("upload", {}).get("warnings")
            or f"Upload failed: {exc}"
        )
        log.error(
            "Upload API returned unexpected structure",
            extra={
                "task_id": self.request.id,
                "tr_filename": tr_filename,
                "missing_key": str(exc),
            },
        )
        safe_delete_temp_file(file_path)
        return error_response(
                str(UploadError(tr_filename, api_error)),
                error_type="UploadError")
        
    self.update_state(state='PROGRESS', meta={'current': 100, 'total': 100})
    
    log.info(
        "Image uploaded successfully",
        extra={"task_id": self.request.id, "tr_filename": tr_filename, "url": wikifile_url},
    )
    
    safe_delete_temp_file(file_path)
    
    return success_response({
        "wikipage_url": wikifile_url,
        "file_link": file_link
    })
    

    
