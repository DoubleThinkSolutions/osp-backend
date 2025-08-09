import logging
from logging.config import dictConfig
import sys
from .config import settings

# Define log configuration
log_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG" if settings.DEBUG else "INFO",
            "formatter": "default",
            "stream": sys.stdout,
        },
    },
    "loggers": {
        "app": {
            "handlers": ["console"],
            "level": "DEBUG" if settings.DEBUG else "INFO",
            "propagate": False
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "DEBUG" if settings.DEBUG else "INFO",
    },
}

# Configure logging
dictConfig(log_config)

# Create logger instance
logger = logging.getLogger("app")
