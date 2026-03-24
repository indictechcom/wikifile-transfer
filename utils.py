"""
utils.py – Shared utility functions for Wikifile-Transfer.

Functions
---------
download_image      Download a source file from a MediaWiki wiki.
process_upload      Upload a local file to a target MediaWiki wiki.
get_localized_wikitext  Localise an Article= template parameter in wikitext.
getHeader           Return the standard User-Agent header dict.
"""

import datetime
import logging

import mwparserfromhell
import requests

from templatelist import TEMPLATES
from exceptions import DownloadError, UploadError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Image downloading
# ---------------------------------------------------------------------------

def download_image(src_project: str, src_lang: str, src_filename: str) -> str:
    """
    Download *src_filename* from *src_lang*.*src_project*.org and save it to
    the ``temp_images/`` directory.

    Returns the generated local filename on success.

    Raises
    ------
    DownloadError
        If the image URL cannot be resolved, the download fails, or the file
        cannot be written to disk.
    """
    src_endpoint = f"https://{src_lang}.{src_project}.org/w/api.php"
    param = {
        "action":      "query",
        "format":      "json",
        "prop":        "imageinfo",
        "titles":      src_filename,
        "iiprop":      "url",
        "iilocalonly": 1,
    }

    # --- Resolve direct URL via the MediaWiki API ---------------------------
    try:
        api_response = requests.get(url=src_endpoint, params=param)
        api_response.raise_for_status()
        pages = api_response.json()["query"]["pages"]
    except requests.RequestException as e:
        raise DownloadError(
            f"Network error querying image info for '{src_filename}' "
            f"on {src_lang}.{src_project}: {e}"
        ) from e
    except (KeyError, ValueError) as e:
        raise DownloadError(
            f"Unexpected API response for '{src_filename}' "
            f"on {src_lang}.{src_project}: {e}"
        ) from e

    try:
        image_url = list(pages.values())[0]["imageinfo"][0]["url"]
    except (KeyError, IndexError):
        # Image not found on the source wiki (e.g. it is only on Commons).
        raise DownloadError(
            f"'{src_filename}' was not found on {src_lang}.{src_project}.org. "
            "It may be hosted on Wikimedia Commons instead."
        )

    # --- Download the binary file -------------------------------------------
    try:
        download_response = requests.get(image_url, allow_redirects=True)
        download_response.raise_for_status()
    except requests.RequestException as e:
        raise DownloadError(
            f"Failed to download image from '{image_url}': {e}"
        ) from e

    # Build a collision-resistant filename from the current timestamp.
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S_%f")
    content_type = download_response.headers.get("content-type", "image/jpeg")
    extension = content_type.replace("image/", "")
    local_filename = f"{timestamp}.{extension}"

    # Write to disk using a context manager so the handle is always closed.
    try:
        with open(f"temp_images/{local_filename}", "wb") as fh:
            fh.write(download_response.content)
    except OSError as e:
        raise DownloadError(
            f"Failed to save downloaded file '{local_filename}' to disk: {e}"
        ) from e

    logger.info("Downloaded '%s' → temp_images/%s", src_filename, local_filename)
    return local_filename


# ---------------------------------------------------------------------------
# File upload to target wiki
# ---------------------------------------------------------------------------

def process_upload(
    file_path: str,
    tr_filename: str,
    src_fileext: str,
    tr_endpoint: str,
    ses,
):
    """
    Upload the file at *file_path* to *tr_endpoint* using the authenticated
    session *ses*.

    Returns a dict ``{"wikipage_url": …, "file_link": …}`` on success.

    Raises
    ------
    UploadError
        If the CSRF token cannot be obtained, the POST request fails, the
        local file cannot be read, or the wiki rejects the upload.
    """
    # --- Obtain a CSRF token ------------------------------------------------
    csrf_param = {"action": "query", "meta": "tokens", "format": "json"}

    try:
        csrf_response = requests.get(url=tr_endpoint, params=csrf_param, auth=ses)
        csrf_response.raise_for_status()
        csrf_token = csrf_response.json()["query"]["tokens"]["csrftoken"]
    except requests.RequestException as e:
        raise UploadError(
            f"Network error fetching CSRF token from '{tr_endpoint}': {e}"
        ) from e
    except (KeyError, ValueError) as e:
        raise UploadError(
            f"Unexpected CSRF token response from '{tr_endpoint}': {e}"
        ) from e

    upload_param = {
        "action":         "upload",
        "filename":       f"{tr_filename}.{src_fileext}",
        "format":         "json",
        "token":          csrf_token,
        "ignorewarnings": 1,
    }

    # --- POST the file ------------------------------------------------------
    # The file handle is opened inside a context manager so it is guaranteed
    # to be closed after the request completes, even if an exception is raised.
    try:
        with open(file_path, "rb") as fh:
            upload_response = requests.post(
                url=tr_endpoint,
                files={"file": fh},
                data=upload_param,
                auth=ses,
            )
        upload_response.raise_for_status()
        response_json = upload_response.json()
    except OSError as e:
        raise UploadError(
            f"Could not open local file '{file_path}' for upload: {e}"
        ) from e
    except requests.RequestException as e:
        raise UploadError(
            f"Network error uploading '{tr_filename}' to '{tr_endpoint}': {e}"
        ) from e
    except ValueError as e:
        raise UploadError(
            f"Invalid JSON in upload response from '{tr_endpoint}': {e}"
        ) from e

    # --- Parse the upload response ------------------------------------------
    try:
        wikifile_url = response_json["upload"]["imageinfo"]["descriptionurl"]
        file_link    = response_json["upload"]["imageinfo"]["url"]
    except KeyError:
        # The wiki returned a response but without imageinfo – upload rejected
        # (e.g. insufficient permissions, duplicate file, etc.).
        raise UploadError(
            f"Upload of '{tr_filename}' was rejected by the target wiki. "
            f"Response: {response_json}"
        )

    logger.info("Uploaded '%s' → %s", tr_filename, wikifile_url)
    return {"wikipage_url": wikifile_url, "file_link": file_link}


# ---------------------------------------------------------------------------
# Wikitext localisation
# ---------------------------------------------------------------------------

def get_localized_wikitext(wikitext: str, src_endpoint: str, target_lang: str) -> str:
    """
    Replace the ``Article=`` parameter in known infobox templates with the
    localised article title for *target_lang*.

    Falls back to the original *wikitext* if the API call fails or the
    template/language is not found, so the upload flow is never blocked.
    """
    wikicode = mwparserfromhell.parse(wikitext)

    for template in wikicode.filter_templates():
        if template.name.strip() not in TEMPLATES:
            continue

        if not template.has("Article"):
            continue

        article_value = template.get("Article")
        if not article_value:
            continue

        article_title = article_value.value.strip()
        lang_params = {
            "action":        "query",
            "format":        "json",
            "prop":          "langlinks",
            "titles":        article_title,
            "formatversion": "2",
        }

        try:
            response = requests.get(url=src_endpoint, params=lang_params)
            response.raise_for_status()
            langlinks = response.json()["query"]["pages"][0]["langlinks"]

            for langlink in langlinks:
                if langlink["lang"] == target_lang:
                    template.add("Article", langlink["title"])
                    logger.debug(
                        "Localised Article '%s' → '%s' (%s)",
                        article_title, langlink["title"], target_lang,
                    )
                    break

        except (KeyError, IndexError):
            # No langlinks found for this article – keep the original value.
            logger.debug(
                "No '%s' langlink found for article '%s'", target_lang, article_title
            )
        except requests.RequestException as e:
            # Network failure – log and return what we have so far rather than
            # failing the entire upload.
            logger.warning(
                "Failed to fetch langlinks for '%s' from '%s': %s",
                article_title, src_endpoint, e,
            )
            return str(wikicode)

    return str(wikicode)


# ---------------------------------------------------------------------------
# Shared headers
# ---------------------------------------------------------------------------

def getHeader() -> dict:
    """Return the standard User-Agent header for all outgoing HTTP requests."""
    agent = (
        "Wikifile-transfer/1.0 "
        "(https://wikifile-transfer.toolforge.org; 0freerunning@gmail.com)"
    )
    return {"User-Agent": agent}
