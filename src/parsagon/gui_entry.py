import multiprocessing
import os

# Pyinstaller fix - must come as early as possible, even above other imports.
multiprocessing.freeze_support()

# Set environment variables
import gui_env  # noqa

assert os.environ["GUI_ENABLED"] == "1", "GUI_ENABLED must be set to 1 in gui_env.py"
import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from parsagon.gui import GUIWindow
from parsagon.settings import get_graphic

is_windows = os.name == "nt"

if __name__ == "__main__":
    app = QApplication(sys.argv)
    if is_windows:
        app.setWindowIcon(QIcon(get_graphic("win_icon.ico")))
    gui_window = GUIWindow()
    sys.exit(app.exec())
