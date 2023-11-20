import datetime
import datetime
import json
import logging.config
import time
import traceback

import psutil
from rich.console import Console
from rich.progress import Progress
from rich.prompt import Prompt

from parsagon.api import (
    create_pipeline_run,
    update_pipeline_run,
    get_pipeline,
    get_pipeline_code,
    get_run,
)
from parsagon.exceptions import ParsagonException, RunFailedException
from parsagon.settings import get_api_key

console = Console()
logger = logging.getLogger(__name__)


def run_with_file_output(*args, **kwargs):
    dump_path = Prompt.ask("Please enter a path/filename to save the output (in JSON format)")
    if not dump_path.endswith(".json"):
        dump_path += ".json"
    result = run(*args, **kwargs)
    with open(dump_path, "w") as f:
        json.dump(result, f, indent=4)
    print(f"Output saved to {dump_path}")
    return result


def run(program_name, variables={}, headless=False, remote=False, output_log=False, verbose=False):
    """
    Executes pipeline code
    """
    if headless and remote:
        raise ParsagonException("Cannot run a program remotely in headless mode")

    if not isinstance(variables, dict):
        raise ParsagonException("Variables must be a dictionary")

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


def batch_runs(
    batch_name,
    program_name,
    runs,
    headless=False,
    ignore_errors=False,
    error_value=None,
    rerun_warnings=False,
    rerun_warning_types=[],
    rerun_errors=False,
    verbose=False,
):
    # Validate runs
    if not all(isinstance(run_, dict) for run_ in runs):
        raise ParsagonException("Runs must be a list of dictionaries")

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
                        if not rerun_warning_types or any(
                            warning["type"] in rerun_warning_types for warning in metadata[i]["warnings"]
                        ):
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
                            progress.update(
                                task,
                                description=f"An error occurred: {error} - Waiting 60s before retrying (Attempt {j+2}/3)",
                            )
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
        if error:
            logger.error(
                f"Unresolvable error occurred on run with variables {variables}: {error} - Data has been saved to {save_file}. Rerun your command to resume."
            )
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
    logger.info(
        f"\nSummary: {len(outputs)} runs made; {num_warnings} warnings encountered across {num_runs_with_warnings} runs. See {metadata_file} for logs.\n"
    )
    return None if error else outputs
