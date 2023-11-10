import json
from parsagon.api import send_assistant_message, send_assistant_function_outputs
from parsagon.create import create_program
from parsagon.executor import Executor


def assist():
    user_message = input("Type what do you want to do: ")
    response = send_assistant_message(user_message)
    while True:
        for message in response["messages"]:
            if message["role"] != "assistant":
                continue
            for content in message["content"]:
                print(content["text"]["value"])
        if response["status"] == "completed":
            reply = input("Reply or type Q to end: ")
            if reply.strip() == "Q":
                break
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
                    args["task"] = args.pop("description")
                    result = create_program(**args)
                    output["output"] = json.dumps(result)
                    outputs.append(output)
            response = send_assistant_function_outputs(outputs, response["thread_id"], response["run_id"])
        else:
            print("An error occurred")
            break


def investigate_page(url):
    print(f"Let me check what {url} looks like...")
    executor = Executor()
    executor.goto(url)
    html = executor.get_visible_html()
    executor.quit()
    return html
