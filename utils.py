import datetime
import os
import requests
import mwparserfromhell
from templatelist import TEMPLATES
from globalExceptions import (
    APIRequestError,
    CSRFTokenError,
    FileNotFoundOnWikiError,
    ImageDownloadError,
    UploadError,
    WikitextProcessingError,
)
from flask import jsonify, has_app_context
from logger import get_logger
 
log = get_logger(__name__)

_TEMP_DIR = "temp_images"
_USER_AGENT = "Wikifile-transfer/1.0 (https://wikifile-transfer.toolforge.org; 0freerunning@gmail.com)"
_HEADERS = {"User-Agent": _USER_AGENT}
_REQUEST_TIMEOUT = 30   # seconds


def _fetch_csrf_token(endpoint: str, auth) -> str:
    try:
        response = requests.get(
            url=endpoint,
            params={"action": "query", "meta": "tokens", "format": "json"},
            auth=auth,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["query"]["tokens"]["csrftoken"]
    
    except requests.HTTPError as exc:
        raise CSRFTokenError(
            f"HTTP error fetching CSRF token from {endpoint!r}: {exc}"
        ) from exc
    
    except requests.RequestException as exc:
        raise CSRFTokenError(
            f"Network error fetching CSRF token from {endpoint!r}: {exc}"
        ) from exc
    
    except (KeyError, ValueError) as exc:
        raise CSRFTokenError(
            f"Unexpected response format when fetching CSRF token from {endpoint!r}: {exc}"
        ) from exc


def success_response(data: dict = None, status: int = 200):
    body = {"success": True, "data": data or {}}
    if has_app_context():
        return jsonify(body), status
    return body

def error_response(message: str, status: int = 500, error_type: str = None):
    body = {"success": False, "error": message}
    if error_type:
        body["error_type"] = error_type
    if has_app_context():
        return jsonify(body), status
    return body

def safe_delete_temp_file(local_path: str) -> None:
    if not local_path or not os.path.exists(local_path):
        return
    try:
        os.unlink(local_path)
        log.debug("Temporary file deleted successfully", extra={"path": local_path})
    except OSError as exc:
        log.warning(
            "Could not delete temporary file (leaked file)",
            extra={"path": local_path, "error": str(exc)},
        )

def download_image(src_project, src_lang, src_filename):
    src_endpoint = "https://"+ src_lang + "." + src_project + ".org/w/api.php"

    param = {
        "action": "query",
        "format": "json",
        "prop": "imageinfo",
        "titles": src_filename,
        "iiprop": "url",
        "iilocalonly": 1
    }

    # page = requests.get(url=src_endpoint, params=param).json()['query']['pages']
    
    log.info(
        "Fetching image URL",
        extra={"src_endpoint": src_endpoint, "src_filename": src_filename},
    )

    try:
        response = requests.get(
            url=src_endpoint, params=param, headers=_HEADERS, timeout=_REQUEST_TIMEOUT
        )
        response.raise_for_status()
        # image_url = list (page.values()) [0]["imageinfo"][0]["url"]
    
    except requests.HTTPError as exc:
        raise APIRequestError(
            src_endpoint,
            reason=str(exc),
            status_code=exc.response.status_code,
        ) from exc
        
    except requests.RequestException as exc:
        raise APIRequestError(src_endpoint, reason=str(exc)) from exc
    
    # except KeyError:
    #     return None
    
    try:
        pages = response.json()["query"]["pages"]
        page  = list(pages.values())[0]
        image_url = page["imageinfo"][0]["url"]
    except (KeyError, IndexError):
        raise FileNotFoundOnWikiError(src_filename)
    
    log.debug("Image URL resolved", extra={"image_url": image_url})

    # Create a unique file name based on time
    current_time = str(datetime.datetime.now())
    get_filename = current_time.replace(':', '_')
    get_filename = get_filename.replace(' ', '_')

    try:
        r = requests.get(image_url, allow_redirects=True, headers=_HEADERS, timeout=_REQUEST_TIMEOUT)
        r.raise_for_status()
        content_type = r.headers.get("content-type", "")
        
    except requests.HTTPError as exc:
        raise ImageDownloadError(src_filename, f"HTTP error downloading image: {exc}") from exc
    
    except requests.RequestException as exc:
        raise ImageDownloadError(src_filename, f"Network error downloading image: {exc}") from exc
 
    extension = content_type.replace("image/", "").split(";")[0].strip()
    if not extension:
        raise ImageDownloadError(src_filename, f"Cannot determine file extension from content-type: {content_type!r}")
    
    # Download the Image File
    # r = requests.get(image_url, allow_redirects=True)
    # filename = get_filename + "." + r.headers.get('content-type').replace('image/', '')
    # open("temp_images/" + filename, 'wb').write(r.content)

    local_filename = f"{current_time}.{extension}"
    local_path     = os.path.join(_TEMP_DIR, local_filename)
 
    os.makedirs(_TEMP_DIR, exist_ok=True)
    
    try:
        with open(local_path, "wb") as fh:
            fh.write(r.content)
            
    except OSError as exc:
        safe_delete_temp_file(local_path)
        raise ImageDownloadError(
            src_filename, f"Could not write image to {local_path!r}: {exc}"
        ) from exc
    
    log.info(
        "Image downloaded successfully",
        extra={"local_path": local_path, "bytes": len(r.content)},
    )
    return local_filename

def process_upload(file_path, tr_filename, src_fileext, tr_endpoint, ses):
    # API Parameter to get CSRF Token
    # csrf_param = {
    #     "action": "query",
    #     "meta": "tokens",
    #     "format": "json"
    # }

    # response = requests.get(url=tr_endpoint, params=csrf_param, auth=ses)
    # csrf_token = response.json()["query"]["tokens"]["csrftoken"]
    
    try:
        csrf_token = _fetch_csrf_token(tr_endpoint, ses)
    except CSRFTokenError as exc:
        log.error("Could not obtain CSRF token", exc_info=True)
        return error_response(str(exc), error_type="CSRFTokenError")
        # return jsonify({"success": False, "data": {}, "error": str(exc), "data": {}})
    
    log.debug("CSRF token acquired")

    # API Parameter to upload the file
    upload_param = {
        "action": "upload",
        "filename": tr_filename + "." + src_fileext,
        "format": "json",
        "token": csrf_token,
        "ignorewarnings": 1
    }

    # Read the file for POST request
    # file = {
    #     'file': open(file_path, 'rb')
    # }

    # response = requests.post(url=tr_endpoint, files=file, data=upload_param, auth=ses).json()
    
    try:
        with open(file_path, "rb") as fh:
            upload_response = requests.post(
                url=tr_endpoint,
                files={"file": fh},
                data=upload_param,
                auth=ses,
                headers=_HEADERS,
            )
        upload_response.raise_for_status()
        response_data = upload_response.json()
    
    except FileNotFoundError as exc:
        raise UploadError(tr_filename, f"Local file not found: {file_path}") from exc
    
    except requests.HTTPError as exc:
        raise APIRequestError(
            tr_endpoint, reason=str(exc), status_code=exc.response.status_code
        ) from exc
    
    except requests.RequestException as exc:
        raise APIRequestError(tr_endpoint, reason=str(exc)) from exc

    # Try block to get Link and URL
    try:
        wikifile_url = response_data["upload"]["imageinfo"]["descriptionurl"]
        file_link = response_data["upload"]["imageinfo"]["url"]
    
    except KeyError as exc:
        api_error = (
            response_data.get("error", {}).get("info")
            or response_data.get("upload", {}).get("warnings")
            or "Unknown API response structure"
        )
        log.error(
            "Upload API returned unexpected structure",
            extra={"tr_filename": tr_filename, "api_error": api_error, "missing_key": str(exc)},
        )
        raise UploadError(tr_filename, str(api_error)) from exc
   
    return {
        "wikipage_url": wikifile_url,
        "file_link": file_link
    }


def get_localized_wikitext(wikitext, src_endpoint, target_lang):
    wikicode = mwparserfromhell.parse(wikitext)

    # for template in wikicode.filter_templates():
    #     if template.name.strip() in TEMPLATES:
    #         if template.has("Article"):
    #             article_value = template.get("Article")

    #             if article_value:
    #                 article_title = article_value.value.strip()
    #                 lang_param = {
    #                     "action": "query",
    #                     "format": "json",
    #                     "prop": "langlinks",
    #                     "titles": article_title,
    #                     "formatversion": "2"
    #                 }

    #                 try:
    #                     response = requests.get(url=src_endpoint, params=lang_param)
    #                     response.raise_for_status()
    #                     langlinks = response.json()["query"]["pages"][0]["langlinks"]

    #                     for langlink in langlinks:
    #                         if langlink["lang"] == target_lang:
    #                             template.add("Article", langlink["title"])
    #                             break
    #                 except:
    #                     return str(wikicode)
    
    try:
        wikicode = mwparserfromhell.parse(wikitext)
    
    except Exception as exc:
        raise WikitextProcessingError(
            f"Failed to parse wikitext: {exc}"
        ) from exc
 
    for template in wikicode.filter_templates():
        template_name = template.name.strip()
 
        if template_name not in TEMPLATES:
            continue
        if not template.has("Article"):
            continue
 
        article_value = template.get("Article").value.strip()
        if not article_value:
            continue
 
        log.debug(
            "Localising article link",
            extra={"template": template_name, "article": article_value, "target_lang": target_lang},
        )
 
        lang_param = {
            "action": "query",
            "format": "json",
            "prop": "langlinks",
            "titles": article_value,
            "formatversion": "2",
        }
 
        try:
            response = requests.get(
                url=src_endpoint,
                params=lang_param,
                headers=_HEADERS,
                timeout=_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            pages = response.json()["query"]["pages"]
            langlinks = pages[0].get("langlinks", [])
        
        except requests.HTTPError as exc:
            log.warning(
                "HTTP error fetching langlinks; skipping template",
                exc_info=True,
                extra={"template": template_name, "article": article_value},
            )
            continue
       
        except requests.RequestException as exc:
            log.warning(
                "Network error fetching langlinks; skipping template",
                exc_info=True,
                extra={"template": template_name, "article": article_value},
            )
            continue
       
        except (KeyError, IndexError, ValueError) as exc:
            log.warning(
                "Unexpected langlinks response format; skipping template",
                exc_info=True,
                extra={"template": template_name, "article": article_value},
            )
            continue
 
        for langlink in langlinks:
            if langlink.get("lang") == target_lang:
                template.add("Article", langlink["title"])
                log.debug(
                    "Article link localised",
                    extra={"from": article_value, "to": langlink["title"]},
                )
                break
        else:
            log.info(
                "No langlink found for target language",
                extra={"article": article_value, "target_lang": target_lang},
            )
 
    return str(wikicode)

    
def getHeader():
    agent = 'Wikifile-transfer/1.0 (https://wikifile-transfer.toolforge.org; 0freerunning@gmail.com)'
    return {
        'User-Agent': agent
    }
