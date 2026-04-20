from celeryWorker import app
import requests
import requests_oauthlib
import os

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

        try:
            response = requests.get(url=tr_endpoint, params=csrf_param, auth=ses)
            response.raise_for_status()
            csrf_token = response.json()["query"]["tokens"]["csrftoken"]
        except (requests.exceptions.RequestException, KeyError, ValueError) as e:
            return {"success": False, "data": {}, "errors": [f"Failed to fetch CSRF Token: {str(e)}"]}

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
        try:
            with open(file_path, 'rb') as f:
                file = {'file': f}
                response = requests.post(url=tr_endpoint, files=file, data=upload_param, auth=ses)
                response.raise_for_status()
                resp_json = response.json()
        except (requests.exceptions.RequestException, ValueError, IOError) as e:
            return {"success": False, "data": {}, "errors": [f"Failed to upload file: {str(e)}"]}

        self.update_state(state='PROGRESS', meta={'current': 75, 'total': 100})

        # Try block to get Link and URL
        try:
            wikifile_url = resp_json["upload"]["imageinfo"]["descriptionurl"]
            file_link = resp_json["upload"]["imageinfo"]["url"]
        except KeyError:
            return {"success": False, "data": {}, "errors": ["Upload failed: Invalid response format from Wikimedia"]}

        self.update_state(state='PROGRESS', meta={'current': 100, 'total': 100})

        return {
            "wikipage_url": wikifile_url,
            "file_link": file_link
        }
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
