import pytest
import json
import os
import sys
from unittest.mock import patch, MagicMock, mock_open

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDownloadImage:
    """Tests for utils.download_image()"""

    @patch('utils.requests.get')
    def test_returns_none_on_api_failure(self, mock_get):
        """download_image returns None when the source wiki API call fails."""
        import requests as req
        mock_get.side_effect = req.RequestException("Connection error")

        from utils import download_image
        result = download_image("wikimedia", "commons", "File:Test.jpg")
        assert result is None

    @patch('utils.requests.get')
    def test_returns_none_on_missing_imageinfo(self, mock_get):
        """download_image returns None when imageinfo key is missing from API response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "query": {"pages": {"-1": {"title": "File:Test.jpg", "missing": ""}}}
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        from utils import download_image
        result = download_image("wikimedia", "commons", "File:Test.jpg")
        assert result is None

    @patch('utils.os.makedirs')
    @patch('builtins.open', mock_open())
    @patch('utils.requests.get')
    def test_handles_non_image_content_type(self, mock_get, mock_makedirs):
        """download_image handles non-image content-type gracefully."""
        # First call: API response with image URL
        api_response = MagicMock()
        api_response.json.return_value = {
            "query": {"pages": {"123": {"imageinfo": [{"url": "https://example.com/test.jpg"}]}}}
        }
        api_response.raise_for_status = MagicMock()

        # Second call: image download with non-image content-type
        download_response = MagicMock()
        download_response.headers = {'content-type': 'text/html'}
        download_response.content = b'<html>error</html>'
        download_response.raise_for_status = MagicMock()

        mock_get.side_effect = [api_response, download_response]

        from utils import download_image
        result = download_image("wikimedia", "commons", "File:Test.jpg")
        # Should still return a filename (fallback to URL extension)
        assert result is not None
        assert result.endswith('.jpg')

    @patch('utils.requests.get')
    def test_returns_none_on_malformed_json(self, mock_get):
        """download_image returns None when API returns unexpected JSON structure."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": {"code": "badtitle"}}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        from utils import download_image
        result = download_image("wikimedia", "commons", "File:Test.jpg")
        assert result is None


class TestProcessUpload:
    """Tests for utils.process_upload()"""

    @patch('utils.requests.post')
    @patch('utils.requests.get')
    def test_returns_none_on_csrf_failure(self, mock_get, mock_post):
        """process_upload returns None when CSRF token retrieval fails."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": {"code": "badtoken"}}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        from utils import process_upload
        # Create a temp file for the test
        os.makedirs("temp_images", exist_ok=True)
        test_path = "temp_images/test_csrf_fail.jpg"
        with open(test_path, 'wb') as f:
            f.write(b'fake image data')

        result = process_upload(test_path, "TestFile", "jpg", "https://en.wikipedia.org/w/api.php", MagicMock())
        assert result is None

    @patch('utils.requests.post')
    @patch('utils.requests.get')
    def test_returns_none_on_mediawiki_error(self, mock_get, mock_post):
        """process_upload returns None when MediaWiki API returns an error response."""
        # CSRF token response (success)
        csrf_response = MagicMock()
        csrf_response.json.return_value = {"query": {"tokens": {"csrftoken": "abc123+\\"}}}
        csrf_response.raise_for_status = MagicMock()
        mock_get.return_value = csrf_response

        # Upload response (MediaWiki error)
        upload_response = MagicMock()
        upload_response.json.return_value = {
            "error": {"code": "mustbeloggedin", "info": "You must be logged in to upload files."}
        }
        upload_response.raise_for_status = MagicMock()
        mock_post.return_value = upload_response

        from utils import process_upload
        os.makedirs("temp_images", exist_ok=True)
        test_path = "temp_images/test_mw_error.jpg"
        with open(test_path, 'wb') as f:
            f.write(b'fake image data')

        result = process_upload(test_path, "TestFile", "jpg", "https://en.wikipedia.org/w/api.php", MagicMock())
        assert result is None

    @patch('utils.requests.post')
    @patch('utils.requests.get')
    def test_successful_upload_returns_urls(self, mock_get, mock_post):
        """process_upload returns file URLs on success."""
        # CSRF token response
        csrf_response = MagicMock()
        csrf_response.json.return_value = {"query": {"tokens": {"csrftoken": "abc123+\\"}}}
        csrf_response.raise_for_status = MagicMock()
        mock_get.return_value = csrf_response

        # Upload response (success)
        upload_response = MagicMock()
        upload_response.json.return_value = {
            "upload": {
                "result": "Success",
                "imageinfo": {
                    "descriptionurl": "https://en.wikipedia.org/wiki/File:Test.jpg",
                    "url": "https://upload.wikimedia.org/wikipedia/en/Test.jpg"
                }
            }
        }
        upload_response.raise_for_status = MagicMock()
        mock_post.return_value = upload_response

        from utils import process_upload
        os.makedirs("temp_images", exist_ok=True)
        test_path = "temp_images/test_success.jpg"
        with open(test_path, 'wb') as f:
            f.write(b'fake image data')

        result = process_upload(test_path, "TestFile", "jpg", "https://en.wikipedia.org/w/api.php", MagicMock())
        assert result is not None
        assert "wikipage_url" in result
        assert "file_link" in result

    @patch('utils.requests.get')
    def test_returns_none_on_network_error(self, mock_get):
        """process_upload returns None on network error."""
        import requests
        mock_get.side_effect = requests.RequestException("Connection refused")

        from utils import process_upload
        os.makedirs("temp_images", exist_ok=True)
        test_path = "temp_images/test_network.jpg"
        with open(test_path, 'wb') as f:
            f.write(b'fake image data')

        result = process_upload(test_path, "TestFile", "jpg", "https://en.wikipedia.org/w/api.php", MagicMock())
        assert result is None


class TestCleanupTempFile:
    """Tests for utils.cleanup_temp_file()"""

    def test_removes_existing_file(self):
        """cleanup_temp_file removes an existing temp file."""
        os.makedirs("temp_images", exist_ok=True)
        test_path = "temp_images/test_cleanup.jpg"
        with open(test_path, 'wb') as f:
            f.write(b'test data')

        from utils import cleanup_temp_file
        cleanup_temp_file(test_path)
        assert not os.path.exists(test_path)

    def test_handles_nonexistent_file(self):
        """cleanup_temp_file handles nonexistent files gracefully."""
        from utils import cleanup_temp_file
        # Should not raise
        cleanup_temp_file("temp_images/nonexistent_file.jpg")

    def test_handles_none_path(self):
        """cleanup_temp_file handles None path gracefully."""
        from utils import cleanup_temp_file
        # Should not raise
        cleanup_temp_file(None)
