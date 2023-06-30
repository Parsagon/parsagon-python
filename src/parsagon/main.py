import argparse
import json
import logging
import logging.config
import time

from halo import Halo

from parsagon import settings
from parsagon.api import (
    get_program_sketches,
    create_pipeline,
    delete_pipeline,
    create_custom_function,
    get_pipeline,
    get_pipelines,
    get_pipeline_code,
    APIException,
    create_pipeline_run,
    get_run,
)
from parsagon.exceptions import ParsagonException
from parsagon.executor import Executor, custom_functions_to_descriptions

logger = logging.getLogger(__name__)


def configure_logging(verbose):
    logging.config.dictConfig(settings.get_logging_config("DEBUG" if verbose else "INFO"))


def get_args():
    parser = argparse.ArgumentParser(
        prog="parsagon", description="Scrapes and interacts with web pages based on natural language.", add_help=False
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="run the task in verbose mode")
    subparsers = parser.add_subparsers()

    # Create
    parser_create = subparsers.add_parser("create", description="Creates a program.")
    parser_create.add_argument(
        "--task",
        dest="task",
        type=str,
        help="natural language description of the task to run",
    )
    parser_create.add_argument(
        "--program",
        dest="program_name",
        type=str,
        help="the name of the program to create",
    )
    parser_create.add_argument(
        "--headless",
        action="store_true",
        help="run the browser in headless mode",
    )
    parser_create.set_defaults(func=create)

    # Detail
    parser_detail = subparsers.add_parser(
        "detail",
        description="Outputs details of a created program.",
    )
    parser_detail.add_argument(
        "-p",
        "--program",
        dest="program_name",
        type=str,
        help="the name of the program",
    )
    parser_detail.set_defaults(func=detail)

    # Run
    parser_run = subparsers.add_parser(
        "run",
        description="Runs a created program.",
    )
    parser_run.add_argument(
        "program_name",
        type=str,
        help="the name of the program to run",
    )
    parser_run.add_argument(
        "--variables",
        type=json.loads,
        default="{}",
        help="a JSON object mapping variables to values",
    )
    parser_run.add_argument(
        "--headless",
        action="store_true",
        help="run the browser in headless mode (for running locally)",
    )
    parser_run.add_argument(
        "--remote",
        action="store_const",
        const="REMOTE",
        default="LOCAL",
        dest="environment",
        help="runs the program remotely on Parsagon's servers",
    )
    parser_run.add_argument(
        "--proxy",
        dest="proxy_type",
        type=str,
        choices=["none", "datacenter", "residential"],
        default="none",
        help="type of the proxy to use, if running the program remotely",
    )
    parser_run.set_defaults(func=run)

    # Delete
    parser_delete = subparsers.add_parser(
        "delete",
        description="Deletes a program.",
    )
    parser_delete.add_argument(
        "program_name",
        type=str,
        help="the name of the program to run",
    )
    parser_delete.set_defaults(func=delete)
    args = parser.parse_args()
    kwargs = vars(args)
    return kwargs, parser


def main():
    kwargs, parser = get_args()
    func = kwargs.pop("func")
    verbose = kwargs["verbose"]
    configure_logging(verbose)

    if func:
        try:
            return func(**kwargs)
        except ParsagonException as e:
            error_message = "Error:\n" + e.to_string(verbose)
            logger.error(error_message)
    else:
        parser.print_help()


def create(task=None, program_name=None, headless=False, verbose=False):
    if task:
        logger.info("Launched with task description:\n%s", task)
    else:
        task = input("Type what you want to do: ")

    logger.info("Analyzing task description...")
    program_sketches = get_program_sketches(task)
    logger.info("Created a program based on task description. Now demonstrating what the program does:\n")

    full_program = program_sketches["full"]
    abridged_program = program_sketches["abridged"]
    logger.debug("Program:\n%s", abridged_program)
    abridged_program += "\n\noutput = func()\nprint(f'Program finished and returned a value of:\\n{output}\\n')\n"  # Make the program runnable

    # Execute the abridged program to gather examples
    executor = Executor(headless=headless)
    executor.execute(abridged_program)

    # The user must select a name
    while True:
        if not program_name:
            program_name = input("Name this program to save, or press enter without typing a name to DISCARD: ")
        if program_name:
            logger.info(f"Saving program as {program_name}")
            try:
                pipeline = create_pipeline(program_name, task, full_program)
            except APIException as e:
                if isinstance(e.value, list) and "Program with name already exists" in e.value:
                    logger.info("A program with this name already exists. Please choose another name.")
                    program_name = None
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


def detail(program_name=None, verbose=False):
    if program_name:
        data = [get_pipeline(program_name)]
    else:
        data = get_pipelines()
    for pipeline in data:
        print(
            f"Program: {pipeline['name']}\nDescription: {pipeline['description']}\nVariables: {pipeline['variables']}\n"
        )


def run(program_name, variables={}, environment="LOCAL", headless=False, proxy_type="none", verbose=False):
    """
    Executes pipeline code
    """
    assert proxy_type in [
        "none",
        "datacenter",
        "residential",
    ], "Proxy type should be one of 'none', 'datacenter', or 'residential'"
    if environment == "REMOTE" and headless:
        raise ParsagonException("Cannot run a program remotely in headless mode")
    logger.info("Preparing to run program %s", program_name)
    code = get_pipeline_code(program_name, variables, environment, headless)["code"]

    logger.info("Running program...")
    globals_locals = {"PARSAGON_API_KEY": settings.get_api_key()}
    if environment == "LOCAL":
        try:
            exec(code, globals_locals, globals_locals)
            result = globals_locals["output"]
        finally:
            if "driver" in globals_locals:
                globals_locals["driver"].quit()
            if "display" in globals_locals:
                globals_locals["display"].stop()
    elif environment == "REMOTE":
        pipeline_id = get_pipeline(program_name)["id"]
        result = create_pipeline_run(pipeline_id, variables)
        logger.info("Waiting for program to finish running...")
        with Halo(text="Loading", spinner="dots"):
            while True:
                # Poll run
                run = get_run(result["id"])
                if run.status == "FINISHED":
                    logger.info("Program finished running")
                    break
                elif run.status == "ERROR":
                    logger.error("Program failed to run: %s", run.error)
                    break
                elif run.status == "CANCELED":
                    logger.error("Program execution was canceled")
                    break
                time.sleep(3)

    else:
        raise ParsagonException(f"Unknown environment: {environment}")
    logger.info("Done.")
    return result


def delete(program_name, verbose=False):
    logger.info("Preparing to delete program %s", program_name)
    pipeline_id = get_pipeline(program_name)["id"]
    logger.info("Deleting program...")
    delete_pipeline(pipeline_id)
    logger.info("Done.")
