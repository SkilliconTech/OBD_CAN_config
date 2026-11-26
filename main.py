import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from obd_tool.resources.theme import FONT_FAMILY
from shell import AppShell


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont(FONT_FAMILY, 10))
    window = AppShell()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
