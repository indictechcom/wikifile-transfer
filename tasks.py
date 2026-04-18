from celeryWorker import app
import requests
import requests_oauthlib
import os
from datetime import datetime
from utils import download_image, process_upload


@app.task(bind=True)
def upload_image_task(self, file_path, tr_filename, src_fileext, tr_endpoint, OAuthObj):

    ses = requests_oauthlib.OAuth1(
        client_key=OAuthObj["consumer_key"],
        client_secret=OAuthObj["consumer_secret"],
        resource_owner_key=OAuthObj["key"],
        resource_owner_secret=OAuthObj["secret"]
    )

    # STARTED STATE
    self.update_state(state='PROGRESS', meta={
        "message": "Initializing upload",
        "progress": 0
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
            "message": "Fetched CSRF token",
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
            "message": "Uploading file",
            "progress": 75
        })

        # STEP 4: Extract response
        wikifile_url = response["upload"]["imageinfo"]["descriptionurl"]
        file_link = response["upload"]["imageinfo"]["url"]

        # PROGRESS - 100%
        self.update_state(state='PROGRESS', meta={
            "message": "Upload completed",
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
        # Re-raise so Celery properly transitions task to FAILURE state
        raise self.retry(exc=e, max_retries=0)


@app.task(bind=True)
def batch_upload_task(self, items, tr_project, tr_lang, tr_endpoint, OAuthObj):
    """
    Process a batch of file uploads sequentially.

    items: list of dicts — {srcUrl, trFilename, srcProject, srcLang, srcFilename}
    Returns a list of per-file result dicts: {file, status, url, error}
    """
    ses = requests_oauthlib.OAuth1(
        client_key=OAuthObj["consumer_key"],
        client_secret=OAuthObj["consumer_secret"],
        resource_owner_key=OAuthObj["key"],
        resource_owner_secret=OAuthObj["secret"],
    )

    total = len(items)
    results = []

    # Report initial state
    self.update_state(state="PROGRESS", meta={
        "progress": 0,
        "current": 0,
        "total": total,
        "message": "Starting batch upload…",
        "results": results,
    })

    for idx, item in enumerate(items):
        src_project = item["srcProject"]
        src_lang = item["srcLang"]
        src_filename = item["srcFilename"]
        tr_filename = item["trFilename"]
        downloaded_path = None

        try:
            # Step 1: Download source file to temp_images/
            downloaded_filename = download_image(src_project, src_lang, src_filename)
            if downloaded_filename is None:
                raise Exception(f"Could not download source file: {src_filename}")

            downloaded_path = "temp_images/" + downloaded_filename
            src_fileext = src_filename.split(".")[-1]

            # Step 2: Upload to target wiki
            resp = process_upload(downloaded_path, tr_filename, src_fileext, tr_endpoint, ses)
            if resp is None:
                raise Exception("Upload to target wiki failed")

            results.append({
                "file": src_filename,
                "trFilename": tr_filename,
                "status": "success",
                "wikipage_url": resp["wikipage_url"],
                "file_link": resp["file_link"],
                "error": None,
            })

        except Exception as e:
            results.append({
                "file": src_filename,
                "trFilename": tr_filename,
                "status": "failed",
                "wikipage_url": None,
                "file_link": None,
                "error": str(e),
            })

        finally:
            # Clean up temp file regardless of success/failure
            if downloaded_path and os.path.exists(downloaded_path):
                try:
                    os.remove(downloaded_path)
                except OSError:
                    pass

        # Report progress after each file
        progress = int(((idx + 1) / total) * 100)
        self.update_state(state="PROGRESS", meta={
            "progress": progress,
            "current": idx + 1,
            "total": total,
            "message": f"Processed {idx + 1} of {total} files",
            "results": results,
        })

    return {
        "status": "SUCCESS",
        "results": results,
        "total": total,
        "succeeded": sum(1 for r in results if r["status"] == "success"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "completed_at": str(datetime.utcnow()),
    }

