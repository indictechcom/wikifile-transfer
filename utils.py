import datetime
import requests

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
        return None

    # Create a unique file name based on time
    current_time = str(datetime.datetime.now())
    get_filename = current_time.replace(':', '_')
    get_filename = get_filename.replace(' ', '_')

    # Download the Image File
    r = requests.get(image_url, allow_redirects=True)
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
    file = {
        'file': open(file_path, 'rb')
    }

    response = requests.post(url=tr_endpoint, files=file, data=upload_param, auth=ses).json()

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


def getHeader():
    agent = 'Wikifile-transfer/1.0 (https://wikifile-transfer.toolforge.org; 0freerunning@gmail.com)'
    return {
        'User-Agent': agent
    }
