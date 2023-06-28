import sys
from os import environ

__API_BASE = environ.get("API_BASE", "https://parsagon.io").rstrip("/")

try:
    __API_KEY = environ["PARSAGON_API_KEY"]
except KeyError:
    raise Exception(
        "Please set the PARSAGON_API_KEY environment variable, e.g. by running: export PARSAGON_API_KEY=..."
    )


def pytest_is_running():
    return "pytest" in sys.modules


def get_api_key():
    """
    Return API key, preventing tests from talking to the real backend
    """
    if pytest_is_running():
        return "test"
    else:
        return __API_KEY


def get_api_base():
    """
    Return API base, preventing tests from talking to the real backend
    """
    if pytest_is_running():
        return "http://test"
    else:
        return __API_BASE


def get_logging_config(log_level="INFO"):
    return {
        "version": 1,
        "disable_existing_loggers": True,
        "formatters": {
            "standard": {"format": "%(message)s"},
        },
        "handlers": {
            "default": {
                "level": "DEBUG",
                "formatter": "standard",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "": {
                "handlers": ["default"],
                "level": log_level,
                "propagate": False,
            },  # root logger
            "parsagon": {
                "handlers": ["default"],
                "level": log_level,
                "propagate": False,
            },
        },
    }
