import logging

import pytest


@pytest.fixture
def debug_logs(caplog, mocker):
    """
    The caplog fixture does not work with Parsagon's logging configuration - override the logging configuration, set sensitivity to debug, and return the caplog fixture.
    """
    mocker.patch("parsagon.main.configure_logging", lambda level: logging.basicConfig(level=logging.DEBUG))
    caplog.set_level(logging.DEBUG)
    return caplog
