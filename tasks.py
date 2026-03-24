"""
tasks.py – Celery task definitions for Wikifile-Transfer.

Async tasks handle large file uploads (> 50 MB) that would time out if
processed synchronously. The client receives a task_id immediately and
polls /api/task_status/<task_id> for updates.

Every failure raises TaskError so Celery marks the task as FAILURE and
the status endpoint can report a clean error message to the client.
"""

import logging

import requests
import requests_oauthlib

from celeryWorker import app
from exceptions import TaskError

logger = logging.getLogger(__name__)


@app.task(bind=True)
def upload_image_task(self, file_path, tr_filename, src_fileext, tr_endpoint, oauth_obj):
    """
    Upload *file_path* to *tr_endpoint* as an authenticated Celery task.

    Progress states: PROGRESS at 0%, 25%, 75%, 100% → then SUCCESS or FAILURE.

    Raises
    ------
    TaskError
        Wraps any failure so Celery marks the task FAILURE and the original
        message is available through the /api/task_status endpoint.
    """
    task_id = self.request.id
    logger.info(
        "Task %s started: uploading '%s.%s' to %s",
        task_id, tr_filename, src_fileext, tr_endpoint,
    )

    ses = requests_oauthlib.OAuth1(
        client_key=oauth_obj["consumer_key"],
        client_secret=oauth_obj["consumer_secret"],
        resource_owner_key=oauth_obj["key"],
        resource_owner_secret=oauth_obj["secret"],
    )

    self.update_state(state="PROGRESS", meta={"current": 0, "total": 100})

    # --- Step 1: Fetch CSRF token (0% → 25%) --------------------------------
    try:
        csrf_response = requests.get(
            url=tr_endpoint,
            params={"action": "query", "meta": "tokens", "format": "json"},
            auth=ses,
        )
        csrf_response.raise_for_status()
        csrf_token = csrf_response.json()["query"]["tokens"]["csrftoken"]
    except requests.RequestException as e:
        logger.exception("Task %s – network error fetching CSRF token", task_id)
        raise TaskError(f"Failed to fetch CSRF token: {e}") from e
    except (KeyError, ValueError) as e:
        logger.exception("Task %s – unexpected CSRF token response", task_id)
        raise TaskError(f"Unexpected CSRF token response: {e}") from e

    self.update_state(state="PROGRESS", meta={"current": 25, "total": 100})

    # --- Step 2: Upload file (25% → 75%) ------------------------------------
    upload_param = {
        "action":         "upload",
        "filename":       f"{tr_filename}.{src_fileext}",
        "format":         "json",
        "token":          csrf_token,
        "ignorewarnings": 1,
    }

    # Use a context manager so the file handle is always closed after the
    # request, even if an exception is raised mid-upload.
    try:
        with open(file_path, "rb") as fh:
            upload_response = requests.post(
                url=tr_endpoint,
                files={"file": fh},
                data=upload_param,
                auth=ses,
            )
        upload_response.raise_for_status()
        response_json = upload_response.json()
    except OSError as e:
        logger.exception("Task %s – could not open '%s'", task_id, file_path)
        raise TaskError(f"Could not read local file for upload: {e}") from e
    except requests.RequestException as e:
        logger.exception("Task %s – network error during upload", task_id)
        raise TaskError(f"Upload request failed: {e}") from e
    except ValueError as e:
        logger.exception("Task %s – invalid JSON in upload response", task_id)
        raise TaskError(f"Unexpected upload response format: {e}") from e

    self.update_state(state="PROGRESS", meta={"current": 75, "total": 100})

    # --- Step 3: Parse response (75% → 100%) --------------------------------
    try:
        wikifile_url = response_json["upload"]["imageinfo"]["descriptionurl"]
        file_link    = response_json["upload"]["imageinfo"]["url"]
    except KeyError:
        # The wiki rejected the upload (permissions, duplicate, etc.).
        logger.error(
            "Task %s – imageinfo missing in upload response: %s",
            task_id, response_json,
        )
        raise TaskError(
            f"Upload rejected by target wiki. Response: {response_json}"
        )

    self.update_state(state="PROGRESS", meta={"current": 100, "total": 100})
    logger.info("Task %s completed: %s", task_id, wikifile_url)

    return {"wikipage_url": wikifile_url, "file_link": file_link}
