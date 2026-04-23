"""
logging_config.py – Structured, rotating file-based logging for Wikifile-Transfer.

Call ``configure_logging(app)`` once after the Flask app is configured.
Log files are written to the ``logs/`` directory at the project root.

Format:  2024-01-15 12:34:56 [INFO    ] app: Server started
         2024-01-15 12:34:57 [WARNING ] error_handlers: HTTP 422 on POST /api/upload
"""

import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask


def configure_logging(flask_app: Flask) -> None:
    """
    Attach a rotating file handler and a console handler to the root logger.

    Settings:
      - Log directory : logs/  (created automatically if missing)
      - File size cap : 5 MB per file, 3 backups kept
      - Log level     : DEBUG in dev (flask_app.config["DEBUG"]=True), INFO otherwise
    """
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_level = logging.DEBUG if flask_app.config.get("DEBUG") else logging.INFO

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler – rotate at 5 MB, keep 3 backup files.
    file_handler = RotatingFileHandler(
        filename=os.path.join(log_dir, "app.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    # Console handler so logs are visible in Docker / dev terminal output.
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    # Apply to the root logger so every module inherits the same config.
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Guard against duplicate handlers when called more than once (e.g. tests).
    if not root_logger.handlers:
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
