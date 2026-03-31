from celeryWorker import app
import requests
import requests_oauthlib
import os
from datetime import datetime


@app.task(bind=True)
def upload_image_task(self, file_path, tr_filename, src_fileext, tr_endpoint, OAuthObj):

    ses = requests_oauthlib.OAuth1(
        client_key=OAuthObj["consumer_key"],
        client_secret=OAuthObj["consumer_secret"],
        resource_owner_key=OAuthObj["key"],
        resource_owner_secret=OAuthObj["secret"]
    )

    # STARTED STATE
    self.update_state(state='STARTED', meta={
        "stage": "Initializing upload",
        "progress": 0,
        "started_at": str(datetime.utcnow())
    })

    try:
        # STEP 1: Get CSRF Token
        csrf_param = {
            "action": "query",
            "meta": "tokens",
            "format": "json"
        }

        response = requests.get(url=tr_endpoint, params=csrf_param, auth=ses)

        if response.status_code != 200:
            raise Exception("Failed to fetch CSRF token")

        csrf_token = response.json()["query"]["tokens"]["csrftoken"]

        # PROGRESS - 25%
        self.update_state(state='PROGRESS', meta={
            "stage": "Fetched CSRF token",
            "progress": 25
        })

        # STEP 2: Prepare upload params
        upload_param = {
            "action": "upload",
            "filename": tr_filename + "." + src_fileext,
            "format": "json",
            "token": csrf_token,
            "ignorewarnings": 1
        }

        # STEP 3: Upload file safely
        with open(file_path, 'rb') as f:
            file = {'file': f}

            response = requests.post(
                url=tr_endpoint,
                files=file,
                data=upload_param,
                auth=ses
            )

        if response.status_code != 200:
            raise Exception("Upload request failed")

        response = response.json()

        # PROGRESS - 75%
        self.update_state(state='PROGRESS', meta={
            "stage": "Uploading file",
            "progress": 75
        })

        # STEP 4: Extract response
        wikifile_url = response["upload"]["imageinfo"]["descriptionurl"]
        file_link = response["upload"]["imageinfo"]["url"]

        # PROGRESS - 100%
        self.update_state(state='PROGRESS', meta={
            "stage": "Upload completed",
            "progress": 100
        })

        return {
            "status": "SUCCESS",
            "data": {
                "wikipage_url": wikifile_url,
                "file_link": file_link
            },
            "completed_at": str(datetime.utcnow())
        }

    except Exception as e:
        # FAILURE STATE
        self.update_state(state='FAILURE', meta={
            "stage": "Upload failed",
            "error": str(e)
        })

        return {
            "status": "FAILED",
            "error": str(e)
        }
