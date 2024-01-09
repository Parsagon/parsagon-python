import contextlib
import os

from PyQt6.QtCore import QThread, pyqtSignal

from parsagon.exceptions import APIException
from parsagon.settings import get_save_api_key_interactive


class GUIController(QThread):
    """
    The GUI controller is a background thread that runs the CLI if the GUI is enabled.  It then delegates all interaction between the CLI code and the GUI.  It is designed as a singleton so that references to the controller don't have to be passed around.
    """

    _instance = None

    update_text_signal = pyqtSignal(str, str, str)  # Include text color
    request_input_signal = pyqtSignal()
    set_loading_signal = pyqtSignal(bool)
    show_progress_signal = pyqtSignal(bool)
    set_progress_title_signal = pyqtSignal(str)
    set_progress_signal = pyqtSignal(int)

    @classmethod
    def shared(cls):
        if cls._instance is None:
            raise RuntimeError("GUIController has not been initialized")
        return cls._instance

    def __init__(self, condition, parent=None):
        super().__init__(parent)
        self.timer = None
        self.condition = condition
        self.current_input = None
        self.progress_total = None
        assert self.__class__._instance is None, "GUIController is a singleton"
        self.__class__._instance = self

    def run(self):
        self.__class__._instance._instance = self
        while True:
            retry = False
            try:
                from parsagon.assistant import assist
                from parsagon.settings import get_graphic, get_api_key

                _ = get_api_key(interactive=True)
                assist(True)
            except Exception as e:
                if isinstance(e, (KeyboardInterrupt, SystemExit)):
                    raise
                else:
                    from parsagon.print import error_print

                    error_print(str(e))
                    error_print(
                        "Parsagon encountered an error.  Please restart the application to continue.  You may want to copy any messages above you want to save."
                    )

                    if isinstance(e, APIException) and e.status_code == 401:
                        get_save_api_key_interactive()
                        retry = True
            if not retry:
                break

    def input(self, prompt):
        if prompt:
            self.print(prompt)
        self.request_input_signal.emit()
        with self.condition:
            self.condition.wait()
            return self.current_input

    def print(self, text, color="black", background="#CBCED2"):
        html = text.replace("\n", "<br>")
        self.update_text_signal.emit(html, color, background)

    @contextlib.contextmanager
    def spinner(self):
        self.set_loading_signal.emit(True)  # Show spinner
        try:
            yield
        finally:
            self.set_loading_signal.emit(False)  # Hide spinner

    def show_progress(self, show_progress, text=""):
        self.show_progress_signal.emit(show_progress)
        if show_progress:
            self.set_progress_title_signal.emit(text)

    def set_progress(self, progress_iteration_num):
        self.set_progress_signal.emit(int(progress_iteration_num / self.progress_total * 100))
