import os
from datetime import datetime
from threading import Condition

from PyQt6.QtCore import Qt
from PyQt6.QtCore import pyqtSlot, QSize, QTimer
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

from parsagon.gui.controller import GUIController
from parsagon.gui.menu import MenuManager
from parsagon.settings import get_graphic

message_padding_constant = 0
message_width_proportion = 0.85
is_windows = os.name == "nt"
font_size_messages = 13 if not is_windows else 10
font_size_input = 15 if not is_windows else 11


try:
    from ctypes import windll

    app_id = "parsagon.parsagon.gui.1"
    windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
except ImportError:
    pass


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

        self.menu_manager = MenuManager(self)
        self.menu_manager.make_menu()

        # Signals
        self.controller = GUIController(self.condition)
        self.controller.set_loading_signal.connect(self.set_loading)
        self.controller.show_progress_signal.connect(self.show_progress)
        self.controller.set_progress_title_signal.connect(self.set_progress_title)
        self.controller.set_progress_signal.connect(self.set_progress)
        self.controller.update_text_signal.connect(self.update_text_ui)
        self.controller.request_input_signal.connect(self.focus_input)
        self.show()

        # Start the assist function after a delay to prevent layout blip upon opening
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

    @pyqtSlot()
    def focus_input(self):
        self.user_input_edit.setFocus()

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
