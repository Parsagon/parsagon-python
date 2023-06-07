import asyncio
import logging

from src.parsagon.api import get_program_sketches
from src.parsagon.executor import Executor
from src.parsagon.selenium_wrapper import SeleniumWrapper
from src.parsagon.settings import LOGGING
import logging.config

logger = logging.getLogger(__name__)


def main(task: str):
    logging.config.dictConfig(LOGGING)

    logger.info("Launched with task description:\n%s", task)

    logger.info("Sending task description to backend...")
    program_sketches = get_program_sketches(task)

    full_program = program_sketches["full"]
    abridged_program = program_sketches["abridged"]
    abridged_program += "\n\nfunc()\n"  # Make the program runnable
    logger.debug("Program:\n%s", abridged_program)

    # Execute the abridged program to gather examples
    selenium_wrapper = SeleniumWrapper()
    executor = Executor(selenium_wrapper)
    executor.execute(abridged_program)

    logger.info("Done.")
