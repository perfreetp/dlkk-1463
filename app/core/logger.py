import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from typing import Optional

from ..config import settings

_logger_instance: Optional[logging.Logger] = None


def setup_logger() -> logging.Logger:
    global _logger_instance

    if _logger_instance is not None:
        return _logger_instance

    logger = logging.getLogger("imaging_qc")
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    if logger.handlers:
        logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s"
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    os.makedirs(settings.LOG_DIR, exist_ok=True)

    info_file = os.path.join(settings.LOG_DIR, f"info_{datetime.now().strftime('%Y%m%d')}.log")
    info_handler = TimedRotatingFileHandler(
        info_file,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(formatter)
    logger.addHandler(info_handler)

    error_file = os.path.join(settings.LOG_DIR, f"error_{datetime.now().strftime('%Y%m%d')}.log")
    error_handler = RotatingFileHandler(
        error_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)

    logger.propagate = False
    _logger_instance = logger

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    if _logger_instance is None:
        setup_logger()

    if name:
        return logging.getLogger(f"imaging_qc.{name}")
    return _logger_instance
