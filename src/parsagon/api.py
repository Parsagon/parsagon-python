import contextlib
import json
from json import JSONDecodeError

import httpx

from parsagon import settings
from parsagon.exceptions import ParsagonException, APIException, ProgramNotFoundException

environment = "PANDAS_1.x"


class RaiseProgramNotFound:
    def __init__(self, program_name):
        self.program_name = program_name

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None and issubclass(exc_type, APIException):
            if exc_value.status_code == 404:
                raise ProgramNotFoundException(self.program_name)
        return False


def _request_to_exception(response):
    status_code = response.status_code
    if status_code == 500:
        raise APIException("A server error occurred. Please notify Parsagon.", status_code)
    if status_code in (502, 503, 504):
        raise APIException("Lost connection to server.", status_code)
    try:
        errors = response.json()
        if "non_field_errors" in errors:
            raise APIException(errors["non_field_errors"], status_code)
        else:
            raise APIException(errors, status_code)
    except JSONDecodeError:
        raise APIException("Could not parse response.", status_code)


def _api_call(httpx_func, endpoint, **kwargs):
    api_key = settings.get_api_key()
    api_endpoint = f"{settings.get_api_base()}/api{endpoint}"
    headers = {"Authorization": f"Token {api_key}"}
    r = httpx_func(api_endpoint, headers=headers, timeout=None, **kwargs)
    if not r.is_success:
        _request_to_exception(r)
    else:
        try:
            return r.json()
        except:
            return None


def get_program_sketches(description):
    """
    Gets a program sketches (full and abridged) from a description.
    :param description: Description in natural language that will be used to generate the scraping program.
    :return: A dict with keys "full" and "abridged" for the respective program ASTs.
    """
    return _api_call(httpx.post, "/transformers/get-program-sketch/", json={"description": description})


def get_interaction_element_id(marked_html, elem_type, description):
    """
    Gets a program sketches (full and abridged) from a description.
    :param marked_html: HTML with data-psgn-id attributes.
    :param elem_type: One of INPUT, BUTTON, or SELECT.
    :param description: A natural language description of the element.
    :return: The integer ID (data-psgn-id) of the element in the marked HTML.
    """
    assert elem_type.isupper()
    result = _api_call(
        httpx.post,
        "/transformers/get-nav-elem/",
        json={"html": marked_html, "elem_type": elem_type, "description": description},
    )["id"]
    return result


def scrape_page(html, schema):
    """
    Scrapes data from the provided page HTML - data will be returned in the schema provided.
    :param url: url of the page to scrape.
    :param html: HTML of the page to scrape.
    :param schema: Schema of the data to scrape
    :return: Scraped data, with lists truncated.
    """
    return _api_call(httpx.post, "/transformers/get-custom-data/", json={"html": html, "schema": schema})


def create_pipeline(name, description, program_sketch):
    return _api_call(
        httpx.post, "/pipelines/", json={"name": name, "description": description, "program_sketch": program_sketch}
    )


def delete_pipeline(pipeline_id):
    return _api_call(httpx.delete, f"/pipelines/{pipeline_id}/")


def create_custom_function(pipeline_id, call_id, custom_function):
    _api_call(
        httpx.post,
        "/transformers/custom-function/",
        json={"pipeline": pipeline_id, "call_id": call_id, **custom_function.to_json()},
    )


def get_pipeline(pipeline_name):
    with RaiseProgramNotFound(pipeline_name):
        return _api_call(
            httpx.get,
            f"/pipelines/name/{pipeline_name}/",
        )


def get_pipelines():
    return _api_call(httpx.get, f"/pipelines/")


def get_pipeline_code(pipeline_name, variables, headless):
    with RaiseProgramNotFound(pipeline_name):
        return _api_call(
            httpx.post,
            f"/pipelines/name/{pipeline_name}/code/",
            json={
                "variables": variables,
                "headless": headless,
            },
        )


def create_pipeline_run(pipeline_id, variables):
    return _api_call(
        httpx.post,
        f"/pipelines/{pipeline_id}/runs/",
        json={"variables": variables},
    )


def get_run(run_id):
    """
    Gets details about a run
    """
    return _api_call(
        httpx.get,
        f"/pipelines/runs/{run_id}/",
    )
