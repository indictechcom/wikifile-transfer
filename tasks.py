from celeryWorker import app
from celery.exceptions import Retry
import requests
import requests_oauthlib
import os
from logging_config import get_logger, log_exception, log_task_event, log_timed_api_call, log_file_operation
from exceptions import AuthenticationError, WikiAPIError, FileOperationError
from utils import getHeader, cleanup_temp_file

logger = get_logger(__name__)


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def upload_image_task(self, file_path, tr_filename, src_fileext, tr_endpoint, OAuthObj):
    """
    Celery async task for uploading files over 50 MB to a target wiki.

    Called by app.py when the uploaded file exceeds 50 MB.
    Retries up to 3 times (60s delay) on network timeouts.

    Returns a dict — never raises — so the frontend polls /api/task_status
    and reads result.success to distinguish pass from fail.
    """
    task_id = self.request.id
    full_filename = f"{tr_filename}.{src_fileext}"
    _should_cleanup = True  # set False only before self.retry() so file survives retries

    logger.info(f"Task {task_id}: starting upload for {full_filename}")
    log_task_event(
        logger,
        task_id=task_id,
        task_name="upload_image_task",
        status="started",
        progress={"filename": full_filename, "endpoint": tr_endpoint}
    )

    try:
        # ─────────────────────────────────────
        # Validate OAuth credentials dict
        # ─────────────────────────────────────
        required_keys = ["consumer_key", "consumer_secret", "key", "secret"]
        missing_keys = [k for k in required_keys if k not in OAuthObj]

        if missing_keys:
            error_msg = f"Missing OAuth credentials: {', '.join(missing_keys)}"
            logger.error(f"Task {task_id}: {error_msg}")
            log_task_event(logger, task_id=task_id, task_name="upload_image_task",
                           status="failed", error=error_msg)
            return {"success": False, "data": {}, "errors": [error_msg]}

        # ─────────────────────────────────────
        # Build OAuth session
        # ─────────────────────────────────────
        try:
            ses = requests_oauthlib.OAuth1(
                client_key=OAuthObj["consumer_key"],
                client_secret=OAuthObj["consumer_secret"],
                resource_owner_key=OAuthObj["key"],
                resource_owner_secret=OAuthObj["secret"]
            )
            logger.info(f"Task {task_id}: OAuth session created")
        except Exception as e:
            error_msg = f"Failed to create OAuth session: {str(e)}"
            log_exception(logger, e, extra_context={"task_id": task_id, "step": "create_oauth_session"})
            log_task_event(logger, task_id=task_id, task_name="upload_image_task",
                           status="failed", error=error_msg)
            return {"success": False, "data": {}, "errors": [error_msg]}

        self.update_state(state="PROGRESS", meta={"current": 0, "total": 100, "status": "Initializing"})

        # ─────────────────────────────────────
        # Step 1 — Fetch CSRF token
        # ─────────────────────────────────────
        csrf_param = {"action": "query", "meta": "tokens", "format": "json"}

        try:
            logger.info(f"Task {task_id}: fetching CSRF token")

            with log_timed_api_call(logger, tr_endpoint, "GET") as ctx:
                response = requests.get(
                    url=tr_endpoint, params=csrf_param,
                    auth=ses, timeout=30, headers=getHeader()
                )
                response.raise_for_status()
                ctx["status_code"] = response.status_code

            csrf_token = response.json()["query"]["tokens"]["csrftoken"]

            if csrf_token == "+\\":
                raise AuthenticationError("Invalid CSRF token — OAuth session may have expired")

            logger.info(f"Task {task_id}: CSRF token obtained")
            self.update_state(state="PROGRESS", meta={"current": 25, "total": 100, "status": "Token obtained"})

        except AuthenticationError:
            # Auth errors are not retryable — return immediately
            error_msg = "Invalid CSRF token — OAuth session may have expired"
            log_task_event(logger, task_id=task_id, task_name="upload_image_task",
                           status="failed", error=error_msg)
            return {"success": False, "data": {}, "errors": [error_msg]}

        except requests.exceptions.Timeout as e:
            error_msg = "Timeout while fetching CSRF token"
            logger.error(f"Task {task_id}: {error_msg}")
            if self.request.retries < self.max_retries:
                _should_cleanup = False
                raise self.retry(exc=e)
            log_task_event(logger, task_id=task_id, task_name="upload_image_task",
                           status="failed", error=error_msg)
            return {"success": False, "data": {}, "errors": [error_msg]}

        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to fetch CSRF token: {str(e)}"
            log_exception(logger, e, extra_context={"task_id": task_id, "step": "fetch_csrf_token"})
            if self.request.retries < self.max_retries:
                _should_cleanup = False
                raise self.retry(exc=e)
            log_task_event(logger, task_id=task_id, task_name="upload_image_task",
                           status="failed", error=error_msg)
            return {"success": False, "data": {}, "errors": [error_msg]}

        except KeyError as e:
            error_msg = f"Unexpected CSRF response format: missing {str(e)}"
            logger.error(f"Task {task_id}: {error_msg}")
            log_task_event(logger, task_id=task_id, task_name="upload_image_task",
                           status="failed", error=error_msg)
            return {"success": False, "data": {}, "errors": [error_msg]}

        # ─────────────────────────────────────
        # Step 2 — Upload file
        # ─────────────────────────────────────
        try:
            if not os.path.exists(file_path):
                error_msg = f"File not found before upload: {file_path}"
                logger.error(f"Task {task_id}: {error_msg}")
                log_task_event(logger, task_id=task_id, task_name="upload_image_task",
                               status="failed", error=error_msg)
                return {"success": False, "data": {}, "errors": [error_msg]}

            file_size = os.path.getsize(file_path)
            logger.info(f"Task {task_id}: uploading {file_path} ({file_size} bytes)")

            upload_param = {
                "action": "upload",
                "filename": full_filename,
                "format": "json",
                "token": csrf_token,
                "ignorewarnings": 1
            }

            self.update_state(state="PROGRESS", meta={"current": 50, "total": 100, "status": "Uploading file"})

            with log_timed_api_call(logger, tr_endpoint, "POST") as ctx:
                with open(file_path, "rb") as f:
                    response = requests.post(
                        url=tr_endpoint,
                        files={"file": f},
                        data=upload_param,
                        auth=ses,
                        timeout=180  # 3 min for large files
                    )
                response.raise_for_status()
                ctx["status_code"] = response.status_code

            result = response.json()
            log_file_operation(logger, "upload", file_path, success=True)
            self.update_state(state="PROGRESS", meta={"current": 75, "total": 100, "status": "Processing result"})

        except OSError as e:
            error_msg = f"Could not read file for upload: {str(e)}"
            log_exception(logger, e, extra_context={"task_id": task_id, "step": "read_file", "file_path": file_path})
            log_file_operation(logger, "upload", file_path, success=False, error=str(e))
            log_task_event(logger, task_id=task_id, task_name="upload_image_task",
                           status="failed", error=error_msg)
            return {"success": False, "data": {}, "errors": [error_msg]}

        except requests.exceptions.Timeout as e:
            error_msg = "Timeout while uploading file"
            log_file_operation(logger, "upload", file_path, success=False, error=error_msg)
            logger.error(f"Task {task_id}: {error_msg}")
            if self.request.retries < self.max_retries:
                _should_cleanup = False
                raise self.retry(exc=e)
            log_task_event(logger, task_id=task_id, task_name="upload_image_task",
                           status="failed", error=error_msg)
            return {"success": False, "data": {}, "errors": [error_msg]}

        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to upload file: {str(e)}"
            log_exception(logger, e, extra_context={"task_id": task_id, "step": "upload_file"})
            log_file_operation(logger, "upload", file_path, success=False, error=str(e))
            if self.request.retries < self.max_retries:
                _should_cleanup = False
                raise self.retry(exc=e)
            log_task_event(logger, task_id=task_id, task_name="upload_image_task",
                           status="failed", error=error_msg)
            return {"success": False, "data": {}, "errors": [error_msg]}

        # ─────────────────────────────────────
        # Step 3 — Validate upload result
        # ─────────────────────────────────────
        upload_result = result.get("upload", {})

        if upload_result.get("result") != "Success":
            error_info = upload_result.get("error", {})
            error_msg = f"Upload failed: {error_info.get('info', 'Unknown error')}"
            logger.error(f"Task {task_id}: {error_msg}")
            log_task_event(logger, task_id=task_id, task_name="upload_image_task",
                           status="failed", error=error_msg)
            return {"success": False, "data": {}, "errors": [error_msg]}

        if "imageinfo" not in upload_result:
            error_msg = "Upload succeeded but no imageinfo returned"
            logger.error(f"Task {task_id}: {error_msg}")
            log_task_event(logger, task_id=task_id, task_name="upload_image_task",
                           status="failed", error=error_msg)
            return {"success": False, "data": {}, "errors": [error_msg]}

        wikifile_url = upload_result["imageinfo"]["descriptionurl"]
        file_link = upload_result["imageinfo"]["url"]

        self.update_state(state="PROGRESS", meta={"current": 100, "total": 100, "status": "Complete"})
        log_task_event(
            logger, task_id=task_id, task_name="upload_image_task",
            status="completed",
            progress={"filename": full_filename, "wikipage_url": wikifile_url}
        )
        logger.info(f"Task {task_id}: upload complete — {full_filename}")

        return {
            "success": True,
            "wikipage_url": wikifile_url,
            "file_link": file_link
        }

    except Retry:
        # Re-raise Celery Retry exceptions so they are not swallowed by the catch-all below
        raise

    except Exception as e:
        error_msg = f"Unexpected error in upload task: {str(e)}"
        log_exception(logger, e, extra_context={"task_id": task_id, "filename": full_filename})
        log_task_event(logger, task_id=task_id, task_name="upload_image_task",
                       status="failed", error=error_msg)
        return {"success": False, "data": {}, "errors": [error_msg]}

    finally:
        # Clean up the temp file on any terminal outcome (success or final failure).
        # Skipped when self.retry() is raised so the file survives to the next attempt.
        if _should_cleanup:
            cleanup_temp_file(file_path)
