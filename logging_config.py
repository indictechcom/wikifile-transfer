import logging
from logging.handlers import RotatingFileHandler
import os
import sys

def setup_logging(app=None, log_dir=None):
    """
    Setup rotating file logging for both Flask app and Celery worker.
    Returns the absolute path of the logfile created.
    """
    # Determine log directory
    if app is not None:
        log_dir = app.config.get('LOG_DIR', log_dir or '/app/logs')
    log_dir = log_dir or '/app/logs'
    
    # Create log directory
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'wikifile.log')
    
    # Create handlers
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5
    )
    console_handler = logging.StreamHandler(sys.stdout)
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(module)s %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Configure root logger (captures all logging.getLogger() calls)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clear existing handlers and add ours
    root_logger.handlers = []
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Also configure Flask app logger if provided
    if app is not None:
        app.logger.handlers = []
        app.logger.addHandler(file_handler)
        app.logger.addHandler(console_handler)
        app.logger.setLevel(logging.INFO)
        # Prevent double logging by not propagating to root logger
        app.logger.propagate = False
    
    # Configure common third-party loggers
    logging.getLogger('werkzeug').setLevel(logging.WARNING)  # Reduce werkzeug verbosity
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    
    # Log a message to confirm setup
    logging.info(f"Logging initialized. Log file: {os.path.abspath(log_file)}")
    
    return os.path.abspath(log_file)