"""
Functional tests for the Flask API routes.
"""
from unittest.mock import patch, MagicMock


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
