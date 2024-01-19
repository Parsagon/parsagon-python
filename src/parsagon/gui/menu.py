import os
import webbrowser
from datetime import datetime

from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import QApplication, QTextEdit, QMessageBox


docs_url = "https://parsagon.io/docs/pipelines/overview"
is_windows = os.name == "nt"


class MenuManager:
    def __init__(self, window):
        self.window = window

    def make_menu(self):
        window = self.window
        menu_bar = window.menuBar()

        # APP NAME / FILE
        app_menu = menu_bar.addMenu("File" if is_windows else "&Parsagon")

        about_action = QAction("About", window)
        app_menu.addAction(about_action)
        about_action.triggered.connect(self.show_about_dialog)

        # EDIT
        edit_menu = menu_bar.addMenu("&Edit")

        # Undo action
        undo_action = QAction("&Undo", window, shortcut=QKeySequence.StandardKey.Undo)
        undo_action.triggered.connect(self.undo)
        edit_menu.addAction(undo_action)

        # Redo action
        redo_action = QAction("&Redo", window, shortcut=QKeySequence.StandardKey.Redo)
        redo_action.triggered.connect(self.redo)
        edit_menu.addAction(redo_action)

        edit_menu.addSeparator()

        # Cut action
        cut_action = QAction("Cu&t", window, shortcut=QKeySequence.StandardKey.Cut)
        cut_action.triggered.connect(self.cut_text)
        edit_menu.addAction(cut_action)

        # Copy action
        copy_action = QAction("&Copy", window, shortcut=QKeySequence.StandardKey.Copy)
        copy_action.triggered.connect(self.copy_text)
        edit_menu.addAction(copy_action)

        # Paste action
        paste_action = QAction("&Paste", window, shortcut=QKeySequence.StandardKey.Paste)
        paste_action.triggered.connect(self.paste_text)
        edit_menu.addAction(paste_action)

        # Select all action
        select_all_action = QAction("Select &All", window, shortcut=QKeySequence.StandardKey.SelectAll)
        select_all_action.triggered.connect(self.select_all_text)
        edit_menu.addAction(select_all_action)

        # HELP
        help_menu = menu_bar.addMenu("&Help")

        documentation_action = QAction("Help", window)
        documentation_action.triggered.connect(self.show_documentation)
        help_menu.addAction(documentation_action)

    def cut_text(self):
        focused_widget = QApplication.focusWidget()
        if isinstance(focused_widget, QTextEdit):
            focused_widget.cut()

    def copy_text(self):
        focused_widget = QApplication.focusWidget()
        if isinstance(focused_widget, QTextEdit):
            focused_widget.copy()

    def paste_text(self):
        focused_widget = QApplication.focusWidget()
        if isinstance(focused_widget, QTextEdit):
            focused_widget.paste()

    def undo(self):
        focused_widget = QApplication.focusWidget()
        if isinstance(focused_widget, QTextEdit):
            focused_widget.undo()

    def redo(self):
        focused_widget = QApplication.focusWidget()
        if isinstance(focused_widget, QTextEdit):
            focused_widget.redo()

    def select_all_text(self):
        focused_widget = QApplication.focusWidget()
        if isinstance(focused_widget, QTextEdit):
            focused_widget.selectAll()

    def show_about_dialog(self):
        version = os.environ.get("VERSION", "unknown")
        year = datetime.now().year
        message = f"""
        Version {version}<br>
        Copyright © {year} Parsagon, Inc.
        """

        # Title appears to be broken
        box = QMessageBox()
        box.about(self.window, "", message)
        box.setWindowTitle("About Parsagon")

    def show_documentation(self):
        webbrowser.open(docs_url)
