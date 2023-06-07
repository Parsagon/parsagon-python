import httpx

from src.parsagon import settings


def _request_to_exception(response):
    if response.status_code == 500:
        raise Exception("A server error occurred. Please notify Parsagon.")
    if response.status_code in (502, 503, 504):
        raise Exception("Lost connection to server.")
    errors = response.json()
    if "non_field_errors" in errors:
        raise Exception(errors["non_field_errors"])
    else:
        raise Exception(errors)


def _api_call(httpx_func, endpoint, json):
    api_key = settings.API_KEY
    api_endpoint = f"{settings.API_BASE}/api{endpoint}"
    headers = {"Authorization": f"Token {api_key}"}
    r = httpx_func(api_endpoint, headers=headers, json=json, timeout=None)
    if not r.is_success:
        _request_to_exception(r)
    else:
        return r.json()


def get_program_sketches(description):
    """
    Gets a program sketches (full and abridged) from a description.
    :param description: Description in natural language that will be used to generate the scraping program.
    :return: A dict with keys "full" and "abridged" for the respective program ASTs.
    """
    return _api_call(httpx.post, "/transformers/get-program-sketch/", json={"description": description})
