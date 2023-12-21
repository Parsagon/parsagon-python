from parsagon.api import edit_program_sketch, get_pipeline, get_pipeline_code_parts, update_pipeline
from parsagon.executor import Executor, custom_functions_to_descriptions
from parsagon.print import assistant_print
from rich.prompt import Confirm, Prompt


def edit_program(task, program_name, variables={}, verbose=False):
    pipeline = get_pipeline(program_name)
    pipeline_code_parts = get_pipeline_code_parts(pipeline["id"])
    custom_functions = {custom_function["call_id"]: custom_function["code"] for custom_function in pipeline_code_parts["custom_functions"]}
    program_sketches = edit_program_sketch(pipeline_code_parts["program_sketch"], task)
    full_program = program_sketches["full"]
    abridged_program = program_sketches["abridged"]
    pseudocode = program_sketches["pseudocode"]
    assistant_print(f"Edited the program to do the following:\n\n{pseudocode}\n")
    approval = Confirm.ask("Confirm the program does what you want")
    if not approval:
        feedback = Prompt.ask("What do you want the program to do differently?")
        return {"success": False, "outcome": "User canceled program editing", "user_feedback": feedback}

    assistant_print(f"Now executing the program to identify web elements to be scraped:")
    args = ", ".join(f"{k}={repr(v)}" for k, v in variables.items())
    abridged_program += f"\n\noutput = func({args})\n"  # Make the program runnable

    # Execute the abridged program to gather examples
    executor = Executor(task, function_bank=custom_functions)
    executor.execute(abridged_program)

    program_name_input = Prompt.ask(
        f'Type "{program_name}" to update this program, or press enter without typing a name to CANCEL',
        choices=[program_name, ""]
    )
    if not program_name_input:
        assistant_print("Discarded edits.")
        return {"success": False, "outcome": f"User decided not to save the edits"}

    pipeline_id = pipeline["id"]
    try:
        for call_id, custom_function in executor.custom_functions.items():
            debug_suffix = f" ({custom_function.name})"
            description = custom_functions_to_descriptions.get(custom_function.name)
            description = " to " + description if description else ""
            if verbose:
                description += debug_suffix
            assistant_print(f"  Saving function{description}...")
            add_examples_to_custom_function(pipeline_id, call_id, custom_function, True)
        assistant_print(f"Finalizing program...")
        update_pipeline(pipeline_id, {"program_sketch": full_program, "abridged_sketch": abridged_program, "pseudocode": pseudocode})
        assistant_print(f"Saved.")
    except Exception as e:
        error_message = "An error occurred while saving the program. The program was not updated."
        assistant_print(error_message)
        return {"success": False, "outcome": error_message}

    return {"success": True, "outcome": f"Program successfully edited", "program_name": program_name}
