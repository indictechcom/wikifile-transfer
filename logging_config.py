#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Logging setup with rotating file handlers to keep track of app activity and errors."""

import logging
import logging.handlers
import os
import json
from datetime import datetime
import time 
from contextlib import contextmanager
from exceptions import WikifileTransferError

# Formats each log record as a single-line JSON object for structured logging
class JSONFormatter(logging.Formatter):

    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        # Include full exception details if the log record has one
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }
        # Include any extra context passed alongside the log message
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data
        return json.dumps(log_data)
    
class ContextFilter(logging.Filter):
        """Adds contextual information to log records, such as request ID or user ID."""
        def filter(self, record):
         if not hasattr(record, "extra_data"):
            record.extra_data = {}
         return True

            


# Creates the logs/ directory and attaches rotating file handlers to the logger
def setup_logging(app_name="wikifile-transfer", log_dir="logs", log_level=logging.INFO,env="dev"):
    if not os.path.exists(log_dir):
        os.makedirs(log_dir,exist_ok=True)

    logger = logging.getLogger(app_name)
    logger.setLevel(log_level)

    # Clear existing handlers to avoid duplicate entries on repeated calls
    logger.handlers.clear()

    #add context filter to include extra data in all logs if there is an extra data
    context_filter=ContextFilter()
    logger.addFilter(context_filter)


    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # General log — captures everything INFO and above, rotates at 10MB
    general_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, f"{app_name}.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    general_handler.setLevel(logging.INFO)
    general_handler.setFormatter(formatter)
    logger.addHandler(general_handler)

    # Error log — captures only ERROR and CRITICAL for quick failure monitoring
    error_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, f"{app_name}-error.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)

    # Structured JSON log — same events as JSON objects for machine parsing
    
    json_handler = logging.handlers.RotatingFileHandler(
        
        filename=os.path.join(log_dir, f"{app_name}-structured.jsonl"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    json_handler.setLevel(logging.INFO)
    json_handler.setFormatter(JSONFormatter())
    logger.addHandler(json_handler)

    #Console Handler for development
    if env=="dev":
     console_handler = logging.StreamHandler()
     console_handler.setLevel(logging.INFO)
     console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(module)s - %(message)s',
        datefmt='%H:%M:%S'
     )
     console_handler.setFormatter(console_formatter)
     logger.addHandler(console_handler)
     logger.info(f"Logging configured — writing to {log_dir}/")
    return logger


# Returns a logger scoped under the wikifile-transfer namespace for the calling module
def get_logger(name=None):
    if name:
        return logging.getLogger(f"wikifile-transfer.{name}")
    return logging.getLogger("wikifile-transfer")


# Logs a caught exception with its full stack trace and optional extra context
def log_exception(logger, exception, extra_context=None):
    extra_data = {
        "exception_type": type(exception).__name__,
        "exception_message": str(exception),
    }
    if extra_context:
        extra_data.update(extra_context)

    logger.error(
        f"Exception occurred: {type(exception).__name__}: {str(exception)}",
        exc_info=True,
        extra={"extra_data": extra_data}
    )


# Logs a MediaWiki API call with its method, endpoint, status code, and result

def log_api_call(logger, endpoint, method, status_code=None, duration=None, exception=None):
    extra_data = {
        "endpoint": endpoint,
        "method": method,
        "status_code": status_code,
        "duration_seconds": duration,
    }

    if exception:
        extra_data["exception_type"] = type(exception).__name__
        extra_data["exception_message"] = str(exception)

        logger.error(
            f"API call failed: {method} {endpoint}",
            exc_info=True,
            extra={"extra_data": extra_data}
        )
    else:
        logger.info(
            f"API call: {method} {endpoint} — {status_code}",
            extra={"extra_data": extra_data}
        )


from contextlib import contextmanager
import time

@contextmanager
def log_timed_api_call(logger, endpoint, method):
    start = time.time()
    context = {}
    try:
        yield context
    except Exception as e:
        duration = time.time() - start

        log_api_call(
            logger,
            endpoint,
            method,
            duration=duration,
            exception=e
        )
        raise
    else:
        duration = time.time() - start

        log_api_call(
            logger,
            endpoint,
            method,
            duration=duration,
            status_code=context.get("status_code", 200)
        )

# Logs a file system operation such as download, upload, or write with its outcome
def log_file_operation(logger, operation, file_path, success=True, error=None):
    extra_data = {
        "operation": operation,
        "file_path": file_path,
        "success": success,
    }
    if not success and error:
        extra_data["error"] = error
        logger.error(
            f"File operation failed: {operation} — {file_path} — {error}",
            extra={"extra_data": extra_data}
        )
    else:
        logger.info(
            f"File operation: {operation} — {file_path}",
            extra={"extra_data": extra_data}
        )


# Logs a Celery async task lifecycle event such as started, completed, or failed
def log_task_event(logger, task_id, task_name, status, error=None, progress=None):
    extra_data = {
        "task_id": task_id,
        "task_name": task_name,
        "status": status,
    }
    if progress:
        extra_data["progress"] = progress
    if error:
        extra_data["error"] = error
        logger.error(
            f"Task failed: {task_name} [{task_id}] — {error}",
            extra={"extra_data": extra_data}
        )
    else:
        logger.info(
            f"Task event: {task_name} [{task_id}] — {status}",
            extra={"extra_data": extra_data}
        )
