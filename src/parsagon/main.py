import asyncio
import logging

from src.parsagon.api import get_program_sketches


logger = logging.getLogger(__name__)


def main(task: str):
    logger.info("Launched with task description:\n%s", task)

    logger.info("Sending task description to backend...")
    program_sketches = get_program_sketches(task)
    logger.debug("Program sketches:\n%s", program_sketches)

    full_program = program_sketches["full"]
    abridged_program = program_sketches["abridged"]

    # Execute the abridged program to gather examples

    logger.info("Done.")
