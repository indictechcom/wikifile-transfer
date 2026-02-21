import os
import logging
import datetime
import requests
import mwparserfromhell
from templatelist import TEMPLATES

logger = logging.getLogger(__name__)


def download_image(src_project, src_lang, src_filename):
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
        response = requests.get(url=src_endpoint, params=param, timeout=30)
        response.raise_for_status()
        page = response.json()["query"]["pages"]
        image_url = list(page.values())[0]["imageinfo"][0]["url"]
    except (KeyError, IndexError, requests.RequestException) as e:
        logger.error("Failed to get image info for %s: %s", src_filename, e)
        return None

    # Create a unique file name based on current timestamp
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")

    try:
        r = requests.get(image_url, allow_redirects=True, timeout=60)
        r.raise_for_status()
    except requests.RequestException as e:
        logger.error("Failed to download image from %s: %s", image_url, e)
        return None

    content_type = r.headers.get("content-type", "")
    if not content_type.startswith("image/"):
        logger.error("Unexpected content-type received: %s", content_type)
        return None

    # Strip the 'image/' prefix and sanitize the extension
    raw_ext = content_type.split("/")[-1].split(";")[0].strip()
    ext = "".join(c for c in raw_ext if c.isalnum())
    if not ext:
        logger.error("Could not determine file extension from content-type: %s", content_type)
        return None

    filename = timestamp + "." + ext

    with open(os.path.join("temp_images", filename), "wb") as f:
        f.write(r.content)

    return filename


def process_upload(file_path, tr_filename, src_fileext, tr_endpoint, ses):
    csrf_param = {
        "action": "query",
        "meta": "tokens",
        "format": "json"
    }

    try:
        response = requests.get(url=tr_endpoint, params=csrf_param, auth=ses, timeout=30)
        response.raise_for_status()
        csrf_token = response.json()["query"]["tokens"]["csrftoken"]
    except (KeyError, requests.RequestException) as e:
        logger.error("Failed to get CSRF token from %s: %s", tr_endpoint, e)
        return None

    upload_param = {
        "action": "upload",
        "filename": tr_filename + "." + src_fileext,
        "format": "json",
        "token": csrf_token,
        "ignorewarnings": 1
    }

    try:
        with open(file_path, "rb") as f:
            response = requests.post(
                url=tr_endpoint,
                files={"file": f},
                data=upload_param,
                auth=ses,
                timeout=120
            ).json()
    except (OSError, requests.RequestException) as e:
        logger.error("Upload request failed for %s: %s", file_path, e)
        return None

    try:
        wikifile_url = response["upload"]["imageinfo"]["descriptionurl"]
        file_link = response["upload"]["imageinfo"]["url"]
    except KeyError:
        logger.error("Unexpected upload response structure: %s", response)
        return None

    return {
        "wikipage_url": wikifile_url,
        "file_link": file_link
    }


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
                        response = requests.get(
                            url=src_endpoint,
                            params=lang_param,
                            timeout=30
                        )
                        response.raise_for_status()
                        langlinks = response.json()["query"]["pages"][0]["langlinks"]

                        for langlink in langlinks:
                            if langlink["lang"] == target_lang:
                                template.add("Article", langlink["title"])
                                break
                    except (KeyError, IndexError, requests.RequestException) as e:
                        logger.warning("Could not localize template article link: %s", e)
                        return str(wikicode)

    return str(wikicode)


def getHeader():
    agent = "Wikifile-transfer/1.0 (https://wikifile-transfer.toolforge.org; 0freerunning@gmail.com)"
    return {
        "User-Agent": agent
    }
