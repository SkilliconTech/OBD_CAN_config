from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QLabel,
    QComboBox, QSpinBox, QScrollArea, QFrame, QPushButton,
)
from can_tool.resources.theme import RADIUS_SM
from can_tool.resources.spin_style import spinbox_stylesheet
from can_tool.models.constants import DEFAULT_CLASSIC_CAN

# (text shown, bitrate number, sampling point)
BITRATE_CHOICES = (
    ("100.000 kbits/s, 75%", 100000, "75%"),
    ("125.000 kbits/s, 75%", 125000, "75%"),
    ("250.000 kbits/s, 75%", 250000, "75%"),
    ("500.000 kbits/s, 75%", 500000, "75%"),
    ("1.000 Mbits/s, 75%", 1000000, "75%"),
)


class ClassicCANSettingsDialog(QWidget):
    """Classic CAN settings shown in the right content panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.settings = dict(
            getattr(parent, "classic_can_settings", DEFAULT_CLASSIC_CAN)
            if parent is not None else DEFAULT_CLASSIC_CAN
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        body = QWidget()
        scroll.setWidget(body)
        main_layout = QVBoxLayout(body)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(8)

        # ---- Bus parameters: bitrate + sampling point, SJW ----
        bus_group = QGroupBox("Bus parameters")
        bus_form = QFormLayout(bus_group)

        self.bitrate_combo = QComboBox()
        for text, rate, sp in BITRATE_CHOICES:
            self.bitrate_combo.addItem(text, (rate, sp))
        bus_form.addRow("Bitrate and\nsampling point:", self.bitrate_combo)

        self.sjw_combo = QComboBox()
        self.sjw_combo.addItems(["1", "2", "3", "4"])
        bus_form.addRow("SJW:", self.sjw_combo)

        main_layout.addWidget(bus_group)

        # ---- Run settings ----
        run_group = QGroupBox("Run settings")
        run_form = QFormLayout(run_group)
        self.startup_delay = self._spin(0, 600000, 100)
        self.run_duration = self._spin(0, 86400000, 1000)
        self.run_duration.setSpecialValueText("0 (run continuously)")
        run_form.addRow("Startup delay:", self.startup_delay)
        run_form.addRow("Run duration:", self.run_duration)
        main_layout.addWidget(run_group)

        # ---- Current settings ----
        current_group = QGroupBox("Current settings")
        current_layout = QVBoxLayout(current_group)
        self.current_bitrate = QLabel()
        self.current_sampling = QLabel()
        self.current_sjw = QLabel()
        self.current_startup = QLabel()
        self.current_duration = QLabel()
        for label in (self.current_bitrate, self.current_sampling,
                      self.current_sjw, self.current_startup,
                      self.current_duration):
            current_layout.addWidget(label)
        main_layout.addWidget(current_group)

        main_layout.addStretch(1)

        # ---- Apply / Save / Cancel ----
        action_row = QHBoxLayout()
        action_row.addStretch(1)
        self.apply_button = QPushButton("Apply")
        self.save_button = QPushButton("Save")
        self.cancel_button = QPushButton("Cancel")
        self.apply_button.setToolTip("Use these settings in the app (does not write the file)")
        self.save_button.setToolTip("Save the changes of this window into the current file")
        self.apply_button.clicked.connect(self.on_apply)
        self.save_button.clicked.connect(self.on_save)
        self.cancel_button.clicked.connect(self.on_cancel)
        for b in (self.apply_button, self.save_button, self.cancel_button):
            action_row.addWidget(b)
        main_layout.addLayout(action_row)

        self.bitrate_combo.currentIndexChanged.connect(self.update_current_settings)
        self.sjw_combo.currentIndexChanged.connect(self.update_current_settings)
        self.startup_delay.valueChanged.connect(self.update_current_settings)
        self.run_duration.valueChanged.connect(self.update_current_settings)

        self._restore_settings()
        self.update_current_settings()

    @staticmethod
    def _spin(low, high, step):
        box = QSpinBox()
        box.setRange(low, high)
        box.setSingleStep(step)
        box.setSuffix(" ms")
        box.setFixedWidth(220)
        return box

    def _restore_settings(self):
        s = self.settings
        rate = s.get("bitrate", 500000)
        index = 0
        for i in range(self.bitrate_combo.count()):
            if self.bitrate_combo.itemData(i)[0] == rate:
                index = i
                break
        self.bitrate_combo.setCurrentIndex(index)

        sjw_index = self.sjw_combo.findText(str(s.get("sjw", "1")))
        self.sjw_combo.setCurrentIndex(max(0, sjw_index))

        self.startup_delay.setValue(s.get("startup_delay_ms", 0))
        self.run_duration.setValue(s.get("run_duration_ms", 0))

    def _collect_settings(self):
        rate, sp = self.bitrate_combo.currentData()
        return {
            "bitrate": rate,
            "sampling_point": sp,
            "sjw": self.sjw_combo.currentText(),
            "startup_delay_ms": self.startup_delay.value(),
            "run_duration_ms": self.run_duration.value(),
        }

    def update_current_settings(self):
        s = self._collect_settings()
        self.current_bitrate.setText(f"Bitrate:  {s['bitrate'] // 1000} kbit/s")
        self.current_sampling.setText(f"Sampling point:  {s['sampling_point']}")
        self.current_sjw.setText(f"SJW:  {s['sjw']}")
        self.current_startup.setText(f"Startup delay:  {s['startup_delay_ms']} ms")
        self.current_duration.setText(
            "Run duration:  continuous" if s["run_duration_ms"] == 0
            else f"Run duration:  {s['run_duration_ms']} ms")

    def has_pending_changes(self):
        baseline = getattr(self, "_form_baseline", None)
        return baseline is not None and self._collect_settings() != baseline

    def apply_to_parent(self):
        if self.parent_window is not None:
            self.parent_window.classic_can_settings = self._collect_settings()
            self.load_from_parent()

    def load_from_parent(self):
        if self.parent_window is None:
            return
        self.settings = dict(
            getattr(self.parent_window, "classic_can_settings", DEFAULT_CLASSIC_CAN))
        self._restore_settings()
        self.update_current_settings()
        self._saved_settings = dict(self.settings)
        self._form_baseline = dict(self._collect_settings())

    def on_apply(self):
        self.apply_to_parent()
        if self.parent_window is not None:
            self.parent_window.statusBar().showMessage("Classic CAN settings applied", 3000)

    def on_save(self):
        self.apply_to_parent()
        self._saved_settings = dict(self._collect_settings())
        if self.parent_window is not None:
            self.parent_window.statusBar().showMessage("Classic CAN changes saved", 3000)

    def on_cancel(self):
        saved = getattr(self, "_saved_settings", None)
        if self.parent_window is not None and saved is not None:
            self.parent_window.classic_can_settings = dict(saved)
        self.load_from_parent()
        if self.parent_window is not None:
            self.parent_window.statusBar().showMessage("Classic CAN changes cancelled", 3000)

    def set_theme(self, c):
        self.setStyleSheet(f"""
            QWidget {{ background-color: transparent; color: {c['text_primary']}; }}
            QLabel {{ color: {c['text_primary']}; background: transparent; }}
            QGroupBox {{
                color: {c['text_primary']};
                border: 1px solid {c['border']};
                border-radius: {RADIUS_SM}px;
                margin-top: 10px; padding-top: 8px;
                background-color: {c['bg_panel']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; left: 10px; padding: 0 4px;
                color: {c['text_primary']};
            }}
            QComboBox {{
                background-color: {c['bg_main']}; color: {c['text_primary']};
                border: 1px solid {c['border']};
                border-radius: {RADIUS_SM}px; padding: 4px 6px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {c['bg_panel']}; color: {c['text_primary']};
                selection-background-color: {c['accent_blue']};
                selection-color: #FFFFFF;
            }}
            QPushButton {{
                background-color: {c['bg_panel']}; color: {c['text_primary']};
                border: 1px solid {c['border']};
                border-radius: {RADIUS_SM}px; padding: 6px 16px;
            }}
            QPushButton:hover {{ border: 1px solid {c['accent_blue']}; }}
            QScrollArea {{ background: transparent; border: none; }}
            QScrollArea > QWidget > QWidget {{ background: transparent; }}
        """ + spinbox_stylesheet(c))