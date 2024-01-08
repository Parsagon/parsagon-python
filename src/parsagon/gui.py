import contextlib
import os
from threading import Condition

from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot, QEventLoop, QSize, QTimer
from PyQt6.QtCore import Qt
from PyQt6.QtGui import (
    QMovie,
    QKeyEvent,
    QFont,
    QPixmap,
    QIcon,
    QTextOption,
    QAction,
)
from PyQt6.QtWidgets import (
    QMainWindow,
    QVBoxLayout,
    QPushButton,
    QWidget,
    QHBoxLayout,
    QTextEdit,
    QLabel,
    QProgressBar,
    QScrollArea,
    QSpacerItem,
    QSizePolicy,
    QFrame,
    QMessageBox,
)

from parsagon.exceptions import APIException
from parsagon.settings import get_graphic, get_save_api_key_interactive

message_padding_constant = 0
message_width_proportion = 0.85
is_windows = os.name == "nt"
font_size_messages = 13 if not is_windows else 10
font_size_input = 15 if not is_windows else 11


class ResultContainer:
    def __init__(self):
        self.value = None


try:
    from ctypes import windll

    app_id = "parsagon.parsagon.gui.1"
    windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
except ImportError:
    pass


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


class GUIWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.condition = Condition()

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
        self.messages_layout.setContentsMargins(0, 10, 0, 10)
        self.messages_layout.setSpacing(0)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.message_container)

        # Add a vertical spacer to push messages to the top
        self.spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.messages_layout.addSpacerItem(self.spacer)
        main_layout.addWidget(self.scroll_area)

        # Progress
        self.progress_container = QWidget()
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
            """
            #inputBorder {
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
        self.user_input_edit.setFont(QFont("Menlo", font_size_input))
        self.user_input_edit.setFixedHeight(43)
        input_layout.addWidget(self.user_input_edit, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.user_input_edit.setEnabled(True)
        self.user_input_edit.setVisible(True)
        self.user_input_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        pixmap = QPixmap(get_graphic("send@2x.png"))
        pixmap.setDevicePixelRatio(2.0)
        send_icon = QIcon(pixmap)
        self.send_button = QPushButton("", self)
        self.send_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_button.setIcon(send_icon)
        self.send_button.setIconSize(QSize(33, 33))
        self.send_button.clicked.connect(self.on_user_input)
        input_layout.addWidget(self.send_button, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.loading_spinner = QLabel(self)
        self.loading_spinner.setAlignment(Qt.AlignmentFlag.AlignCenter)

        spinner_movie = QMovie(get_graphic("loading.gif"))
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

        # Create the menu bar
        menu_bar = self.menuBar()

        # Create a menu for the app name
        app_menu = menu_bar.addMenu("Parsagon")

        # Create an "About" action
        about_action = QAction("About", self)
        app_menu.addAction(about_action)
        about_action.triggered.connect(self.show_about_dialog)

        # Signals
        self.controller = GUIController(self.condition)
        self.controller.set_loading_signal.connect(self.set_loading)
        self.controller.show_progress_signal.connect(self.show_progress)
        self.controller.set_progress_title_signal.connect(self.set_progress_title)
        self.controller.set_progress_signal.connect(self.set_progress)
        self.controller.update_text_signal.connect(self.update_text_ui)
        self.controller.request_input_signal.connect(self.focus_input)
        self.controller.execute_on_main_thread_signal.connect(self.execute_callback)
        self.show()

        self.timer = QTimer.singleShot(500, self.delayed_setup)

    def delayed_setup(self):
        self.controller.start()

    def on_user_input(self):
        user_input = self.user_input_edit.toPlainText()
        if user_input:
            self.update_text_ui(user_input, "user")
        with self.condition:
            self.controller.current_input = user_input
            self.user_input_edit.clear()
            self.condition.notify()

    def show_about_dialog(self):
        version = os.environ.get("VERSION", "unknown")

        message = f"""
        Version {version}<br>
        Copyright © 2024 Parsagon
        """

        # Title appears to be broken
        box = QMessageBox()
        box.about(self, "", message)
        box.setWindowTitle("About Parsagon")

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
    def update_text_ui(self, text, text_color="user", background_color="#33B1FF"):
        text = text.replace("\n", "<br>")
        is_user = text_color == "user"
        if is_user:
            text_color = "white"
        align_right = is_user

        message_edit = QTextEdit(self)
        message_edit.setFont(QFont("Menlo", font_size_messages))
        message_edit.insertHtml(text)
        message_edit.setReadOnly(True)
        message_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        message_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        message_edit.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        message_edit.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        message_edit.setObjectName("message")
        message_edit.setStyleSheet(
            f"""
            #message {{
                border: none;
                background-color: transparent;
                color: {text_color}
            }}
        """
        )

        outer_callout_layout = QVBoxLayout()
        outer_callout_layout.setContentsMargins(0, 0, 0, 0)
        outer_callout_layout.setSpacing(0)

        callout = QFrame(self)
        callout.setObjectName("messageContainer")
        callout.setStyleSheet(
            f"""
            #messageContainer {{
                border-radius: 12px;
                background-color: {background_color};
            }}
        """
        )
        callout_tail = QLabel(self)
        path_suffix = "_user" if align_right else ""
        callout_arrow_path = get_graphic(f"callout_arrow{path_suffix}@2x.png")
        pixmap = QPixmap(callout_arrow_path)
        pixmap.setDevicePixelRatio(2.0)
        callout_tail.setPixmap(pixmap)
        callout_tail_width = pixmap.width() // 2
        padding_amount = 7
        callout_tail.setFixedSize(QSize(callout_tail_width + padding_amount, pixmap.height()))
        callout_tail.setObjectName("calloutTail")
        callout_tail.setAlignment(Qt.AlignmentFlag.AlignLeft if not align_right else Qt.AlignmentFlag.AlignRight)
        padding_side = "right" if align_right else "left"
        callout_tail.setStyleSheet(
            f"""
            #calloutTail {{
                padding-{padding_side}: {padding_amount}px;
            }}
        """
        )

        inner_callout_layout = QVBoxLayout(callout)
        inner_callout_layout.setContentsMargins(5, 5, 5, 5)
        inner_callout_layout.setSpacing(0)
        inner_callout_layout.addWidget(message_edit)

        outer_callout_layout.addWidget(callout)
        outer_callout_layout.addWidget(
            callout_tail, alignment=Qt.AlignmentFlag.AlignLeft if not align_right else Qt.AlignmentFlag.AlignRight
        )

        hbox = QHBoxLayout()
        hbox.setContentsMargins(10, 0, 10, 0)
        if align_right:
            hbox.addSpacerItem(QSpacerItem(35, 20, QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum))
            hbox.addLayout(outer_callout_layout)
        else:
            hbox.addLayout(outer_callout_layout)
            hbox.addSpacerItem(QSpacerItem(35, 20, QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum))

        self.messages_layout.addLayout(hbox)
        message_edit.show()
        inner_callout_layout.update()
        callout.show()
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
