"""
Centralized logging configuration for Wikifile Transfer application.

This module sets up structured, rotating file-based logging for both
the Flask app and Celery tasks to ensure consistent logging across
all components.
"""

import os
import logging
from logging.handlers import RotatingFileHandler


def setup_logging(log_file_name='app.log', log_level=logging.INFO):
    """
    Configure structured, rotating file-based logging.
    
    Args:
        log_file_name (str): Name of the log file. Default: 'app.log'
        log_level (int): Logging level. Default: logging.INFO
    
    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Configure rotating file handler (10MB per file, keep 5 backups)
    log_handler = RotatingFileHandler(
        os.path.join(log_dir, log_file_name),
        maxBytes=10 * 1024 * 1024,  # 10MB per file
        backupCount=5  # Keep 5 backup files
    )
    
    # Define structured log format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    log_handler.setFormatter(formatter)

    # Get root logger and configure it
    logger = logging.getLogger()
    logger.setLevel(log_level)
    logger.addHandler(log_handler)

    # Also add console handler for visibility
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def get_logger(name):
    """
    Get a configured logger for a specific module.
    
    Args:
        name (str): Module name (typically __name__)
    
    Returns:
        logging.Logger: Logger instance for the module
    """
    return logging.getLogger(name)
