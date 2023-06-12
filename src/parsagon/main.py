import argparse
import asyncio
import logging

from src.parsagon.api import get_program_sketches, create_pipeline, create_transformers
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
    parser.add_argument("-v", "--verbose", action="store_true", help="run the task in verbose mode")
    parser.add_argument(
        "-p", "--pipeline", type=str, help="the name of the pipeline to create (otherwise user input is required)"
    )

    return parser.parse_args()


def main():
    args = parse_args()
    logging.config.dictConfig(get_logging_config("DEBUG" if args.verbose else "INFO"))
    task = args.task
    pipeline_name = args.pipeline
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

    if not pipeline_name:
        pipeline_name = input("Name this program, or press enter without typing a name to DISCARD: ")
    if pipeline_name:
        logger.info(f"Saving program as {pipeline_name}")
        pipeline = create_pipeline(pipeline_name, full_program)
        pipeline_id = pipeline["id"]
        for custom_function in executor.custom_functions:
            logger.info(f"  Saving {custom_function.name}...")
            create_transformers(pipeline_id, custom_function)
        logger.info(f"Saved.")
    else:
        logger.info("Discarded program.")

    logger.info("Done.")
