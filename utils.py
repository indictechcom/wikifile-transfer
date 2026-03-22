import datetime
import requests
import mwparserfromhell
from templatelist import TEMPLATES


def get_headers():
    agent = 'Wikifile-transfer/1.0 (https://wikifile-transfer.toolforge.org; 0freerunning@gmail.com)'
    return {
        'User-Agent': agent
    }


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

    page = requests.get(url=src_endpoint, params=param, headers=get_headers()).json()['query']['pages']

    try:
        image_url = list(page.values())[0]["imageinfo"][0]["url"]
    except KeyError as e:
        print(f"[ERROR] Image URL not found in response: {e}")
        return None

    current_time = str(datetime.datetime.now()).replace(':', '_').replace(' ', '_')

    r = requests.get(image_url, allow_redirects=True, headers=get_headers())
    filename = current_time + "." + r.headers.get('content-type').replace('image/', '')

    open("temp_images/" + filename, 'wb').write(r.content)

    return filename


def process_upload(file_path, tr_filename, src_fileext, tr_endpoint, ses):
    csrf_param = {
        "action": "query",
        "meta": "tokens",
        "format": "json"
    }

    response = requests.get(url=tr_endpoint, params=csrf_param, auth=ses, headers=get_headers())
    csrf_token = response.json()["query"]["tokens"]["csrftoken"]

    upload_param = {
        "action": "upload",
        "filename": tr_filename + "." + src_fileext,
        "format": "json",
        "token": csrf_token,
        "ignorewarnings": 1
    }

    file = {
        'file': open(file_path, 'rb')
    }

    response = requests.post(
        url=tr_endpoint,
        files=file,
        data=upload_param,
        auth=ses,
        headers=get_headers()
    ).json()

    try:
        wikifile_url = response["upload"]["imageinfo"]["descriptionurl"]
        file_link = response["upload"]["imageinfo"]["url"]
    except KeyError as e:
        print(f"[ERROR] Upload response parsing failed: {e}")
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
                            headers=get_headers()
                        )
                        response.raise_for_status()

                        langlinks = response.json()["query"]["pages"][0]["langlinks"]

                        for langlink in langlinks:
                            if langlink["lang"] == target_lang:
                                template.add("Article", langlink["title"])
                                break

                    except Exception as e:
                        print(f"[ERROR] Failed to localize wikitext: {e}")
                        return str(wikicode)

    return str(wikicode)
