"""
Tests for utils.py — download_image, process_upload, get_localized_wikitext, getHeader.

All external HTTP calls are mocked with unittest.mock so these tests run
without a live Wikimedia API or network connection.
"""

import os
import pytest
from unittest.mock import patch, MagicMock, mock_open

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_ENDPOINT = "https://en.wikipedia.org/w/api.php"
FAKE_IMAGE_URL = "https://upload.wikimedia.org/wikipedia/commons/test.jpg"
FAKE_FILENAME = "Test_file.jpg"


def _imageinfo_response(image_url=FAKE_IMAGE_URL):
    """Return a mock response that looks like MediaWiki imageinfo API."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "query": {
            "pages": {
                "12345": {
                    "imageinfo": [{"url": image_url}]
                }
            }
        }
    }
    mock_resp.headers = {"content-type": "image/jpeg"}
    mock_resp.content = b"fake image bytes"
    return mock_resp


def _csrf_response(token="+\\"):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "query": {"tokens": {"csrftoken": token}}
    }
    return mock_resp


def _upload_success_response():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "upload": {
            "imageinfo": {
                "descriptionurl": "https://en.wikipedia.org/wiki/File:Test.jpg",
                "url": "https://upload.wikimedia.org/wikipedia/en/Test.jpg",
            }
        }
    }
    return mock_resp


def _upload_failure_response():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"error": {"code": "badtoken"}}
    return mock_resp


# ---------------------------------------------------------------------------
# getHeader
# ---------------------------------------------------------------------------

class TestGetHeader:
    def test_returns_dict_with_user_agent(self):
        from utils import getHeader
        headers = getHeader()
        assert isinstance(headers, dict)
        assert "User-Agent" in headers

    def test_user_agent_not_empty(self):
        from utils import getHeader
        assert len(getHeader()["User-Agent"]) > 0

    def test_user_agent_identifies_tool(self):
        from utils import getHeader
        # The header must mention the tool so Wikimedia servers can identify it
        assert "wikifile" in getHeader()["User-Agent"].lower()


# ---------------------------------------------------------------------------
# download_image
# ---------------------------------------------------------------------------

class TestDownloadImage:
    @patch("utils.requests.get")
    def test_returns_filename_on_success(self, mock_get):
        """Happy path: API returns imageinfo, file is written, filename returned."""
        # First call: imageinfo query; second call: image download
        mock_get.side_effect = [_imageinfo_response(), _imageinfo_response()]

        with patch("builtins.open", mock_open()):
            from utils import download_image
            result = download_image("wikipedia", "en", FAKE_FILENAME)

        assert result is not None
        assert isinstance(result, str)
        assert result.endswith(".jpeg")

    @patch("utils.requests.get")
    def test_returns_none_when_imageinfo_missing(self, mock_get):
        """If the API returns a page with no imageinfo key, return None."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "query": {
                "pages": {
                    "-1": {"title": FAKE_FILENAME}  # no imageinfo key
                }
            }
        }
        mock_get.return_value = mock_resp

        from utils import download_image
        result = download_image("wikipedia", "en", FAKE_FILENAME)
        assert result is None

    @patch("utils.requests.get")
    def test_filename_is_timestamped(self, mock_get):
        """Generated filename must be unique (timestamp-based) to avoid collisions."""
        mock_get.side_effect = [_imageinfo_response(), _imageinfo_response()]

        with patch("builtins.open", mock_open()):
            from utils import download_image
            result1 = download_image("wikipedia", "en", FAKE_FILENAME)

        # Timestamp format uses underscores, not colons or spaces
        assert " " not in result1
        assert ":" not in result1

    @patch("utils.requests.get")
    def test_constructs_correct_endpoint(self, mock_get):
        """Endpoint URL must be built from project + lang."""
        mock_get.side_effect = [_imageinfo_response(), _imageinfo_response()]

        with patch("builtins.open", mock_open()):
            from utils import download_image
            download_image("commons", "en", FAKE_FILENAME)

        first_call_url = mock_get.call_args_list[0][1]["url"]
        assert "en.commons.org" in first_call_url

    @patch("utils.requests.get")
    def test_content_type_missing_returns_safely(self, mock_get):
        """If content-type header is absent, function must not crash with AttributeError."""
        imageinfo_resp = _imageinfo_response()
        download_resp = MagicMock()
        download_resp.headers = {}        # no content-type header
        download_resp.content = b"data"
        mock_get.side_effect = [imageinfo_resp, download_resp]

        with patch("builtins.open", mock_open()):
            from utils import download_image
            # Should not raise AttributeError on .replace('image/', '')
            try:
                download_image("wikipedia", "en", FAKE_FILENAME)
            except AttributeError:
                pytest.fail(
                    "download_image crashed with AttributeError on missing content-type. "
                    "headers.get('content-type') returned None and .replace() was called on it."
                )


# ---------------------------------------------------------------------------
# process_upload
# ---------------------------------------------------------------------------

class TestProcessUpload:
    @patch("utils.requests.post")
    @patch("utils.requests.get")
    def test_returns_urls_on_success(self, mock_get, mock_post):
        """Happy path: CSRF fetch + upload succeed, URLs returned."""
        mock_get.return_value = _csrf_response()
        mock_post.return_value = _upload_success_response()

        fake_auth = MagicMock()

        with patch("builtins.open", mock_open(read_data=b"img")):
            from utils import process_upload
            result = process_upload(
                "temp_images/test.jpg", "TestFile", "jpg",
                FAKE_ENDPOINT, fake_auth
            )

        assert result is not None
        assert "wikipage_url" in result
        assert "file_link" in result
        assert result["wikipage_url"].startswith("https://")

    @patch("utils.requests.post")
    @patch("utils.requests.get")
    def test_returns_none_when_upload_response_missing_imageinfo(self, mock_get, mock_post):
        """If MediaWiki rejects the upload (bad token, etc.), return None, not crash."""
        mock_get.return_value = _csrf_response()
        mock_post.return_value = _upload_failure_response()

        fake_auth = MagicMock()

        with patch("builtins.open", mock_open(read_data=b"img")):
            from utils import process_upload
            result = process_upload(
                "temp_images/test.jpg", "TestFile", "jpg",
                FAKE_ENDPOINT, fake_auth
            )

        assert result is None

    @patch("utils.requests.post")
    @patch("utils.requests.get")
    def test_upload_param_contains_correct_filename(self, mock_get, mock_post):
        """Uploaded filename must be trfilename + '.' + extension."""
        mock_get.return_value = _csrf_response()
        mock_post.return_value = _upload_success_response()
        fake_auth = MagicMock()

        with patch("builtins.open", mock_open(read_data=b"img")):
            from utils import process_upload
            process_upload(
                "temp_images/test.jpg", "MyPhoto", "png",
                FAKE_ENDPOINT, fake_auth
            )

        post_data = mock_post.call_args[1]["data"]
        assert post_data["filename"] == "MyPhoto.png"

    @patch("utils.requests.post")
    @patch("utils.requests.get")
    def test_csrf_token_sent_in_upload_request(self, mock_get, mock_post):
        """The CSRF token obtained from the API must be included in the upload POST."""
        token = "test_csrf_token_abc123+\\"
        mock_get.return_value = _csrf_response(token=token)
        mock_post.return_value = _upload_success_response()
        fake_auth = MagicMock()

        with patch("builtins.open", mock_open(read_data=b"img")):
            from utils import process_upload
            process_upload(
                "temp_images/test.jpg", "TestFile", "jpg",
                FAKE_ENDPOINT, fake_auth
            )

        post_data = mock_post.call_args[1]["data"]
        assert post_data["token"] == token


# ---------------------------------------------------------------------------
# get_localized_wikitext
# ---------------------------------------------------------------------------

WIKITEXT_WITH_TEMPLATE = """\
== License ==
{{Non-free film poster
| Article = Lagaan
| Description = Promotional poster for Lagaan
}}
"""

WIKITEXT_WITH_CATEGORY = """\
[[Category:Hindi films]]
[[Category:2001 Indian films]]
"""

WIKITEXT_WITH_SORT_KEY = """\
[[Category:Hindi films|Aamir]]
"""

WIKITEXT_NO_TEMPLATE = """\
== Description ==
A simple image without templates.
"""


class TestGetLocalizedWikitext:

    @patch("utils.requests.get")
    def test_localizes_article_param_when_langlink_found(self, mock_get):
        """Article param in a matching template must be replaced with target language title."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "query": {
                "pages": [{
                    "title": "Lagaan",
                    "langlinks": [{"lang": "bn", "title": "লগান"}]
                }]
            }
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        from utils import get_localized_wikitext
        result = get_localized_wikitext(WIKITEXT_WITH_TEMPLATE, FAKE_ENDPOINT, "bn")
        assert "লগান" in result

    @patch("utils.requests.get")
    def test_preserves_original_when_no_langlink_for_target(self, mock_get):
        """If no langlink matches target_lang, original Article value must be kept."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "query": {
                "pages": [{
                    "title": "Lagaan",
                    "langlinks": [{"lang": "fr", "title": "Lagaan (film)"}]  # fr, not bn
                }]
            }
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        from utils import get_localized_wikitext
        result = get_localized_wikitext(WIKITEXT_WITH_TEMPLATE, FAKE_ENDPOINT, "bn")
        assert "Lagaan" in result  # original preserved

    @patch("utils.requests.get")
    def test_returns_original_on_api_exception(self, mock_get):
        """If the Langlinks API call raises any exception, return the original wikitext."""
        mock_get.side_effect = Exception("network error")

        from utils import get_localized_wikitext
        result = get_localized_wikitext(WIKITEXT_WITH_TEMPLATE, FAKE_ENDPOINT, "bn")
        # Must not crash; must return a non-empty string
        assert isinstance(result, str)
        assert len(result) > 0

    @patch("utils.requests.get")
    def test_passthrough_when_no_matching_templates(self, mock_get):
        """Wikitext without any matching templates must be returned unchanged."""
        from utils import get_localized_wikitext
        result = get_localized_wikitext(WIKITEXT_NO_TEMPLATE, FAKE_ENDPOINT, "hi")
        assert "simple image" in result
        mock_get.assert_not_called()

    @patch("utils.requests.get")
    def test_wikitext_without_templates_is_not_modified(self, mock_get):
        """Plain wikitext returns identical content (no mutation)."""
        from utils import get_localized_wikitext
        result = get_localized_wikitext(WIKITEXT_NO_TEMPLATE, FAKE_ENDPOINT, "ta")
        assert result.strip() == WIKITEXT_NO_TEMPLATE.strip()

    @patch("utils.requests.get")
    def test_categories_not_localized_in_current_implementation(self, mock_get):
        """
        Documents the known gap: [[Category:...]] nodes are NOT currently localized.
        This test acts as a regression marker — if category localization is added,
        this test should be updated to assert the new behaviour.
        """
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "query": {
                "pages": [{
                    "title": "Category:Hindi films",
                    "langlinks": [{"lang": "bn", "title": "বিষয়শ্রেণী:হিন্দি চলচ্চিত্র"}]
                }]
            }
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        from utils import get_localized_wikitext
        result = get_localized_wikitext(WIKITEXT_WITH_CATEGORY, FAKE_ENDPOINT, "bn")

        # Current implementation does NOT localize categories.
        # After the GSoC category localization feature is merged, this assertion changes.
        assert "Category:Hindi films" in result, (
            "Category localization is not yet implemented. "
            "[[Category:Hindi films]] should still be present in the output."
        )