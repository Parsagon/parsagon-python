import argparse
import json
import logging
import logging.config
import time

from halo import Halo

from parsagon.api import (
    get_program_sketches,
    create_pipeline,
    delete_pipeline,
    create_custom_function,
    add_examples_to_custom_function,
    create_pipeline_run,
    get_pipeline,
    get_pipelines,
    get_pipeline_code,
    get_run,
    poll_data,
    APIException,
)
from parsagon.exceptions import ParsagonException
from parsagon.executor import Executor, custom_functions_to_descriptions
from parsagon.settings import get_api_key, get_settings, clear_settings, save_setting, get_logging_config

logger = logging.getLogger(__name__)


def configure_logging(verbose):
    logging.config.dictConfig(get_logging_config("DEBUG" if verbose else "INFO"))


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
    parser_create.add_argument(
        "--infer",
        action="store_true",
        help="let Parsagon infer all elements to be scraped",
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

    # Update
    parser_update = subparsers.add_parser(
        "update",
        description="Updates a created program.",
    )
    parser_update.add_argument(
        "program_name",
        type=str,
        help="the name of the program to update",
    )
    parser_update.add_argument(
        "--variables",
        type=json.loads,
        default="{}",
        help="a JSON object mapping variables to values",
    )
    parser_update.add_argument(
        "--headless",
        action="store_true",
        help="run the browser in headless mode",
    )
    parser_update.add_argument(
        "--infer",
        action="store_true",
        help="let Parsagon infer all elements to be scraped",
    )
    parser_update.add_argument(
        "--replace",
        action="store_true",
        help="remove old example data while updating the program",
    )
    parser_update.set_defaults(func=update)

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
        help="run the browser in headless mode",
    )
    parser_run.add_argument(
        "--remote",
        action="store_true",
        help="run the program in the cloud",
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
    parser_delete.add_argument(
        "-y", "--yes", dest="confirm_with_user", action="store_false", help="auto-confirm option"
    )
    parser_delete.set_defaults(func=delete)

    # Setup
    parser_setup = subparsers.add_parser(
        "setup",
        description="Interactively sets up Parsagon with an API key.",
    )
    parser_setup.set_defaults(func=setup)

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


def create(task=None, program_name=None, headless=False, infer=False, verbose=False):
    if task:
        logger.info("Launched with task description:\n%s", task)
    else:
        task = input("Type what you want to do: ")

    logger.info("Analyzing task description...")
    program_sketches = get_program_sketches(task)

    full_program = program_sketches["full"]
    abridged_program = program_sketches["abridged"]
    pseudocode = program_sketches["pseudocode"]
    logger.info(f"Created a program based on task description. Program does the following:\n\n{pseudocode}\n\nNow executing the program to identify web elements to be scraped:\n")
    logger.debug("Program:\n%s", abridged_program)
    abridged_program += "\n\noutput = func()\nprint(f'Program finished and returned a value of:\\n{output}\\n')\n"  # Make the program runnable

    # Execute the abridged program to gather examples
    executor = Executor(headless=headless, infer=infer)
    executor.execute(abridged_program)

    # The user must select a name
    while True:
        if not program_name:
            program_name = input("Name this program to save, or press enter without typing a name to DISCARD: ")
        if program_name:
            logger.info(f"Saving program as {program_name}")
            try:
                pipeline = create_pipeline(program_name, task, full_program, pseudocode)
            except APIException as e:
                if isinstance(e.value, list) and "Pipeline with name already exists" in e.value:
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


def update(program_name, variables={}, headless=False, infer=False, replace=False, verbose=False):
    pipeline = get_pipeline(program_name)
    abridged_program = pipeline["abridged_sketch"]
    # Make the program runnable
    variables_str = ", ".join(f"{k}={repr(v)}" for k, v in variables.items())
    abridged_program += f"\n\noutput = func({variables_str})"
    abridged_program += "\nprint(f'Program finished and returned a value of:\\n{output}\\n')\n"

    # Execute the abridged program to gather examples
    executor = Executor(headless=headless, infer=infer)
    executor.execute(abridged_program)

    while True:
        program_name_input = input(f"Type \"{program_name}\" to update this program, or press enter without typing a name to CANCEL: ")
        if not program_name_input:
            logger.info("Canceled update.")
            return
        if program_name_input == program_name:
            break

    pipeline_id = pipeline["id"]
    try:
        for call_id, custom_function in executor.custom_functions.items():
            debug_suffix = f" ({custom_function.name})"
            description = custom_functions_to_descriptions.get(custom_function.name)
            description = " to " + description if description else ""
            if verbose:
                description += debug_suffix
            logger.info(f"  Saving function{description}...")
            add_examples_to_custom_function(pipeline_id, call_id, custom_function, replace)
        logger.info(f"Saved.")
    except Exception as e:
        print(e)
        logger.info(f"An error occurred while saving the program. The program was not updated.")


def detail(program_name=None, verbose=False):
    if program_name:
        data = [get_pipeline(program_name)]
    else:
        data = get_pipelines()
    for pipeline in data:
        print(
            f"Program: {pipeline['name']}\nDescription: {pipeline['description']}\nVariables: {pipeline['variables']}\n"
        )


def run(program_name, variables={}, headless=False, remote=False, verbose=False):
    """
    Executes pipeline code
    """
    if headless and remote:
        raise ParsagonException("Cannot run a program remotely in headless mode")

    if remote:
        pipeline_id = get_pipeline(program_name)["id"]
        result = create_pipeline_run(pipeline_id, variables)
        with Halo(text="Program running remotely...", spinner="dots"):
            while True:
                run = get_run(result["id"])
                status = run["status"]
                if status == "FINISHED":
                    logger.info("Program finished running.")
                    return run["output"]
                elif status == "ERROR":
                    raise ParsagonException(f"Program failed to run: {run['error']}")
                elif status == "CANCELED":
                    raise ParsagonException("Program execution was canceled")
                time.sleep(5)

    logger.info("Preparing to run program %s", program_name)
    code = get_pipeline_code(program_name, variables, headless)["code"]

    logger.info("Running program...")
    globals_locals = {"PARSAGON_API_KEY": get_api_key()}
    try:
        exec(code, globals_locals, globals_locals)
    finally:
        if "driver" in globals_locals:
            globals_locals["driver"].quit()
        if "display" in globals_locals:
            globals_locals["display"].stop()
    logger.info("Done.")
    return globals_locals["output"]


def delete(program_name, verbose=False, confirm_with_user=False):
    if (
        confirm_with_user
        and input(f"Are you sure you want to delete program with name {program_name}? (y/N) ").lower().strip() != "y"
    ):
        logger.error("Cancelled operation.")
        return
    logger.info("Preparing to delete program %s", program_name)
    pipeline_id = get_pipeline(program_name)["id"]
    logger.info("Deleting program...")
    delete_pipeline(pipeline_id)
    logger.info("Done.")


def setup(verbose=False):
    try:
        old_api_key = get_api_key()
    except ParsagonException:
        old_api_key = None
    try:
        save_setting("api_key", None)
        get_api_key(interactive=True)
    except KeyboardInterrupt:
        save_setting("api_key", old_api_key)
        logger.error("\nCancelled operation.")
        return
    logger.info("Setup complete.")


def _get_data(url, page_type, timeout):
    start_time = time.time()
    with Halo(text="Extracting data...", spinner="dots"):
        while time.time() - start_time <= timeout:
            result = poll_data(url, page_type)
            if result["done"]:
                return result["result"]
            time.sleep(15)
    logger.info("No data found")
    return None


def get_product(url, timeout=300):
    return _get_data(url, "PRODUCT_DETAIL", timeout)


def get_review_article(url, timeout=300):
    return _get_data(url, "REVIEW_ARTICLE_DETAIL", timeout)


def get_article_list(url, timeout=300):
    return _get_data(url, "ARTICLE_LIST", timeout)
