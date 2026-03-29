

import logging
import logging.handlers
import os
import sys
import pytest
from unittest.mock import patch


def _reload_logger(log_dir: str, log_level: str = "DEBUG"):

    root = logging.getLogger()
    root.handlers.clear()

    sys.modules.pop("logger", None)

    with patch("config.LOG_DIR", log_dir), \
         patch("config.LOG_LEVEL", log_level):
        import logger as lg
        return lg


class TestLoggerHandlers:
    def test_rotating_file_handler_attached(self, tmp_path):
        lg = _reload_logger(str(tmp_path))
        root = logging.getLogger()
        handler_types = [type(h) for h in root.handlers]
        assert logging.handlers.RotatingFileHandler in handler_types

    def test_stream_handler_attached(self, tmp_path):
        lg = _reload_logger(str(tmp_path))
        root = logging.getLogger()
        handler_types = [type(h) for h in root.handlers]
        assert logging.StreamHandler in handler_types

    def test_log_file_in_correct_directory(self, tmp_path):
        lg = _reload_logger(str(tmp_path))
        root = logging.getLogger()
        rotating = next(
            h for h in root.handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        )
        assert str(tmp_path) in rotating.baseFilename

    def test_log_file_named_correctly(self, tmp_path):
        lg = _reload_logger(str(tmp_path))
        root = logging.getLogger()
        rotating = next(
            h for h in root.handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        )
        assert "wikifile_transfer.log" in rotating.baseFilename

    def test_rotating_handler_max_bytes(self, tmp_path):
        lg = _reload_logger(str(tmp_path))
        root = logging.getLogger()
        rotating = next(
            h for h in root.handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        )
        assert rotating.maxBytes == 5 * 1024 * 1024

    def test_rotating_handler_backup_count(self, tmp_path):
        lg = _reload_logger(str(tmp_path))
        root = logging.getLogger()
        rotating = next(
            h for h in root.handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        )
        assert rotating.backupCount == 5


class TestLoggerLevel:
    def test_info_level_set(self, tmp_path):
        _reload_logger(str(tmp_path), "INFO")
        assert logging.getLogger().level == logging.INFO

    def test_debug_level_set(self, tmp_path):
        _reload_logger(str(tmp_path), "DEBUG")
        assert logging.getLogger().level == logging.DEBUG

    def test_warning_level_set(self, tmp_path):
        _reload_logger(str(tmp_path), "WARNING")
        assert logging.getLogger().level == logging.WARNING


class TestLoggerFormat:
    def test_format_contains_expected_fields(self, tmp_path):
        lg = _reload_logger(str(tmp_path))
        root = logging.getLogger()
        rotating = next(
            h for h in root.handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        )
        fmt = rotating.formatter._fmt
        assert "%(asctime)s" in fmt
        assert "%(levelname)" in fmt
        assert "%(name)s" in fmt
        assert "%(filename)s" in fmt
        assert "%(lineno)d" in fmt
        assert "%(message)s" in fmt


class TestGetLogger:
    def test_returns_logger_instance(self, tmp_path):
        lg = _reload_logger(str(tmp_path))
        result = lg.get_logger("mymodule")
        assert isinstance(result, logging.Logger)

    def test_name_is_correct(self, tmp_path):
        lg = _reload_logger(str(tmp_path))
        result = lg.get_logger("mymodule")
        assert result.name == "mymodule"

    def test_same_name_returns_same_logger(self, tmp_path):
        lg = _reload_logger(str(tmp_path))
        a = lg.get_logger("shared")
        b = lg.get_logger("shared")
        assert a is b

    def test_different_names_return_different_loggers(self, tmp_path):
        lg = _reload_logger(str(tmp_path))
        a = lg.get_logger("module_a")
        b = lg.get_logger("module_b")
        assert a is not b


class TestLogDirectory:
    def test_log_dir_created_if_missing(self, tmp_path):
        new_dir = str(tmp_path / "nested" / "logs")
        assert not os.path.exists(new_dir)
        _reload_logger(new_dir)
        assert os.path.exists(new_dir)
