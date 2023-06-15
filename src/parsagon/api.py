import json

import httpx

from parsagon import settings

environment = "PANDAS_1.x"


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


def _api_call(httpx_func, endpoint, **kwargs):
    api_key = settings.API_KEY
    api_endpoint = f"{settings.API_BASE}/api{endpoint}"
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
    :param html: HTML of the page to scrape.
    :param schema: Schema of the data to scrape, in the format
    :return: Scraped data, with lists truncated.
    """
    return _api_call(httpx.post, "/transformers/get-custom-data/", json={"html": html, "schema": schema})


def create_pipeline(name, program_sketch):
    return _api_call(httpx.post, "/pipelines/", json={"name": name, "program_sketch": program_sketch})


def delete_pipeline(pipeline_id):
    return _api_call(httpx.delete, f"/pipelines/{pipeline_id}/")


def _examples_of_page_to_elem(html, elem_id):
    """
    Returns scraper search examples for a page going to an element
    """
    return {
        "inputs": [
            {
                "format": "WEB",
                "dataStr": json.dumps({"html": html}),
            }
        ],
        "output": [str(elem_id)],
    }


def create_transformers(pipeline_id, custom_function):
    """
    Creates transformers associated with a custom function
    :param pipeline_id:
    :param custom_function:
    :return:
    """
    _api_call(
        httpx.post,
        "/transformers/custom-function/",
        json={"pipeline": pipeline_id, **custom_function.to_json()},
    )


def get_pipeline_code(pipeline_name, environment):
    return _api_call(
        httpx.post,
        f"/pipelines/get-code-by-name/",
        json={
            "pipeline_name": pipeline_name,
            "environment": environment,
        },
    )
