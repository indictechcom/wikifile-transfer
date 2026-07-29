import datetime
import requests
import mwparserfromhell
from templatelist import TEMPLATES
import os
import logging

from exceptions import DownloadError, MediaWikiAPIError, UploadError

logger = logging.getLogger(__name__)

def download_image(src_project, src_lang, src_filename):
    src_endpoint = "https://"+ src_lang + "." + src_project + ".org/w/api.php"

    filename = None

    param = {
        "action": "query",
        "format": "json",
        "prop": "imageinfo",
        "titles": src_filename,
        "iiprop": "url",
        "iilocalonly": 1
    }

    try:
        response = requests.get(url=src_endpoint, params=param, timeout=30)
        response.raise_for_status()
        page = response.json()['query']['pages']
    except (requests.exceptions.RequestException, KeyError) as e:
        logger.error("Failed to fetch image info", exc_info=True, extra={
            "src_endpoint": src_endpoint,
            "src_filename": src_filename,
            "error": str(e)
        })
        raise MediaWikiAPIError(f"Failed to fetch image info: {str(e)}")

    try:
        image_url = list(page.values())[0]["imageinfo"][0]["url"]
    except (KeyError, IndexError) as e:
        logger.error("Image URL not found in API response", exc_info=True, extra={
            "src_filename": src_filename
        })
        raise DownloadError(f"Image URL not found for {src_filename}")

    # Create a unique file name based on time
    current_time = str(datetime.datetime.now())
    get_filename = current_time.replace(':', '_')
    get_filename = get_filename.replace(' ', '_')

    try:
        # Download the Image File
        r = requests.get(image_url, allow_redirects=True, timeout=60)
        r.raise_for_status()
        
        content_type = r.headers.get('content-type', '')
        if not content_type.startswith('image/'):
            logger.error("URL does not point to image", extra={
                "image_url": image_url,
                "content_type": content_type
            })
            raise DownloadError(f"URL does not point to an image (content-type: {content_type})")
            
        file_ext = content_type.replace('image/', '')
        filename = get_filename + "." + file_ext
        
        # Ensure temp_images directory exists
        os.makedirs("temp_images", exist_ok=True)
        
        with open("temp_images/" + filename, 'wb') as f:
            f.write(r.content)
            
        logger.info("Successfully downloaded image", extra={
            "src_filename": src_filename,
            "local_filename": filename
        })
        
        return filename
        
    except requests.exceptions.RequestException as e:
        logger.error("Failed to download image file", exc_info=True, extra={
            "image_url": image_url,
            "error": str(e)
        })
        raise DownloadError(f"Failed to download image: {str(e)}")
    except IOError as e:
        logger.error("Failed to save image file", exc_info=True, extra={
            "filename": filename,
            "error": str(e)
        })
        raise DownloadError(f"Failed to save image: {str(e)}")

    return filename


def process_upload(file_path, tr_filename, src_fileext, tr_endpoint, ses):
    # API Parameter to get CSRF Token
    csrf_param = {
        "action": "query",
        "meta": "tokens",
        "format": "json"
    }

    try:
        response = requests.get(url=tr_endpoint, params=csrf_param, auth=ses, timeout=30)
        response.raise_for_status()
        csrf_token = response.json()["query"]["tokens"]["csrftoken"]
    except (requests.exceptions.RequestException, KeyError) as e:
        logger.error("Failed to get CSRF token", exc_info=True, extra={
            "tr_endpoint": tr_endpoint,
            "error": str(e)
        })
        raise MediaWikiAPIError(f"Failed to get CSRF token: {str(e)}")

    # API Parameter to upload the file
    upload_param = {
        "action": "upload",
        "filename": tr_filename + "." + src_fileext,
        "format": "json",
        "token": csrf_token,
        "ignorewarnings": 1
    }

    try:
        # Read the file for POST request
        with open(file_path, 'rb') as f:
            file = {'file': f}
            response = requests.post(url=tr_endpoint, files=file, data=upload_param, auth=ses, timeout=60)
            response.raise_for_status()
            result = response.json()
    except (IOError, requests.exceptions.RequestException) as e:
        logger.error("Upload request failed", exc_info=True, extra={
            "tr_endpoint": tr_endpoint,
            "tr_filename": tr_filename,
            "error": str(e)
        })
        raise UploadError(f"Upload request failed: {str(e)}")


    # Try block to get Link and URL
    try:
        wikifile_url = result["upload"]["imageinfo"]["descriptionurl"]
        file_link = result["upload"]["imageinfo"]["url"]
        
        logger.info("Upload successful", extra={
            "tr_filename": tr_filename,
            "wikifile_url": wikifile_url
        })
        
        return {
            "wikipage_url": wikifile_url,
            "file_link": file_link
        }
    except KeyError as e:
        logger.error("Missing expected keys in upload response", exc_info=True, extra={
            "response_keys": list(result.keys()) if isinstance(result, dict) else str(type(result))
        })
        raise UploadError("Upload response missing required data")


def get_localized_wikitext(wikitext, src_endpoint, target_lang):
    wikicode = mwparserfromhell.parse(wikitext)

    for template in wikicode.filter_templates():
        if template.name.strip() in TEMPLATES:
            if template.has("Article"):
                article_value = template.get("Article")

                if article_value:
                    article_title = article_value.value.strip()
                    lang_param = {
                        "action": "query",
                        "format": "json",
                        "prop": "langlinks",
                        "titles": article_title,
                        "formatversion": "2"
                    }

                    try:
                        response = requests.get(url=src_endpoint, params=lang_param, timeout=30)
                        response.raise_for_status()
                        langlinks = response.json()["query"]["pages"][0]["langlinks"]

                        for langlink in langlinks:
                            if langlink["lang"] == target_lang:
                                template.add("Article", langlink["title"])
                                break
                    except Exception as e:
                        logger.warning("Failed to get language links", extra={
                            "article_title": article_title,
                            "src_endpoint": src_endpoint,
                            "error": str(e)
                        })
                        # Continue without localization - non-fatal

    return str(wikicode)

def getHeader():
    agent = 'Wikifile-transfer/1.0 (https://wikifile-transfer.toolforge.org; 0freerunning@gmail.com)'
    return {
        'User-Agent': agent
    }
