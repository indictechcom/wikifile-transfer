
import os
import pytest
from unittest.mock import patch, MagicMock, mock_open

from globalExceptions import (
    APIRequestError,
    CSRFTokenError,
    FileNotFoundOnWikiError,
    ImageDownloadError,
    UploadError,
)
import requests


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_response(json_data=None, status_code=200, headers=None, content=b"imagedata"):
    """Build a mock requests.Response."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data or {}
    mock.headers = headers or {"content-type": "image/jpeg"}
    mock.content = content
    mock.raise_for_status = MagicMock()
    if status_code >= 400:
        http_err = requests.HTTPError(response=mock)
        mock.raise_for_status.side_effect = http_err
    return mock


# ── _fetch_csrf_token ─────────────────────────────────────────────────────────

class TestFetchCSRFToken:
    def test_returns_token_on_success(self):
        mock_resp = _mock_response({
            "query": {"tokens": {"csrftoken": "abc+\\"}}
        })
        with patch("utils.requests.get", return_value=mock_resp):
            from utils import _fetch_csrf_token
            token = _fetch_csrf_token("https://en.wikipedia.org/w/api.php", auth=None)
        assert token == "abc+\\"

    def test_raises_csrf_error_on_http_error(self):
        mock_resp = _mock_response(status_code=403)
        with patch("utils.requests.get", return_value=mock_resp):
            from utils import _fetch_csrf_token
            with pytest.raises(CSRFTokenError, match="HTTP error"):
                _fetch_csrf_token("https://en.wikipedia.org/w/api.php", auth=None)

    def test_raises_csrf_error_on_network_error(self):
        with patch("utils.requests.get", side_effect=requests.ConnectionError("refused")):
            from utils import _fetch_csrf_token
            with pytest.raises(CSRFTokenError, match="Network error"):
                _fetch_csrf_token("https://en.wikipedia.org/w/api.php", auth=None)

    def test_raises_csrf_error_on_missing_key(self):
        mock_resp = _mock_response({"unexpected": "structure"})
        with patch("utils.requests.get", return_value=mock_resp):
            from utils import _fetch_csrf_token
            with pytest.raises(CSRFTokenError, match="Unexpected response format"):
                _fetch_csrf_token("https://en.wikipedia.org/w/api.php", auth=None)


# download_image

class TestDownloadImage:

    _GOOD_API_RESPONSE = {
        "query": {
            "pages": {
                "12345": {
                    "imageinfo": [{"url": "https://upload.wikimedia.org/File:Cat.jpg"}]
                }
            }
        }
    }

    def test_happy_path_returns_filename(self, tmp_path):
        api_resp = _mock_response(self._GOOD_API_RESPONSE)
        img_resp = _mock_response(content=b"JPEG_DATA",
                                   headers={"content-type": "image/jpeg"})

        with patch("utils.requests.get", side_effect=[api_resp, img_resp]), \
             patch("utils._TEMP_DIR", str(tmp_path)), \
             patch("utils.os.makedirs"), \
             patch("builtins.open", mock_open()):
            from utils import download_image
            result = download_image("wikipedia", "en", "File:Cat.jpg")

        assert result.endswith(".jpeg") or result.endswith(".jpg")

    def test_raises_file_not_found_when_imageinfo_absent(self):
        api_resp = _mock_response({
            "query": {"pages": {"12345": {}}}  # no imageinfo key
        })
        with patch("utils.requests.get", return_value=api_resp):
            from utils import download_image
            with pytest.raises(FileNotFoundOnWikiError) as exc_info:
                download_image("wikipedia", "en", "File:Missing.jpg")
        assert "File:Missing.jpg" in str(exc_info.value)

    def test_raises_api_request_error_on_http_error(self):
        api_resp = _mock_response(status_code=500)
        with patch("utils.requests.get", return_value=api_resp):
            from utils import download_image
            with pytest.raises(APIRequestError) as exc_info:
                download_image("wikipedia", "en", "File:Cat.jpg")
        assert exc_info.value.status_code == 500

    def test_raises_api_request_error_on_network_error(self):
        with patch("utils.requests.get", side_effect=requests.ConnectionError("refused")):
            from utils import download_image
            with pytest.raises(APIRequestError):
                download_image("wikipedia", "en", "File:Cat.jpg")

    def test_raises_image_download_error_on_bad_content_type(self):
        api_resp = _mock_response(self._GOOD_API_RESPONSE)
        img_resp = _mock_response(content=b"DATA",
                                   headers={"content-type": ""})

        with patch("utils.requests.get", side_effect=[api_resp, img_resp]):
            from utils import download_image
            with pytest.raises(ImageDownloadError, match="content-type"):
                download_image("wikipedia", "en", "File:Cat.jpg")

    def test_raises_image_download_error_on_download_http_error(self):
        api_resp = _mock_response(self._GOOD_API_RESPONSE)
        img_resp = _mock_response(status_code=404,
                                   headers={"content-type": "image/jpeg"})

        with patch("utils.requests.get", side_effect=[api_resp, img_resp]):
            from utils import download_image
            with pytest.raises(ImageDownloadError, match="HTTP error"):
                download_image("wikipedia", "en", "File:Cat.jpg")

    def test_raises_image_download_error_on_write_failure(self):
        api_resp = _mock_response(self._GOOD_API_RESPONSE)
        img_resp = _mock_response(content=b"DATA",
                                   headers={"content-type": "image/jpeg"})

        with patch("utils.requests.get", side_effect=[api_resp, img_resp]), \
             patch("utils.os.makedirs"), \
             patch("builtins.open", side_effect=OSError("disk full")):
            from utils import download_image
            with pytest.raises(ImageDownloadError, match="Could not write"):
                download_image("wikipedia", "en", "File:Cat.jpg")

    def test_raises_image_download_error_on_network_error_during_download(self):
        api_resp = _mock_response(self._GOOD_API_RESPONSE)

        with patch("utils.requests.get",
                   side_effect=[api_resp, requests.ConnectionError("refused")]):
            from utils import download_image
            with pytest.raises(ImageDownloadError, match="Network error"):
                download_image("wikipedia", "en", "File:Cat.jpg")

    def test_endpoint_built_correctly(self):
        """Verify the API endpoint URL is constructed from project + lang."""
        api_resp = _mock_response({
            "query": {"pages": {"12345": {}}}
        })
        with patch("utils.requests.get", return_value=api_resp) as mock_get:
            from utils import download_image
            try:
                download_image("wikipedia", "fr", "File:Chat.jpg")
            except FileNotFoundOnWikiError:
                pass
        called_url = mock_get.call_args[1]["url"]
        assert "fr.wikipedia.org" in called_url


# process_upload

class TestProcessUpload:

    _CSRF_RESPONSE = {
        "query": {"tokens": {"csrftoken": "test_token+\\"}}
    }
    _UPLOAD_RESPONSE = {
        "upload": {
            "imageinfo": {
                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Cat.jpg",
                "url": "https://upload.wikimedia.org/Cat.jpg",
            }
        }
    }

    def test_happy_path_returns_urls(self, tmp_path):
        fake_file = tmp_path / "image.jpg"
        fake_file.write_bytes(b"JPEG")

        csrf_resp = _mock_response(self._CSRF_RESPONSE)
        upload_resp = _mock_response(self._UPLOAD_RESPONSE)

        with patch("utils.requests.get", return_value=csrf_resp), \
             patch("utils.requests.post", return_value=upload_resp):
            from utils import process_upload
            result = process_upload(str(fake_file), "Cat", "jpg",
                                    "https://commons.wikimedia.org/w/api.php", ses=None)

        assert result["wikipage_url"] == "https://commons.wikimedia.org/wiki/File:Cat.jpg"
        assert result["file_link"] == "https://upload.wikimedia.org/Cat.jpg"

    def test_csrf_token_failure_returns_error_response(self, tmp_path):
        """Test process_upload returns a CSRF error response instead of raising."""
        fake_file = tmp_path / "image.jpg"
        fake_file.write_bytes(b"JPEG")

        # Simulate 403 HTTP error when fetching CSRF token
        csrf_resp = _mock_response(status_code=403)
        from utils import process_upload
        with patch("utils.requests.get", return_value=csrf_resp):
            resp = process_upload(str(fake_file), "Cat", "jpg",
                                  "https://commons.wikimedia.org/w/api.php", ses=None)

        # Validate returned dict
        assert resp["success"] is False
        assert resp["error_type"] == "CSRFTokenError"
        assert "HTTP error fetching CSRF token" in resp["error"]

    def test_raises_upload_error_when_file_missing(self):
        csrf_resp = _mock_response(self._CSRF_RESPONSE)
        with patch("utils.requests.get", return_value=csrf_resp):
            from utils import process_upload
            with pytest.raises(UploadError, match="Local file not found"):
                process_upload("/nonexistent/path/image.jpg", "Cat", "jpg",
                               "https://commons.wikimedia.org/w/api.php", ses=None)

    def test_raises_api_request_error_on_upload_http_error(self, tmp_path):
        fake_file = tmp_path / "image.jpg"
        fake_file.write_bytes(b"JPEG")

        csrf_resp = _mock_response(self._CSRF_RESPONSE)
        upload_resp = _mock_response(status_code=500)

        with patch("utils.requests.get", return_value=csrf_resp), \
             patch("utils.requests.post", return_value=upload_resp):
            from utils import process_upload
            with pytest.raises(APIRequestError) as exc_info:
                process_upload(str(fake_file), "Cat", "jpg",
                               "https://commons.wikimedia.org/w/api.php", ses=None)
        assert exc_info.value.status_code == 500

    def test_raises_api_request_error_on_network_error(self, tmp_path):
        fake_file = tmp_path / "image.jpg"
        fake_file.write_bytes(b"JPEG")

        csrf_resp = _mock_response(self._CSRF_RESPONSE)

        with patch("utils.requests.get", return_value=csrf_resp), \
             patch("utils.requests.post", side_effect=requests.ConnectionError("refused")):
            from utils import process_upload
            with pytest.raises(APIRequestError):
                process_upload(str(fake_file), "Cat", "jpg",
                               "https://commons.wikimedia.org/w/api.php", ses=None)

    def test_raises_upload_error_on_missing_imageinfo(self, tmp_path):
        fake_file = tmp_path / "image.jpg"
        fake_file.write_bytes(b"JPEG")

        csrf_resp = _mock_response(self._CSRF_RESPONSE)
        bad_upload_resp = _mock_response({
            "upload": {"result": "Failure", "warnings": {"duplicate": ["File:Other.jpg"]}}
        })

        with patch("utils.requests.get", return_value=csrf_resp), \
             patch("utils.requests.post", return_value=bad_upload_resp):
            from utils import process_upload
            with pytest.raises(UploadError):
                process_upload(str(fake_file), "Cat", "jpg",
                               "https://commons.wikimedia.org/w/api.php", ses=None)

    def test_upload_error_contains_api_error_info(self, tmp_path):
        fake_file = tmp_path / "image.jpg"
        fake_file.write_bytes(b"JPEG")

        csrf_resp = _mock_response(self._CSRF_RESPONSE)
        bad_upload_resp = _mock_response({
            "error": {"info": "You do not have permission to upload files."}
        })

        with patch("utils.requests.get", return_value=csrf_resp), \
             patch("utils.requests.post", return_value=bad_upload_resp):
            from utils import process_upload
            with pytest.raises(UploadError) as exc_info:
                process_upload(str(fake_file), "Cat", "jpg",
                               "https://commons.wikimedia.org/w/api.php", ses=None)
        assert "permission" in str(exc_info.value)


# ── get_localized_wikitext ────────────────────────────────────────────────────

class TestGetLocalizedWikitext:

    _SIMPLE_WIKITEXT = "{{Photograph|Article=Cat}}"
    _LANGLINKS_RESPONSE = {
        "query": {
            "pages": [{
                "langlinks": [
                    {"lang": "fr", "title": "Chat"},
                    {"lang": "de", "title": "Katze"},
                ]
            }]
        }
    }

    def test_happy_path_rewrites_article_param(self):
        mock_resp = _mock_response(self._LANGLINKS_RESPONSE)

        with patch("utils.requests.get", return_value=mock_resp), \
             patch("utils.TEMPLATES", ["Photograph"]):
            from utils import get_localized_wikitext
            result = get_localized_wikitext(
                self._SIMPLE_WIKITEXT,
                "https://en.wikipedia.org/w/api.php",
                "fr"
            )
        assert "Chat" in result

    def test_returns_unchanged_when_no_langlink_found(self):
        response_no_match = _mock_response({
            "query": {
                "pages": [{
                    "langlinks": [{"lang": "de", "title": "Katze"}]
                }]
            }
        })

        with patch("utils.requests.get", return_value=response_no_match), \
             patch("utils.TEMPLATES", ["Photograph"]):
            from utils import get_localized_wikitext
            result = get_localized_wikitext(
                self._SIMPLE_WIKITEXT,
                "https://en.wikipedia.org/w/api.php",
                "fr"
            )
        # Article= should still be "Cat" since no French link was found
        assert "Cat" in result

    def test_skips_template_on_http_error_continues(self):
        """An HTTP error for one template should not crash the whole function."""
        mock_resp = _mock_response(status_code=503)

        with patch("utils.requests.get", return_value=mock_resp), \
             patch("utils.TEMPLATES", ["Photograph"]):
            from utils import get_localized_wikitext
            # Should not raise — just skip the template
            result = get_localized_wikitext(
                self._SIMPLE_WIKITEXT,
                "https://en.wikipedia.org/w/api.php",
                "fr"
            )
        assert isinstance(result, str)

    def test_skips_template_on_network_error_continues(self):
        with patch("utils.requests.get", side_effect=requests.ConnectionError("refused")), \
             patch("utils.TEMPLATES", ["Photograph"]):
            from utils import get_localized_wikitext
            result = get_localized_wikitext(
                self._SIMPLE_WIKITEXT,
                "https://en.wikipedia.org/w/api.php",
                "fr"
            )
        assert isinstance(result, str)

    def test_skips_template_on_unexpected_response_structure(self):
        mock_resp = _mock_response({"garbage": True})

        with patch("utils.requests.get", return_value=mock_resp), \
             patch("utils.TEMPLATES", ["Photograph"]):
            from utils import get_localized_wikitext
            result = get_localized_wikitext(
                self._SIMPLE_WIKITEXT,
                "https://en.wikipedia.org/w/api.php",
                "fr"
            )
        assert isinstance(result, str)

    def test_ignores_templates_not_in_list(self):
        wikitext = "{{SomeOtherTemplate|Article=Cat}}"

        with patch("utils.TEMPLATES", []):  # empty — no templates match
            from utils import get_localized_wikitext
            with patch("utils.requests.get") as mock_get:
                result = get_localized_wikitext(
                    wikitext,
                    "https://en.wikipedia.org/w/api.php",
                    "fr"
                )
                mock_get.assert_not_called()

    def test_returns_string(self):
        with patch("utils.requests.get", return_value=_mock_response(self._LANGLINKS_RESPONSE)), \
             patch("utils.TEMPLATES", ["Photograph"]):
            from utils import get_localized_wikitext
            result = get_localized_wikitext(
                self._SIMPLE_WIKITEXT,
                "https://en.wikipedia.org/w/api.php",
                "fr"
            )
        assert isinstance(result, str)

    def test_multiple_templates_processed(self):
        wikitext = "{{Photograph|Article=Cat}} {{Photograph|Article=Dog}}"
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return _mock_response(self._LANGLINKS_RESPONSE)

        with patch("utils.requests.get", side_effect=side_effect), \
             patch("utils.TEMPLATES", ["Photograph"]):
            from utils import get_localized_wikitext
            get_localized_wikitext(
                wikitext,
                "https://en.wikipedia.org/w/api.php",
                "fr"
            )
        assert call_count == 2
