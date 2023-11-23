import argparse
import datetime
import json
import logging
import logging.config
import psutil
import time
import traceback

from rich.console import Console
from rich.progress import Progress
from rich.prompt import Prompt

from parsagon.api import (
    get_program_sketches,
    create_pipeline,
    delete_pipeline,
    add_examples_to_custom_function,
    create_pipeline_run,
    update_pipeline_run,
    get_pipeline,
    get_pipelines,
    get_pipeline_code,
    get_run,
    poll_data,
)
from parsagon.assistant import assist
from parsagon.create import create_program
from parsagon.exceptions import ParsagonException, RunFailedException
from parsagon.executor import Executor, custom_functions_to_descriptions
from parsagon.settings import get_api_key, get_settings, clear_settings, save_setting, get_logging_config

console = Console()
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
        "--headless",
        action="store_true",
        help="run the browser in headless mode",
    )
    parser_create.add_argument(
        "--infer",
        action="store_true",
        help="let Parsagon infer all elements to be scraped",
    )
    parser_create.add_argument(
        "--no_assistant",
        action="store_true",
        help="disable the Parsagon assistant",
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
    parser_run.add_argument(
        "--output_log",
        action="store_true",
        help="output log data from the run",
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


def create(headless=False, infer=False, no_assistant=False, verbose=False):
    task = Prompt.ask("Type what do you want to do")
    if no_assistant:
        create_program(task, headless=headless, infer=infer)
    else:
        assist(task, headless=headless, infer=infer)


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


def run(program_name, variables={}, headless=False, remote=False, output_log=False, verbose=False):
    """
    Executes pipeline code
    """
    if headless and remote:
        raise ParsagonException("Cannot run a program remotely in headless mode")

    logger.info("Preparing to run program %s", program_name)
    pipeline_id = get_pipeline(program_name)["id"]

    if remote:
        result = create_pipeline_run(pipeline_id, variables, False)
        with console.status("Program running remotely...") as status:
            while True:
                run = get_run(result["id"])
                status = run["status"]

                if output_log and status in ("FINISHED", "ERROR"):
                    return {k: v for k, v in run.items() if k in ("output", "status", "log", "warnings", "error")}

                if status == "FINISHED":
                    if verbose:
                        logger.info(run["log"])
                        for warning in run["warnings"]:
                            logger.warning(warning)
                    logger.info("Program finished running.")
                    return run["output"]
                elif status == "ERROR":
                    raise ParsagonException(f"Program failed to run: {run['error']}")
                elif status == "CANCELED":
                    raise ParsagonException("Program execution was canceled")

                time.sleep(5)

    run = create_pipeline_run(pipeline_id, variables, True)
    code = get_pipeline_code(program_name, variables, headless)["code"]
    start_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
    run_data = {"start_time": start_time}

    logger.info("Running program...")
    globals_locals = {"PARSAGON_API_KEY": get_api_key()}
    try:
        exec(code, globals_locals, globals_locals)
        run_data["status"] = "FINISHED"
    except:
        run_data["status"] = "ERROR"
        run_data["error"] = str(traceback.format_exc())
        if not output_log:
            raise
    finally:
        end_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
        run_data["end_time"] = end_time
        if "driver" in globals_locals:
            globals_locals["driver"].quit()
        if "display" in globals_locals:
            globals_locals["display"].stop()
        if "parsagon_log" in globals_locals:
            run_data["log"] = "\n".join(globals_locals["parsagon_log"])
            logger.info(run_data["log"])
        if "parsagon_warnings" in globals_locals:
            run_data["warnings"] = globals_locals["parsagon_warnings"]
        for proc in psutil.process_iter():
            try:
                if proc.name() == "chromedriver":
                    proc.kill()
            except psutil.NoSuchProcess:
                continue
        run = update_pipeline_run(run["id"], run_data)
    logger.info("Done.")
    if output_log:
        if "error" not in run_data:
            run["output"] = globals_locals["output"]
        return {k: v for k, v in run.items() if k in ("output", "status", "log", "warnings", "error")}
    return globals_locals["output"]


def batch_runs(batch_name, program_name, runs, headless=False, ignore_errors=False, error_value=None, rerun_warnings=False, rerun_warning_types=[], rerun_errors=False, verbose=False):
    save_file = f"{batch_name}.json"
    try:
        with open(save_file) as f:
            outputs = json.load(f)
    except FileNotFoundError:
        outputs = []
    metadata_file = f"{batch_name}_metadata.json"
    try:
        with open(metadata_file) as f:
            metadata = json.load(f)
    except FileNotFoundError:
        metadata = []

    num_initial_results = len(outputs)
    error = None
    variables = None
    try:
        default_desc = f'Running program "{program_name}"'
        with Progress() as progress:
            task = progress.add_task(default_desc, total=len(runs))
            for i, variables in progress.track(enumerate(runs), task_id=task):
                if i < num_initial_results:
                    if rerun_errors and metadata[i]["status"] == "ERROR":
                        pass
                    elif rerun_warnings and metadata[i]["warnings"]:
                        if not rerun_warning_types or any(warning["type"] in rerun_warning_types for warning in metadata[i]["warnings"]):
                            pass
                        else:
                            continue
                    else:
                        continue
                for j in range(3):
                    result = run(program_name, variables, headless, output_log=True)
                    if result["status"] != "ERROR":
                        output = result.pop("output")
                        if i < num_initial_results:
                            outputs[i] = output
                            metadata[i] = result
                        else:
                            outputs.append(output)
                            metadata.append(result)
                        break
                    else:
                        error = result["error"].strip().split("\n")[-1]
                        if j < 2:
                            progress.update(task, description=f"An error occurred: {error} - Waiting 60s before retrying (Attempt {j+2}/3)")
                            time.sleep(60)
                            progress.update(task, description=default_desc)
                            error = None
                            continue
                        else:
                            if ignore_errors:
                                error = None
                                if i < num_initial_results:
                                    outputs[i] = error_value
                                else:
                                    outputs.append(error_value)
                                break
                            else:
                                raise RunFailedException
    except RunFailedException:
        pass
    except Exception as e:
        error = repr(e)
    finally:
        configure_logging(verbose)
        if error:
            logger.error(f"Unresolvable error occurred on run with variables {variables}: {error} - Data has been saved to {save_file}. Rerun your command to resume.")
        with open(save_file, "w") as f:
            json.dump(outputs, f)
        with open(metadata_file, "w") as f:
            json.dump(metadata, f)
    num_warnings = 0
    num_runs_with_warnings = 0
    for m in metadata:
        if m["warnings"]:
            num_warnings += len(m["warnings"])
            num_runs_with_warnings += 1
    logger.info(f"\nSummary: {len(outputs)} runs made; {num_warnings} warnings encountered across {num_runs_with_warnings} runs. See {metadata_file} for logs.\n")
    return None if error else outputs


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
    with console.status("Extracting data...") as status:
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
