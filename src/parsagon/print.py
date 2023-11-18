from rich.console import Console
from rich.panel import Panel
from rich.text import Text


console = Console()


def assistant_print(text):
    console.print(Panel(text, style="blue"))


def assistant_spinner(text=""):
    return console.status(Text(text, style="blue"))


def browser_print(text):
    console.print(text, style="green")


def error_print(text):
    console.print(text, style="red")
