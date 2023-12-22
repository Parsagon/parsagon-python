import contextlib
import sys
from pathlib import Path
from threading import Condition

from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot, QEventLoop, QSize
from PyQt6.QtGui import QTextCursor, QMovie, QKeyEvent
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QPushButton,
    QLineEdit,
    QWidget,
    QHBoxLayout,
    QTextEdit,
    QLabel, QProgressBar,
)
from PyQt6.QtCore import Qt


# Global variable that simply keeps the GUI window from being garbage collected
gui_window = None


class ResultContainer:
    def __init__(self):
        self.value = None


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
    execute_on_main_thread_signal = pyqtSignal(object, QEventLoop, ResultContainer)

    @classmethod
    def shared(cls):
        if cls._instance is None:
            raise RuntimeError("GUIController has not been initialized")
        return cls._instance

    def __init__(self, condition, callback, parent=None):
        super().__init__(parent)
        self.condition = condition
        self.current_input = None
        self.callback = callback
        self.progress_total = None
        assert self.__class__._instance is None, "GUIController is a singleton"
        self.__class__._instance = self

    def run(self):
        self.callback()

    def input(self, prompt):
        self.print(prompt)
        self.request_input_signal.emit()
        with self.condition:
            self.condition.wait()
            return self.current_input

    def print(self, text, color="black", background=None):
        self.update_text_signal.emit(text, color, background)

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

    def on_main_thread(self, callback):
        loop = QEventLoop()
        result_container = ResultContainer()
        self.execute_on_main_thread_signal.emit(callback, loop, result_container)
        loop.exec()  # Block until loop.quit() is called in the main thread
        return result_container.value  # Return the result stored in the container


class CustomTextEdit(QTextEdit):
    def __init__(self, on_user_input_callback, parent=None):
        super().__init__(parent)
        self.on_user_input_callback = on_user_input_callback
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Return:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.on_user_input_callback()  # Call the passed function
        else:
            super().keyPressEvent(event)


class GUI(QMainWindow):
    def __init__(self, background_thread_callback):
        super().__init__()
        self.condition = Condition()
        self.background_thread_callback = background_thread_callback

        self.setWindowTitle("Parsagon")
        self.setGeometry(100, 100, 400, 700)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        main_layout = QVBoxLayout()

        self.message_edit = QTextEdit(self)
        self.message_edit.setReadOnly(True)  # Make the text edit read-only
        main_layout.addWidget(self.message_edit)

        # Progress
        self.progress_container = QWidget()  # or QFrame()
        progress_layout = QVBoxLayout()
        self.progress_container.setLayout(progress_layout)
        self.progress_title = QLabel("Loading...", self)
        progress_layout.addWidget(self.progress_title)
        self.progress_bar = QProgressBar(self, minimum=0, maximum=100)
        progress_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.progress_container)
        self.progress_container.setVisible(False)

        input_layout = QHBoxLayout()

        self.user_input_edit = CustomTextEdit(self.on_user_input, self)
        self.user_input_edit.setFixedHeight(30)
        input_layout.addWidget(self.user_input_edit, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.user_input_edit.setEnabled(True)
        self.user_input_edit.setVisible(True)

        self.send_button = QPushButton("Send", self)
        self.send_button.clicked.connect(self.on_user_input)
        input_layout.addWidget(self.send_button, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.loading_spinner = QLabel(self)
        self.loading_spinner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spinner_movie = QMovie(str(Path(__file__).parent / "loading.gif"))
        spinner_movie.setScaledSize(QSize(30, 15))
        self.loading_spinner.setMovie(spinner_movie)
        self.loading_spinner.setFixedHeight(30)
        spinner_movie.start()
        self.loading_spinner.setVisible(False)  # Initially hidden
        input_layout.addWidget(self.loading_spinner, alignment=Qt.AlignmentFlag.AlignVCenter)

        main_layout.addLayout(input_layout)

        self.central_widget = QWidget()
        self.central_widget.setLayout(main_layout)
        self.setCentralWidget(self.central_widget)

        # Signals
        self.controller = GUIController(self.condition, self.background_thread_callback)
        self.controller.set_loading_signal.connect(self.set_loading)
        self.controller.show_progress_signal.connect(self.show_progress)
        self.controller.set_progress_title_signal.connect(self.set_progress_title)
        self.controller.set_progress_signal.connect(self.set_progress)
        self.controller.update_text_signal.connect(self.update_text_ui)
        self.controller.request_input_signal.connect(self.focus_input)
        self.controller.execute_on_main_thread_signal.connect(self.execute_callback)
        self.controller.start()

        self.show()

    def on_user_input(self):
        user_input = self.user_input_edit.toPlainText()
        if user_input:  # Add non-empty input to the message list
            self.update_text_ui(user_input, "black")  # Display user input in blue for distinction
        with self.condition:
            self.controller.current_input = user_input
            self.user_input_edit.clear()
            self.condition.notify()

    @pyqtSlot(bool)
    def set_loading(self, loading):
        self.send_button.setVisible(not loading)
        self.loading_spinner.setVisible(loading)

    @pyqtSlot(bool)
    def show_progress(self, show_progress):
        self.progress_container.setVisible(show_progress)

    @pyqtSlot(str)
    def set_progress_title(self, title):
        self.progress_title.setText(title)

    @pyqtSlot(int)
    def set_progress(self, progress):
        self.progress_bar.setValue(progress)

    @pyqtSlot(str, str, str)
    def update_text_ui(self, text, text_color="black", background_color=None):
        # Create HTML with block-level elements and inline CSS for text and background color
        style = f"color: {text_color};"
        if background_color:
            style += f" background-color: {background_color};"
        new_text = f'<div style="{style}">{text}</div><br>'  # Add <br> after closing </div>

        self.message_edit.moveCursor(QTextCursor.MoveOperation.End)
        self.message_edit.insertHtml(new_text)
        self.message_edit.moveCursor(QTextCursor.MoveOperation.End)

    @pyqtSlot()
    def focus_input(self):
        self.user_input_edit.setFocus()

    @pyqtSlot(object, QEventLoop, ResultContainer)
    def execute_callback(self, callback, loop, result_container):
        result_container.value = callback()  # Store the result of the callback
        loop.quit()  # Exit the event loop to unblock the background thread


def run_gui(verbose=False):
    global gui_window
    app = QApplication(sys.argv)
    from parsagon.assistant import assist

    try:
        gui_window_ = GUI(assist)
        gui_window = gui_window_
    except Exception as e:
        from parsagon.print import error_print
        error_print(str(e))
        sys.exit(1)
    sys.exit(app.exec())
