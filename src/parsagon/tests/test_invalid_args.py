import pytest

from parsagon.main import main


def test_headless_remote_run_invalid(mocker, debug_logs):
    """
    Tests that we are unable to run a program in headless mode when the environment is remote, and that this is logged to the user.
    """
    main(["run", "test_program", "--headless", "--remote"])
    debug_logs_lower = debug_logs.text.lower()
    assert "error" in debug_logs_lower
    assert "headless" in debug_logs_lower
    assert "remote" in debug_logs_lower
