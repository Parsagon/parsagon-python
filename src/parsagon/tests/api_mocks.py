import functools
import json
import re

from httpx import codes


class MockResponse:
    def __init__(self, status_code, json_body=None, text_body=None):
        self.status_code = status_code
        self.json_body = json_body
        self.text_body = text_body
        assert not (json_body and text_body)

    def json(self):
        if not self.json_body:
            raise json.JSONDecodeError("No JSON body", "", 0)
        return self.json_body

    @property
    def is_success(self):
        return codes.is_success(self.status_code)

    @property
    def text(self):
        return json.dumps(self.json_body) if self.json_body else self.text_body or ""


not_found_pipeline_name = "my_incorrect_name"
not_found_pipeline_id = 44
not_found_response = MockResponse(404, json_body={"detail": "Not found."})


def mock_httpx_method_func(*args, **kwargs):
    """
    A mock that is used for httpx post, get, put, patch, and delete methods.  The "method" kwarg differentiates which mock is being called, and the "mock_options" kwarg provides further options pertaining to the desired behavior of the mock. The following keys are supported:

    - code_to_return: For operations that require code to be returned, this will be used.
    """
    method = kwargs["method"].lower()
    mock_options = kwargs["mock_options"]
    url = args[0]

    if match := re.search(r"/pipelines/name/(.+)/code/$", url):
        assert method == "post"
        pipeline_name = match.group(1)
        if pipeline_name == not_found_pipeline_name:
            return not_found_response
        return MockResponse(
            200,
            json_body={
                "code": mock_options["code_to_return"],
            },
        )

    if match := re.search(r"/pipelines/name/(.+)/$", url):
        assert method == "get"
        pipeline_name = match.group(1)
        if pipeline_name == not_found_pipeline_name:
            return not_found_response
        return MockResponse(
            200,
            json_body={
                "id": hash(pipeline_name) % 1000,
                "name": pipeline_name,
            },
        )

    if match := re.search(r"/pipelines/(\d+)/$", url):
        assert method == "delete"
        pipeline_id = match.group(1)
        if pipeline_id == not_found_pipeline_id:
            return not_found_response
        return MockResponse(204)

    raise Exception("Unknown combination of method and url: %s %s" % (method, url))


def install_api_mocks(mocker, mock_options=None):
    """
    Installs mocks for the backend. The "mock_options" kwarg can be used to customize responses. See mock_httpx_method_func for details.
    """

    if mock_options is None:
        mock_options = {}

    # NOTE: Remember to update this if we add code that introduces other calling points to the backend, or if we change the way these httpx method functions are imported.
    for method in ["get", "post", "put", "patch", "delete"]:
        mocker.patch(
            "parsagon.api.httpx.%s" % method,
            functools.partial(mock_httpx_method_func, method=method, mock_options=mock_options),
        )
