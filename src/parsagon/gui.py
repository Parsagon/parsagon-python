import contextlib
import multiprocessing
import os
import sys
from pathlib import Path
from threading import Condition

from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot, QEventLoop, QSize
from PyQt6.QtGui import (
    QTextCursor,
    QMovie,
    QKeyEvent,
    QPalette,
    QColor,
    QFont,
    QPixmap,
    QIcon,
    QTextOption,
    QFontMetrics,
)
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QPushButton,
    QLineEdit,
    QWidget,
    QHBoxLayout,
    QTextEdit,
    QLabel,
    QProgressBar,
    QScrollArea,
    QSpacerItem,
    QSizePolicy,
    QFrame,
)
from PyQt6.QtCore import Qt

# Global variable that simply keeps the GUI window from being garbage collected
gui_window = None


message_padding_constant = 4
message_width_proportion = 0.85


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
        GUIController._instance = self
        try:
            self.callback(self)
        except Exception as e:
            if isinstance(e, (KeyboardInterrupt, SystemExit)):
                raise
            else:
                from parsagon.print import error_print

                error_print(str(e))
                error_print(
                    "Parsagon encountered an error.  Please restart the application to continue.  You may want to copy any messages above you want to save."
                )

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

        palette = self.palette()
        palette.setColor(self.backgroundRole(), Qt.GlobalColor.white)
        self.setPalette(palette)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 12)
        main_layout.setSpacing(10)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.message_container = QWidget()
        self.messages_layout = QVBoxLayout(self.message_container)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.message_container)

        # Add a vertical spacer to push messages to the top
        self.spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.messages_layout.addSpacerItem(self.spacer)
        main_layout.addWidget(self.scroll_area)

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

        input_wrapper_layout = QHBoxLayout()
        input_wrapper_layout.setContentsMargins(10, 0, 10, 0)

        input_border = QWidget()
        input_border.setContentsMargins(10, 2, 7, 2)
        input_border.setObjectName("inputBorder")
        input_border.setStyleSheet(
            """#inputBorder {
            border: 1px solid #CBCED2;
            border-radius: 14px;
        }
        QWidget {
            border: none;
        }
        """
        )
        input_wrapper_layout.addWidget(input_border)
        input_layout = QHBoxLayout(input_border)
        input_layout.setContentsMargins(0, 0, 0, 0)

        self.user_input_edit = CustomTextEdit(self.on_user_input, self)
        self.user_input_edit.setFont(QFont("Menlo", 15))
        self.user_input_edit.setFixedHeight(43)
        input_layout.addWidget(self.user_input_edit, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.user_input_edit.setEnabled(True)
        self.user_input_edit.setVisible(True)

        from parsagon.settings import get_resource_path

        pixmap = QPixmap(str(get_resource_path() / "send@2x.png"))
        pixmap.setDevicePixelRatio(2.0)
        icon = QIcon(pixmap)
        self.send_button = QPushButton("", self)
        self.send_button.setIcon(icon)
        self.send_button.setIconSize(QSize(33, 33))
        self.send_button.clicked.connect(self.on_user_input)
        input_layout.addWidget(self.send_button, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.loading_spinner = QLabel(self)
        self.loading_spinner.setAlignment(Qt.AlignmentFlag.AlignCenter)

        spinner_movie = QMovie(str(get_resource_path() / "loading.gif"))
        spinner_movie.setScaledSize(QSize(33, 33))
        spinner_movie.currentPixmap().setDevicePixelRatio(2.0)
        self.loading_spinner.setMovie(spinner_movie)
        self.loading_spinner.setFixedHeight(33)
        spinner_movie.start()
        self.loading_spinner.setVisible(False)  # Initially hidden
        input_layout.addWidget(self.loading_spinner, alignment=Qt.AlignmentFlag.AlignVCenter)

        main_layout.addLayout(input_wrapper_layout)
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
        self.show()

        self.controller.start()

    def on_user_input(self):
        user_input = self.user_input_edit.toPlainText()
        if user_input:  # Add non-empty input to the message list
            self.update_text_ui(user_input, "user")  # Display user input in blue for distinction
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

        message_edit = QTextEdit(self)
        message_edit.setFont(QFont("Menlo", 13))
        message_edit.insertHtml(text)

        # message_edit.setFixedWidth(int(self.scroll_area.width() * message_width_proportion))
        message_edit.setReadOnly(True)
        # message_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        message_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        message_edit.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        message_edit.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        message_edit.show()
        self.messages_layout.addWidget(message_edit, alignment=Qt.AlignmentFlag.AlignTop)
        message_edit.show()
        message_edit.setFixedHeight(int(message_edit.document().size().height()) + message_padding_constant)

        # Update the spacer
        self.messages_layout.removeItem(self.spacer)
        self.messages_layout.addSpacerItem(self.spacer)

        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())

    @pyqtSlot()
    def focus_input(self):
        self.user_input_edit.setFocus()

    @pyqtSlot(object, QEventLoop, ResultContainer)
    def execute_callback(self, callback, loop, result_container):
        result_container.value = callback()  # Store the result of the callback
        loop.quit()  # Exit the event loop to unblock the background thread


def gui_assist(global_gui):
    from parsagon.assistant import assist
    from parsagon.gui import GUIController

    GUIController._instance = global_gui
    from parsagon.settings import get_api_key

    _ = get_api_key(interactive=True)
    assist(True)


def run_gui(verbose=False):
    global gui_window
    app = QApplication(sys.argv)
    gui_window_ = GUI(gui_assist)
    gui_window = gui_window_
    return app.exec()


if __name__ == "__main__":
    # Pyinstaller fix
    multiprocessing.freeze_support()

    # Environment variables for development
    os.environ["API_BASE"] = "https://parsagon.dev"
    os.environ[
        "SSL_CERT_FILE"
    ] = "/Users/gabemontague/Dropbox/Mac/Documents/Documents/Projects/parsagon/code/ps-scraper-web/certs/dev-parsagon.dev.pem"

    sys.exit(run_gui(verbose=True))
