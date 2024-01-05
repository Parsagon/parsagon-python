import multiprocessing
import os

# Pyinstaller fix - must come as early as possible
multiprocessing.freeze_support()

# Set environment variables
# os.environ["API_BASE"] = "https://parsagon.dev"

from parsagon.gui import GUIWindow

import sys

from PyQt6.QtWidgets import QApplication

if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui_window = GUIWindow()
    sys.exit(app.exec())
