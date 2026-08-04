import urllib.parse
import datetime
import requests
import mwparserfromhell
from templatelist import TEMPLATES

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

    page = requests.get(url=src_endpoint, params=param, headers=getHeader()).json()['query']['pages']

    try:
        image_url = list (page.values()) [0]["imageinfo"][0]["url"]
    except KeyError:
        return None

    # Create a unique file name based on time
    current_time = str(datetime.datetime.now())
    get_filename = current_time.replace(':', '_').replace(' ', '_')

    r = requests.get(image_url, allow_redirects=True, headers=getHeader())
    filename = get_filename + "." + r.headers.get('content-type').replace('image/', '')
    open("temp_images/" + filename, 'wb').write(r.content)

    return filename


def process_upload(file_path, tr_filename, src_fileext, tr_endpoint, ses):
    # API Parameter to get CSRF Token
    csrf_param = {
        "action": "query",
        "meta": "tokens",
        "format": "json"
    }

    response = requests.get(url=tr_endpoint, params=csrf_param, auth=ses, headers=getHeader())
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
    file = {'file': open(file_path, 'rb')}
    response = requests.post(url=tr_endpoint, files=file, data=upload_param, auth=ses, headers=getHeader()).json()

    # Try block to get Link and URL
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
                    except:
                        return str(wikicode)

    return str(wikicode)

def process_task_item(file_path, tr_project, task_item, src_fileext, ses):
    """
    Synchronously processes a single transfer tasks.
    """
    try:
        lang = task_item.get("lang")
        raw_tr_filename = task_item.get("trfilename", "")
        tr_filename = urllib.parse.unquote(raw_tr_filename).strip()
        
        add_template = task_item.get("addTemplate", False)
        page_content = task_item.get("pageContent", "")
        edit_article = task_item.get("editArticle", False)
        article_link = task_item.get("articleLink", "")
        
        if not lang or not tr_filename:
            return None

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
            return None

        wikifile_url = upload_resp["upload"]["imageinfo"]["descriptionurl"]
        file_link = upload_resp["upload"]["imageinfo"]["url"]

        article_edit_success = None
        if edit_article and article_link:
            try:
                image_title = f"{tr_filename}.{src_fileext}"
                article_edit_success = edit_target_article(
                    article_url=article_link, 
                    tr_endpoint=tr_endpoint, 
                    image_title=image_title, 
                    csrf_token=csrf_token, 
                    ses=ses
                )
            except Exception as e:
                article_edit_success = False

        return {
            "wikipage_url": wikifile_url,
            "file_link": file_link,
            "article_edit_success": article_edit_success
        }

    except Exception as e:
        return None

def edit_target_article(article_url, tr_endpoint, image_title, csrf_token, ses):
    """
    Fetches the article wikitext, locates an empty image parameter in an template and inserts the uploaded image title.
    """
    # Implement later
    raise NotImplementedError


def getHeader():
    agent = 'Wikifile-transfer/1.0 (https://wikifile-transfer.toolforge.org; 0freerunning@gmail.com)'
    return {
        'User-Agent': agent
    }
