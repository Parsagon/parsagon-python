import logging
from parsagon.api import get_program_sketches, create_pipeline, create_custom_function, delete_pipeline
from parsagon.exceptions import APIException
from parsagon.executor import Executor, custom_functions_to_descriptions
from parsagon.secrets import extract_secrets

logger = logging.getLogger(__name__)


def create_program(task, program_name=None, headless=False, infer=False):
    logger.info("Creating a program based on your specifications...")
    task, secrets = extract_secrets(task)
    program_sketches = get_program_sketches(task)

    full_program = program_sketches["full"]
    abridged_program = program_sketches["abridged"]
    pseudocode = program_sketches["pseudocode"]
    logger.info(f"Here's what the program does:\n\n{pseudocode}\n\n")
    while True:
        approval = input("Confirm the program does what you want (Y/n): ")
        if approval.strip() == "Y":
            break
        if approval.strip() == "n":
            feedback = input("What do you want the program to do differently? ")
            return {"success": False, "outcome": "User canceled program creation", "user_feedback": feedback}

    logger.info(f"Now executing the program to identify web elements to be scraped:\n")
    args = ", ".join(f"{k}={repr(v)}" for k, v in secrets.items())
    abridged_program += f"\n\noutput = func({args})" + "\nprint(f'Program finished and returned a value of:\\n{output}\\n')\n"  # Make the program runnable

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
                pipeline = create_pipeline(program_name, task, full_program, pseudocode, secrets)
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
                    description = custom_functions_to_descriptions.get(custom_function.name)
                    description = " to " + description if description else ""
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
            return {"success": False, "outcome": f"User decided not to save the program"}

    logger.info("Done.")
    return {"success": True, "outcome": f"Program successfully saved with name {program_name}", "program_name": program_name}
