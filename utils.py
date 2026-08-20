import urllib.parse
import datetime
import requests
import mwparserfromhell
from templatelist import TEMPLATES
import logging

# Initialize module logger
logger = logging.getLogger(__name__)

def download_image(src_project, src_lang, src_filename):
    logger.info(f"Downloading image {src_filename} from {src_lang}.{src_project}.org")
    src_endpoint = "https://"+ src_lang + "." + src_project + ".org/w/api.php"

    param = {
        "action": "query",
        "format": "json",
        "prop": "imageinfo",
        "titles": src_filename,
        "iiprop": "url",
        "iilocalonly": 1
    }

    try:
        page = requests.get(url=src_endpoint, params=param, headers=getHeader()).json()['query']['pages']
        image_url = list (page.values()) [0]["imageinfo"][0]["url"]
    except KeyError as e:
        logger.error(f"Image info KeyError for {src_filename}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error fetching image details for {src_filename}: {e}")
        return None

    # Create a unique file name based on time
    current_time = str(datetime.datetime.now())
    get_filename = current_time.replace(':', '_').replace(' ', '_')

    try:
        r = requests.get(image_url, allow_redirects=True, headers=getHeader())
        filename = get_filename + "." + r.headers.get('content-type').replace('image/', '')
        with open("temp_images/" + filename, 'wb') as f:
            f.write(r.content)

        logger.info(f"Successfully downloaded to temp_images/{filename}")
        return filename
    except Exception as e:
        logger.error(f"Failed to download and save image {image_url}: {e}", exc_info=True)
        return None


def process_upload(file_path, tr_filename, src_fileext, tr_endpoint, ses):
    logger.info(f"Processing synchronous upload for {tr_filename} to {tr_endpoint}")
    # API Parameter to get CSRF Token
    csrf_param = {
        "action": "query",
        "meta": "tokens",
        "format": "json"
    }

    try:
        response = requests.get(url=tr_endpoint, params=csrf_param, auth=ses, headers=getHeader())
        csrf_token = response.json()["query"]["tokens"]["csrftoken"]
    except Exception as e:
        logger.error(f"Failed to fetch CSRF token from {tr_endpoint}: {e}")
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
    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(url=tr_endpoint, files=files, data=upload_param, auth=ses, headers=getHeader()).json()
    except Exception as e:
        logger.error(f"POST upload request failed for {tr_filename}: {e}", exc_info=True)
        return None

    # Try block to get Link and URL
    try:
        wikifile_url = response["upload"]["imageinfo"]["descriptionurl"]
        file_link = response["upload"]["imageinfo"]["url"]
        logger.info(f"Upload successful: {wikifile_url}")
    except KeyError as e:
        logger.error(f"Upload response missing image info data: {response}")
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
                        response = requests.get(url=src_endpoint, params=lang_param, headers=getHeader())
                        response.raise_for_status()
                        langlinks = response.json()["query"]["pages"][0]["langlinks"]

                        for langlink in langlinks:
                            if langlink["lang"] == target_lang:
                                template.add("Article", langlink["title"])
                                break
                    except Exception as e:
                        logger.warning(f"Error fetching langlinks for {article_title}: {e}")
                        return str(wikicode)

    return str(wikicode)

def get_wikitext(article_name, tr_endpoint, ses):
    """
    Fetches the wikitext of an article from the target project.
    """
    title = urllib.parse.unquote(article_name)
    logger.debug(f"Fetching wikitext for {title} via API")

    params = {
        "action": "parse",
        "page": title,
        "prop": "wikitext",
        "format": "json",
        "formatversion": "2"
    }

    response = requests.get(url=tr_endpoint, params=params, auth=ses, headers=getHeader())
    response.raise_for_status()
    data = response.json()

    if "error" in data:
        error_info = data["error"].get("info", "Failed to fetch wikitext")
        logger.error(f"Wikitext API error for {title}: {error_info}")
        raise Exception(error_info)

    return data["parse"]["wikitext"]

def process_task_item(file_path, tr_project, task_item, src_fileext, ses):
    """
    Synchronously processes a single transfer tasks.
    """
    lang = task_item.get("lang")
    raw_tr_filename = task_item.get("trfilename", "")
    tr_filename = urllib.parse.unquote(raw_tr_filename).strip()

    logger.info(f"Processing synchronous task item for {tr_filename} to {lang}.{tr_project}")

    add_template = task_item.get("addTemplate", False)
    page_content = task_item.get("pageContent", "")
    edit_article = task_item.get("editArticle", False)
    article_link = task_item.get("articleLink", "")

    if not lang or not tr_filename:
        logger.error("Missing 'lang' or 'trfilename' in task payload.")
        raise ValueError("Missing 'lang' or 'trfilename' in task payload.")

    tr_endpoint = f"https://{lang}.{tr_project}.org/w/api.php"

    csrf_param = {
        "action": "query",
        "meta": "tokens",
        "format": "json"
    }

    response = requests.get(url=tr_endpoint, params=csrf_param, auth=ses, headers=getHeader())
    response.raise_for_status()
    csrf_token = response.json()["query"]["tokens"]["csrftoken"]

    upload_param = {
        "action": "upload",
        "filename": f"{tr_filename}.{src_fileext}",
        "format": "json",
        "token": csrf_token,
        "ignorewarnings": 1
    }

    if add_template and page_content:
        upload_param["text"] = page_content

    with open(file_path, 'rb') as f:
        files = {'file': f}
        upload_resp = requests.post(
            url=tr_endpoint,
            files=files,
            data=upload_param,
            auth=ses,
            headers=getHeader()
        ).json()

    if "error" in upload_resp:
        api_err = upload_resp["error"].get("info", str(upload_resp["error"]))
        logger.error(f"Wikimedia API Upload Error: {api_err}")
        raise Exception(f"Wikimedia API Upload Error: {api_err}")

    wikifile_url = upload_resp["upload"]["imageinfo"]["descriptionurl"]
    file_link = upload_resp["upload"]["imageinfo"]["url"]
    logger.info(f"Successfully processed item: {wikifile_url}")

    wikitext_fetch_success = None
    wikitext = None
    if edit_article and article_link:
        try:
            # Fetch the wikitext of the article
            wikitext = get_wikitext(article_link, tr_endpoint, ses)
            wikitext_fetch_success = True
        except Exception as e:
            logger.warning(f"Task item failed to fetch wikitext: {e}")
            wikitext_fetch_success = False

    return {
        "wikipage_url": wikifile_url,
        "file_link": file_link,
        "wikitext_fetch_success": wikitext_fetch_success,
        "wikitext": wikitext
    }


def getHeader():
    agent = 'Wikifile-transfer/1.0 (https://wikifile-transfer.toolforge.org; 0freerunning@gmail.com)'
    return {
        'User-Agent': agent
    }