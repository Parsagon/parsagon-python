import json
from parsagon.api import send_assistant_message, send_assistant_function_outputs
from parsagon.create import create_program
from parsagon.executor import Executor
from parsagon.print import assistant_print, assistant_spinner, browser_print, error_print
from rich.prompt import Prompt


def assist(task, headless, infer):
    with assistant_spinner():
        response = send_assistant_message(task)
    while True:
        if not response["success"]:
            error_print("The OpenAI API is currently experiencing difficulties. You can try again later, or you can run `parsagon create --no_assistant` to use Parsagon without assistance from GPT.")
            return
        for message in response["messages"]:
            if message["role"] != "assistant":
                continue
            for content in message["content"]:
                assistant_print(content["text"]["value"])
        if response["status"] == "completed":
            reply = Prompt.ask("Reply or type Q to end")
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
                    html = investigate_page(**args)
                    output["output"] = html
                    outputs.append(output)
                elif name == "create_program":
                    result = create_program(args["description"], headless=headless, infer=infer)
                    output["output"] = json.dumps(result)
                    outputs.append(output)
            with assistant_spinner():
                response = send_assistant_function_outputs(outputs, response["thread_id"], response["run_id"])
        else:
            print("An error occurred")
            break


def investigate_page(url):
    browser_print(f"Checking what {url} looks like...")
    executor = Executor()
    executor.goto(url)
    html = executor.get_visible_html()
    executor.quit()
    return html
