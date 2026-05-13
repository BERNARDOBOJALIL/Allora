import logging
import json
from datetime import datetime
from typing import Any


class StructuredLogFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "service": "location-service",
            "level": record.levelname,
            "event": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_data["error"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Setup a structured logger."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Console handler with JSON formatter
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredLogFormatter())

    logger.addHandler(handler)
    return logger
