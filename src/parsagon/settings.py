from os import environ

BACKEND_URL = environ.get("BACKEND_URL").rstrip("/") + "/"
API_KEY = environ.get("API_KEY")
