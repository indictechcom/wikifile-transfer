import datetime
import requests
import mwparserfromhell
import os
from templatelist import TEMPLATES
from exceptions import DownloadError, UploadError

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
        response = requests.get(url=src_endpoint, params=param).json()
        page = response['query']['pages']
        image_url = list (page.values()) [0]["imageinfo"][0]["url"]
    except (KeyError, IndexError):
        raise DownloadError("The source file could not be found or processed.")

    # Create a unique file name based on time
    current_time = str(datetime.datetime.now())
    get_filename = current_time.replace(':', '_').replace(' ', '_')

    # Download the Image File with proper error handling and cleanup logic
    try:
        r = requests.get(image_url, allow_redirects=True)
        r.raise_for_status()
        
        filename = get_filename + "." + r.headers.get('content-type').replace('image/', '')
        with open("temp_images/" + filename, 'wb') as f:
            f.write(r.content)
            
        return filename
    except requests.exceptions.RequestException as e:
        raise DownloadError(f"Failed to download the image from source: {str(e)}")


def process_upload(file_path, tr_filename, src_fileext, tr_endpoint, ses):
    # API Parameter to get CSRF Token
    csrf_param = {
        "action": "query",
        "meta": "tokens",
        "format": "json"
    }

    try:
        response = requests.get(url=tr_endpoint, params=csrf_param, auth=ses)
        response.raise_for_status()
        csrf_token = response.json()["query"]["tokens"]["csrftoken"]
    except (requests.exceptions.RequestException, KeyError):
        raise UploadError("Failed to fetch CSRF token from target wiki.")

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
            file_data = {'file': f}
            response_json = requests.post(url=tr_endpoint, files=file_data, data=upload_param, auth=ses).json()
    except Exception as e:
        raise UploadError(f"File upload connection failed: {str(e)}")

    # Try block to get Link and URL
    try:
        wikifile_url = response_json["upload"]["imageinfo"]["descriptionurl"]
        file_link = response_json["upload"]["imageinfo"]["url"]
    except KeyError:
        error_info = response_json.get("error", {}).get("info", "Unknown Wikimedia error")
        raise UploadError(f"Wikimedia rejected the upload: {error_info}")


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
