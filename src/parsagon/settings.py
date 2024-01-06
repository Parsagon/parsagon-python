import json
import logging
import os
import sys
from os import environ
from pathlib import Path
import logging.config

from parsagon.exceptions import ParsagonException

__API_BASE = environ.get("API_BASE", "https://parsagon.io").rstrip("/")
__SETTINGS_FILE = environ.get("SETTINGS_FILE", ".parsagon_profile")


logger = logging.getLogger(__name__)

GUI_ENABLED = os.environ.get("GUI_ENABLED", "0") == "1"


def pytest_is_running():
    return "pytest" in sys.modules


def get_save_api_key_interactive():
    from parsagon.print import input, error_print

    while True:
        api_key = input("Please enter your Parsagon API key: ")
        if len(api_key) != 40:
            error_print("Error: a Parsagon API key must be 40 characters long.")
        else:
            break
    save_setting("api_key", api_key)
    return api_key


def get_api_key(interactive=False):
    """
    Return API key, preventing tests from talking to the real backend
    """
    if pytest_is_running():
        return "test"

    saved_api_key = get_setting("api_key")
    if saved_api_key is not None:
        assert isinstance(saved_api_key, str), "API key must be a string."
        return saved_api_key
    elif interactive:
        return get_save_api_key_interactive()
    else:
        raise ParsagonException("No API key found. Please run `parsagon setup`.")


def save_settings(settings):
    with open(get_settings_file_path(), "w") as f:
        json.dump(settings, f, indent=4, sort_keys=True)


def save_setting(name, value):
    settings = get_settings()
    settings[name] = value
    save_settings(settings)


def get_settings():
    if get_settings_file_path().is_file():
        with open(get_settings_file_path(), "r") as f:
            return json.load(f)
    else:
        return {}


def clear_settings():
    if get_settings_file_path().is_file():
        get_settings_file_path().unlink()


def get_setting(key):
    return get_settings().get(key)


def get_settings_file_path():
    """
    Return settings file path, which is a hidden file in the user's home directory
    """
    return Path().home() / __SETTINGS_FILE


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


def configure_logging(verbose):
    logging.config.dictConfig(get_logging_config("DEBUG" if verbose else "INFO"))


def get_resource_path():
    if GUI_ENABLED:
        try:
            return Path(sys._MEIPASS)
        except AttributeError:
            return Path(__file__).parent
    else:
        return Path(__file__).parent


def get_graphic(name):
    return str(get_resource_path() / "graphics" / name)
