import asyncio
import logging

from src.parsagon.api import get_program_sketches
from src.parsagon.executor import Executor
from src.parsagon.settings import LOGGING
import logging.config

logger = logging.getLogger(__name__)


def main(task: str):
    logging.config.dictConfig(LOGGING)

    logger.info("Launched with task description:\n%s", task)

    logger.info("Analyzing task description...")
    program_sketches = get_program_sketches(task)

    full_program = program_sketches["full"]
    abridged_program = program_sketches["abridged"]
    #logger.debug("Program:\n%s", abridged_program)
    abridged_program += "\n\noutput = func()\nprint(f'Program finished and returned a value of:\\n{output}')\n"  # Make the program runnable

    # Execute the abridged program to gather examples
    executor = Executor()
    executor.execute(abridged_program)

    logger.info("Done.")
