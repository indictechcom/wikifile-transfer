"""
Functional tests for the Flask API routes.
"""
from unittest.mock import patch, MagicMock
import requests


def test_index_page_get(client):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/' page is requested (GET)
    THEN check that the response is valid
    """
    with patch('app.render_template', return_value='<html>Mock Index</html>'):
        response = client.get('/')
    assert response.status_code == 200


def test_index_page_via_index_path(client):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/index' page is requested (GET)
    THEN check that the response is valid
    """
    with patch('app.render_template', return_value='<html>Mock Index</html>'):
        response = client.get('/index')
    assert response.status_code == 200


def test_index_page_post(client):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/' page is posted to (POST)
    THEN check that a '405' Method Not Allowed status code is returned
    """
    response = client.post('/')
    assert response.status_code == 405


def test_get_user_logged_out(client):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/api/user' endpoint is requested without being logged in
    THEN check that logged is False and username is None
    """
    with patch('app.MW_OAUTH') as mock_oauth:
        mock_oauth.get_current_user.return_value = None
        response = client.get('/api/user')

    assert response.status_code == 200
    data = response.get_json()
    assert data['logged'] is False
    assert data['username'] is None


def test_get_user_logged_in(client):
    """
    GIVEN a Flask application configured for testing
    WHEN the '/api/user' endpoint is requested while logged in
    THEN check that logged is True and username matches
    """
    with patch('app.MW_OAUTH') as mock_oauth:
        mock_oauth.get_current_user.return_value = 'WikiTestUser'
        response = client.get('/api/user')

    assert response.status_code == 200
    data = response.get_json()
    assert data['logged'] is True
    assert data['username'] == 'WikiTestUser'


def test_get_preference_default(client):
    """
    GIVEN a Flask application configured for testing
    WHEN '/api/preference' is requested (GET) without a logged-in user
    THEN check that default preferences are returned
    """
    with patch('app.MW_OAUTH') as mock_oauth:
        mock_oauth.get_current_user.return_value = None
        response = client.get('/api/preference')

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['data']['project'] == 'wikipedia'
    assert data['data']['lang'] == 'en'
    assert data['data']['skip_upload_selection'] is False


def test_get_preference_with_existing_user(client, init_database):
    """
    GIVEN a Flask application with a seeded test user in the database
    WHEN '/api/preference' is requested (GET) while logged in as that user
    THEN check that the user's saved preferences are returned
    """
    with patch('app.MW_OAUTH') as mock_oauth:
        mock_oauth.get_current_user.return_value = 'TestUser'
        response = client.get('/api/preference')

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['data']['project'] == 'wikipedia'
    assert data['data']['lang'] == 'en'


def test_post_preference_creates_new_user(client):
    """
    GIVEN a Flask application configured for testing
    WHEN '/api/preference' is POSTed with preferences for a user not in the DB
    THEN check that success is returned (user is created)
    """
    with patch('app.MW_OAUTH') as mock_oauth:
        mock_oauth.get_current_user.return_value = 'BrandNewUser'
        response = client.post(
            '/api/preference',
            json={'project': 'wiktionary', 'lang': 'de', 'skip_upload_selection': True}
        )

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True


def test_post_preference_updates_existing_user(client, init_database):
    """
    GIVEN a Flask application with an existing test user
    WHEN '/api/preference' is POSTed with updated preferences
    THEN check that success is returned (user is updated)
    """
    with patch('app.MW_OAUTH') as mock_oauth:
        mock_oauth.get_current_user.return_value = 'TestUser'
        response = client.post(
            '/api/preference',
            json={'project': 'wikibooks', 'lang': 'fr', 'skip_upload_selection': True}
        )

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True


def test_preference_invalid_method(client):
    """
    GIVEN a Flask application configured for testing
    WHEN '/api/preference' is accessed with an unsupported HTTP method (DELETE)
    THEN check that a '405' status code is returned
    """
    response = client.delete('/api/preference')
    assert response.status_code == 405


def test_get_language_preference_default(client):
    """
    GIVEN a Flask application configured for testing
    WHEN '/api/user_language' is requested without a logged-in user
    THEN check that the default language 'en' is returned
    """
    with patch('app.MW_OAUTH') as mock_oauth:
        mock_oauth.get_current_user.return_value = None
        response = client.get('/api/user_language')

    assert response.status_code == 200
    data = response.get_json()
    assert data['data']['user_language'] == 'en'


def test_get_language_preference_with_user(client, init_database):
    """
    GIVEN a Flask application with an existing user (user_language='en')
    WHEN '/api/user_language' is requested while logged in
    THEN check that the user's language preference is returned
    """
    with patch('app.MW_OAUTH') as mock_oauth:
        mock_oauth.get_current_user.return_value = 'TestUser'
        response = client.get('/api/user_language')

    assert response.status_code == 200
    data = response.get_json()
    assert data['data']['user_language'] == 'en'


def test_post_language_preference_new_user(client):
    """
    GIVEN a Flask application configured for testing
    WHEN '/api/user_language' is POSTed for a user not in the DB
    THEN check that success is returned (user is created with new language)
    """
    with patch('app.MW_OAUTH') as mock_oauth:
        mock_oauth.get_current_user.return_value = 'LangTestUser'
        response = client.post(
            '/api/user_language',
            json={'user_language': 'ja'}
        )

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True


def test_post_language_preference_update(client, init_database):
    """
    GIVEN a Flask application with an existing test user
    WHEN '/api/user_language' is POSTed with a new language
    THEN check that success is returned (language is updated)
    """
    with patch('app.MW_OAUTH') as mock_oauth:
        mock_oauth.get_current_user.return_value = 'TestUser'
        response = client.post(
            '/api/user_language',
            json={'user_language': 'fr'}
        )

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True


def test_upload_get_not_allowed(client):
    """
    GIVEN a Flask application configured for testing
    WHEN '/api/upload' is accessed with GET
    THEN check that a '405' Method Not Allowed status code is returned
    """
    response = client.get('/api/upload')
    assert response.status_code == 405


def test_upload_invalid_url(client):
    """
    GIVEN a Flask application configured for testing
    WHEN '/api/upload' is POSTed with a malformed source URL
    THEN check that a '400' status code is returned with an error message
    """
    response = client.post('/api/upload', json={
        'srcUrl': 'https://invalid-url.com/not-wiki',
        'trproject': 'wikipedia',
        'trlang': 'fr',
        'trfilename': 'TestFile'
    })

    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False


def test_upload_no_session(client):
    """
    GIVEN a Flask application with no authenticated session
    WHEN '/api/upload' is POSTed with valid data but unauthenticated
    THEN check that a '400' status code is returned
    """
    with patch('app.download_image', return_value='mock.png'), \
         patch('app.authenticated_session', return_value=None):
        response = client.post('/api/upload', json={
            'srcUrl': 'https://en.wikipedia.org/wiki/File:Test.png',
            'trproject': 'wikipedia',
            'trlang': 'fr',
            'trfilename': 'TestFile'
        })

    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False


def test_upload_download_failure(client):
    """
    GIVEN a Flask application with mocked functions
    WHEN '/api/upload' is POSTed but the image download fails
    THEN check that a '400' status code is returned
    """
    with patch('app.download_image', return_value=None), \
         patch('app.authenticated_session', return_value=MagicMock()):
        response = client.post('/api/upload', json={
            'srcUrl': 'https://en.wikipedia.org/wiki/File:Missing.png',
            'trproject': 'wikipedia',
            'trlang': 'fr',
            'trfilename': 'MissingFile'
        })

    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False


def test_upload_success_sync(client):
    """
    GIVEN a Flask application with mocked download and upload functions
    WHEN '/api/upload' is POSTed with valid data for a small file (<50MB)
    THEN check that a '200' status code is returned with upload results
    """
    with patch('app.authenticated_session', return_value=MagicMock()), \
         patch('app.download_image', return_value='mock_file.png'), \
         patch('os.path.getsize', return_value=1024), \
         patch('app.process_upload') as mock_process:

        mock_process.return_value = {
            'wikipage_url': 'https://fr.wikipedia.org/wiki/File:Test.png',
            'file_link': 'https://upload.wikimedia.org/test.png'
        }

        response = client.post('/api/upload', json={
            'srcUrl': 'https://en.wikipedia.org/wiki/File:Test.png',
            'trproject': 'wikipedia',
            'trlang': 'fr',
            'trfilename': 'TestFile'
        })

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert 'wikipage_url' in data['data']
    assert 'source' in data['data']


def test_upload_sync_process_failure(client):
    """
    GIVEN a Flask application with mocked functions
    WHEN '/api/upload' is POSTed but the synchronous upload fails (returns None)
    THEN check that a '500' status code is returned
    """
    with patch('app.authenticated_session', return_value=MagicMock()), \
         patch('app.download_image', return_value='mock_file.png'), \
         patch('os.path.getsize', return_value=1024), \
         patch('app.process_upload', return_value=None):

        response = client.post('/api/upload', json={
            'srcUrl': 'https://en.wikipedia.org/wiki/File:Test.png',
            'trproject': 'wikipedia',
            'trlang': 'fr',
            'trfilename': 'FailedFile'
        })

    assert response.status_code == 500
    data = response.get_json()
    assert data['success'] is False


def test_upload_large_file_async(client):
    """
    GIVEN a Flask application with mocked external dependencies
    WHEN '/api/upload' is POSTed with a file exceeding 50MB
    THEN check that a '202' status code is returned with a Celery task_id
    """
    # Set the OAuth session token for the async code path
    with client.session_transaction() as sess:
        sess['mwoauth_access_token'] = {'key': 'mock_key', 'secret': 'mock_secret'}

    mock_celery_task = MagicMock()
    mock_celery_task.id = 'mock-task-id-123'

    with patch('app.authenticated_session', return_value=MagicMock()), \
         patch('app.download_image', return_value='mock_file.png'), \
         patch('os.path.getsize', return_value=60 * 1024 * 1024), \
         patch('app.upload_image_task') as mock_upload_task:

        mock_upload_task.delay.return_value = mock_celery_task

        response = client.post('/api/upload', json={
            'srcUrl': 'https://en.wikipedia.org/wiki/File:LargeFile.png',
            'trproject': 'wikipedia',
            'trlang': 'fr',
            'trfilename': 'LargeFile'
        })

    assert response.status_code == 202
    data = response.get_json()
    assert data['success'] is True
    assert data['task_id'] == 'mock-task-id-123'


def test_upload_multi_get_not_allowed(client):
    """
    GIVEN a Flask application configured for testing
    WHEN '/api/upload_multi' is accessed with GET
    THEN check that a '405' status code is returned
    """
    response = client.get('/api/upload_multi')
    assert response.status_code == 405


def test_upload_multi_invalid_url(client):
    """
    GIVEN a Flask application configured for testing
    WHEN '/api/upload_multi' is POSTed with a malformed URL
    THEN check that a '400' status code is returned
    """
    response = client.post('/api/upload_multi', json={
        'srcUrl': 'https://invalid-url.com/not-wiki',
        'trproject': 'wikipedia',
        'tasks': []
    })

    assert response.status_code == 400
    data = response.get_json()
    assert data['status'] == 'FAILURE'


def test_upload_multi_empty_tasks(client):
    """
    GIVEN a Flask application configured for testing
    WHEN '/api/upload_multi' is POSTed with a valid URL but empty tasks array
    THEN check that a '400' status code is returned
    """
    with patch('app.download_image', return_value='mock.png'), \
         patch('app.authenticated_session', return_value=MagicMock()):
        response = client.post('/api/upload_multi', json={
            'srcUrl': 'https://en.wikipedia.org/wiki/File:Test.png',
            'trproject': 'wikipedia',
            'tasks': []
        })

    assert response.status_code == 400
    data = response.get_json()
    assert data['status'] == 'FAILURE'


def test_upload_multi_single_task_sync(client):
    """
    GIVEN a Flask application with mocked dependencies
    WHEN '/api/upload_multi' is POSTed with a single task for a small file
    THEN check that a '200' status code is returned (synchronous processing)
    """
    with patch('app.authenticated_session', return_value=MagicMock()), \
         patch('app.download_image', return_value='mock.png'), \
         patch('os.path.getsize', return_value=1024), \
         patch('app.process_task_item') as mock_process:

        mock_process.return_value = {
            'wikipage_url': 'https://fr.wikipedia.org/wiki/File:Test.png',
            'file_link': 'https://upload.wikimedia.org/test.png',
            'wikitext_fetch_success': None,
            'wikitext': None
        }

        response = client.post('/api/upload_multi', json={
            'srcUrl': 'https://en.wikipedia.org/wiki/File:Test.png',
            'trproject': 'wikipedia',
            'tasks': [{'lang': 'fr', 'trfilename': 'TestFile'}]
        })

    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'SUCCESS'
    assert data['lang'] == 'fr'


def test_upload_multi_dispatches_celery(client):
    """
    GIVEN a Flask application with mocked dependencies
    WHEN '/api/upload_multi' is POSTed with multiple tasks
    THEN check that a '202' status code is returned with pending task IDs
    """
    with client.session_transaction() as sess:
        sess['mwoauth_access_token'] = {'key': 'mock_key', 'secret': 'mock_secret'}

    mock_task_fr = MagicMock()
    mock_task_fr.id = 'task-fr-123'
    mock_task_de = MagicMock()
    mock_task_de.id = 'task-de-456'

    with patch('app.authenticated_session', return_value=MagicMock()), \
         patch('app.download_image', return_value='mock.png'), \
         patch('os.path.getsize', return_value=1024), \
         patch('app.upload_task_item') as mock_task:

        mock_task.delay.side_effect = [mock_task_fr, mock_task_de]

        response = client.post('/api/upload_multi', json={
            'srcUrl': 'https://en.wikipedia.org/wiki/File:Test.png',
            'trproject': 'wikipedia',
            'tasks': [
                {'lang': 'fr', 'trfilename': 'TestFile_FR'},
                {'lang': 'de', 'trfilename': 'TestFile_DE'}
            ]
        })

    assert response.status_code == 202
    data = response.get_json()
    assert data['status'] == 'PENDING'
    assert 'fr' in data['tasks']
    assert 'de' in data['tasks']


def test_get_wikitext_missing_params(client):
    """
    GIVEN a Flask application configured for testing
    WHEN '/api/get_wikitext' is requested without required query parameters
    THEN check that an empty wikitext string is returned with 200 status
    """
    response = client.get('/api/get_wikitext')
    assert response.status_code == 200
    data = response.get_json()
    assert data['wikitext'] == ''


def test_get_wikitext_partial_params(client):
    """
    GIVEN a Flask application configured for testing
    WHEN '/api/get_wikitext' is requested with only some parameters
    THEN check that an empty wikitext string is returned
    """
    response = client.get('/api/get_wikitext?src_lang=en&src_project=wikipedia')
    assert response.status_code == 200
    data = response.get_json()
    assert data['wikitext'] == ''


def test_get_wikitext_success(client):
    """
    GIVEN a Flask application with mocked Wikimedia API
    WHEN '/api/get_wikitext' is requested with all required parameters
    THEN check that the localized wikitext is returned
    """
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        'query': {
            'pages': [{
                'revisions': [{
                    'slots': {'main': {'content': 'original wikitext content'}}
                }]
            }]
        }
    }

    with patch('app.requests.get', return_value=mock_response), \
         patch('app.get_localized_wikitext', return_value='localized wikitext content'):
        response = client.get(
            '/api/get_wikitext?src_lang=en&src_project=wikipedia'
            '&src_filename=File:Test.png&tr_lang=fr'
        )

    assert response.status_code == 200
    data = response.get_json()
    assert data['wikitext'] == 'localized wikitext content'


def test_get_wikitext_no_revisions(client):
    """
    GIVEN a Flask application with mocked Wikimedia API
    WHEN '/api/get_wikitext' is requested but the page has no revisions
    THEN check that an empty wikitext string is returned
    """
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        'query': {
            'pages': [{'title': 'File:Test.png'}]
        }
    }

    with patch('app.requests.get', return_value=mock_response):
        response = client.get(
            '/api/get_wikitext?src_lang=en&src_project=wikipedia'
            '&src_filename=File:Test.png&tr_lang=fr'
        )

    assert response.status_code == 200
    data = response.get_json()
    assert data['wikitext'] == ''


def test_task_status_pending(client):
    """
    GIVEN a Flask application configured for testing
    WHEN '/api/task_status/<task_id>' is requested for a PENDING task
    THEN check the response contains status 'PENDING'
    """
    mock_task = MagicMock()
    mock_task.status = 'PENDING'
    mock_task.successful.return_value = False
    mock_task.failed.return_value = False
    mock_task.info = None

    with patch('app.AsyncResult', return_value=mock_task):
        response = client.get('/api/task_status/test-task-123')

    assert response.status_code == 200
    data = response.get_json()
    assert data['task_id'] == 'test-task-123'
    assert data['status'] == 'PENDING'


def test_task_status_progress(client):
    """
    GIVEN a Flask application configured for testing
    WHEN '/api/task_status/<task_id>' is requested for a task in PROGRESS
    THEN check that the progress value is returned
    """
    mock_task = MagicMock()
    mock_task.status = 'PROGRESS'
    mock_task.successful.return_value = False
    mock_task.failed.return_value = False
    mock_task.info = {'current': 50, 'total': 100}

    with patch('app.AsyncResult', return_value=mock_task):
        response = client.get('/api/task_status/test-progress-task')

    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'PROGRESS'
    assert data['progress'] == 50


def test_task_status_success(client):
    """
    GIVEN a Flask application configured for testing
    WHEN '/api/task_status/<task_id>' is requested for a successfully completed task
    THEN check the response contains status 'SUCCESS' and the result data
    """
    mock_task = MagicMock()
    mock_task.status = 'SUCCESS'
    mock_task.successful.return_value = True
    mock_task.failed.return_value = False
    mock_task.result = {
        'wikipage_url': 'https://example.com/wiki/File:Test.png',
        'file_link': 'https://upload.example.com/test.png',
        'wikitext_fetch_success': True,
        'wikitext': 'some wikitext'
    }

    with patch('app.AsyncResult', return_value=mock_task):
        response = client.get('/api/task_status/test-success-task')

    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'SUCCESS'
    assert data['result'] is not None
    assert 'error' not in data


def test_task_status_partial(client):
    """
    GIVEN a Flask application configured for testing
    WHEN '/api/task_status/<task_id>' is requested and wikitext_fetch_success is False
    THEN check that status is overridden to 'PARTIAL' with an error message
    """
    mock_task = MagicMock()
    mock_task.status = 'SUCCESS'
    mock_task.successful.return_value = True
    mock_task.failed.return_value = False
    mock_task.result = {
        'wikipage_url': 'https://example.com/wiki/File:Test.png',
        'file_link': 'https://upload.example.com/test.png',
        'wikitext_fetch_success': False
    }

    with patch('app.AsyncResult', return_value=mock_task):
        response = client.get('/api/task_status/test-partial-task')

    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'PARTIAL'
    assert 'error' in data


def test_task_status_failure(client):
    """
    GIVEN a Flask application configured for testing
    WHEN '/api/task_status/<task_id>' is requested for a failed task
    THEN check the response contains status 'FAILURE' and an error message
    """
    mock_task = MagicMock()
    mock_task.status = 'FAILURE'
    mock_task.successful.return_value = False
    mock_task.failed.return_value = True
    mock_task.result = Exception('Upload failed')

    with patch('app.AsyncResult', return_value=mock_task):
        response = client.get('/api/task_status/test-failed-task')

    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'FAILURE'
    assert 'error' in data


def test_edit_page_get_not_allowed(client):
    """
    GIVEN a Flask application configured for testing
    WHEN '/api/edit_page' is accessed with GET
    THEN check that a '405' status code is returned
    """
    response = client.get('/api/edit_page')
    assert response.status_code == 405


def test_edit_article_missing_params(client):
    """
    GIVEN a Flask application configured for testing
    WHEN '/api/edit_article' is POSTed with missing required fields
    THEN check that a '400' status code is returned
    """
    response = client.post('/api/edit_article', json={})
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert 'Missing parameters' in data['errors'][0]


def test_edit_article_missing_article_name(client):
    """
    GIVEN a Flask application configured for testing
    WHEN '/api/edit_article' is POSTed without an articleName
    THEN check that a '400' status code is returned
    """
    response = client.post('/api/edit_article', json={
        'content': 'some content',
        'lang': 'en',
        'project': 'wikipedia'
    })
    assert response.status_code == 400


def test_edit_article_get_not_allowed(client):
    """
    GIVEN a Flask application configured for testing
    WHEN '/api/edit_article' is accessed with GET
    THEN check that a '405' status code is returned
    """
    response = client.get('/api/edit_article')
    assert response.status_code == 405


def test_404_handler(client):
    """
    GIVEN a Flask application configured for testing
    WHEN a non-existent route is requested
    THEN check that a '404' status code is returned with a JSON error body
    """
    response = client.get('/api/nonexistent_endpoint')
    assert response.status_code == 404
    data = response.get_json()
    assert data['success'] is False
    assert 'Resource not found' in data['errors'][0]


def test_task_status_app_error_failure(client):
    """
    GIVEN a task that failed with an AppError
    WHEN '/api/task_status/<task_id>' is polled
    THEN check that status is FAILURE and error message matches the AppError message
    """
    from exceptions import UploadError

    mock_task = MagicMock()
    mock_task.status = 'FAILURE'
    mock_task.successful.return_value = False
    mock_task.failed.return_value = True
    mock_task.result = UploadError('Upload response missing image info data')

    with patch('app.AsyncResult', return_value=mock_task):
        response = client.get('/api/task_status/test-upload-error-task')

    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'FAILURE'
    assert data['error'] == 'Upload response missing image info data'


def test_app_error_handler_validation(client):
    """
    GIVEN a route raising a ValidationError
    WHEN requested
    THEN check that 400 is returned with consistent JSON error schema
    """
    from exceptions import ValidationError

    with patch('app.download_image', side_effect=ValidationError('Test validation failure')):
        response = client.post('/api/upload', json={
            'srcUrl': 'https://en.wikipedia.org/wiki/File:Test.png',
            'trproject': 'wikipedia',
            'trlang': 'fr',
            'trfilename': 'TestFile'
        })

    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert data['data'] == {}
    assert data['errors'] == ['Test validation failure']


def test_app_error_handler_upload(client):
    """
    GIVEN a route raising an UploadError
    WHEN requested
    THEN check that 502 is returned with consistent JSON error schema
    """
    from exceptions import UploadError

    with patch('app.authenticated_session', return_value=MagicMock()), \
         patch('app.download_image', return_value='mock_file.png'), \
         patch('os.path.getsize', return_value=1024), \
         patch('app.process_upload', side_effect=UploadError('Remote wiki upload rejected')):

        response = client.post('/api/upload', json={
            'srcUrl': 'https://en.wikipedia.org/wiki/File:Test.png',
            'trproject': 'wikipedia',
            'trlang': 'fr',
            'trfilename': 'TestFile'
        })

    assert response.status_code == 502
    data = response.get_json()
    assert data['success'] is False
    assert data['errors'] == ['Remote wiki upload rejected']


def test_http_exception_preserves_status_and_description(client):
    """
    GIVEN a route raising a Werkzeug HTTPException (e.g. 401 Unauthorized)
    WHEN requested
    THEN check that the original status code and description are preserved in JSON
    """
    from werkzeug.exceptions import Unauthorized

    with patch('app.download_image', side_effect=Unauthorized('Custom unauthorized description')):
        response = client.post('/api/upload', json={
            'srcUrl': 'https://en.wikipedia.org/wiki/File:Test.png',
            'trproject': 'wikipedia',
            'trlang': 'fr',
            'trfilename': 'TestFile'
        })

    assert response.status_code == 401
    data = response.get_json()
    assert data['success'] is False
    assert data['errors'] == ['Custom unauthorized description']


def test_unhandled_exception_returns_500_without_leak(client):
    """
    GIVEN a route encountering an unexpected generic Exception
    WHEN requested
    THEN check that 500 is returned with a generic safe error without leaking internal details
    """
    with patch('app.download_image', side_effect=ZeroDivisionError('secret_internal_detail_divided_by_zero')):
        response = client.post('/api/upload', json={
            'srcUrl': 'https://en.wikipedia.org/wiki/File:Test.png',
            'trproject': 'wikipedia',
            'trlang': 'fr',
            'trfilename': 'TestFile'
        })

    assert response.status_code == 500
    data = response.get_json()
    assert data['success'] is False
    assert data['errors'] == ['An unexpected error occurred']
    assert 'secret_internal_detail_divided_by_zero' not in str(data)


# ============================================================================
# Increment 3: Request Payload Validation Tests
# ============================================================================

def test_payload_validation_missing_content_type(client):
    """
    GIVEN a POST request with no Content-Type header or text/plain
    WHEN requested on a JSON endpoint
    THEN check that 400 is returned with consistent JSON error schema
    """
    response = client.post('/api/upload', data='{}', content_type='text/plain')
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'
    assert 'Content-Type: application/json' in data['errors'][0]


def test_payload_validation_empty_body(client):
    """
    GIVEN a POST request with Content-Type application/json but an empty body
    WHEN requested on a JSON endpoint
    THEN check that 400 is returned with consistent JSON error schema
    """
    response = client.post('/api/upload', data='', content_type='application/json')
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'
    assert 'empty' in data['errors'][0].lower()


def test_payload_validation_malformed_json(client):
    """
    GIVEN a POST request with malformed JSON syntax
    WHEN requested on a JSON endpoint
    THEN check that 400 is returned with consistent JSON error schema
    """
    response = client.post('/api/upload', data='{"invalid": json', content_type='application/json')
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'
    assert 'Malformed JSON payload' in data['errors'][0]


def test_payload_validation_wrong_top_level_list(client):
    """
    GIVEN a POST request with a JSON array instead of a JSON object
    WHEN requested on a JSON endpoint
    THEN check that 400 is returned with consistent JSON error schema
    """
    response = client.post('/api/upload', data='[1, 2, 3]', content_type='application/json')
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'
    assert 'JSON object' in data['errors'][0]


def test_payload_validation_wrong_top_level_primitive(client):
    """
    GIVEN a POST request with a JSON primitive string instead of an object
    WHEN requested on a JSON endpoint
    THEN check that 400 is returned with consistent JSON error schema
    """
    response = client.post('/api/upload', data='"just a string"', content_type='application/json')
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'
    assert 'JSON object' in data['errors'][0]


def test_upload_missing_or_invalid_target_fields(client):
    """
    GIVEN an upload request with non-string or missing target parameters
    WHEN '/api/upload' is requested
    THEN check that 400 is returned safely without unhandled exceptions
    """
    response = client.post('/api/upload', json={
        'srcUrl': 'https://en.wikipedia.org/wiki/File:Test.png',
        'trproject': 'wikipedia',
        'trlang': 'fr',
        'trfilename': None
    })
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'


def test_upload_multi_empty_body(client):
    """
    GIVEN an empty request body
    WHEN '/api/upload_multi' is POSTed
    THEN check that 400 is returned with status FAILURE
    """
    response = client.post('/api/upload_multi', data='', content_type='application/json')
    assert response.status_code == 400
    data = response.get_json()
    assert data['status'] == 'FAILURE'
    assert data['success'] is False


def test_upload_multi_malformed_json(client):
    """
    GIVEN malformed JSON
    WHEN '/api/upload_multi' is POSTed
    THEN check that 400 is returned with status FAILURE
    """
    response = client.post('/api/upload_multi', data='{malformed', content_type='application/json')
    assert response.status_code == 400
    data = response.get_json()
    assert data['status'] == 'FAILURE'
    assert data['success'] is False


def test_upload_multi_wrong_top_level_type(client):
    """
    GIVEN a JSON list instead of an object
    WHEN '/api/upload_multi' is POSTed
    THEN check that 400 is returned with status FAILURE
    """
    response = client.post('/api/upload_multi', data='[1, 2]', content_type='application/json')
    assert response.status_code == 400
    data = response.get_json()
    assert data['status'] == 'FAILURE'
    assert data['success'] is False


def test_upload_multi_invalid_tasks_type(client):
    """
    GIVEN tasks field that is not a list of dictionaries
    WHEN '/api/upload_multi' is POSTed
    THEN check that 400 is returned with status FAILURE
    """
    response = client.post('/api/upload_multi', json={
        'srcUrl': 'https://en.wikipedia.org/wiki/File:Test.png',
        'trproject': 'wikipedia',
        'tasks': 'not-a-list'
    })
    assert response.status_code == 400
    data = response.get_json()
    assert data['status'] == 'FAILURE'
    assert data['success'] is False


def test_preference_authenticated_empty_body(client):
    """
    GIVEN an authenticated user sending an empty body
    WHEN '/api/preference' is POSTed
    THEN check that 400 is returned
    """
    with patch('app.MW_OAUTH') as mock_oauth:
        mock_oauth.get_current_user.return_value = 'TestUser'
        response = client.post('/api/preference', data='', content_type='application/json')
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'


def test_preference_authenticated_malformed_json(client):
    """
    GIVEN an authenticated user sending malformed JSON
    WHEN '/api/preference' is POSTed
    THEN check that 400 is returned
    """
    with patch('app.MW_OAUTH') as mock_oauth:
        mock_oauth.get_current_user.return_value = 'TestUser'
        response = client.post('/api/preference', data='{broken', content_type='application/json')
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'


def test_preference_authenticated_wrong_top_level(client):
    """
    GIVEN an authenticated user sending a top-level list
    WHEN '/api/preference' is POSTed
    THEN check that 400 is returned
    """
    with patch('app.MW_OAUTH') as mock_oauth:
        mock_oauth.get_current_user.return_value = 'TestUser'
        response = client.post('/api/preference', data='["pref1", "pref2"]', content_type='application/json')
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'


def test_preference_authenticated_invalid_field_types(client):
    """
    GIVEN an authenticated user sending non-string project/lang types
    WHEN '/api/preference' is POSTed
    THEN check that 400 is returned
    """
    with patch('app.MW_OAUTH') as mock_oauth:
        mock_oauth.get_current_user.return_value = 'TestUser'
        response = client.post('/api/preference', json={'project': 12345, 'lang': 'fr'})
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'


def test_user_language_authenticated_empty_body(client):
    """
    GIVEN an authenticated user sending an empty body
    WHEN '/api/user_language' is POSTed
    THEN check that 400 is returned
    """
    with patch('app.MW_OAUTH') as mock_oauth:
        mock_oauth.get_current_user.return_value = 'TestUser'
        response = client.post('/api/user_language', data='', content_type='application/json')
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'


def test_user_language_authenticated_malformed_json(client):
    """
    GIVEN an authenticated user sending malformed JSON
    WHEN '/api/user_language' is POSTed
    THEN check that 400 is returned
    """
    with patch('app.MW_OAUTH') as mock_oauth:
        mock_oauth.get_current_user.return_value = 'TestUser'
        response = client.post('/api/user_language', data='{"broken":', content_type='application/json')
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'


def test_user_language_authenticated_wrong_top_level(client):
    """
    GIVEN an authenticated user sending a list
    WHEN '/api/user_language' is POSTed
    THEN check that 400 is returned
    """
    with patch('app.MW_OAUTH') as mock_oauth:
        mock_oauth.get_current_user.return_value = 'TestUser'
        response = client.post('/api/user_language', data='["en"]', content_type='application/json')
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'


def test_user_language_authenticated_invalid_field(client):
    """
    GIVEN an authenticated user sending non-string user_language
    WHEN '/api/user_language' is POSTed
    THEN check that 400 is returned
    """
    with patch('app.MW_OAUTH') as mock_oauth:
        mock_oauth.get_current_user.return_value = 'TestUser'
        response = client.post('/api/user_language', json={'user_language': 999})
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'


def test_edit_page_empty_body(client):
    """
    GIVEN an empty body
    WHEN '/api/edit_page' is POSTed
    THEN check that 400 is returned
    """
    response = client.post('/api/edit_page', data='', content_type='application/json')
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'


def test_edit_page_malformed_json(client):
    """
    GIVEN malformed JSON
    WHEN '/api/edit_page' is POSTed
    THEN check that 400 is returned
    """
    response = client.post('/api/edit_page', data='{broken', content_type='application/json')
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'


def test_edit_page_wrong_top_level(client):
    """
    GIVEN a JSON list instead of an object
    WHEN '/api/edit_page' is POSTed
    THEN check that 400 is returned
    """
    response = client.post('/api/edit_page', data='[1, 2]', content_type='application/json')
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'


def test_edit_page_invalid_target_url(client):
    """
    GIVEN a non-MediaWiki targetUrl
    WHEN '/api/edit_page' is POSTed
    THEN check that 400 is returned safely
    """
    response = client.post('/api/edit_page', json={
        'targetUrl': 'https://example.com/not-wiki',
        'content': 'Some content'
    })
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'


def test_edit_page_missing_namespace_prefix(client):
    """
    GIVEN a targetUrl with a filename that lacks a namespace prefix (e.g. no colon)
    WHEN '/api/edit_page' is POSTed
    THEN check that 400 is returned safely without IndexError
    """
    response = client.post('/api/edit_page', json={
        'targetUrl': 'https://en.wikipedia.org/wiki/NoNamespaceFile.png',
        'content': 'Some content'
    })
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'


def test_edit_page_success(client):
    """
    GIVEN valid edit_page parameters and mocked remote responses
    WHEN '/api/edit_page' is POSTed
    THEN check that 200 is returned
    """
    mock_get_csrf = MagicMock()
    mock_get_csrf.status_code = 200
    mock_get_csrf.json.return_value = {'query': {'tokens': {'csrftoken': 'mock_csrf_token'}}}

    mock_post_edit = MagicMock()
    mock_post_edit.status_code = 200
    mock_post_edit.json.return_value = {'edit': {'result': 'Success'}}

    with patch('app.authenticated_session', return_value=MagicMock()), \
         patch('app.requests.get', return_value=mock_get_csrf), \
         patch('app.requests.post', return_value=mock_post_edit):
        response = client.post('/api/edit_page', json={
            'targetUrl': 'https://en.wikipedia.org/wiki/File:ValidFile.png',
            'content': 'Appended text'
        })

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True


def test_edit_article_empty_body(client):
    """
    GIVEN an empty body
    WHEN '/api/edit_article' is POSTed
    THEN check that 400 is returned
    """
    response = client.post('/api/edit_article', data='', content_type='application/json')
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'


def test_edit_article_malformed_json(client):
    """
    GIVEN malformed JSON
    WHEN '/api/edit_article' is POSTed
    THEN check that 400 is returned
    """
    response = client.post('/api/edit_article', data='{broken', content_type='application/json')
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'


def test_edit_article_wrong_top_level(client):
    """
    GIVEN a list instead of an object
    WHEN '/api/edit_article' is POSTed
    THEN check that 400 is returned
    """
    response = client.post('/api/edit_article', data='[1, 2]', content_type='application/json')
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'


def test_edit_article_success(client):
    """
    GIVEN valid edit_article parameters and mocked remote responses
    WHEN '/api/edit_article' is POSTed
    THEN check that 200 is returned
    """
    mock_get_csrf = MagicMock()
    mock_get_csrf.status_code = 200
    mock_get_csrf.json.return_value = {'query': {'tokens': {'csrftoken': 'mock_csrf_token'}}}

    mock_post_edit = MagicMock()
    mock_post_edit.status_code = 200
    mock_post_edit.json.return_value = {'edit': {'result': 'Success'}}

    with patch('app.authenticated_session', return_value=MagicMock()), \
         patch('app.requests.get', return_value=mock_get_csrf), \
         patch('app.requests.post', return_value=mock_post_edit):
        response = client.post('/api/edit_article', json={
            'articleName': 'Sample_Article',
            'content': 'Complete wikitext',
            'lang': 'en',
            'project': 'wikipedia'
        })

    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True


# ============================================================================
# Increment 4: Preference Route Authentication Tests
# ============================================================================

def test_post_preference_unauthenticated(client, init_database):
    """
    GIVEN an unauthenticated request (user logged out)
    WHEN '/api/preference' is POSTed
    THEN check that 401 is returned, no database session is committed,
         and no user record with username=None or new username is created
    """
    from model import User

    initial_user_count = User.query.count()

    with patch('app.MW_OAUTH') as mock_oauth:
        mock_oauth.get_current_user.return_value = None
        response = client.post('/api/preference', json={
            'project': 'wiktionary',
            'lang': 'de',
            'skip_upload_selection': True
        })

    assert response.status_code == 401
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'
    assert data['errors'] == ['Authentication required']

    # Assert no user record was created or committed
    assert User.query.filter_by(username=None).first() is None
    assert User.query.count() == initial_user_count


def test_post_preference_whitespace_username_unauthenticated(client, init_database):
    """
    GIVEN a request with an empty/whitespace username
    WHEN '/api/preference' is POSTed
    THEN check that 401 is returned and no user record is created
    """
    from model import User

    initial_user_count = User.query.count()

    with patch('app.MW_OAUTH') as mock_oauth:
        mock_oauth.get_current_user.return_value = "   "
        response = client.post('/api/preference', json={
            'project': 'wiktionary',
            'lang': 'de'
        })

    assert response.status_code == 401
    data = response.get_json()
    assert data['success'] is False
    assert data['errors'] == ['Authentication required']
    assert User.query.count() == initial_user_count


def test_post_user_language_unauthenticated(client, init_database):
    """
    GIVEN an unauthenticated request (user logged out)
    WHEN '/api/user_language' is POSTed
    THEN check that 401 is returned, no database session is committed,
         and no user record with username=None or new username is created
    """
    from model import User

    initial_user_count = User.query.count()

    with patch('app.MW_OAUTH') as mock_oauth:
        mock_oauth.get_current_user.return_value = None
        response = client.post('/api/user_language', json={
            'user_language': 'es'
        })

    assert response.status_code == 401
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'
    assert data['errors'] == ['Authentication required']

    # Assert no user record was created or committed
    assert User.query.filter_by(username=None).first() is None
    assert User.query.count() == initial_user_count


def test_post_user_language_whitespace_username_unauthenticated(client, init_database):
    """
    GIVEN a request with an empty/whitespace username
    WHEN '/api/user_language' is POSTed
    THEN check that 401 is returned and no user record is created
    """
    from model import User

    initial_user_count = User.query.count()

    with patch('app.MW_OAUTH') as mock_oauth:
        mock_oauth.get_current_user.return_value = "   "
        response = client.post('/api/user_language', json={
            'user_language': 'es'
        })

    assert response.status_code == 401
    data = response.get_json()
    assert data['success'] is False
    assert data['errors'] == ['Authentication required']
    assert User.query.count() == initial_user_count


# ============================================================================
# Increments 5-8: Timeouts, Parsing, Classification, and Consistency Tests
# ============================================================================

def test_edit_page_unauthenticated(client):
    """
    GIVEN an unauthenticated session (ses is None)
    WHEN '/api/edit_page' is POSTed with valid payload
    THEN check that 401 Authentication required is returned
    """
    with patch('app.authenticated_session', return_value=None):
        response = client.post('/api/edit_page', json={
            'targetUrl': 'https://en.wikipedia.org/wiki/File:TestFile.png',
            'content': 'Valid wikitext content'
        })

    assert response.status_code == 401
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'
    assert data['errors'] == ['Authentication required']


def test_edit_page_csrf_timeout(client):
    """
    GIVEN an authenticated session but remote wiki times out during CSRF retrieval
    WHEN '/api/edit_page' is POSTed
    THEN check that 502 Bad Gateway is returned with safe error message
    """
    with patch('app.authenticated_session', return_value=MagicMock()), \
         patch('app.requests.get', side_effect=requests.exceptions.Timeout("CSRF connect timeout")):
        response = client.post('/api/edit_page', json={
            'targetUrl': 'https://en.wikipedia.org/wiki/File:TestFile.png',
            'content': 'Valid wikitext content'
        })

    assert response.status_code == 502
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'
    assert data['errors'] == ['Timeout connecting to remote wiki']


def test_edit_page_csrf_parse_error(client):
    """
    GIVEN an authenticated session but remote wiki returns malformed CSRF JSON
    WHEN '/api/edit_page' is POSTed
    THEN check that 502 Bad Gateway is returned safely without unhandled KeyError
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {'query': {}}

    with patch('app.authenticated_session', return_value=MagicMock()), \
         patch('app.requests.get', return_value=mock_resp):
        response = client.post('/api/edit_page', json={
            'targetUrl': 'https://en.wikipedia.org/wiki/File:TestFile.png',
            'content': 'Valid wikitext content'
        })

    assert response.status_code == 502
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'
    assert data['errors'] == ['Failed to retrieve CSRF token']


def test_edit_page_post_timeout(client):
    """
    GIVEN valid CSRF token but remote wiki times out during POST edit
    WHEN '/api/edit_page' is POSTed
    THEN check that 502 Bad Gateway is returned with safe error message
    """
    mock_csrf = MagicMock()
    mock_csrf.status_code = 200
    mock_csrf.raise_for_status.return_value = None
    mock_csrf.json.return_value = {'query': {'tokens': {'csrftoken': 'mock_token'}}}

    with patch('app.authenticated_session', return_value=MagicMock()), \
         patch('app.requests.get', return_value=mock_csrf), \
         patch('app.requests.post', side_effect=requests.exceptions.Timeout("Edit POST timeout")):
        response = client.post('/api/edit_page', json={
            'targetUrl': 'https://en.wikipedia.org/wiki/File:TestFile.png',
            'content': 'Valid wikitext content'
        })

    assert response.status_code == 502
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'
    assert data['errors'] == ['Timeout connecting to remote wiki']


def test_edit_page_post_api_error(client):
    """
    GIVEN valid CSRF token but remote wiki returns an API error on edit
    WHEN '/api/edit_page' is POSTed
    THEN check that 502 Bad Gateway is returned with the MediaWiki error message
    """
    mock_csrf = MagicMock()
    mock_csrf.status_code = 200
    mock_csrf.raise_for_status.return_value = None
    mock_csrf.json.return_value = {'query': {'tokens': {'csrftoken': 'mock_token'}}}

    mock_edit = MagicMock()
    mock_edit.status_code = 200
    mock_edit.raise_for_status.return_value = None
    mock_edit.json.return_value = {'error': {'info': 'Protected page', 'code': 'protectedpage'}}

    with patch('app.authenticated_session', return_value=MagicMock()), \
         patch('app.requests.get', return_value=mock_csrf), \
         patch('app.requests.post', return_value=mock_edit):
        response = client.post('/api/edit_page', json={
            'targetUrl': 'https://en.wikipedia.org/wiki/File:TestFile.png',
            'content': 'Valid wikitext content'
        })

    assert response.status_code == 502
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'
    assert data['errors'] == ['Edit Error: Protected page']


def test_edit_article_unauthenticated(client):
    """
    GIVEN an unauthenticated session (ses is None)
    WHEN '/api/edit_article' is POSTed with valid payload
    THEN check that 401 Authentication required is returned
    """
    with patch('app.authenticated_session', return_value=None):
        response = client.post('/api/edit_article', json={
            'articleName': 'Sample_Article',
            'content': 'New wikitext content',
            'lang': 'en',
            'project': 'wikipedia'
        })

    assert response.status_code == 401
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'
    assert data['errors'] == ['Authentication required']


def test_edit_article_csrf_timeout(client):
    """
    GIVEN an authenticated session but remote wiki times out during CSRF retrieval
    WHEN '/api/edit_article' is POSTed
    THEN check that 502 Bad Gateway is returned with safe error message
    """
    with patch('app.authenticated_session', return_value=MagicMock()), \
         patch('app.requests.get', side_effect=requests.exceptions.Timeout("CSRF connect timeout")):
        response = client.post('/api/edit_article', json={
            'articleName': 'Sample_Article',
            'content': 'New wikitext content',
            'lang': 'en',
            'project': 'wikipedia'
        })

    assert response.status_code == 502
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'
    assert data['errors'] == ['Timeout connecting to remote wiki']


def test_edit_article_csrf_parse_error(client):
    """
    GIVEN an authenticated session but remote wiki returns malformed CSRF response
    WHEN '/api/edit_article' is POSTed
    THEN check that 502 Bad Gateway is returned safely without unhandled KeyError
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {'query': {}}

    with patch('app.authenticated_session', return_value=MagicMock()), \
         patch('app.requests.get', return_value=mock_resp):
        response = client.post('/api/edit_article', json={
            'articleName': 'Sample_Article',
            'content': 'New wikitext content',
            'lang': 'en',
            'project': 'wikipedia'
        })

    assert response.status_code == 502
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'
    assert data['errors'] == ['Failed to retrieve CSRF token']


def test_edit_article_post_timeout(client):
    """
    GIVEN valid CSRF token but remote wiki times out during POST edit
    WHEN '/api/edit_article' is POSTed
    THEN check that 502 Bad Gateway is returned with safe error message
    """
    mock_csrf = MagicMock()
    mock_csrf.status_code = 200
    mock_csrf.raise_for_status.return_value = None
    mock_csrf.json.return_value = {'query': {'tokens': {'csrftoken': 'mock_token'}}}

    with patch('app.authenticated_session', return_value=MagicMock()), \
         patch('app.requests.get', return_value=mock_csrf), \
         patch('app.requests.post', side_effect=requests.exceptions.Timeout("Edit POST timeout")):
        response = client.post('/api/edit_article', json={
            'articleName': 'Sample_Article',
            'content': 'New wikitext content',
            'lang': 'en',
            'project': 'wikipedia'
        })

    assert response.status_code == 502
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'
    assert data['errors'] == ['Timeout connecting to remote wiki']


def test_edit_article_post_api_error(client):
    """
    GIVEN valid CSRF token but remote wiki returns an API error on edit
    WHEN '/api/edit_article' is POSTed
    THEN check that 502 Bad Gateway is returned with the MediaWiki error message
    """
    mock_csrf = MagicMock()
    mock_csrf.status_code = 200
    mock_csrf.raise_for_status.return_value = None
    mock_csrf.json.return_value = {'query': {'tokens': {'csrftoken': 'mock_token'}}}

    mock_edit = MagicMock()
    mock_edit.status_code = 200
    mock_edit.raise_for_status.return_value = None
    mock_edit.json.return_value = {'error': {'info': 'Protected page', 'code': 'protectedpage'}}

    with patch('app.authenticated_session', return_value=MagicMock()), \
         patch('app.requests.get', return_value=mock_csrf), \
         patch('app.requests.post', return_value=mock_edit):
        response = client.post('/api/edit_article', json={
            'articleName': 'Sample_Article',
            'content': 'New wikitext content',
            'lang': 'en',
            'project': 'wikipedia'
        })

    assert response.status_code == 502
    data = response.get_json()
    assert data['success'] is False
    assert data['status'] == 'FAILURE'
    assert data['errors'] == ['Edit Error: Protected page']


def test_task_status_failed_with_timeout_exception(client):
    """
    GIVEN a failed background Celery task whose result is requests.exceptions.Timeout
    WHEN '/api/task_status/<task_id>' is requested
    THEN check that 200 is returned with status FAILURE and clean error message (no leaked connection pool details)
    """
    mock_task = MagicMock()
    mock_task.status = 'FAILURE'
    mock_task.successful.return_value = False
    mock_task.failed.return_value = True
    mock_task.result = requests.exceptions.Timeout("HTTPSConnectionPool(host='en.wikipedia.org'): Read timed out")

    with patch('app.AsyncResult', return_value=mock_task):
        response = client.get('/api/task_status/task-timeout-test')

    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'FAILURE'
    assert data['error'] == 'Request timed out connecting to remote wiki'
    assert 'HTTPSConnectionPool' not in str(data)


def test_task_status_failed_with_request_exception(client):
    """
    GIVEN a failed background Celery task whose result is requests.exceptions.ConnectionError
    WHEN '/api/task_status/<task_id>' is requested
    THEN check that 200 is returned with status FAILURE and clean error message
    """
    mock_task = MagicMock()
    mock_task.status = 'FAILURE'
    mock_task.successful.return_value = False
    mock_task.failed.return_value = True
    mock_task.result = requests.exceptions.ConnectionError("Connection refused to remote host")

    with patch('app.AsyncResult', return_value=mock_task):
        response = client.get('/api/task_status/task-conn-err-test')

    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'FAILURE'
    assert data['error'] == 'Network error connecting to remote wiki'


def test_get_preference_error_key_consistency(client):
    """
    GIVEN a GET request to '/api/preference'
    WHEN requested
    THEN check that 'errors' key is present and is an empty list
    """
    with patch('app.MW_OAUTH') as mock_oauth:
        mock_oauth.get_current_user.return_value = None
        response = client.get('/api/preference')

    assert response.status_code == 200
    data = response.get_json()
    assert 'errors' in data
    assert data['errors'] == []


def test_get_user_language_error_key_consistency(client):
    """
    GIVEN a GET request to '/api/user_language'
    WHEN requested
    THEN check that 'errors' key is present and is an empty list
    """
    with patch('app.MW_OAUTH') as mock_oauth:
        mock_oauth.get_current_user.return_value = None
        response = client.get('/api/user_language')

    assert response.status_code == 200
    data = response.get_json()
    assert 'errors' in data
    assert data['errors'] == []
