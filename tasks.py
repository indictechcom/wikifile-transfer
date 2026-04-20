from celeryWorker import app
import requests
import requests_oauthlib

@app.task(
    bind=True,
    autoretry_for=(requests.exceptions.RequestException,),
    retry_kwargs={'max_retries': 3},
    retry_backoff=True
)
def upload_image_task(self, file_path, tr_filename, src_fileext, tr_endpoint, OAuthObj):
    try:
        ses = requests_oauthlib.OAuth1(
            client_key=OAuthObj["consumer_key"],
            client_secret=OAuthObj["consumer_secret"],
            resource_owner_key=OAuthObj["key"],
            resource_owner_secret=OAuthObj["secret"]
        )

        headers = {
            'User-Agent': 'Wikifile-transfer/1.0 (https://wikifile-transfer.toolforge.org)'
        }

        self.update_state(state='PROGRESS', meta={'current': 0, 'total': 100})

        # Step 1: Get CSRF Token
        csrf_param = {
            "action": "query",
            "meta": "tokens",
            "format": "json"
        }

        response = requests.get(
            url=tr_endpoint,
            params=csrf_param,
            auth=ses,
            headers=headers,
            timeout=10
        )
        response.raise_for_status()

        csrf_token = response.json()["query"]["tokens"]["csrftoken"]

        self.update_state(state='PROGRESS', meta={'current': 25, 'total': 100})

        # Step 2: Upload File
        upload_param = {
            "action": "upload",
            "filename": f"{tr_filename}.{src_fileext}",
            "format": "json",
            "token": csrf_token,
            "ignorewarnings": 1
        }

        with open(file_path, 'rb') as f:
            response = requests.post(
                url=tr_endpoint,
                files={'file': f},
                data=upload_param,
                auth=ses,
                headers=headers,
                timeout=20
            )

        response.raise_for_status()
        data = response.json()

        self.update_state(state='PROGRESS', meta={'current': 75, 'total': 100})

        # Step 3: Extract Response
        try:
            wikifile_url = data["upload"]["imageinfo"]["descriptionurl"]
            file_link = data["upload"]["imageinfo"]["url"]
        except KeyError:
            return {"success": False, "data": {}, "errors": ["Upload failed"]}

        self.update_state(state='PROGRESS', meta={'current': 100, 'total': 100})

        return {
            "success": True,
            "wikipage_url": wikifile_url,
            "file_link": file_link
        }

    except requests.exceptions.RequestException as e:
        raise self.retry(exc=e)
