"""
Unit tests for utility functions.
"""
import pytest
from unittest.mock import patch, MagicMock, mock_open
from utils import (
    getHeader,
    download_image,
    process_upload,
    get_localized_wikitext,
    get_wikitext,
    process_task_item,
)


class TestGetHeader:
    def test_returns_dict_with_user_agent(self):
        """
        GIVEN the getHeader utility function
        WHEN it is called
        THEN check it returns a dictionary with a User-Agent key
        """
        header = getHeader()
        assert isinstance(header, dict)
        assert 'User-Agent' in header

    def test_user_agent_content(self):
        """
        GIVEN the getHeader utility function
        WHEN it is called
        THEN check the User-Agent string contains the expected tool identifier
        """
        header = getHeader()
        assert 'Wikifile-transfer' in header['User-Agent']
        assert 'wikifile-transfer.toolforge.org' in header['User-Agent']


class TestDownloadImage:
    def test_success(self):
        """
        GIVEN a valid source project, language, and filename
        WHEN download_image is called and the API returns valid image data
        THEN check that a filename string is returned (not None)
        """
        # Mock the API response for image info
        mock_api_response = MagicMock()
        mock_api_response.json.return_value = {
            'query': {
                'pages': {
                    '123': {
                        'imageinfo': [{'url': 'https://example.com/image.png'}]
                    }
                }
            }
        }

        # Mock the image download response
        mock_image_response = MagicMock()
        mock_image_response.content = b'fake image content'
        mock_image_response.headers = {'content-type': 'image/png'}

        with patch('utils.requests.get', side_effect=[mock_api_response, mock_image_response]), \
             patch('builtins.open', mock_open()):
            result = download_image('wikipedia', 'en', 'File:Test.png')

        assert result is not None
        assert result.endswith('.png')

    def test_key_error_no_imageinfo(self):
        """
        GIVEN a source file that does not exist on the wiki
        WHEN download_image is called and the API returns no imageinfo
        THEN check that None is returned
        """
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'query': {
                'pages': {
                    '-1': {'title': 'File:NonExistent.png', 'missing': ''}
                }
            }
        }

        with patch('utils.requests.get', return_value=mock_response):
            result = download_image('wikipedia', 'en', 'File:NonExistent.png')

        assert result is None

    def test_network_exception(self):
        """
        GIVEN a network failure
        WHEN download_image is called and requests raises an exception
        THEN check that None is returned
        """
        with patch('utils.requests.get', side_effect=Exception("Network error")):
            result = download_image('wikipedia', 'en', 'File:Test.png')

        assert result is None


class TestProcessUpload:
    def test_success(self):
        """
        GIVEN a valid file path, filename, extension, endpoint, and session
        WHEN process_upload is called and the API returns successful upload data
        THEN check that a dict with wikipage_url and file_link is returned
        """
        # Mock CSRF token response
        mock_csrf_response = MagicMock()
        mock_csrf_response.json.return_value = {
            'query': {'tokens': {'csrftoken': 'mock_csrf_token'}}
        }

        # Mock upload response
        mock_upload_response = MagicMock()
        mock_upload_response.json.return_value = {
            'upload': {
                'imageinfo': {
                    'descriptionurl': 'https://en.wikipedia.org/wiki/File:Test.png',
                    'url': 'https://upload.wikimedia.org/test.png'
                }
            }
        }

        mock_session = MagicMock()

        with patch('utils.requests.get', return_value=mock_csrf_response), \
             patch('utils.requests.post', return_value=mock_upload_response), \
             patch('builtins.open', mock_open(read_data=b'fake file content')):
            result = process_upload(
                'temp_images/test.png', 'TestFile', 'png',
                'https://en.wikipedia.org/w/api.php', mock_session
            )

        assert result is not None
        assert result['wikipage_url'] == 'https://en.wikipedia.org/wiki/File:Test.png'
        assert result['file_link'] == 'https://upload.wikimedia.org/test.png'

    def test_csrf_failure(self):
        """
        GIVEN a valid file path and session
        WHEN process_upload is called but the CSRF token fetch fails
        THEN check that None is returned
        """
        with patch('utils.requests.get', side_effect=Exception("CSRF fetch failed")):
            result = process_upload(
                'temp_images/test.png', 'TestFile', 'png',
                'https://en.wikipedia.org/w/api.php', MagicMock()
            )

        assert result is None

    def test_missing_imageinfo_in_response(self):
        """
        GIVEN a valid file and session
        WHEN process_upload is called but the upload response is missing imageinfo
        THEN check that None is returned
        """
        mock_csrf_response = MagicMock()
        mock_csrf_response.json.return_value = {
            'query': {'tokens': {'csrftoken': 'mock_csrf_token'}}
        }

        mock_upload_response = MagicMock()
        mock_upload_response.json.return_value = {
            'upload': {'result': 'Warning'}
        }

        with patch('utils.requests.get', return_value=mock_csrf_response), \
             patch('utils.requests.post', return_value=mock_upload_response), \
             patch('builtins.open', mock_open(read_data=b'fake file content')):
            result = process_upload(
                'temp_images/test.png', 'TestFile', 'png',
                'https://en.wikipedia.org/w/api.php', MagicMock()
            )

        assert result is None


class TestGetLocalizedWikitext:
    def test_with_matching_langlink(self):
        """
        GIVEN wikitext containing a known template with an Article parameter
        WHEN get_localized_wikitext is called and a matching langlink exists
        THEN check that the Article parameter is replaced with the localized title
        """
        wikitext = '{{Non-free use rationale|Article=English Title}}'

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'query': {
                'pages': [{
                    'langlinks': [
                        {'lang': 'fr', 'title': 'Titre Français'},
                        {'lang': 'de', 'title': 'Deutscher Titel'}
                    ]
                }]
            }
        }

        with patch('utils.requests.get', return_value=mock_response):
            result = get_localized_wikitext(
                wikitext, 'https://en.wikipedia.org/w/api.php', 'fr'
            )

        assert 'Titre Français' in result

    def test_no_matching_langlink(self):
        """
        GIVEN wikitext containing a known template with an Article parameter
        WHEN get_localized_wikitext is called but no matching langlink exists
        THEN check that the original Article value is preserved
        """
        wikitext = '{{Non-free use rationale|Article=English Title}}'

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'query': {
                'pages': [{
                    'langlinks': [
                        {'lang': 'de', 'title': 'Deutscher Titel'}
                    ]
                }]
            }
        }

        with patch('utils.requests.get', return_value=mock_response):
            result = get_localized_wikitext(
                wikitext, 'https://en.wikipedia.org/w/api.php', 'ja'
            )

        assert 'English Title' in result

    def test_no_article_param_in_template(self):
        """
        GIVEN wikitext containing a known template without an Article parameter
        WHEN get_localized_wikitext is called
        THEN check that the wikitext is returned unchanged
        """
        wikitext = '{{Non-free logo|image=example.png}}'

        result = get_localized_wikitext(
            wikitext, 'https://en.wikipedia.org/w/api.php', 'fr'
        )

        assert result == wikitext

    def test_unknown_template_unchanged(self):
        """
        GIVEN wikitext containing an unknown template (not in TEMPLATES list)
        WHEN get_localized_wikitext is called
        THEN check that the wikitext is returned unchanged
        """
        wikitext = '{{SomeRandomTemplate|Article=Test}}'

        result = get_localized_wikitext(
            wikitext, 'https://en.wikipedia.org/w/api.php', 'fr'
        )

        assert 'Test' in result


class TestGetWikitext:
    def test_success(self):
        """
        GIVEN a valid article name and API endpoint
        WHEN get_wikitext is called and the API returns wikitext
        THEN check that the wikitext string is returned
        """
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'parse': {
                'wikitext': '== Section ==\nSome content here.'
            }
        }

        with patch('utils.requests.get', return_value=mock_response):
            result = get_wikitext(
                'Test_Article', 'https://en.wikipedia.org/w/api.php', MagicMock()
            )

        assert result == '== Section ==\nSome content here.'

    def test_api_error_raises_exception(self):
        """
        GIVEN a valid article name and endpoint
        WHEN get_wikitext is called but the API returns an error response
        THEN check that an Exception is raised with the error message
        """
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'error': {'info': 'Page not found', 'code': 'missingtitle'}
        }

        with patch('utils.requests.get', return_value=mock_response):
            with pytest.raises(Exception, match="Page not found"):
                get_wikitext(
                    'Nonexistent_Article',
                    'https://en.wikipedia.org/w/api.php',
                    MagicMock()
                )


class TestProcessTaskItem:
    def test_success(self):
        """
        GIVEN a valid file path, project, task item, and session
        WHEN process_task_item is called successfully
        THEN check the returned dict has wikipage_url and file_link
        """
        mock_csrf = MagicMock()
        mock_csrf.raise_for_status.return_value = None
        mock_csrf.json.return_value = {
            'query': {'tokens': {'csrftoken': 'mock_token'}}
        }

        mock_upload = MagicMock()
        mock_upload.json.return_value = {
            'upload': {
                'imageinfo': {
                    'descriptionurl': 'https://fr.wikipedia.org/wiki/File:Test.png',
                    'url': 'https://upload.wikimedia.org/test.png'
                }
            }
        }

        task_item = {'lang': 'fr', 'trfilename': 'TestFile'}

        with patch('utils.requests.get', return_value=mock_csrf), \
             patch('utils.requests.post', return_value=mock_upload), \
             patch('builtins.open', mock_open(read_data=b'fake file content')):
            result = process_task_item(
                'temp_images/test.png', 'wikipedia', task_item, 'png', MagicMock()
            )

        assert result['wikipage_url'] == 'https://fr.wikipedia.org/wiki/File:Test.png'
        assert result['file_link'] == 'https://upload.wikimedia.org/test.png'
        assert result['wikitext_fetch_success'] is None
        assert result['wikitext'] is None

    def test_missing_lang_raises_error(self):
        """
        GIVEN a task item without a 'lang' field
        WHEN process_task_item is called
        THEN check that a ValueError is raised
        """
        task_item = {'trfilename': 'TestFile'}

        with pytest.raises(ValueError, match="Missing 'lang' or 'trfilename'"):
            process_task_item(
                'temp_images/test.png', 'wikipedia', task_item, 'png', MagicMock()
            )

    def test_missing_filename_raises_error(self):
        """
        GIVEN a task item without a 'trfilename' field
        WHEN process_task_item is called
        THEN check that a ValueError is raised
        """
        task_item = {'lang': 'fr'}

        with pytest.raises(ValueError, match="Missing 'lang' or 'trfilename'"):
            process_task_item(
                'temp_images/test.png', 'wikipedia', task_item, 'png', MagicMock()
            )

    def test_api_upload_error_raises_exception(self):
        """
        GIVEN a valid file and task item
        WHEN process_task_item is called but the upload API returns an error
        THEN check that an Exception is raised with the API error message
        """
        mock_csrf = MagicMock()
        mock_csrf.raise_for_status.return_value = None
        mock_csrf.json.return_value = {
            'query': {'tokens': {'csrftoken': 'mock_token'}}
        }

        mock_upload = MagicMock()
        mock_upload.json.return_value = {
            'error': {'info': 'Upload permission denied', 'code': 'permissiondenied'}
        }

        task_item = {'lang': 'fr', 'trfilename': 'TestFile'}

        with patch('utils.requests.get', return_value=mock_csrf), \
             patch('utils.requests.post', return_value=mock_upload), \
             patch('builtins.open', mock_open(read_data=b'fake file content')):
            with pytest.raises(Exception, match="Wikimedia API Upload Error"):
                process_task_item(
                    'temp_images/test.png', 'wikipedia', task_item, 'png', MagicMock()
                )
