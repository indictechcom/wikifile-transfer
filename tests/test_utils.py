"""
Tests for utility functions in utils.py
"""
import pytest
from unittest.mock import patch, MagicMock, mock_open


class TestDownloadImage:
    """Tests for download_image()"""

    @patch("utils.requests.get")
    def test_returns_none_when_imageinfo_missing(self, mock_get):
        from utils import download_image

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "query": {"pages": {"-1": {"title": "File:Missing.jpg"}}}
        }
        mock_get.return_value = mock_response

        result = download_image("wikipedia", "en", "File:Missing.jpg")
        assert result is None

    @patch("builtins.open", mock_open())
    @patch("utils.requests.get")
    def test_returns_filename_on_success(self, mock_get):
        from utils import download_image

        api_response = MagicMock()
        api_response.json.return_value = {
            "query": {
                "pages": {
                    "1": {
                        "imageinfo": [{"url": "https://upload.wikimedia.org/test.jpg"}]
                    }
                }
            }
        }

        file_response = MagicMock()
        file_response.headers = {"content-type": "image/jpeg"}
        file_response.content = b"fake-image-bytes"

        mock_get.side_effect = [api_response, file_response]

        result = download_image("wikipedia", "en", "File:Test.jpg")
        assert result is not None
        assert result.endswith(".jpeg")

    @patch("utils.requests.get")
    def test_constructs_correct_api_endpoint(self, mock_get):
        from utils import download_image

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "query": {"pages": {"-1": {}}}
        }
        mock_get.return_value = mock_response

        download_image("wikipedia", "fr", "File:Test.jpg")

        called_url = mock_get.call_args[1]["url"]
        assert "fr.wikipedia.org" in called_url


class TestProcessUpload:
    """Tests for process_upload()"""

    @patch("utils.requests.post")
    @patch("utils.requests.get")
    def test_returns_none_when_upload_response_missing_keys(self, mock_get, mock_post):
        from utils import process_upload

        csrf_response = MagicMock()
        csrf_response.json.return_value = {"query": {"tokens": {"csrftoken": "test+\\"}}}
        mock_get.return_value = csrf_response

        upload_response = MagicMock()
        upload_response.json.return_value = {"upload": {"result": "Warning"}}
        mock_post.return_value = upload_response

        with patch("builtins.open", mock_open(read_data=b"fake")):
            result = process_upload(
                "temp/test.jpg", "Test", "jpg",
                "https://fr.wikipedia.org/w/api.php", MagicMock()
            )
        assert result is None

    @patch("utils.requests.post")
    @patch("utils.requests.get")
    def test_returns_urls_on_successful_upload(self, mock_get, mock_post):
        from utils import process_upload

        csrf_response = MagicMock()
        csrf_response.json.return_value = {"query": {"tokens": {"csrftoken": "test+\\"}}}
        mock_get.return_value = csrf_response

        upload_response = MagicMock()
        upload_response.json.return_value = {
            "upload": {
                "imageinfo": {
                    "descriptionurl": "https://fr.wikipedia.org/wiki/File:Test.jpg",
                    "url": "https://upload.wikimedia.org/test.jpg"
                }
            }
        }
        mock_post.return_value = upload_response

        with patch("builtins.open", mock_open(read_data=b"fake")):
            result = process_upload(
                "temp/test.jpg", "Test", "jpg",
                "https://fr.wikipedia.org/w/api.php", MagicMock()
            )

        assert result is not None
        assert result["wikipage_url"] == "https://fr.wikipedia.org/wiki/File:Test.jpg"
        assert result["file_link"] == "https://upload.wikimedia.org/test.jpg"

    @patch("utils.requests.post")
    @patch("utils.requests.get")
    def test_upload_includes_correct_filename(self, mock_get, mock_post):
        from utils import process_upload

        csrf_response = MagicMock()
        csrf_response.json.return_value = {"query": {"tokens": {"csrftoken": "test+\\"}}}
        mock_get.return_value = csrf_response

        upload_response = MagicMock()
        upload_response.json.return_value = {
            "upload": {
                "imageinfo": {
                    "descriptionurl": "https://fr.wikipedia.org/wiki/File:MyFile.jpg",
                    "url": "https://upload.wikimedia.org/myfile.jpg"
                }
            }
        }
        mock_post.return_value = upload_response

        with patch("builtins.open", mock_open(read_data=b"fake")):
            process_upload(
                "temp/test.jpg", "MyFile", "jpg",
                "https://fr.wikipedia.org/w/api.php", MagicMock()
            )

        post_data = mock_post.call_args[1]["data"]
        assert post_data["filename"] == "MyFile.jpg"


class TestGetLocalizedWikitext:
    """Tests for get_localized_wikitext()"""

    def test_returns_wikitext_unchanged_when_no_matching_templates(self):
        from utils import get_localized_wikitext

        wikitext = "== Description ==\nSome plain text with no templates."
        result = get_localized_wikitext(wikitext, "https://en.wikipedia.org/w/api.php", "fr")
        assert result == wikitext

    def test_returns_string(self):
        from utils import get_localized_wikitext

        result = get_localized_wikitext("plain text", "https://en.wikipedia.org/w/api.php", "de")
        assert isinstance(result, str)

    @patch("utils.requests.get")
    def test_returns_wikitext_on_api_error(self, mock_get):
        from utils import get_localized_wikitext
        from templatelist import TEMPLATES

        if not TEMPLATES:
            pytest.skip("TEMPLATES list is empty")

        import requests
        mock_get.side_effect = requests.RequestException("timeout")

        template_name = list(TEMPLATES)[0]
        wikitext = f"{{{{{template_name}|Article=Test article}}}}"

        result = get_localized_wikitext(wikitext, "https://en.wikipedia.org/w/api.php", "fr")
        assert isinstance(result, str)
        assert len(result) > 0
