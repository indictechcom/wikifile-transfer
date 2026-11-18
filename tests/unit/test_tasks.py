"""
Unit tests for background tasks.
"""
import pytest
from unittest.mock import MagicMock, ANY
from tasks import upload_task_item, upload_image_task

class TestTasks:

    def test_upload_task_item_success(self, mocker):
        """
        GIVEN a task item with mock details
        WHEN upload_task_item is called via Celery
        THEN check that it successfully mocks the requests and returns the correct image/page URLs
        """
        mock_get = mocker.patch('tasks.requests.get')
        mock_post = mocker.patch('tasks.requests.post')
        mock_unquote = mocker.patch('tasks.urllib.parse.unquote', side_effect=lambda x: x)
        mock_open = mocker.patch('builtins.open', new_callable=MagicMock)
        mock_os_remove = mocker.patch('tasks.os.remove')
        mock_get_wikitext = mocker.patch('tasks.get_wikitext', return_value="Sample wikitext")

        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"query": {"tokens": {"csrftoken": "mock_csrf_token"}}}

        mock_post.return_value.json.return_value = {
            "upload": {
                "imageinfo": {
                    "descriptionurl": "http://mock.wiki/File:mock.jpg",
                    "url": "http://mock.wiki/images/mock.jpg"
                }
            }
        }

        task_item = {
            "lang": "en",
            "trfilename": "mock",
            "addTemplate": False,
            "pageContent": "",
            "editArticle": False,
            "articleLink": ""
        }
        OAuthObj = {
            "consumer_key": "123",
            "consumer_secret": "abc",
            "key": "xyz",
            "secret": "789"
        }

        mocker.patch('tasks.upload_task_item.update_state')
        result = upload_task_item("dummy/path.jpg", "wikipedia", task_item, "jpg", OAuthObj)

        assert "wikipage_url" in result
        assert result["wikipage_url"] == "http://mock.wiki/File:mock.jpg"
        assert result["file_link"] == "http://mock.wiki/images/mock.jpg"

    def test_upload_image_task_success(self, mocker):
        """
        GIVEN an image file to upload
        WHEN upload_image_task is called via Celery
        THEN check that it successfully mocks the Wikimedia API calls and returns the correct image URLs
        """
        mock_get = mocker.patch('tasks.requests.get')
        mock_post = mocker.patch('tasks.requests.post')
        mock_unquote = mocker.patch('tasks.urllib.parse.unquote', side_effect=lambda x: x)
        mock_open = mocker.patch('builtins.open', new_callable=MagicMock)
        mock_os_remove = mocker.patch('tasks.os.remove')
        mock_get_wikitext = mocker.patch('tasks.get_wikitext', return_value="Sample wikitext")

        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"query": {"tokens": {"csrftoken": "mock_csrf_token"}}}

        mock_post.return_value.json.return_value = {
            "upload": {
                "imageinfo": {
                    "descriptionurl": "http://mock.wiki/File:mock.jpg",
                    "url": "http://mock.wiki/images/mock.jpg"
                }
            }
        }

        OAuthObj = {
            "consumer_key": "123",
            "consumer_secret": "abc",
            "key": "xyz",
            "secret": "789"
        }

        mocker.patch('tasks.upload_image_task.update_state')
        result = upload_image_task("dummy/path.jpg", "mock", "jpg", "http://mock.endpoint", OAuthObj)

        assert "wikipage_url" in result
        assert result["wikipage_url"] == "http://mock.wiki/File:mock.jpg"
        assert result["file_link"] == "http://mock.wiki/images/mock.jpg"

    def test_upload_image_task_api_error_raises(self, mocker):
        """
        GIVEN an image file to upload
        WHEN upload_image_task is called and Wikimedia returns an API error
        THEN check that MediaWikiAPIError is raised (not returned as success)
        """
        from exceptions import MediaWikiAPIError

        mock_get = mocker.patch('tasks.requests.get')
        mock_post = mocker.patch('tasks.requests.post')
        mocker.patch('tasks.urllib.parse.unquote', side_effect=lambda x: x)
        mocker.patch('builtins.open', new_callable=MagicMock)
        mocker.patch('tasks.upload_image_task.update_state')

        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"query": {"tokens": {"csrftoken": "mock_csrf_token"}}}

        mock_post.return_value.json.return_value = {
            "error": {"code": "badtoken", "info": "Invalid CSRF token"}
        }

        OAuthObj = {"consumer_key": "1", "consumer_secret": "2", "key": "3", "secret": "4"}

        with pytest.raises(MediaWikiAPIError) as exc_info:
            upload_image_task("dummy/path.jpg", "mock", "jpg", "http://mock.endpoint", OAuthObj)

        assert "Invalid CSRF token" in str(exc_info.value)

    def test_upload_image_task_missing_imageinfo_raises(self, mocker):
        """
        GIVEN an image file to upload
        WHEN upload_image_task is called and Wikimedia returns malformed upload structure
        THEN check that UploadError is raised (not returned as success)
        """
        from exceptions import UploadError

        mock_get = mocker.patch('tasks.requests.get')
        mock_post = mocker.patch('tasks.requests.post')
        mocker.patch('tasks.urllib.parse.unquote', side_effect=lambda x: x)
        mocker.patch('builtins.open', new_callable=MagicMock)
        mocker.patch('tasks.upload_image_task.update_state')

        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"query": {"tokens": {"csrftoken": "mock_csrf_token"}}}

        mock_post.return_value.json.return_value = {"upload": {}}

        OAuthObj = {"consumer_key": "1", "consumer_secret": "2", "key": "3", "secret": "4"}

        with pytest.raises(UploadError) as exc_info:
            upload_image_task("dummy/path.jpg", "mock", "jpg", "http://mock.endpoint", OAuthObj)

        assert "missing image info" in str(exc_info.value).lower()

    def test_upload_task_item_api_error_raises(self, mocker):
        """
        GIVEN a task item
        WHEN upload_task_item is called and Wikimedia returns an API error
        THEN check that MediaWikiAPIError is raised
        """
        from exceptions import MediaWikiAPIError

        mock_get = mocker.patch('tasks.requests.get')
        mock_post = mocker.patch('tasks.requests.post')
        mocker.patch('tasks.urllib.parse.unquote', side_effect=lambda x: x)
        mocker.patch('builtins.open', new_callable=MagicMock)
        mocker.patch('tasks.upload_task_item.update_state')

        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"query": {"tokens": {"csrftoken": "mock_csrf_token"}}}

        mock_post.return_value.json.return_value = {
            "error": {"code": "fileexists", "info": "A file with this name already exists"}
        }

        task_item = {"lang": "en", "trfilename": "mock"}
        OAuthObj = {"consumer_key": "1", "consumer_secret": "2", "key": "3", "secret": "4"}

        with pytest.raises(MediaWikiAPIError) as exc_info:
            upload_task_item("dummy/path.jpg", "wikipedia", task_item, "jpg", OAuthObj)

        assert "already exists" in str(exc_info.value)
