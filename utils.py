import datetime
import os
import requests
import mwparserfromhell
from templatelist import TEMPLATES
from logger import log_exception
from exceptions import operation_success, operation_failure, download_error, upload_error, file_handling_error
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

    page = requests.get(url=src_endpoint, params=param).json()['query']['pages']

    try:
        image_url = list (page.values()) [0]["imageinfo"][0]["url"]
    except KeyError:
        log_exception("Failed to retrieve image URL for %s", src_filename)
        return operation_failure(download_error(f"Unable to resolve image URL for {src_filename}"))

    # Create a unique file name based on time
    current_time = str(datetime.datetime.now())
    get_filename = current_time.replace(':', '_')
    get_filename = get_filename.replace(' ', '_')

    # Download the Image File
    r = requests.get(image_url, allow_redirects=True)
    filename = get_filename + "." + r.headers.get('content-type').replace('image/', '')
    with open("temp_images/" + filename, 'wb') as output_file:
        output_file.write(r.content)

    return operation_success({"filename": filename})


def process_upload(file_path, tr_filename, src_fileext, tr_endpoint, ses):
    # API Parameter to get CSRF Token
    csrf_param = {
        "action": "query",
        "meta": "tokens",
        "format": "json"
    }

    response = requests.get(url=tr_endpoint, params=csrf_param, auth=ses)
    csrf_token = response.json()["query"]["tokens"]["csrftoken"]

    # API Parameter to upload the file
    upload_param = {
        "action": "upload",
        "filename": tr_filename + "." + src_fileext,
        "format": "json",
        "token": csrf_token,
        "ignorewarnings": 1
    }

    # Read the file for POST request
    with open(file_path, 'rb') as file_handle:
        file = {
            'file': file_handle
        }
        response = requests.post(url=tr_endpoint, files=file, data=upload_param, auth=ses).json()

    # Try block to get Link and URL
    try:
        wikifile_url = response["upload"]["imageinfo"]["descriptionurl"]
        file_link = response["upload"]["imageinfo"]["url"]
    except KeyError:
        log_exception("Failed to retrieve upload results for %s", tr_filename)
        return operation_failure(upload_error(f"Unable to parse upload response for {tr_filename}"))

    return operation_success({
        "wikipage_url": wikifile_url,
        "file_link": file_link
    })


def cleanup_temp_file(file_path):
    if not file_path:
        return operation_failure(file_handling_error("File path is empty"))

    if not os.path.exists(file_path):
        return operation_success({"removed": False, "reason": "file_not_found"})

    try:
        os.remove(file_path)
        return operation_success({"removed": True})
    except OSError as error:
        log_exception("Failed to remove temporary file %s", file_path)
        return operation_failure(file_handling_error(str(error)))


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
                        log_exception("Failed to retrieve language links for %s", article_title)
                        return str(wikicode)

    return str(wikicode)

def getHeader():
    agent = 'Wikifile-transfer/1.0 (https://wikifile-transfer.toolforge.org; 0freerunning@gmail.com)'
    return {
        'User-Agent': agent
    }
