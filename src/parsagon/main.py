import argparse
import json
import logging
import logging.config

from parsagon.api import (
    get_program_sketches,
    create_pipeline,
    delete_pipeline,
    create_custom_function,
    get_pipeline,
    get_pipelines,
    get_pipeline_code,
    APIException,
)
from parsagon.executor import Executor, custom_functions_to_descriptions
from parsagon.settings import get_logging_config

logger = logging.getLogger(__name__)


def create_cli():
    parser = argparse.ArgumentParser(
        prog="parsagon-create",
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
        "-p", "--program", type=str, help="the name of the program to create (otherwise user input is required)"
    )

    args = parser.parse_args()
    task = args.task
    verbose = args.verbose
    pipeline_name = args.program
    create(task, pipeline_name, verbose=verbose)


def configure_logging(verbose):
    logging.config.dictConfig(get_logging_config("DEBUG" if verbose else "INFO"))


def create(task, pipeline_name=None, verbose=False):
    configure_logging(verbose)

    logger.info("Launched with task description:\n%s", task)

    logger.info("Analyzing task description...")
    program_sketches = get_program_sketches(task)

    full_program = program_sketches["full"]
    abridged_program = program_sketches["abridged"]
    logger.debug("Program:\n%s", abridged_program)
    abridged_program += "\n\noutput = func()\nprint(f'Program finished and returned a value of:\\n{output}')\n"  # Make the program runnable

    # Execute the abridged program to gather examples
    executor = Executor()
    executor.execute(abridged_program)

    # The user must select a name
    while True:
        if not pipeline_name:
            pipeline_name = input("Name this program, or press enter without typing a name to DISCARD: ")
        if pipeline_name:
            logger.info(f"Saving program as {pipeline_name}")
            try:
                pipeline = create_pipeline(pipeline_name, task, full_program)
            except APIException as e:
                if isinstance(e.value, list) and "Pipeline with name already exists" in e.value:
                    logger.info("A program with this name already exists. Please choose another name.")
                    pipeline_name = None
                    continue
                else:
                    raise e
            pipeline_id = pipeline["id"]
            try:
                for call_id, custom_function in executor.custom_functions.items():
                    debug_suffix = f" ({custom_function.name})"
                    description = custom_functions_to_descriptions.get(custom_function.name)
                    description = " to " + description if description else ""
                    if verbose:
                        description += debug_suffix
                    logger.info(f"  Saving function{description}...")
                    create_custom_function(pipeline_id, call_id, custom_function)
                logger.info(f"Saved.")
            except:
                delete_pipeline(pipeline_id)
                logger.info(f"An error occurred while saving the program. The program has been discarded.")
            finally:
                break
        else:
            logger.info("Discarded program.")
            break

    logger.info("Done.")


def detail_cli():
    parser = argparse.ArgumentParser(
        prog="parsagon-detail",
        description="Outputs details of a created program.",
    )
    parser.add_argument(
        "--program",
        type=str,
        help="the name of the program",
    )
    args = parser.parse_args()
    pipeline_name = args.program
    return detail(pipeline_name)


def detail(pipeline_name=None):
    if pipeline_name:
        data = [get_pipeline(pipeline_name)]
    else:
        data = get_pipelines()
    for pipeline in data:
        print(
            f"Program: {pipeline['name']}\nDescription: {pipeline['description']}\nVariables: {pipeline['variables']}\n"
        )


def run_cli():
    parser = argparse.ArgumentParser(
        prog="parsagon-run",
        description="Runs a created program.",
    )
    parser.add_argument(
        "program",
        type=str,
        help="the name of the program to run",
    )
    parser.add_argument(
        "--variables",
        type=json.loads,
        default="{}",
        help="a JSON object mapping variables to values",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="run the task in verbose mode")
    args = parser.parse_args()
    pipeline_name = args.program
    variables = args.variables
    verbose = args.verbose
    return run(pipeline_name, variables=variables, environment="LOCAL", verbose=verbose)


def run(pipeline_name, variables={}, environment="LOCAL", verbose=False):
    """
    Executes pipeline code
    """
    configure_logging(verbose)
    logger.info("Preparing to run program %s", pipeline_name)
    try:
        code = get_pipeline_code(pipeline_name, variables, environment)["code"]
    except APIException as e:
        if isinstance(e.value, dict) and e.value.get("detail") == "Not found.":
            logger.error("Error: A program with this name does not exist.")
            return
        else:
            raise e
    logger.info("Running program...")
    globals_locals = {}
    try:
        exec(code, globals_locals, globals_locals)
    finally:
        if "driver" in globals_locals:
            globals_locals["driver"].quit()
    logger.info("Done.")
    return globals_locals["output"]
