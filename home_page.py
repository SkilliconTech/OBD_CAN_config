from PySide6.QtCore import Qt, QPointF, QRectF, QSize, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QFont, QColor, QPainter, QPainterPath, QPen, QBrush, QLinearGradient,
    QRadialGradient, QDesktopServices,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox,
    QFrame, QGraphicsDropShadowEffect,
)

from obd_tool.resources.theme import LIGHT, DARK, RADIUS_SM, FONT_FAMILY
from obd_tool.resources.icons import make_theme_icon, logo_icon

COMPANY_URL = "https://skillicon.in/"


class PillButton(QPushButton):
    """Large pill-shaped button. primary=True is the filled teal one."""

    def __init__(self, text, primary, parent=None):
        super().__init__(f"{text}   \u2192", parent)
        self.primary = primary
        self.setObjectName("pillButton")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(250, 62)
        self.setFont(QFont(FONT_FAMILY, 13, QFont.DemiBold))

        if primary:
            glow = QGraphicsDropShadowEffect(self)
            glow.setBlurRadius(28)
            glow.setOffset(0, 8)
            glow.setColor(QColor(14, 119, 105, 90))
            self.setGraphicsEffect(glow)

    def set_colors(self, c, teal):
        if self.primary:
            self.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                                stop:0 #0E7769, stop:1 #15957F);
                    color: white; border: none; border-radius: 31px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                                stop:0 #0B665A, stop:1 #0F7F6C);
                }
                QPushButton:pressed { background-color: #095A50; }
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {c['bg_panel']};
                    color: {c['text_primary']};
                    border: 2px solid {c['btn_border']};
                    border-radius: 31px;
                }}
                QPushButton:hover {{
                    border: 2px solid {teal}; color: {teal};
                }}
                QPushButton:pressed {{ background-color: {c['btn_bg']}; }}
            """)
class HomePage(QWidget):
    """Home page: logo, title, short text and two buttons, one per tool."""

    obd_requested = Signal()
    can_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("homePage")
        self.dark_mode = False
        name = QLabel("SkillLogger")
        name.setFont(QFont(FONT_FAMILY, 40, QFont.Bold))
        name.setStyleSheet("color: #18262B;")

        self.obd_button = PillButton("OBD Config", primary=True)
        self.can_button = PillButton("CAN Config", primary=False)
        self.obd_button.clicked.connect(self.obd_requested)
        self.can_button.clicked.connect(self.can_requested)

        buttons = QHBoxLayout()
        buttons.setSpacing(18)
        buttons.addWidget(self.obd_button)
        buttons.addWidget(self.can_button)
        buttons.addStretch(1)

        self.name_label = name

        # ---- top right: help, theme, company logo ----
        self.help_button = QPushButton("?")
        self.help_button.setObjectName("helpButton")
        self.help_button.setFixedSize(42, 42)
        self.help_button.setFont(QFont(FONT_FAMILY, 16, QFont.Bold))
        self.help_button.setCursor(Qt.PointingHandCursor)
        self.help_button.setToolTip("Help")
        self.help_button.clicked.connect(self.on_help)

        self.theme_toggle = QPushButton()
        self.theme_toggle.setObjectName("themeToggle")
        self.theme_toggle.setFixedSize(42, 42)
        self.theme_toggle.setCursor(Qt.PointingHandCursor)
        self.theme_toggle.setIconSize(QSize(18, 18))
        self.theme_toggle.clicked.connect(self.toggle_theme)

        self.brand_btn = QPushButton()
        self.brand_btn.setObjectName("brandButton")
        self.brand_btn.setCursor(Qt.PointingHandCursor)
        self.brand_btn.setFlat(True)
        self.brand_btn.setIcon(logo_icon())
        self.brand_btn.setIconSize(QSize(184, 34))
        self.brand_btn.setToolTip("Visit skillicon.in")
        self.brand_btn.setStyleSheet("""
            #brandButton { background-color: transparent; border: none;
                           padding: 6px 12px; }
            #brandButton:hover, #brandButton:pressed {
                background-color: transparent; border: none; }
        """)
        self.brand_btn.clicked.connect(self.on_logo_clicked)

        topbar = QHBoxLayout()
        topbar.addStretch(1)
        topbar.addWidget(self.help_button)
        topbar.addSpacing(3)
        topbar.addWidget(self.theme_toggle)
        topbar.addSpacing(4)
        topbar.addWidget(self.brand_btn)

        layout = QVBoxLayout(self)
        name.setFont(QFont(FONT_FAMILY, 54, QFont.Bold))

        self.accent = QFrame()
        self.accent.setFixedSize(64, 5)

        layout.setContentsMargins(90, 24, 32, 40)
        layout.addLayout(topbar)
        layout.addStretch(3)
        layout.addWidget(name, 0, Qt.AlignLeft)
        layout.addSpacing(14)
        layout.addWidget(self.accent, 0, Qt.AlignLeft)
        layout.addSpacing(48)
        layout.addLayout(buttons)
        layout.addStretch(4)

        # animation for the signal lines on the right
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)

        self.apply_theme()

    # ECUs on the animated CAN bus (right side of the page)
    _NODES = ("ECM", "ABS", "TCM", "BCM", "LOGGER")

    # one packet at a time, in this order: (from node, to node)
    # node numbers follow _NODES: 0=ECM 1=ABS 2=TCM 3=BCM 4=LOGGER
    _ROUTES = (
        (0, 4),
        (2, 1),
        (3, 4),
        (1, 0),
        (4, 2),
    )
    _TRAVEL = 2.2     # seconds a packet takes to travel
    _PAUSE = 0.6      # short rest after it arrives, before the next one starts

    @staticmethod
    def _path_length(pts):
        return sum(
            ((pts[k + 1].x() - pts[k].x()) ** 2 +
             (pts[k + 1].y() - pts[k].y()) ** 2) ** 0.5
            for k in range(len(pts) - 1)
        )

    @staticmethod
    def _point_along(pts, dist):
        if dist < 0:
            return None
        for k in range(len(pts) - 1):
            a, b = pts[k], pts[k + 1]
            seg = ((b.x() - a.x()) ** 2 + (b.y() - a.y()) ** 2) ** 0.5
            if seg == 0:
                continue
            if dist <= seg:
                f = dist / seg
                return QPointF(a.x() + (b.x() - a.x()) * f,
                               a.y() + (b.y() - a.y()) * f)
            dist -= seg
        return pts[-1]

    def _tick(self):
        self._phase += 0.04
        self.update()

    def showEvent(self, event):
        self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        g = QLinearGradient(0, 0, w, h)
        if self.dark_mode:
            g.setColorAt(0.0, QColor(DARK["bg_main"]))
            g.setColorAt(1.0, QColor(DARK["bg_panel"]))
            grid = QColor(255, 255, 255, 12)
        else:
            g.setColorAt(0.0, QColor("#E6EDEF"))
            g.setColorAt(1.0, QColor("#EEF0F0"))
            grid = QColor(120, 150, 160, 22)
        p.fillRect(self.rect(), g)

        # soft teal glow on the right side
        glow = QRadialGradient(w * 0.72, h * 0.5, max(w, h) * 0.5)
        glow.setColorAt(0.0, QColor(14, 119, 105, 46 if self.dark_mode else 34))
        glow.setColorAt(1.0, QColor(14, 119, 105, 0))
        p.fillRect(self.rect(), glow)

        # grid
        p.setPen(QPen(grid, 1))
        step = 60
        for x in range(0, w, step):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, step):
            p.drawLine(0, y, w, y)

        # ---- CAN bus with moving data packets ----
        c = DARK if self.dark_mode else LIGHT
        teal = QColor("#2BB5A0" if self.dark_mode else "#0E7769")

        x0 = w * 0.50
        x1 = w - 70
        bus_y = h * 0.52
        count = len(self._NODES)
        step = (x1 - x0) / count
        xs = [x0 + step * (i + 0.5) for i in range(count)]
        nw = min(96.0, step - 14)
        nh = 54.0
        node_y = [bus_y - 110 if i % 2 == 0 else bus_y + 110
                  for i in range(count)]
        edge_y = [node_y[i] + (nh / 2 if i % 2 == 0 else -nh / 2)
                  for i in range(count)]

        # the two bus wires (CAN_H / CAN_L), fading in from the left
        bx0, bx1 = x0 - step * 0.5, x1 + 30
        fade = QLinearGradient(bx0, 0, bx1, 0)
        none = QColor(teal)
        none.setAlpha(0)
        solid = QColor(teal)
        solid.setAlpha(110)
        fade.setColorAt(0.0, none)
        fade.setColorAt(0.25, solid)
        fade.setColorAt(1.0, solid)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QBrush(fade), 2.2))
        for dy in (-4, 4):
            p.drawLine(QPointF(bx0, bus_y + dy), QPointF(bx1, bus_y + dy))

        # stubs from each ECU down/up to the bus
        stub = QColor(teal)
        stub.setAlpha(90)
        p.setPen(QPen(stub, 2))
        for i in range(count):
            p.drawLine(QPointF(xs[i], edge_y[i]), QPointF(xs[i], bus_y))

        # one packet at a time: the next one starts only after the last one
        # has arrived and its node has finished glowing
        packets = []
        glow = [0.0] * count
        slot = self._TRAVEL + self._PAUSE
        t = self._phase % (slot * len(self._ROUTES))
        index = int(t // slot)
        local = t - index * slot
        src, dst = self._ROUTES[index]
        if local < self._TRAVEL:
            prog = local / self._TRAVEL
            packets.append((src, dst, prog))
            if prog < 0.15:
                glow[src] = (0.15 - prog) / 0.15
            if prog > 0.85:
                glow[dst] = (prog - 0.85) / 0.15
        else:
            glow[dst] = 1.0 - (local - self._TRAVEL) / self._PAUSE
            
        # ECU boxes
        p.setFont(QFont(FONT_FAMILY, 10, QFont.DemiBold))
        for i, label in enumerate(self._NODES):
            rect = QRectF(xs[i] - nw / 2, node_y[i] - nh / 2, nw, nh)
            is_logger = label == "LOGGER"
            p.setBrush(QColor(c["bg_panel"]))
            p.setPen(QPen(teal if is_logger else QColor(c["border"]), 2))
            p.drawRoundedRect(rect, 12, 12)
            if glow[i] > 0:
                fill = QColor(teal)
                fill.setAlpha(int(70 * glow[i]))
                edge = QColor(teal)
                edge.setAlpha(int(255 * glow[i]))
                p.setBrush(fill)
                p.setPen(QPen(edge, 2))
                p.drawRoundedRect(rect, 12, 12)
            p.setPen(teal if is_logger else QColor(c["text_primary"]))
            p.drawText(rect, Qt.AlignCenter, label)

        # data packets with a short fading tail
        p.setPen(Qt.NoPen)
        for src, dst, prog in packets:
            pts = [
                QPointF(xs[src], edge_y[src]),
                QPointF(xs[src], bus_y),
                QPointF(xs[dst], bus_y),
                QPointF(xs[dst], edge_y[dst]),
            ]
            total = self._path_length(pts)
            d = prog * prog * (3 - 2 * prog) * total      # ease in and out
            for j in range(8):
                pos = self._point_along(pts, d - j * 10)
                if pos is None:
                    break
                col = QColor(teal)
                col.setAlpha(255 if j == 0 else max(0, 170 - j * 22))
                r = 5.5 - j * 0.45
                p.setBrush(col)
                p.drawEllipse(pos, r, r)
        p.end()
    # ------------------------------------------------------------------
    # Help, logo, theme
    # ------------------------------------------------------------------
    def on_help(self):
        QMessageBox.information(
            self,
            "Help",
            "SkillLogger\n\n"
            "OBD Config  choose modes and PIDs and create the OBD logger "
            "config.json\n"
            "CAN Config  set Classic CAN / CAN FD, filters, triggers and "
            "log files\n\n"
            "Inside a tool, use the Home button (top left) to come back here."
        )

    def on_logo_clicked(self):
        QDesktopServices.openUrl(QUrl(COMPANY_URL))

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.apply_theme()

    def apply_theme(self):
        c = DARK if self.dark_mode else LIGHT
        teal = "#2BB5A0" if self.dark_mode else "#0E7769"

        self.name_label.setStyleSheet(f"color: {c['text_primary']};")

        self.help_button.setStyleSheet(f"""
            #helpButton {{ background-color: {c['bg_panel']};
                           color: {c['text_primary']};
                           border: 1px solid {c['border']};
                           border-radius: {RADIUS_SM}px; }}
            #helpButton:hover {{ border: 1px solid {c['accent_blue']}; }}
        """)
        self.theme_toggle.setStyleSheet(f"""
            #themeToggle {{ background-color: {c['bg_panel']};
                            border: 1px solid {c['border']};
                            border-radius: {RADIUS_SM}px; }}
            #themeToggle:hover {{ border: 1px solid {c['accent_blue']}; }}
        """)
        self.theme_toggle.setIcon(
            make_theme_icon(self.dark_mode, c["toggle_icon"])
        )

        self.accent.setStyleSheet(
            f"background-color: {teal}; border-radius: 2px;"
        )
        self.obd_button.set_colors(c, teal)
        self.can_button.set_colors(c, teal)
        self.update()
    
    @staticmethod
    def _make_button(text, primary):
        b = QPushButton(text)
        b.setFixedSize(230, 58)
        b.setCursor(Qt.PointingHandCursor)
        b.setFont(QFont(FONT_FAMILY, 13, QFont.DemiBold))
        if primary:
            style = """
            QPushButton { background-color: #0E7769; color: white;
                          border: none; border-radius: 29px; }
            QPushButton:hover { background-color: #0B665A; }
            QPushButton:pressed { background-color: #095A50; }
            """
        else:
            style = """
            QPushButton { background-color: #F3F6F7; color: #18262B;
                          border: 1px solid #C5CED1; border-radius: 29px; }
            QPushButton:hover { border: 1px solid #0E7769; color: #0E7769; }
            QPushButton:pressed { background-color: #E3E9EB; }
            """
        b.setStyleSheet(style)
        return b