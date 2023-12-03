import argparse
import logging

import pytest

from parsagon import delete, run
from parsagon.main import main
from parsagon.tests.api_mocks import install_api_mocks, not_found_pipeline_name


def test_pipeline_delete(mocker):
    install_api_mocks(mocker)
    delete("test_program")


def test_pipeline_not_found(mocker, debug_logs):
    install_api_mocks(mocker, {"code_to_return": 'raise Exception("Should not exec this code if pipeline not found.")'})

    # On delete
    main(["delete", not_found_pipeline_name, "-y"])
    assert f"A program with name {not_found_pipeline_name} does not exist." in debug_logs.text
    debug_logs.clear()

    # On attempted run
    main(["run", not_found_pipeline_name])
    assert f"A program with name {not_found_pipeline_name} does not exist." in debug_logs.text
