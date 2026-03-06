import datetime
import requests
import mwparserfromhell
from templatelist import TEMPLATES

def getHeader():
    """
    Returns the official User-Agent header required by Wikimedia API policy.
    """
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

    headers = getHeader()
    page = requests.get(url=src_endpoint, params=param, headers=headers).json()['query']['pages']

    try:
        image_url = list(page.values())[0]["imageinfo"][0]["url"]
    except KeyError:
        return None

    current_time = str(datetime.datetime.now())
    get_filename = current_time.replace(':', '_').replace(' ', '_')

    r = requests.get(image_url, allow_redirects=True, headers=headers)
    filename = get_filename + "." + r.headers.get('content-type').replace('image/', '')
    
    with open("temp_images/" + filename, 'wb') as f:
        f.write(r.content)

    return filename

def process_upload(file_path, tr_filename, src_fileext, tr_endpoint, ses):
    csrf_param = {
        "action": "query",
        "meta": "tokens",
        "format": "json"
    }

    headers = getHeader()

    response = requests.get(url=tr_endpoint, params=csrf_param, auth=ses, headers=headers)
    csrf_token = response.json()["query"]["tokens"]["csrftoken"]

    upload_param = {
        "action": "upload",
        "filename": tr_filename + "." + src_fileext,
        "format": "json",
        "token": csrf_token,
        "ignorewarnings": 1
    }

    with open(file_path, 'rb') as f:
        file_payload = {'file': f}
        response = requests.post(url=tr_endpoint, files=file_payload, data=upload_param, auth=ses, headers=headers).json()

    try:
        wikifile_url = response["upload"]["imageinfo"]["descriptionurl"]
        file_link = response["upload"]["imageinfo"]["url"]
    except KeyError:
        return None

    return {
        "wikipage_url": wikifile_url,
        "file_link": file_link
    }

def get_localized_wikitext(wikitext, src_endpoint, target_lang):
    wikicode = mwparserfromhell.parse(wikitext)
    headers = getHeader()

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
                        response = requests.get(url=src_endpoint, params=lang_param, headers=headers)
                        response.raise_for_status()
                        langlinks = response.json()["query"]["pages"][0]["langlinks"]

                        for langlink in langlinks:
                            if langlink["lang"] == target_lang:
                                template.add("Article", langlink["title"])
                                break
                    except:
                        continue 

    return str(wikicode)