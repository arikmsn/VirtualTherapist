"""Shared pytest fixtures and configuration."""

import logging
import pytest
from loguru import logger


@pytest.fixture(autouse=True)
def propagate_loguru_to_caplog(caplog):
    """Bridge loguru → stdlib logging so pytest's caplog fixture captures loguru output."""
    handler_id = logger.add(
        lambda msg: logging.getLogger(msg.record["name"]).handle(
            logging.makeLogRecord(
                {
                    "name": msg.record["name"],
                    "levelno": msg.record["level"].no,
                    "levelname": msg.record["level"].name,
                    "msg": msg.record["message"],
                    "pathname": msg.record["file"].path,
                    "lineno": msg.record["line"],
                    "funcName": msg.record["function"],
                }
            )
        ),
        format="{message}",
    )
    yield
    logger.remove(handler_id)
