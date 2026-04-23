import datetime
import requests
import mwparserfromhell
import os
import logging
from templatelist import TEMPLATES

logger = logging.getLogger(__name__)


def download_image(src_project, src_lang, src_filename):
    """Download an image from a source wiki. Returns the local filename or None on failure."""
    src_endpoint = "https://" + src_lang + "." + src_project + ".org/w/api.php"

    param = {
        "action": "query",
        "format": "json",
        "prop": "imageinfo",
        "titles": src_filename,
        "iiprop": "url",
        "iilocalonly": 1
    }

    try:
        response = requests.get(url=src_endpoint, params=param)
        response.raise_for_status()
        data = response.json()

        # Validate the API response structure
        if "query" not in data or "pages" not in data["query"]:
            logger.error("Unexpected API response structure from %s: %s", src_endpoint, data)
            return None

        page = data['query']['pages']
        image_url = list(page.values())[0]["imageinfo"][0]["url"]
    except (KeyError, IndexError) as e:
        logger.error("Could not extract image URL from source wiki: %s", e)
        return None
    except requests.RequestException as e:
        logger.error("Failed to fetch image info from %s: %s", src_endpoint, e)
        return None

    # Create a unique file name based on time
    current_time = str(datetime.datetime.now())
    get_filename = current_time.replace(':', '_').replace(' ', '_')

    try:
        r = requests.get(image_url, allow_redirects=True)
        r.raise_for_status()

        # Validate content-type header
        content_type = r.headers.get('content-type', '')
        if 'image/' in content_type:
            ext = content_type.split('image/')[-1].split(';')[0]  # handle "image/jpeg; charset=..."
        else:
            # Fallback: extract extension from the original URL
            ext = image_url.rsplit('.', 1)[-1] if '.' in image_url else 'bin'
            logger.warning("Non-image content-type '%s' received, falling back to extension '%s'", content_type, ext)

        filename = get_filename + "." + ext
        filepath = os.path.join("temp_images", filename)

        # Ensure temp_images directory exists
        os.makedirs("temp_images", exist_ok=True)

        with open(filepath, 'wb') as f:
            f.write(r.content)

        return filename
    except requests.RequestException as e:
        logger.error("Failed to download image from %s: %s", image_url, e)
        return None
    except OSError as e:
        logger.error("Failed to save image file: %s", e)
        return None


def process_upload(file_path, tr_filename, src_fileext, tr_endpoint, ses):
    """Upload a file to the target wiki. Returns a result dict or None on failure."""
    file_handle = None
    try:
        # API Parameter to get CSRF Token
        csrf_param = {
            "action": "query",
            "meta": "tokens",
            "format": "json"
        }

        response = requests.get(url=tr_endpoint, params=csrf_param, auth=ses)
        response.raise_for_status()
        token_data = response.json()

        # Validate CSRF token response
        try:
            csrf_token = token_data["query"]["tokens"]["csrftoken"]
        except KeyError:
            logger.error("Failed to retrieve CSRF token from %s. Response: %s", tr_endpoint, token_data)
            return None

        # API Parameter to upload the file
        upload_param = {
            "action": "upload",
            "filename": tr_filename + "." + src_fileext,
            "format": "json",
            "token": csrf_token,
            "ignorewarnings": 1
        }

        # Read the file for POST request
        file_handle = open(file_path, 'rb')
        file = {'file': file_handle}

        response = requests.post(url=tr_endpoint, files=file, data=upload_param, auth=ses)
        response.raise_for_status()
        result = response.json()

        # Check for MediaWiki API-level error
        if "error" in result:
            error_code = result["error"].get("code", "unknown")
            error_info = result["error"].get("info", "No details provided")
            logger.error("MediaWiki upload error: [%s] %s", error_code, error_info)
            return None

        # Try block to get Link and URL
        try:
            wikifile_url = result["upload"]["imageinfo"]["descriptionurl"]
            file_link = result["upload"]["imageinfo"]["url"]
        except KeyError:
            upload_result = result.get("upload", {}).get("result", "unknown")
            logger.error("Upload response missing expected fields. Upload result: %s, Full response: %s",
                         upload_result, result)
            return None

        return {
            "wikipage_url": wikifile_url,
            "file_link": file_link
        }

    except requests.RequestException as e:
        logger.error("Network error during upload to %s: %s", tr_endpoint, e)
        return None
    except Exception as e:
        logger.error("Unexpected error during upload: %s", e)
        return None
    finally:
        # Close file handle if opened
        if file_handle is not None:
            file_handle.close()
        # Clean up temp file
        cleanup_temp_file(file_path)


def cleanup_temp_file(file_path):
    """Safely remove a temporary file."""
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.info("Cleaned up temp file: %s", file_path)
    except OSError as e:
        logger.warning("Failed to clean up temp file %s: %s", file_path, e)


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
                        response = requests.get(url=src_endpoint, params=lang_param)
                        response.raise_for_status()
                        langlinks = response.json()["query"]["pages"][0]["langlinks"]

                        for langlink in langlinks:
                            if langlink["lang"] == target_lang:
                                template.add("Article", langlink["title"])
                                break
                    except:
                        return str(wikicode)

    return str(wikicode)

def getHeader():
    agent = 'Wikifile-transfer/1.0 (https://wikifile-transfer.toolforge.org; 0freerunning@gmail.com)'
    return {
        'User-Agent': agent
    }
