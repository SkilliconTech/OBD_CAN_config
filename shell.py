from PySide6.QtCore import Qt, QPointF, QSize, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QStackedWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton,
)

from home_page import HomePage

def make_home_icon(color="#18262B", size=18):
    scale = 4
    px = size * scale
    pm = QPixmap(px, px)
    pm.fill(Qt.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(1.6 * scale)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    # roof
    p.drawPolyline([QPointF(px * 0.12, px * 0.50),
                    QPointF(px * 0.50, px * 0.16),
                    QPointF(px * 0.88, px * 0.50)])
    # walls and floor
    p.drawPolyline([QPointF(px * 0.22, px * 0.44),
                    QPointF(px * 0.22, px * 0.84),
                    QPointF(px * 0.78, px * 0.84),
                    QPointF(px * 0.78, px * 0.44)])
    # door
    p.drawPolyline([QPointF(px * 0.42, px * 0.84),
                    QPointF(px * 0.42, px * 0.58),
                    QPointF(px * 0.58, px * 0.58),
                    QPointF(px * 0.58, px * 0.84)])
    p.end()
    return QIcon(pm)
class ToolHost(QWidget):
    """Holds one embedded tool. The tool has its own Home button."""

    def __init__(self, tool, parent=None):
        super().__init__(parent)
        self.tool = tool

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(tool)

class AppShell(QMainWindow):
    """Main window: Home page + the two tools, switched with a stack."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Configuration Tools")
        self.resize(1400, 950)

        self.obd_host = None
        self.can_host = None

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.home = HomePage()
        self.home.obd_requested.connect(self.open_obd)
        self.home.can_requested.connect(self.open_can)
        self.stack.addWidget(self.home)

    # Each tool is created the first time its button is clicked, then kept
    # alive, so going Home and back does not lose what was typed.
    def open_obd(self):
        if self.obd_host is None:
            from obd_tool.views.obd_main_window import ObdMainWindow
            self.obd_host = self._add_host(ObdMainWindow())
        self.setWindowTitle("OBD Config")
        self.stack.setCurrentWidget(self.obd_host)

    def open_can(self):
        if self.can_host is None:
            from can_tool.views.main_window import ConfigurationTool
            self.can_host = self._add_host(ConfigurationTool())
        self.setWindowTitle("CAN Config")
        self.stack.setCurrentWidget(self.can_host)

    def _add_host(self, tool):
        host = ToolHost(tool)
        host.tool.home_requested.connect(self.go_home)
        self.stack.addWidget(host)
        return host

    def go_home(self):
        self.setWindowTitle("Configuration Tools")
        self.stack.setCurrentWidget(self.home)

    def closeEvent(self, event):
        # The CAN tool asks "Save your changes?" in its own closeEvent,
        # which Qt does not call for an embedded window, so ask it here.
        if self.can_host is not None:
            if not self.can_host.tool._confirm_discard_changes():
                event.ignore()
                return
        event.accept()
