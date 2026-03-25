# Wikifile Transfer

A tool to copy files across Wikimedia projects using MediaWiki APIs and OAuth authentication. It supports: source file download from one Wikimedia project, target upload to another project, Wikimedia OAuth sign-in, asynchronous upload for large files with Celery, and localized wikitext title mapping.

## Features

- OAuth-based user login via `flask-mwoauth`
- Source image download via MediaWiki API
- Target image upload with CSRF token handling
- Large file handling (50MB+): asynchronous Celery task (`tasks.upload_image_task`)
- Edit file descriptions and append wikitext (`/api/edit_page`)
- User preferences (project, language, skip selection) persisted via SQLAlchemy model `User`
- Localized wikitext translation helper (`utils.get_localized_wikitext`)

## Architecture

- Python backend: Flask app (`app.py`)
- Task queue: Celery (`celeryWorker.py`) with Redis broker
- DB model: SQLAlchemy (`model.py`) and Flask-Migrate
- Utils: `utils.py` for download/upload and template localization
- Frontend: React (Create React App under `frontend/`)
- Deployment: `docker-compose.yml` orchestrates `web`, `worker`, and `redis`

## Prerequisites

- Python 3.10+ (or compatible)
- Node.js 18+ and npm
- Redis (local or Docker)
- MySQL/MariaDB for `SQLALCHEMY_DATABASE_URI` (or SQLite for prototyping)
- Wikimedia OAuth consumer key/secret

## Configuration

Copy and edit `config.yaml.bak`:

```yaml
ENV: dev # dev, prod
SECRET_KEY: your-secret-key
CONSUMER_KEY: <wikimedia-consumer-key>
CONSUMER_SECRET: <wikimedia-consumer-secret>
OAUTH_MWURI: https://meta.wikimedia.org/w
SESSION_COOKIE_SECURE: True
SESSION_REFRESH_EACH_REQUEST: False
PREFERRED_URL_SCHEME: https
SQLALCHEMY_DATABASE_URI: mysql+pymysql://user:pass@host/dbname
SQLALCHEMY_TRACK_MODIFICATIONS: False
```

Ensure `temp_images/` exists and is writable.

## Local development

1. Create virtualenv:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

2. Create database and run migrations:

```bash
flask db init  # only first time
flask db migrate -m "initial"
flask db upgrade
```

3. Start Redis (e.g. `redis-server`) or use Docker via compose.

4. Start Celery worker:

```bash
celery -A celeryWorker.app worker --loglevel=info
```

5. Start Flask app:

```bash
python app.py
```

6. Start frontend (in separate shell):

```bash
cd frontend
npm install
npm start
```

## Docker setup

```bash
docker-compose up --build
```

- Backend exposed at `http://localhost:5001`
- Redis at `localhost:6379`

## API endpoints

- `GET /` or `/index` - web UI entry
- `POST /api/upload` - transfer file from source URL to target project (synchronous if <50MB, asynchronous otherwise)
- `GET/POST /api/preference` - user preferences
- `GET/POST /api/user_language` - preferred frontend language
- `GET /api/get_wikitext` - fetch source page wikitext + localize links
- `POST /api/edit_page` - append content to target file page
- `GET /api/user` - logged-in user status
- `GET /api/task_status/<task_id>` - Celery upload task status/result

## Important files

- `app.py` - Flask routes and app logic
- `utils.py` - helper operations: download/upload/locale conversion
- `tasks.py` - Celery file upload worker
- `celeryWorker.py` - Celery app config
- `model.py` - SQLAlchemy `User` model
- `templatelist.py` - list of templates to localize in wikitext

## Notes

- The service assumes valid `srcUrl` with pattern `<lang>.<project>.org/wiki/<filename>`.
- Uploaded filenames are built from user-provided `trfilename` + source extension.
- All uploads use `ignorewarnings=1` by default; review for policy compliance.

## License

MIT License