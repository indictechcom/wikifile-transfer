from celeryWorker import app
import requests
import requests_oauthlib
import os
import logging

@app.task(bind=True)
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

        response = requests.get(url=tr_endpoint, params=csrf_param, auth=ses)
        csrf_token = response.json()["query"]["tokens"]["csrftoken"]

        self.update_state(state='PROGRESS', meta={'current': 25, 'total': 100})

        # API Parameter to upload the file
        upload_param = {
            "action": "upload",
            "filename": tr_filename + "." + src_fileext,
            "format": "json",
            "token": csrf_token,
            "ignorewarnings": 1
        }

        # SAFE FILE HANDLING
        with open(file_path, 'rb') as f:
            file = {'file': f}

            response = requests.post(
                url=tr_endpoint,
                files=file,
                data=upload_param,
                auth=ses
            ).json()

        self.update_state(state='PROGRESS', meta={'current': 75, 'total': 100})

        # Try block to get Link and URL
        try:
            wikifile_url = response["upload"]["imageinfo"]["descriptionurl"]
            file_link = response["upload"]["imageinfo"]["url"]
        except KeyError:
            return {"success": False, "data": {}, "errors": ["Upload failed"]}

        self.update_state(state='PROGRESS', meta={'current': 100, 'total': 100})

        return {
            "wikipage_url": wikifile_url,
            "file_link": file_link
        }

    finally:
        # ALWAYS CLEAN TEMP FILE
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logging.info(f"Deleted temp file: {file_path}")
            except Exception as e:
                logging.error(f"Error deleting temp file {file_path}: {e}")