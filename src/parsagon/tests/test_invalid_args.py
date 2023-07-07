import pytest

from parsagon import run
from parsagon.tests.cli_mocks import call_cli


def test_headless_remote_run_invalid(mocker, debug_logs):
    """
    Tests that we are unable to run a program in headless mode when the environment is remote, and that this is logged to the user.
    """
    call_cli(
        mocker,
        {
            "func": run,
            "program_name": "test_program",
            "headless": True,
            "remote": True,
            "verbose": False,
        },
    )
    debug_logs_lower = debug_logs.text.lower()
    assert "error" in debug_logs_lower
    assert "headless" in debug_logs_lower
    assert "remote" in debug_logs_lower
