from celeryWorker import app
import requests
import requests_oauthlib
import os

def get_headers():
    return {
        'User-Agent': 'Wikifile-transfer/1.0 (https://wikifile-transfer.toolforge.org; 0freerunning@gmail.com)'
    }

@app.task(bind=True)
def upload_image_task(self, file_path, tr_filename, src_fileext, tr_endpoint, OAuthObj):
    ses = requests_oauthlib.OAuth1(
        client_key=OAuthObj["consumer_key"],
        client_secret=OAuthObj["consumer_secret"],
        resource_owner_key=OAuthObj["key"],
        resource_owner_secret=OAuthObj["secret"]
    )

    self.update_state(state='PROGRESS', meta={'current': 0, 'total': 100})

    # Get CSRF Token
    csrf_param = {
        "action": "query",
        "meta": "tokens",
        "format": "json"
    }

    response = requests.get(
        url=tr_endpoint,
        params=csrf_param,
        auth=ses,
        headers=get_headers(),
        timeout=10
    )
    csrf_token = response.json()["query"]["tokens"]["csrftoken"]

    self.update_state(state='PROGRESS', meta={'current': 25, 'total': 100})

    # Upload file
    upload_param = {
        "action": "upload",
        "filename": tr_filename + "." + src_fileext,
        "format": "json",
        "token": csrf_token,
        "ignorewarnings": 1
    }

    file = {
        'file': open(file_path, 'rb')
    }

    response = requests.post(
        url=tr_endpoint,
        files=file,
        data=upload_param,
        auth=ses,
        headers=get_headers(),
        timeout=10
    ).json()

    self.update_state(state='PROGRESS', meta={'current': 75, 'total': 100})

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
