from PySide6.QtCore import Qt, QPointF, QSize
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QPushButton

from obd_tool.resources.theme import LIGHT, RADIUS_SM


def make_home_icon(color, size=20):
    scale = 4
    px = size * scale
    pm = QPixmap(px, px)
    pm.fill(Qt.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(1.7 * scale)
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


class HomeButton(QPushButton):
    """Square button with only a house icon. Connect to its clicked signal."""

    def __init__(self, parent=None):
        super().__init__(parent)
        c = LIGHT
        self.setObjectName("homeButton")
        self.setFixedSize(42, 42)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Home")
        self.setIconSize(QSize(20, 20))
        self.setIcon(make_home_icon(c["toggle_icon"]))
        self.setStyleSheet(f"""
            #homeButton {{ background-color: {c['bg_panel']};
                           border: 1px solid {c['border']};
                           border-radius: {RADIUS_SM}px; }}
            #homeButton:hover {{ border: 1px solid {c['accent_blue']}; }}
        """)