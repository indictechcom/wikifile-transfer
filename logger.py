import logging
import os
import sys


def initialize_logging_file(log_file_path):
    final_path = log_file_path if log_file_path else "./logs/wikifile_transfer.log"
    os.makedirs(os.path.dirname(final_path), exist_ok=True)
    logging.basicConfig(
        filename=final_path,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )


def log_info(message, *args, **kwargs):
    logging.info(message, *args, **kwargs)


def log_error(message, *args, **kwargs):
    logging.error(message, *args, **kwargs)


def log_exception(message, *args, **kwargs):
    if kwargs.get("exc_info") is not None:
        logging.exception(message, *args, **kwargs)
    elif sys.exc_info()[0] is not None:
        logging.exception(message, *args, **kwargs)
    else:
        logging.error(message, *args, **kwargs)


def log_warning(message, *args, **kwargs):
    logging.warning(message, *args, **kwargs)