import argparse
import asyncio
import logging

from src.parsagon.api import get_program_sketches
from src.parsagon.executor import Executor
import logging.config

from src.parsagon.settings import get_logging_config

logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        prog="parsagon",
        description="Scrapes and interacts with web pages based on natural language.",
    )

    parser.add_argument(
        "task",
        metavar="task",
        type=str,
        help="natural language description of the task to run, optionally with numbered steps.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="run the task in verbose mode"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    logging.config.dictConfig(get_logging_config("DEBUG" if args.verbose else "INFO"))
    task = args.task
    logger.info("Launched with task description:\n%s", args.task)

    logger.info("Analyzing task description...")
    program_sketches = get_program_sketches(task)

    full_program = program_sketches["full"]
    abridged_program = program_sketches["abridged"]
    logger.debug("Program:\n%s", abridged_program)
    abridged_program += "\n\noutput = func()\nprint(f'Program finished and returned a value of:\\n{output}')\n"  # Make the program runnable

    # Execute the abridged program to gather examples
    executor = Executor()
    executor.execute(abridged_program)

    logger.info("Done.")
