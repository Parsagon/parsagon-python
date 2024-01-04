from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich.progress import Progress as RichProgress

gui_enabled = False
if gui_enabled:
    from parsagon.gui import GUIController
console = Console()


# === Printing ===
def normal_print(text):
    if not gui_enabled:
        console.print(text)
    else:
        GUIController.shared().print(text)


def assistant_print(text):
    if not gui_enabled:
        console.print(Panel(text, style="blue"))
    else:
        GUIController.shared().print(text, "white", "blue")


def browser_print(text):
    if not gui_enabled:
        console.print(text, style="green")
    else:
        GUIController.shared().print(text, "green")


def error_print(text):
    if not gui_enabled:
        console.print(text, style="red")
    else:
        GUIController.shared().print(text, "red")


# === Input, prompting ===
def ask(prompt):
    if not gui_enabled:
        return Prompt.ask(prompt)
    else:
        return GUIController.shared().input(prompt + ":")


original_input = input


def input(prompt):
    if not gui_enabled:
        return original_input(prompt)
    else:
        return GUIController.shared().input(prompt)


def confirm(prompt):
    if not gui_enabled:
        return Confirm.ask(prompt)
    else:
        return GUIController.shared().input(prompt + " (y/n):") == "y"


# === Status, loading ===
def assistant_spinner(text=""):
    if not gui_enabled:
        return console.status(Text(text, style="blue"))
    else:
        return GUIController.shared().spinner()  # text argument


def status(text):
    if not gui_enabled:
        return console.status(text)
    else:
        return GUIController.shared().spinner()  # text argument


class Progress:
    def __init__(self):
        if not gui_enabled:
            self.rich_progress = RichProgress()

    def track(self, iterable, description="Working...", task_id=None):
        if not gui_enabled:
            return self.rich_progress.track(iterable, description=description, task_id=task_id)
        else:

            def gui_generator():
                gui_controller = GUIController.shared()
                gui_controller.show_progress(True, description)
                gui_controller.progress_total = len(iterable)
                for i, item in enumerate(iterable):
                    yield item
                    GUIController.shared().set_progress(i)
                gui_controller.show_progress(False)

            return gui_generator()

    def add_task(self, description, total):
        if not gui_enabled:
            return self.rich_progress.add_task(description, total=total)
        else:
            gui_controller = GUIController.shared()
            gui_controller.show_progress(True, description)
            gui_controller.progress_total = total

    def update(self, task_id, description):
        if not gui_enabled:
            self.rich_progress.update(task_id, description=description)
        else:
            gui_controller = GUIController.shared()
            gui_controller.show_progress(False)
            gui_controller.print(description)

    def __enter__(self):
        if not gui_enabled:
            return self.rich_progress.__enter__()
        else:
            return self

    def __exit__(self, exc_type, exc_value, traceback):
        # Cleanup code, like closing files or releasing resources
        if not gui_enabled:
            # Assuming RichProgress needs some kind of finalization
            self.rich_progress.__exit__(exc_type, exc_value, traceback)
        else:
            gui_controller = GUIController.shared()
            gui_controller.show_progress(False)
