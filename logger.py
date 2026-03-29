"""
logger.py
Centralized logging configuration for wikifile-transfer.

Usage (in any module):
    from logger import get_logger
    log = get_logger(__name__)
    log.info("Something happened", extra={"file": filename})
"""

import logging
import logging.handlers
import os

from config import LOG_DIR, LOG_LEVEL

LOG_FILE = os.path.join(LOG_DIR, "wikifile_transfer.log")

# Max 5 MB per file, keep 5 backups
_MAX_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 5

_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | "
    "%(filename)s:%(lineno)d | %(message)s"
)


def _configure_root_logger() -> None:
    os.makedirs(LOG_DIR, exist_ok=True)

    root = logging.getLogger()
    if root.handlers:          # already configured – skip
        return

    root.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    formatter = logging.Formatter(_FORMAT)

    # Rotating file handler
    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    fh.setFormatter(formatter)
    root.addHandler(fh)

    # Console handler (useful in development / Docker logs)
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    root.addHandler(ch)


_configure_root_logger()


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger that inherits the root configuration."""
    return logging.getLogger(name)