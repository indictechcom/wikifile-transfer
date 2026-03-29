"""
config.py
Loads application settings from config.ini.
"""

import configparser
import os

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.ini")

_cfg = configparser.ConfigParser()

if not _cfg.read(_CONFIG_PATH):
    raise FileNotFoundError(
        f"Configuration file not found: {_CONFIG_PATH!r}. "
        "Copy config.ini.example to config.ini and fill in the values."
    )

# ── App ───────────────────────────────────────────────────────────────────────

PRODUCTION: bool = _cfg.getboolean("app", "production", fallback=False)

# ── Broker URL ────────────────────────────────────────────────────────────────

if PRODUCTION:
    _password = _cfg.get("redis_prod", "password", fallback="")
    _host     = _cfg.get("redis_prod", "host",     fallback="localhost")
    _port     = _cfg.get("redis_prod", "port",     fallback="6379")
    _db       = _cfg.getint("redis_prod", "db",    fallback=0)

    CELERY_BROKER_URL: str = "redis://:{password}@{host}:{port}/{db}".format(
        password=_password,
        host=_host,
        port=_port,
        db=_db,
    )
else:
    CELERY_BROKER_URL: str = _cfg.get("redis_dev", "url", fallback="redis://redis:6379/0")

# ── Celery ────────────────────────────────────────────────────────────────────

CELERY_DEFAULT_QUEUE: str = _cfg.get("celery", "default_queue",  fallback="wikifile-transfer")
CELERY_RESULT_EXPIRES: int = _cfg.getint("celery", "result_expires", fallback=3600)

# ── Logging ───────────────────────────────────────────────────────────────────

LOG_LEVEL: str = _cfg.get("logging", "level", fallback="INFO").upper()
LOG_DIR:   str = _cfg.get("logging", "dir",   fallback="logs")