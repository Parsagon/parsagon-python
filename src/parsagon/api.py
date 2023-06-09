import json

import httpx

from src.parsagon import settings

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
    return int(result)


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
    name = custom_function.name
    if name in ("click_elem", "select_option", "fill_input"):
        action_type = {
            "click_elem": "SCRAPE_CLICK_HTMLELEM",
            "select_option": "SCRAPE_SELECT_HTMLELEM",
            "fill_input": "SCRAPE_FILL_HTMLELEM",
        }[name]
        params = (
            {
                "actionType": action_type,
                "inputVariableName": "page",
                "outputWebActionSilent": False,
                "actionName": action_type,
                "inputType": "VAR",
                "inputVariableNames": ["page"],
                "inputScrapeInclude": "ALL",
                "outputType": "VAR",
                "outputVariableName": "page",
                "outputVariableAction": "MODIFY",
                "outputVariableType": "WEBPAGE",
            },
        )
        html = custom_function.context["html"]
        elem_id = custom_function.context["elem_id"]
        scrape_elem_programs = _api_call(
            httpx.post,
            "/transformers/scraper-search",
            json={
                "params": params,
                "examples": _examples_of_page_to_elem(html, elem_id),
                "environment": environment,
                "operation": "SCRAPE_HTMLELEM",
                "field": {"name": "element", "type": "ACTION", "nodes": [[str(elem_id)]]},
            },
        )["programs"]
        assert len(scrape_elem_programs) > 0
        scrape_elem_tree = scrape_elem_programs[0]["tree"]
        scrape_interact_programs = _api_call(
            httpx.post,
            "/transformers/scraper-search",
            json={
                "params": params,
                "environment": environment,
                "operation": action_type,
                "partial_program": scrape_elem_tree,
            },
        )
        assert len(scrape_interact_programs) > 0
        tree = scrape_interact_programs[0]["tree"]

    elif custom_function.name == "scrape_elem":
        params = {
            "actionType": "SCRAPE_WEB",
            "inputVariableName": "page",
            "outputVariableName": "scraped_data",
            "actionName": "SCRAPE_WEB",
            "inputType": "VAR",
            "inputVariableNames": ["page"],
            "inputScrapeInclude": "ALL",
            "outputType": "VAR",
            "outputVariableType": "JSON",
            "outputVariableAction": "CREATE",
        }
        schema = custom_function.args["schema"]
        nodes = custom_function.context["nodes"]
        url = custom_function.context["url"]
        html = custom_function.context["html"]

        def get_scrape_type(gpt_type):
            return {
                "str": "TEXT",
                "int": "TEXT",
            }[gpt_type]

        html_fields = [
            {"name": name, "type": get_scrape_type(gpt_type), "nodes": nodes, "gpt_type": gpt_type}
            for name, gpt_type in schema.keys
        ]
        field_sets = [html_fields]
        input_sets = [[{"dataStr": json.dumps({"html": html, "url": url}), "format": "WEB"}]]
        dataset0_obj = {"type": "OBJECT", "is_list": False, "object": None, "user_created": False, "name": "dataset0"}
        columns = [
            {
                "name": name,
                "type": get_scrape_type(gpt_type),
                "is_list": False,
                "object": dataset0_obj,
                "user_created": True,
            }
            for name, gpt_type in schema.keys
        ]

        scrape_page_programs = _api_call(
            httpx.post,
            "/transformers/scraper-search",
            json={
                "params": params,
                "examples": custom_function.examples,
                "environment": environment,
                "operation": "SCRAPE_PAGE_COMPOUND",
                "field_sets": field_sets,
                "input_sets": input_sets,
                "columns": columns,
            },
        )["programs"]
        tree = scrape_page_programs["programs"][0]["tree"]
    else:
        raise NotImplementedError(f"Custom function not implemented: {custom_function.name}")

    return _api_call(
        httpx.post,
        "/transformers/",
        json={
            "pipeline": pipeline_id,
            **custom_function.as_dict(),
            "tree": tree,
            "params": params,
            "examples": [],
            "aux_examples": [],
            "outer_transformer": None,
            "call_id": custom_function.call_id,
        },
    )
