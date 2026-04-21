import datetime
import requests
import mwparserfromhell
from templatelist import TEMPLATES
from logging_config import get_logger, log_file_operation, log_timed_api_call, log_exception
from exceptions import WikiAPIError, FileOperationError, ResourceNotFoundError, AuthenticationError
logger = get_logger(__name__)


import os
import datetime
import requests


def cleanup_temp_file(file_path):
    """Remove a temp file from disk. Silently ignores missing files."""
    if not file_path:
        return
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up temp file: {file_path}")
    except OSError as e:
        logger.warning(f"Failed to remove temp file {file_path}: {e}")


def download_image(src_project, src_lang, src_filename):
    """
    Download an image from a Wiki source.

    Raises:
        WikiAPIError
        FileOperationError
        ResourceNotFoundError
    """
    src_endpoint = f"https://{src_lang}.{src_project}.org/w/api.php"

    params = {
        "action": "query",
        "format": "json",
        "prop": "imageinfo",
        "titles": src_filename,
        "iiprop": "url",
        "iilocalonly": 1
    }

    # ─────────────────────────────────────
    # Fetch metadata
    # ─────────────────────────────────────
    try:
        logger.info(
            f"Fetching image info for {src_filename} "
            f"from {src_lang}.{src_project}.org"
        )

        with log_timed_api_call(logger, src_endpoint, "GET") as context:
            response = requests.get(
                url=src_endpoint,
                params=params,
                timeout=30,
                headers=getHeader()
            )
            response.raise_for_status()
            context["status_code"] = response.status_code
            #       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
            # this is why yield returns context dict
            # you set the status_code here
            # log_timed_api_call reads it in the else block

        data = response.json()
        logger.info(f"Raw API response for {src_filename}: {data}")
        page = data.get("query", {}).get("pages", {})

        if not page:
            raise ResourceNotFoundError(
                f"No page data returned for {src_filename}",
                resource_type="image",
                resource_id=src_filename
            )

        page_data = list(page.values())[0]

        if "imageinfo" not in page_data:
            raise ResourceNotFoundError(
                f"Image not found: {src_filename}",
                resource_type="image",
                resource_id=src_filename,
                details={"page_data": page_data}
            )

        image_url = page_data["imageinfo"][0]["url"]
        logger.info(f"Found image URL: {image_url}")

    except requests.exceptions.Timeout as e:
        raise WikiAPIError(
            f"Timeout while fetching image info for {src_filename}",
            api_endpoint=src_endpoint,
            details={"timeout_seconds": 30}
        ) from e

    except requests.exceptions.RequestException as e:
        raise WikiAPIError(
            f"Failed to fetch image info: {str(e)}",
            api_endpoint=src_endpoint,
            status_code=getattr(e.response, "status_code", None)
        ) from e

    except (KeyError, IndexError) as e:
        raise ResourceNotFoundError(
            f"Invalid response format for {src_filename}",
            resource_type="image",
            resource_id=src_filename,
            details={"error": str(e)}
        ) from e

    # ─────────────────────────────────────
    # Download file
    # ─────────────────────────────────────
    try:
        filename_base = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        logger.info(f"Downloading image from {image_url}")

        with log_timed_api_call(logger, image_url, "GET") as context:
            r = requests.get(image_url, allow_redirects=True, timeout=60, headers=getHeader())
            r.raise_for_status()
            context["status_code"] = r.status_code

        content_type = r.headers.get("Content-Type", "image/jpeg")
        mime = content_type.split(";")[0]
        file_extension = mime.replace("image/", "")
        filename = f"{filename_base}.{file_extension}"

        os.makedirs("temp_images", exist_ok=True)
        file_path = os.path.join("temp_images", filename)

        with open(file_path, "wb") as f:
            f.write(r.content)

        log_file_operation(
            logger,
            operation="download",
            file_path=file_path,
            success=True
        )

        logger.info(f"Image downloaded successfully: {filename}")
        return filename

    except requests.exceptions.Timeout as e:
        log_file_operation(
            logger,
            operation="download",
            file_path=image_url,
            success=False,
            error=str(e)
        )
        raise FileOperationError(
            f"Timeout while downloading image from {image_url}",
            operation="download",
            file_path=image_url,
            details={"timeout_seconds": 60}
        ) from e

    except requests.exceptions.RequestException as e:
        log_file_operation(
            logger,
            operation="download",
            file_path=image_url,
            success=False,
            error=str(e)
        )
        raise FileOperationError(
            f"Failed to download image: {str(e)}",
            operation="download",
            file_path=image_url
        ) from e

    except OSError as e:
        partial = file_path if "file_path" in locals() else None
        cleanup_temp_file(partial)
        log_file_operation(
            logger,
            operation="write",
            file_path=partial or "unknown",
            success=False,
            error=str(e)
        )
        raise FileOperationError(
            f"Failed to write image file: {str(e)}",
            operation="write",
            file_path=partial or "unknown"
        ) from e


# Uploads a file to the target wiki using OAuth — fetches CSRF token first, then POSTs the file
def process_upload(file_path, tr_filename, src_fileext, tr_endpoint, ses):
    logger.info(f"Starting upload process for {tr_filename}.{src_fileext}")

    csrf_param = {
        "action": "query",
        "meta": "tokens",
        "format": "json"
    }

    # ─────────────────────────────────────
    # Fetch CSRF token
    # ─────────────────────────────────────
    try:
        logger.info("Fetching CSRF token")

        with log_timed_api_call(logger, tr_endpoint, "GET") as context:
            response = requests.get(
                url=tr_endpoint,
                params=csrf_param,
                auth=ses,
                timeout=30,
                headers=getHeader()
            )
            response.raise_for_status()
            context["status_code"] = response.status_code

        csrf_token = response.json()["query"]["tokens"]["csrftoken"]

        if csrf_token == "+\\":
            raise AuthenticationError("Invalid CSRF token — OAuth session may have expired")

    except requests.exceptions.Timeout as e:
        raise WikiAPIError(
            "Timeout while fetching CSRF token",
            api_endpoint=tr_endpoint,
            details={"timeout_seconds": 30}
        ) from e

    except requests.exceptions.RequestException as e:
        raise WikiAPIError(
            f"Failed to fetch CSRF token: {str(e)}",
            api_endpoint=tr_endpoint,
            status_code=getattr(e.response, "status_code", None)
        ) from e

    except KeyError as e:
        raise WikiAPIError(
            f"Unexpected CSRF response format: missing {str(e)}",
            api_endpoint=tr_endpoint
        ) from e

    # ─────────────────────────────────────
    # Upload file
    # ─────────────────────────────────────
    try:
        if not os.path.exists(file_path):
            raise FileOperationError(
                f"File not found before upload: {file_path}",
                operation="check_file",
                file_path=file_path
            )

        upload_param = {
            "action": "upload",
            "filename": f"{tr_filename}.{src_fileext}",
            "format": "json",
            "token": csrf_token,
            "ignorewarnings": 1
        }

        logger.info(f"Uploading {file_path} to {tr_endpoint}")

        with log_timed_api_call(logger, tr_endpoint, "POST") as context:
            with open(file_path, "rb") as f:
                response = requests.post(
                    url=tr_endpoint,
                    files={"file": f},
                    data=upload_param,
                    auth=ses,
                    timeout=120
                )
            response.raise_for_status()
            context["status_code"] = response.status_code

        result = response.json()
        upload_result = result.get("upload", {})

        if upload_result.get("result") != "Success":
            error_info = upload_result.get("error", {}).get("info", "Unknown error")
            raise WikiAPIError(
                f"Upload failed: {error_info}",
                api_endpoint=tr_endpoint,
                details={"upload_result": upload_result}
            )

        if "imageinfo" not in upload_result:
            raise WikiAPIError(
                "Upload succeeded but no imageinfo returned",
                api_endpoint=tr_endpoint,
                details={"upload_result": upload_result}
            )

        wikifile_url = upload_result["imageinfo"]["descriptionurl"]
        file_link = upload_result["imageinfo"]["url"]

        log_file_operation(logger, "upload", file_path, success=True)
        logger.info(f"Upload successful: {tr_filename}.{src_fileext}")

        return {
            "wikipage_url": wikifile_url,
            "file_link": file_link
        }

    except requests.exceptions.Timeout as e:
        raise WikiAPIError(
            "Timeout while uploading file",
            api_endpoint=tr_endpoint,
            details={"timeout_seconds": 120}
        ) from e

    except requests.exceptions.RequestException as e:
        log_file_operation(logger, "upload", file_path, success=False, error=str(e))
        raise WikiAPIError(
            f"Failed to upload file: {str(e)}",
            api_endpoint=tr_endpoint,
            status_code=getattr(e.response, "status_code", None)
        ) from e

    except OSError as e:
        log_exception(logger, e, extra_context={"file_path": file_path})
        raise FileOperationError(
            f"Could not read file for upload: {str(e)}",
            operation="read",
            file_path=file_path
        ) from e


# Replaces the Article parameter in wiki templates with its translated title in the target language
def get_localized_wikitext(wikitext, src_endpoint, target_lang):
    logger.info(f"Localizing wikitext for target language: {target_lang}")

    try:
        wikicode = mwparserfromhell.parse(wikitext)
        templates_processed = 0
        templates_localized = 0

        for template in wikicode.filter_templates():
            if template.name.strip() in TEMPLATES:
                templates_processed += 1

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

                        # Per-article lookup — failures skip that article, not the whole function
                        try:
                            response = requests.get(
                                url=src_endpoint,
                                params=lang_param,
                                timeout=30,
                                headers=getHeader()
                            )
                            response.raise_for_status()

                            pages = response.json().get("query", {}).get("pages", [])

                            if pages and "langlinks" in pages[0]:
                                for langlink in pages[0]["langlinks"]:
                                    if langlink["lang"] == target_lang:
                                        template.add("Article", langlink["title"])
                                        templates_localized += 1
                                        logger.info(
                                            f"Localized: {article_title} -> {langlink['title']}"
                                        )
                                        break

                        except requests.exceptions.Timeout:
                            logger.warning(
                                f"Timeout fetching langlinks for {article_title}, skipping"
                            )
                            continue

                        except requests.exceptions.RequestException as e:
                            logger.warning(
                                f"Request error for {article_title}: {str(e)}, skipping"
                            )
                            continue

                        except (KeyError, IndexError) as e:
                            logger.warning(
                                f"Unexpected response format for {article_title}, skipping"
                            )
                            continue

        logger.info(
            f"Localization complete: {templates_localized}/{templates_processed} templates localized"
        )
        return str(wikicode)

    except Exception as e:
        logger.warning(f"Failed to localize wikitext: {str(e)}, returning original")
        log_exception(logger, e, extra_context={
            "function": "get_localized_wikitext",
            "target_lang": target_lang
        })
        return wikitext


# Returns the User-Agent header identifying this tool to the Wikimedia API
def getHeader():
    agent = 'Wikifile-transfer/1.0 (https://wikifile-transfer.toolforge.org; 0freerunning@gmail.com)'
    return {
        'User-Agent': agent
    }
