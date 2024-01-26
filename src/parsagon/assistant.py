import json
from parsagon.api import send_assistant_message, send_assistant_function_outputs, schedule, delete_schedule
from parsagon.create import create_program
from parsagon.executor import Executor
from parsagon.print import assistant_print, assistant_spinner, browser_print, error_print, ask, input, ask_reply
from parsagon.runs import run, batch_runs


def assist(verbose=False):
    task = ask("Type what do you want to do")
    with assistant_spinner():
        response = send_assistant_message(task)
    while True:
        if not response["success"]:
            error_print(
                "The OpenAI API is currently experiencing difficulties. You can try again later, or you can run `parsagon create --no_assistant` to use Parsagon without assistance from GPT."
            )
            return
        for message in response["messages"]:
            if message["role"] != "assistant":
                continue
            for content in message["content"]:
                assistant_print(content["text"]["value"])
        if response["status"] == "completed":
            reply = ask_reply()
            if reply.strip() == "Q":
                break
            with assistant_spinner():
                response = send_assistant_message(reply, response["thread_id"])
        elif response["status"] == "requires_action":
            outputs = []
            for function_call in response["required_action"]:
                name = function_call["function"]["name"]
                args = json.loads(function_call["function"]["arguments"])
                output = {"tool_call_id": function_call["id"], "function_name": name}
                if name == "investigate_page":
                    html = get_page_html(**args)
                    output["output"] = html
                    outputs.append(output)
                elif name == "create_program":
                    result = create_program(args["description"])
                    output["output"] = json.dumps(result)
                    outputs.append(output)
                elif name == "run_program":
                    result = run(**args)
                    output["output"] = json.dumps(result)
                    outputs.append(output)
                elif name == "batch_runs":
                    batch_name = input("Please enter a name for the batch run (for saving of intermediate results): ")
                    result = batch_runs(batch_name, **args)
                    output["output"] = json.dumps(result)
                    outputs.append(output)
                elif name == "set_schedule":
                    result = schedule(**args)
                    output["output"] = json.dumps(result)
                    outputs.append(output)
                elif name == "clear_schedule":
                    delete_schedule(**args)
                    output["output"] = "Schedule cleared"
                    outputs.append(output)
            with assistant_spinner():
                response = send_assistant_function_outputs(outputs, response["thread_id"], response["run_id"])
        else:
            error_print("An error occurred")
            break


def get_page_html(url, headless=False, use_uc=False):
    browser_print(f"Checking what {url} looks like...")
    executor = Executor("", headless=headless, use_uc=use_uc)
    executor.goto(url)
    html = executor.get_visible_html()
    executor.quit()
    return html


def get_page_text(url, headless=False, use_uc=False):
    browser_print(f"Checking what {url} looks like...")
    executor = Executor("", headless=headless, use_uc=use_uc)
    executor.goto(url)
    text = executor.driver.execute_script("return document.body.innerText;")
    executor.quit()
    return text
