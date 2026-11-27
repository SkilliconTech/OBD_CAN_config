import copy
from PySide6.QtCore import Qt, Signal, QObject, QEvent, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QHeaderView, QPushButton, QMessageBox,
)
from can_tool.views.widget_helpers import make_note
from can_tool.views.filter_dialog import FilterDialog
from can_tool.services.config_validator import validate_filters, find_conflict_with
from can_tool.resources.theme import RADIUS_SM


class LockGuard(QObject):
    """Blocks clicks and typing on widgets while their page is locked."""

    def __init__(self, owner, page, only_double_click=False):
        super().__init__(owner)
        self.owner = owner
        self.page = page
        self.only_double_click = only_double_click

    def eventFilter(self, obj, event):
        if self.owner.is_unlocked(self.page):
            return False

        kind = event.type()

        if self.only_double_click:
            if kind == QEvent.MouseButtonDblClick:
                self.owner.warn_locked(self.page)
                return True
            return False

        if kind in (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick):
            self.owner.warn_locked(self.page)
            return True

        if kind in (QEvent.MouseButtonRelease, QEvent.Wheel,
                    QEvent.KeyRelease, QEvent.ContextMenu):
            return True

        if kind == QEvent.KeyPress and event.key() not in (
                Qt.Key_Tab, Qt.Key_Backtab):
            return True

        return False
    
class LogConfigWidget(QWidget):
    """Filters page (the only page left under Log Configuration)."""
    configuration_changed = Signal()

    def __init__(self, get_full_config, show_status, parent=None):
        super().__init__(parent)
        self.get_full_config = get_full_config
        self.show_status = show_status
        self.rules = []
        self._unlocked = {"filters": False}
        self._warning_open = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(make_note("Filters control which frames are stored."))

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Name", "Identifier", "Type", "Condition"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.doubleClicked.connect(lambda _: self.edit_filter())
        layout.addWidget(self.table)

        row = QHBoxLayout()
        for label, slot in [("Add", self.add_filter), ("Edit", self.edit_filter),
                            ("Remove", self.remove_filter),
                            ("Remove All", self.remove_all)]:
            button = QPushButton(label)
            button.clicked.connect(slot)
            row.addWidget(button)
        layout.addLayout(row)

        self._install_lock_guards()

    # ---------------- lock ----------------
    def is_unlocked(self, page):
        return self._unlocked.get(page, True)

    def set_unlocked(self, page, value):
        self._unlocked[page] = bool(value)

    def warn_locked(self, page):
        if self._warning_open:
            return
        self._warning_open = True

        def show():
            QMessageBox.critical(
                self.window(), "Filters are locked",
                "Filters are locked, so nothing can be added or changed.\n\n"
                "Switch on 'Editing' next to the page title to unlock them.")
            self._warning_open = False
        QTimer.singleShot(0, show)

    def _install_lock_guards(self):
        guard = LockGuard(self, "filters")
        for button in self.findChildren(QPushButton):
            button.installEventFilter(guard)
        self.table.viewport().installEventFilter(
            LockGuard(self, "filters", only_double_click=True))

    def notify_configuration_changed(self):
        self.configuration_changed.emit()

    # ---------------- data ----------------
    def collect(self):
        return copy.deepcopy(self.rules)

    def apply(self, rules):
        validate_filters(rules)
        self.rules = copy.deepcopy(rules)
        self.refresh_table()

    def refresh_table(self):
        self.table.setRowCount(len(self.rules))
        for row, r in enumerate(self.rules):
            if r["type"] == "id_list":
                condition = ", ".join(r["ids"])
            elif r["type"] == "id_range":
                condition = f"{r['id_start']} – {r['id_end']}"
            else:
                condition = f"Match {r['match_id']}; mask {r['mask']}"
            for col, value in enumerate([
                r["filter_id"],
                "Extended" if r["extended_id"] else "Standard",
                r["type"],
                condition,
            ]):
                self.table.setItem(row, col, QTableWidgetItem(value))

    def edit_rule(self, index=None):
        parent = self.window()
        if index is None:
            n = 1
            while any(r["filter_id"] == f"F{n}" for r in self.rules):
                n += 1
            rule = dict(filter_id=f"F{n}", type="id_list",
                        extended_id=False, ids=["0x123"])
        else:
            rule = self.rules[index]

        dialog = FilterDialog(parent, rule)
        while dialog.exec():
            rule = dialog.rule()

            new_id = rule["filter_id"].strip().lower()
            if any(r["filter_id"].strip().lower() == new_id
                   for i, r in enumerate(self.rules) if i != index):
                QMessageBox.warning(
                    parent, "Duplicate filter ID",
                    f"A filter with the ID '{rule['filter_id']}' already exists.\n\n"
                    "Each filter must have a different ID. Please choose another.")
                continue

            others = [r for i, r in enumerate(self.rules) if i != index]
            clash = find_conflict_with(rule, others)
            if clash:
                QMessageBox.warning(
                    parent, "CAN identifier already used",
                    f"This filter uses a CAN identifier that filter '{clash}' "
                    "already uses.\n\nChange the identifier.")
                continue

            if index is None:
                self.rules.append(rule)
            else:
                self.rules[index] = rule
            self.refresh_table()
            self.notify_configuration_changed()
            break

    def add_filter(self):
        self.edit_rule()

    def edit_filter(self):
        if self.table.currentRow() >= 0:
            self.edit_rule(self.table.currentRow())

    def remove_filter(self):
        row = self.table.currentRow()
        if row < 0:
            return
        name = self.rules[row]["filter_id"]
        if QMessageBox.question(
                self.window(), "Remove filter",
                f"Do you want to remove the filter '{name}'?\n\nThis cannot be undone.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        del self.rules[row]
        self.refresh_table()
        self.notify_configuration_changed()

    def remove_all(self):
        if not self.rules:
            return
        if QMessageBox.warning(
                self.window(), "Remove all filters",
                f"Do you want to remove all {len(self.rules)} filter(s)?\n\n"
                "This cannot be undone.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self.rules.clear()
        self.refresh_table()
        self.notify_configuration_changed()

    # ---------------- theme ----------------
    def set_theme(self, c):
        self.setStyleSheet(f"""
            QLabel {{ color: {c['text_primary']}; background: transparent; }}
            QTableWidget {{
                background-color: {c['bg_main']}; color: {c['text_primary']};
                border: 1px solid {c['border']};
                border-radius: {RADIUS_SM}px;
                gridline-color: {c['border']};
                selection-background-color: {c['accent_blue']};
                selection-color: #FFFFFF;
            }}
            QHeaderView::section {{
                background-color: {c['bg_panel']}; color: {c['text_secondary']};
                border: none; border-bottom: 1px solid {c['border']};
                padding: 6px;
            }}
            QPushButton {{
                background-color: {c['bg_panel']}; color: {c['text_primary']};
                border: 1px solid {c['border']};
                border-radius: {RADIUS_SM}px; padding: 6px 16px;
            }}
            QPushButton:hover {{ border: 1px solid {c['accent_blue']}; }}
        """)