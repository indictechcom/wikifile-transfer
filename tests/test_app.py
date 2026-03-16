import pytest
import json
import os
import sys
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def app():
    """Create a test Flask app with minimal config."""
    # Create a minimal config.yaml for testing
    import yaml
    config = {
        'ENV': 'dev',
        'SECRET_KEY': 'test-secret-key',
        'CONSUMER_KEY': 'test-consumer-key',
        'CONSUMER_SECRET': 'test-consumer-secret',
        'OAUTH_MWURI': 'https://meta.wikimedia.org/w',
        'SESSION_COOKIE_SECURE': False,
        'SESSION_REFRESH_EACH_REQUEST': False,
        'PREFERRED_URL_SCHEME': 'https',
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
    }

    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.yaml')
    config_existed = os.path.exists(config_path)

    if not config_existed:
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

    from app import app as flask_app
    flask_app.config['TESTING'] = True

    yield flask_app

    if not config_existed:
        os.remove(config_path)


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


class TestUploadRoute:
    """Tests for the /api/upload endpoint."""

    def test_rejects_missing_json(self, client):
        """Upload returns 400 when no JSON payload is provided."""
        response = client.post('/api/upload', content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False

    def test_rejects_missing_src_url(self, client):
        """Upload returns 400 when srcUrl is missing."""
        response = client.post('/api/upload',
                               data=json.dumps({"trproject": "wikipedia"}),
                               content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert any("srcUrl" in err for err in data["errors"])

    def test_rejects_invalid_url_format(self, client):
        """Upload returns 400 when srcUrl doesn't match expected wiki URL pattern."""
        response = client.post('/api/upload',
                               data=json.dumps({"srcUrl": "https://example.com/not-a-wiki"}),
                               content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert any("Invalid source URL" in err for err in data["errors"])

    @patch('app.download_image', return_value=None)
    def test_returns_400_on_download_failure(self, mock_download, client):
        """Upload returns 400 when downloading the source file fails."""
        response = client.post('/api/upload',
                               data=json.dumps({
                                   "srcUrl": "https://commons.wikimedia.org/wiki/File:Test.jpg",
                                   "trproject": "wikipedia",
                                   "trlang": "en",
                                   "trfilename": "Test"
                               }),
                               content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert any("download" in err.lower() for err in data["errors"])

    @patch('app.authenticated_session', return_value=None)
    @patch('app.cleanup_temp_file')
    @patch('app.download_image', return_value="test_file.jpg")
    def test_returns_401_when_not_authenticated(self, mock_download, mock_cleanup, mock_auth, client):
        """Upload returns 401 when user is not authenticated."""
        response = client.post('/api/upload',
                               data=json.dumps({
                                   "srcUrl": "https://commons.wikimedia.org/wiki/File:Test.jpg",
                                   "trproject": "wikipedia",
                                   "trlang": "en",
                                   "trfilename": "Test"
                               }),
                               content_type='application/json')
        assert response.status_code == 401
        data = response.get_json()
        assert data["success"] is False
        assert any("authenticated" in err.lower() or "log in" in err.lower() for err in data["errors"])

    @patch('app.cleanup_temp_file')
    @patch('app.download_image', return_value="test_file.jpg")
    def test_returns_400_when_target_fields_missing(self, mock_download, mock_cleanup, client):
        """Upload returns 400 when target project/language/filename are missing."""
        response = client.post('/api/upload',
                               data=json.dumps({
                                   "srcUrl": "https://commons.wikimedia.org/wiki/File:Test.jpg"
                               }),
                               content_type='application/json')
        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
