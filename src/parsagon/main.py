import argparse
import json
import logging.config
import time

from rich.console import Console
from rich.prompt import Prompt

from parsagon.api import (
    delete_pipeline,
    add_examples_to_custom_function,
    get_pipeline,
    get_pipelines,
    poll_extract
)
from parsagon.assistant import assist
from parsagon.create import create_program
from parsagon.exceptions import ParsagonException
from parsagon.executor import Executor, custom_functions_to_descriptions
from parsagon.runs import run_with_file_output
from parsagon.settings import get_api_key, save_setting, configure_logging

console = Console()
logger = logging.getLogger(__name__)


def get_args():
    parser = argparse.ArgumentParser(
        prog="parsagon", description="Scrapes and interacts with web pages based on natural language.", add_help=False
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="run the task in verbose mode")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="run the browser in headless mode",
    )
    parser.add_argument(
        "--infer",
        action="store_true",
        help="let Parsagon infer all elements to be scraped",
    )
    subparsers = parser.add_subparsers()

    # Create
    parser_create = subparsers.add_parser("create", description="Creates a program.")
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
    parser_create.set_defaults(func=create_cli)

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
    parser_run.add_argument(
        "--output_log",
        action="store_true",
        help="output log data from the run",
    )
    parser_run.set_defaults(func=run_with_file_output)

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

    # Help
    parser_help = subparsers.add_parser(
        "help",
        description="Shows help.",
    )
    parser_help.set_defaults(func=help, parser=parser)

    args = parser.parse_args()
    kwargs = vars(args)
    return kwargs, parser


def main():
    kwargs, parser = get_args()
    func = kwargs.pop("func", None)
    if func is None:
        func = assist
    else:
        # Pop assist-only arguments
        kwargs.pop("infer")
        kwargs.pop("headless")
    verbose = kwargs["verbose"]
    configure_logging(verbose)

    try:
        return func(**kwargs)
    except ParsagonException as e:
        error_message = "Error:\n" + e.to_string(verbose)
        logger.error(error_message)


def create_cli(headless=False, infer=False, verbose=False):
    task = Prompt.ask("Enter a detailed scraping task")
    create_program(task, headless=headless, infer=infer)


def update(program_name, variables={}, headless=False, infer=False, replace=False, verbose=False):
    configure_logging(verbose)

    pipeline = get_pipeline(program_name)
    abridged_program = pipeline["abridged_sketch"]
    # Make the program runnable
    variables_str = ", ".join(f"{k}={repr(v)}" for k, v in variables.items())
    abridged_program += f"\n\noutput = func({variables_str})\n"

    # Execute the abridged program to gather examples
    executor = Executor(headless=headless, infer=infer)
    executor.execute(abridged_program)

    while True:
        program_name_input = input(
            f'Type "{program_name}" to update this program, or press enter without typing a name to CANCEL: '
        )
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
        logger.error(f"An error occurred while saving the program. The program was not updated.")


def detail(program_name=None, verbose=False):
    if program_name:
        data = [get_pipeline(program_name)]
    else:
        data = get_pipelines()
    for pipeline in data:
        print(
            f"Program: {pipeline['name']}\nDescription: {pipeline['description']}\nVariables: {pipeline['variables']}\n"
        )


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


def help(parser, verbose):
    parser.print_help()


def _get_data(url, page_type, timeout):
    start_time = time.time()
    with console.status("Extracting data...") as status:
        while time.time() - start_time <= timeout:
            result = poll_extract(url, page_type)
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
