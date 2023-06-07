from os import environ

API_BASE = environ["API_BASE"].rstrip("/")
API_KEY = environ["API_KEY"]

LOG_LEVEL = "DEBUG"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "formatters": {
        "standard": {"format": "[%(levelname)s] %(message)s"},
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
        "": {"handlers": ["default"], "level": LOG_LEVEL, "propagate": False},  # root logger
        "src.parsagon": {"handlers": ["default"], "level": LOG_LEVEL, "propagate": False},
    },
}
