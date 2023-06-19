from os import environ

API_BASE = environ.get("API_BASE", "https://parsagon.io").rstrip("/")

try:
    API_KEY = environ["PARSAGON_API_KEY"]
except KeyError:
    raise Exception("Please set the PARSAGON_API_KEY environment variable, e.g. by running: export PARSAGON_API_KEY=...")


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
