from celeryWorker import app
import requests
import requests_oauthlib
from logger import log_exception,log_info
from exceptions import operation_success, operation_failure, upload_error
from utils import cleanup_temp_file

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
        
        csrf_param = {
            "action": "query",
            "meta": "tokens",
            "format": "json"
        }

        response = requests.get(url=tr_endpoint, params=csrf_param, auth=ses)
        csrf_token = response.json()["query"]["tokens"]["csrftoken"]

        self.update_state(state='PROGRESS', meta={'current': 25, 'total': 100})

        upload_param = {
            "action": "upload",
            "filename": tr_filename + "." + src_fileext,
            "format": "json",
            "token": csrf_token,
            "ignorewarnings": 1
        }

        with open(file_path, 'rb') as file_handle:
            file = {
                'file': file_handle
            }
            response = requests.post(url=tr_endpoint, files=file, data=upload_param, auth=ses).json()

        log_info("Upload response for %s: %s", tr_filename, response)

        self.update_state(state='PROGRESS', meta={'current': 75, 'total': 100})

        try:
            wikifile_url = response["upload"]["imageinfo"]["descriptionurl"]
            file_link = response["upload"]["imageinfo"]["url"]
        except KeyError:
            log_exception("Failed to retrieve upload results for %s", tr_filename)
            return operation_failure(upload_error(f"Unable to parse async upload response for {tr_filename}"))

        self.update_state(state='PROGRESS', meta={'current': 100, 'total': 100})

        return operation_success({
            "wikipage_url": wikifile_url,
            "file_link": file_link
        })
    finally:
        cleanup_result = cleanup_temp_file(file_path)
        if not cleanup_result.get("ok"):
            log_exception("Failed to cleanup temporary file in async task: %s", file_path)
