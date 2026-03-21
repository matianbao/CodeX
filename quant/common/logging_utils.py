from __future__ import annotations

import logging


_DEFAULT_FORMAT = "[%(levelname)s] %(name)s - %(message)s"


def configure_logging(level: int = logging.INFO) -> None:
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(level=level, format=_DEFAULT_FORMAT)
    else:
        root_logger.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"quant.{name}")
