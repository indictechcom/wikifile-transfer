from celeryWorker import app
import requests
import requests_oauthlib
import urllib.parse
import os
from utils import get_wikitext, getHeader
from celery.utils.log import get_task_logger

# Initialize Celery logger
logger = get_task_logger(__name__)

@app.task(
    bind=True,
    autoretry_for=(requests.RequestException,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
    acks_late=True,
)
def upload_task_item(self, file_path, tr_project, task_item, src_fileext, OAuthObj):
    """
    Celery task to handle a single language asynchronous transfer.
    """
    self.update_state(state='PROGRESS', meta={'current': 0, 'total': 100})

    try:
        # 1. Reconstruct OAuth Session
        ses = requests_oauthlib.OAuth1(
            client_key=OAuthObj["consumer_key"],
            client_secret=OAuthObj["consumer_secret"],
            resource_owner_key=OAuthObj["key"],
            resource_owner_secret=OAuthObj["secret"]
        )

        # 2. Parse Task Parameters
        lang = task_item.get("lang")
        raw_tr_filename = task_item.get("trfilename", "")
        tr_filename = urllib.parse.unquote(raw_tr_filename).strip()

        task_id = self.request.id
        logger.info(f"[task:{task_id}] Starting async upload for {tr_filename} targeting {lang}.{tr_project}")

        add_template = task_item.get("addTemplate", False)
        page_content = task_item.get("pageContent", "")
        edit_article = task_item.get("editArticle", False)
        article_link = task_item.get("articleLink", "")

        if not lang or not tr_filename:
            logger.error(f"[task:{task_id}] Task failed: Missing 'lang' or 'trfilename' in payload.")
            raise ValueError("Missing 'lang' or 'trfilename' in task payload.")

        tr_endpoint = f"https://{lang}.{tr_project}.org/w/api.php"

        # 3. Fetch CSRF Token
        logger.debug(f"[task:{task_id}] Fetching CSRF token from {tr_endpoint}")
        csrf_param = {
            "action": "query",
            "meta": "tokens",
            "format": "json"
        }

        response = requests.get(url=tr_endpoint, params=csrf_param, auth=ses, headers=getHeader())
        response.raise_for_status()
        csrf_token = response.json()["query"]["tokens"]["csrftoken"]

        self.update_state(state='PROGRESS', meta={'current': 25, 'total': 100})

        # 4. Prepare Upload Parameters & Execute Upload
        upload_param = {
            "action": "upload",
            "filename": f"{tr_filename}.{src_fileext}",
            "format": "json",
            "token": csrf_token,
            "ignorewarnings": 1
        }

        # Add Template text as file description if checked
        if add_template and page_content:
            upload_param["text"] = page_content

        # POST File Upload Request
        logger.info(f"[task:{task_id}] Executing POST upload for {tr_filename} to {tr_endpoint}")
        with open(file_path, 'rb') as f:
            files = {'file': f}
            upload_resp = requests.post(
                url=tr_endpoint,
                files=files,
                data=upload_param,
                auth=ses,
                headers=getHeader()
            ).json()

        # Catch API-level upload errors embedded in 200 JSON
        if "error" in upload_resp:
            api_err = upload_resp["error"].get("info", str(upload_resp["error"]))
            logger.error(f"[task:{task_id}] Wikimedia API Upload Error: {api_err}")
            raise Exception(f"Wikimedia API Upload Error: {api_err}")

        # Extract success URLs
        wikifile_url = upload_resp["upload"]["imageinfo"]["descriptionurl"]
        file_link = upload_resp["upload"]["imageinfo"]["url"]

        logger.info(f"[task:{task_id}] File uploaded successfully: {wikifile_url}")
        self.update_state(state='PROGRESS', meta={'current': 75, 'total': 100})

        # 5. Get Wikitext of the Article if edit_article is True
        wikitext_fetch_success = None
        wikitext = None
        if edit_article and article_link:
            try:
                # Fetch the wikitext of the article
                logger.info(f"[task:{task_id}] Fetching wikitext for article: {article_link}")
                wikitext = get_wikitext(article_link, tr_endpoint, ses)
                wikitext_fetch_success = True
            except Exception as e:
                logger.warning(f"[task:{task_id}] Failed to fetch wikitext for {article_link}: {e}")
                wikitext_fetch_success = False

        self.update_state(state='PROGRESS', meta={'current': 100, 'total': 100})

        return {
            "wikipage_url": wikifile_url,
            "file_link": file_link,
            "wikitext_fetch_success": wikitext_fetch_success,
            "wikitext": wikitext
        }

    except Exception as e:
        logger.error(f"[task:{task_id}] Celery upload_task_item failed: {e}", exc_info=True)
        raise  # Preserves original traceback

@app.task(
    bind=True,
    autoretry_for=(requests.RequestException,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
    acks_late=True,
)
def upload_image_task(self, file_path, tr_filename, src_fileext, tr_endpoint, OAuthObj):
    task_id = self.request.id
    logger.info(f"[task:{task_id}] Starting standalone async upload for {tr_filename} to {tr_endpoint}")
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

        response = requests.get(url=tr_endpoint, params=csrf_param, auth=ses, headers=getHeader())
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

        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(url=tr_endpoint, files=files, data=upload_param, auth=ses, headers=getHeader()).json()

        self.update_state(state='PROGRESS', meta={'current': 75, 'total': 100})

        # Try block to get Link and URL
        try:
            wikifile_url = response["upload"]["imageinfo"]["descriptionurl"]
            file_link = response["upload"]["imageinfo"]["url"]
            logger.info(f"[task:{task_id}] Standalone upload successful: {wikifile_url}")
        except KeyError:
            logger.error(f"[task:{task_id}] Upload response missing image info data: {response}")
            return {"success": False, "data": {}, "errors": ["Upload failed"]}

        self.update_state(state='PROGRESS', meta={'current': 100, 'total': 100})

        return {
            "wikipage_url": wikifile_url,
            "file_link": file_link
        }
    except Exception as e:
        logger.error(f"[task:{task_id}] Celery upload_image_task failed: {e}", exc_info=True)
        raise