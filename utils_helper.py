#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Helper functions for error handling and safety.
"""

import os
import logging

logger = logging.getLogger(__name__)


def _safe_remove_temp(filepath: str, *, temp_dir: str = "temp_images") -> None:
    """
    Remove file only if it is inside temp_dir (prevents accidental deletes).
    """
    try:
        temp_dir_abs = os.path.abspath(temp_dir)
        filepath_abs = os.path.abspath(filepath)
        
        # Ensure filepath is inside temp_dir
        if os.path.commonpath([temp_dir_abs, filepath_abs]) == temp_dir_abs and os.path.exists(filepath_abs):
            os.remove(filepath_abs)
            logger.debug("Successfully removed temp file", extra={"filepath": filepath})
    except Exception as e:
        logger.warning("Failed to remove temp file", exc_info=True, extra={"filepath": filepath, "error": str(e)})