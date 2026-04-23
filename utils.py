import datetime
import logging
import os
import requests
import mwparserfromhell
from templatelist import TEMPLATES

logger = logging.getLogger(__name__)

def cleanup_temp_file(file_path):
    if not file_path:
        return
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Temporary file {file_path} removed")
        else:
            logger.debug(f"Temporary file {file_path} already removed")
    except OSError as e:
        logging.warning(f"Failed to clean up temporary file {file_path}: {e}")

def get_headers():
    agent = 'Wikifile-transfer/1.0 (https://wikifile-transfer.toolforge.org; 0freerunning@gmail.com)'
    return {
        'User-Agent': agent
    }

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

    try:
        response = requests.get(url=src_endpoint, params=param, headers=get_headers(), timeout=30)
        response.raise_for_status()
        data = response.json()

        if "query" not in data or "pages" not in data["query"]:
            logger.error(f"Unexpected API response structure: {data}")
            return None

        page = data["query"]["pages"]
        image_url = list (page.values()) [0]["imageinfo"][0]["url"]
 
    except (KeyError, IndexError) as e:
        logger.error(f"Error occurred while fetching image URL {src_filename}: {e}")
        return None
    
    except requests.RequestException as e:
        logger.error(f"HTTP request failed while fetching image URL {src_filename}: {e}")
        return None

    # Create a unique file name based on time
    current_time = str(datetime.datetime.now())
    get_filename = current_time.replace(':', '_')
    get_filename = get_filename.replace(' ', '_')

    filepath = None

    # Download the Image File
    try:
        r = requests.get(image_url, allow_redirects=True, headers=get_headers(), timeout=60)
        r.raise_for_status()
        content_type = r.headers.get('content-type', '')
        if 'image/' in content_type:
            ext = content_type.split('image/')[-1].split(';')[0]
        else:
            ext = image_url.rsplit('.',1)[-1] if '.' in image_url else 'bin'
            logger.warning(f"Non-image content type '{content_type}' for {src_filename}, using extension '{ext}'")

        filename = get_filename + "." + ext
        filepath = os.path.join("temp_images", filename)

        os.makedirs("temp_images", exist_ok=True)

        with open(filepath, 'wb') as f:
            f.write(r.content)
        
        return filename
    
    except requests.RequestException as e:
        logger.error(f"Failed to download image {src_filename} from {image_url}: {e}")
        cleanup_temp_file(filepath)
        return None
    except OSError as e:
        logger.error(f"Failed to save image {src_filename} to {filepath}: {e}")
        cleanup_temp_file(filepath)
        return None

def process_upload(file_path, tr_filename, src_fileext, tr_endpoint, ses):
    # API Parameter to get CSRF Token
    try:
        csrf_param = {
            "action": "query",
            "meta": "tokens",
            "format": "json"
        }

        response = requests.get(url=tr_endpoint, params=csrf_param, auth=ses, headers=get_headers(), timeout=30)
        response.raise_for_status()

        try:
            csrf_token = response.json()["query"]["tokens"]["csrftoken"]
        except KeyError:
            logger.error(f"Failed to get CSFR token from {tr_endpoint}")
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
        with open(file_path, 'rb') as f:
            response = requests.post(
                url = tr_endpoint,
                files = {'file': f},
                data = upload_param,
                auth = ses,
                headers = get_headers(),
                timeout=120
            )

        response.raise_for_status()
        results = response.json()

        if 'error' in results:
            logger.error(f"MediaWiki upload error: {results['error']}")
            return None

        # Try block to get Link and URL
        try:
            wikifile_url = results["upload"]["imageinfo"]["descriptionurl"]
            file_link = results["upload"]["imageinfo"]["url"]
        except KeyError:
            logger.error(f"Unexpected upload response structure: {results}")
            return None

        return {
            "wikipage_url": wikifile_url,
            "file_link": file_link
        }
    
    except requests.RequestException as e:
        logger.error(f"Network error during upload to {tr_endpoint}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during upload: {e}")
        return None


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
                        response = requests.get(url=src_endpoint, params=lang_param, headers=get_headers(), timeout=30)
                        response.raise_for_status()
                        langlinks = response.json()["query"]["pages"][0]["langlinks"]

                        for langlink in langlinks:
                            if langlink["lang"] == target_lang:
                                template.add("Article", langlink["title"])
                                break
                    except Exception as e:
                        logger.warning(f"Failed to localize template {template.name.strip()}: {e}")
                        continue
                    

    return str(wikicode)
