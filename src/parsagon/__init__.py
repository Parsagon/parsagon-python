import httpx


# Configuration variables
api_key = None
api_base = "https://parsagon.io/api"


def _request_to_exception(response):
    if response.status_code == 500:
        raise Exception('A server error occurred. Please notify Parsagon.')
    if response.status_code in (502, 503, 504):
        raise Exception('Lost connection to server.')
    errors = response.json()
    if 'non_field_errors' in errors:
        raise Exception(errors['non_field_errors'])
    else:
        raise Exception(errors)


def text_to_program(text):
    headers = {"Authorization": f"Token {api_key}"}
    r = httpx.post(api_endpoint, headers=headers, json={"text": text})
    if not r.is_success:
        _request_to_exception(r)

