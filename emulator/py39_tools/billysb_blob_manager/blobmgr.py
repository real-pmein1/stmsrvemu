import copy
import os
import re
import sys
from datetime import datetime
import struct
import zlib
import traceback
import configparser
from pathlib import Path
from shutil import copystat
from time import sleep, monotonic
from os import path, mkdir, utime, remove as osremove
from json import dumps as jsondump
from json import loads as jsonload
from bisect import bisect_right

from pyperclip import copy as clipboardcopy

from blobreader import ReadBlob

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import SQLAlchemyError

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFontMetrics
from PyQt5.QtWidgets import (
        QApplication,
        QAbstractItemView,
        QCheckBox,
        QDialog,
        QFileDialog,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QMenu,
        QProgressBar,
        QSlider,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QVBoxLayout,
        QWidget,
)

from sbgui import ImageCheckBox, ImageRadioButton, NineSliceButton, NineSliceLineEdit, SbMainQWindow, SbMessageBox, SteamSeparator


# Ensure repository root (contains `utilities`, `config.py`, etc.) is importable.
# Includes source and PyInstaller-frozen execution paths.
SCRIPT_DIR = Path(__file__).resolve().parent
repo_candidates = [Path.cwd(), SCRIPT_DIR, SCRIPT_DIR.parent, SCRIPT_DIR.parent.parent]

if getattr(sys, 'frozen', False):
    exe_dir = Path(sys.executable).resolve().parent
    repo_candidates.append(exe_dir)
    repo_candidates.extend(list(exe_dir.parents)[:6])

if hasattr(sys, '_MEIPASS'):
    repo_candidates.append(Path(getattr(sys, '_MEIPASS')))

seen_candidates = set()
for candidate in repo_candidates:
    resolved = candidate.resolve()
    resolved_str = str(resolved)
    if resolved_str in seen_candidates:
        continue
    seen_candidates.add(resolved_str)

    if (resolved / 'utilities').is_dir():
        if resolved_str not in sys.path:
            sys.path.insert(0, resolved_str)
        break


# Function to strip comments from the config values
def strip_comments(value):
    # Remove everything after a semicolon, including the semicolon itself
    if value:
        return value.split(';', 1)[0].strip()
    return None


# Function to normalize the date format to YYYY-mm-dd

def normalize_date_format(steam_date):
    # Strip leading/trailing spaces
    steam_date = steam_date.strip()

    # Debug: Print raw steam_date for troubleshooting
    print(f"Raw steam_date: '{steam_date}'")

    # Replace / and _ with - to standardize the date format
    steam_date = steam_date.replace('/', '-').replace('_', '-')

    # Try to directly validate the date string as 'YYYY-MM-DD'
    try:
        datetime.strptime(steam_date, '%Y-%m-%d')
        return steam_date  # Return the date as it's now in the correct format
    except ValueError:
        print(f"Invalid date: '{steam_date}'")  # Debug for invalid date
        return None  # Return None if the format is invalid


# Function to normalize the time format to HH:MM:SS
def normalize_time_format(steam_time):
    # Strip leading/trailing spaces
    steam_time = steam_time.strip()

    # Debug: Print raw steam_time to help with troubleshooting
    print(f"Raw steam_time: '{steam_time}'")

    # Match formats like HH:MM:SS, HH-MM-SS, HH_MM_SS
    time_pattern = re.compile(r'(\d{2})[:\-_](\d{2})[:\-_](\d{2})')
    match = time_pattern.match(steam_time)

    if match:
        # Convert to HH:MM:SS format
        time_str = f"{match.group(1)}:{match.group(2)}:{match.group(3)}"

        # Debug: Print normalized time before validation
        print(f"Normalized time string: '{time_str}'")

        # Validate if it's a valid time
        try:
            datetime.strptime(time_str, '%H:%M:%S')
            return time_str
        except ValueError:
            # Debug: Invalid time detected
            print(f"Invalid time format: '{time_str}'")
            return None  # Invalid time, return None
    else:
        # Debug: Regex did not match
        print(f"Time format did not match expected pattern: '{steam_time}'")

    return None  # No match or invalid time format


class _SqlAlchemyCursorCompat:
    def __init__(self, connection):
        self.connection = connection
        self._rows = []

    def execute(self, query, params = None):
        if params is None:
            result = self.connection._connection.exec_driver_sql(query)
        else:
            result = self.connection._connection.exec_driver_sql(query, params)

        if result.returns_rows:
            self._rows = result.fetchall()
        else:
            self._rows = []
            if self.connection.autocommit:
                self.connection.commit()
        return self

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def __iter__(self):
        return iter(self._rows)


class _SqlAlchemyConnectionCompat:
    def __init__(self, engine):
        self._engine = engine
        self._connection = engine.connect()
        self.autocommit = False

    def cursor(self):
        return _SqlAlchemyCursorCompat(self)

    def commit(self):
        self._connection.commit()

    def close(self):
        self._connection.close()

    def ping(self):
        self._connection.exec_driver_sql("SELECT 1")
        return True


class _SqlAlchemyMariaDBCompat:
    Error = SQLAlchemyError

    def __init__(self):
        self._engines = {}

    def connect(self, user, password, host, port, database = None, **kwargs):
        connect_args = {}
        if 'connect_timeout' in kwargs:
            connect_args['connect_timeout'] = kwargs['connect_timeout']

        key = (host, int(port), user, password, database, tuple(sorted(connect_args.items())))
        engine = self._engines.get(key)
        if engine is None:
            url = URL.create(
                    "mysql+pymysql",
                    username = user,
                    password = password,
                    host = host,
                    port = int(port),
                    database = database
            )
            engine = create_engine(url, connect_args = connect_args)
            self._engines[key] = engine
        return _SqlAlchemyConnectionCompat(engine)


_SQLALCHEMY_MARIADB_COMPAT = _SqlAlchemyMariaDBCompat()


def _install_sqlalchemy_mariadb_adapter(*modules):
    sys.modules['mariadb'] = _SQLALCHEMY_MARIADB_COMPAT
    for module in modules:
        if module is not None:
            module.mariadb = _SQLALCHEMY_MARIADB_COMPAT


APP = QApplication.instance() or QApplication(sys.argv)

BTN_STYLE = """
QPushButton {
    font-family: Tahoma;
    font-size: 9pt;
    font-weight: bold;
    color: white;
    padding: 0px;
    margin: 0px;
}
"""

LABEL_STYLE = "font-family: Tahoma; font-size: 9pt; font-weight: bold; color: #d5dbcf;"
TITLE_LABEL_STYLE = "font-family: Tahoma; font-size: 9pt; font-weight: bold; color: #c4b451;"
STATUS_STYLE = "font-family: Tahoma; font-size: 9pt; font-weight: bold; color: #c4b451;"

PROGRESS_STYLE = """
QProgressBar {
    border: 1px solid #444;
    border-radius: 2px;
    background-color: #2b2b2b;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #c4b451;
    width: 10px;
    margin: 2 2px;
}
"""

TABLE_STYLE = """
QTableWidget {
    background-color: #3e4637;
    alternate-background-color: #484f49;
    color: #ffffff;
    gridline-color: #293021;
    border: 1px solid #292e23;
    font-family: Tahoma;
    font-size: 8pt;
    font-weight: bold;
    selection-background-color: #958831;
    selection-color: #ffffff;
}
QHeaderView::section {
    background-color: #4c5844;
    color: #ffffff;
    border: 1px solid #292e23;
    padding: 3px;
    font-family: Tahoma;
    font-size: 8pt;
    font-weight: bold;
}
QTableWidget::item:selected {
    background-color: #958831;
    color: #ffffff;
}
QScrollBar:vertical { border: none; background: #464646; width: 24px; margin: 0px; }
QScrollBar::handle:vertical { background: #686b64; min-height: 25px; border-radius: 3px; margin: 24px 4px; width: 16px; }
QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical { background: #686b64; height: 16px; border-radius: 3px; width: 16px; margin: 4px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
"""

MENU_STYLE = """
QMenu {
    background-color: #4c5844;
    color: #d5dbcf;
    border: 1px solid #292e23;
    padding: 3px;
    font-family: Tahoma;
    font-size: 9pt;
    font-weight: bold;
}
QMenu::item {
    padding: 5px 24px 5px 12px;
    background-color: transparent;
    color: #d5dbcf;
}
QMenu::item:selected {
    background-color: #958831;
    color: #ffffff;
}
QMenu::separator {
    height: 1px;
    background: #292e23;
    margin: 4px 6px;
}
"""


def pump_qt_events():
    APP.processEvents()


def show_error(message, title = "Error", parent = None):
    SbMessageBox.critical(parent, title, str(message))


def show_info(message, title = "Alert", parent = None):
    SbMessageBox.info(parent, title, str(message))


class _QtElement:
    def __init__(self, widget):
        self.Widget = widget
        self.widget = widget

    def update(self, value = None, disabled = None, select_rows = None, values = None, **kwargs):
        if value is None and 'current_count' in kwargs:
            value = kwargs['current_count']
        if value is not None:
            if isinstance(self.Widget, QCheckBox):
                self.Widget.setChecked(bool(value))
            elif isinstance(self.Widget, QProgressBar):
                self.Widget.setValue(int(value))
            elif hasattr(self.Widget, "setText"):
                self.Widget.setText(str(value))
            elif hasattr(self.Widget, "setValue"):
                self.Widget.setValue(value)
            elif hasattr(self.Widget, "setChecked"):
                self.Widget.setChecked(bool(value))
        if disabled is not None:
            self.Widget.setEnabled(not disabled)
        pump_qt_events()

    def Update(self, **kwargs):
        return self.update(**kwargs)

    def get(self):
        if hasattr(self.Widget, "text"):
            return self.Widget.text()
        if hasattr(self.Widget, "value"):
            return self.Widget.value()
        if hasattr(self.Widget, "isChecked"):
            return self.Widget.isChecked()
        return None

    def set_focus(self):
        self.Widget.setFocus()

    def bind(self, *args, **kwargs):
        return None


class _QtTableElement(_QtElement):
    def __init__(self, table, manager):
        super().__init__(table)
        self.manager = manager

    def update(self, value = None, values = None, select_rows = None, **kwargs):
        if values is not None:
            self.manager.window.populate_table(values)
        if select_rows is not None:
            self.manager.window.select_rows(select_rows)
        pump_qt_events()

    def get(self):
        return self.manager.window.selected_rows()

    def expand(self, *args, **kwargs):
        return None


class LoadingWindow(SbMainQWindow):
    def __init__(self):
        super().__init__(500, 162, "Loading Blob Information")
        self.set_resize_enabled(False)
        self.setFixedSize(500, 162)
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(40, 50, 40, 18)
        layout.setSpacing(8)
        layout.addStretch(1)
        self.status = QLabel("Loading")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setStyleSheet(TITLE_LABEL_STYLE)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(PROGRESS_STYLE)
        layout.addWidget(self.status)
        layout.addWidget(self.progress)
        layout.addStretch(1)
        self.show()
        pump_qt_events()

    def __getitem__(self, key):
        if key == '-STATUS-':
            return _QtElement(self.status)
        if key == '-PBAR-':
            return _QtElement(self.progress)
        raise KeyError(key)

    def bring_to_front(self):
        self.raise_()
        self.activateWindow()
        pump_qt_events()

    def close(self):
        super().close()
        pump_qt_events()


class DataSourceDialog(SbMainQWindow):
    def __init__(self):
        super().__init__(420, 190, "Choose Data Source")
        self.set_resize_enabled(False)
        self.choice = None
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(40, 72, 40, 28)
        layout.setSpacing(8)
        label = QLabel("Would you like to read the blobs from the database or from files?")
        label.setWordWrap(True)
        label.setStyleSheet(LABEL_STYLE)
        layout.addWidget(label)

        self.files = ImageRadioButton("Files", size=22)
        self.database = ImageRadioButton("Database", size=22)
        self.database.setChecked(True)
        layout.addWidget(self.files)
        layout.addWidget(self.database)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        ok = NineSliceButton("OK")
        cancel = NineSliceButton("Cancel")
        for btn in (ok, cancel):
            btn.setFixedSize(80, 24)
            btn.setStyleSheet(BTN_STYLE)
            buttons.addWidget(btn)
        layout.addLayout(buttons)
        ok.clicked.connect(self._ok)
        cancel.clicked.connect(self.close)

    def _ok(self):
        self.choice = 'files' if self.files.isChecked() else 'database'
        self.close()

    def exec_choice(self):
        self.show()
        while self.isVisible():
            pump_qt_events()
            sleep(0.01)
        return self.choice


class BlobManagerWindow(SbMainQWindow):
    def __init__(self, manager, title):
        super().__init__(1157, 780, title)
        self.manager = manager
        self._queue = []
        self._closed = False
        self.elements = {}
        self._build()
        self.center_window()

    def center_window(self):
        screen = APP.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        self.move(geo.center().x() - self.width() // 2, geo.center().y() - self.height() // 2)

    def _build(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(40, 72, 40, 44)
        root.setSpacing(7)

        self.ifb = QLabel(f"{self.manager.GetLocale('label_installed_blob1')} {self.manager.GetLocale('label_installed_blob1_none')}")
        self.isb = QLabel(f"{self.manager.GetLocale('label_installed_blob2')} {self.manager.GetLocale('label_installed_blob2_none')}")
        for label in (self.ifb, self.isb):
            label.setStyleSheet(LABEL_STYLE)
            root.addWidget(label)
        root.addWidget(SteamSeparator())

        top = QHBoxLayout()
        self.status = QLabel("")
        self.status.setStyleSheet(STATUS_STYLE)
        top.addStretch(1)
        top.addWidget(self.status, 2)
        top.addStretch(1)
        self.search_input = NineSliceLineEdit()
        self.search_input.setPlaceholderText("Filter blobs")
        self.search_input.setFixedWidth(220)
        self.search_input.setFixedHeight(24)
        self.swap_btn = NineSliceButton(self.manager.GetLocale('label_swap'))
        self.swap_btn.setEnabled(False)
        search_shim = QWidget()
        search_shim_layout = QVBoxLayout(search_shim)
        search_shim_layout.setContentsMargins(0, 2, 0, 0)
        search_shim_layout.setSpacing(0)
        search_shim_layout.addWidget(self.search_input)
        top.addWidget(search_shim)
        for btn, width in ((self.swap_btn, 80),):
            btn.setFixedSize(width, 24)
            btn.setStyleSheet(BTN_STYLE)
            top.addWidget(btn)
        root.addLayout(top)

        self.table = QTableWidget(0, len(self.manager.TopRow))
        self.table.setHorizontalHeaderLabels(self.manager.TopRow)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(TABLE_STYLE)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        for idx, width in enumerate((70, 70, 95, 145, 430)):
            self.table.setColumnWidth(idx, width)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        root.addWidget(self.table, 1)

        bottom_widget = QWidget()
        bottom_widget.setStyleSheet("background-color: #5c5a58;")
        bottom = QHBoxLayout(bottom_widget)
        bottom.setContentsMargins(0, 6, 0, 6)
        self.selected_label = QLabel(f"{self.manager.GetLocale('label_selected')} {self.manager.GetLocale('label_selected_none')}")
        self.selected_label.setStyleSheet("font-family: Tahoma; font-size: 9pt; font-weight: bold; color: #d5dbcf; text-decoration: underline;")
        bottom.addWidget(self.selected_label, 1)

        speed_label = QLabel("Speed")
        speed_label.setStyleSheet(LABEL_STYLE)
        bottom.addWidget(speed_label)
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(1, 10)
        self.speed_slider.setValue(1)
        self.speed_slider.setFixedWidth(120)
        self.speed_slider.setStyleSheet("""
        QSlider::groove:horizontal {
            height: 4px;
            background: #d5dbcf;
        }
        QSlider::sub-page:horizontal {
            background: #c4b451;
        }
        QSlider::add-page:horizontal {
            background: #d5dbcf;
        }
        QSlider::handle:horizontal {
            background: #c4b451;
            width: 10px;
            margin: -5px 0;
            border: 1px solid #8f8437;
        }
        QSlider::handle:horizontal:hover {
            background: #d8cb65;
        }
        """)
        bottom.addWidget(self.speed_slider)
        self.speed_text = QLabel("1x")
        self.speed_text.setStyleSheet(LABEL_STYLE)
        self.speed_text.setFixedWidth(28)
        bottom.addWidget(self.speed_text)
        self.countdown = QLabel("Next swap: --:--:--")
        self.countdown.setStyleSheet(LABEL_STYLE)
        self.countdown.setFixedWidth(145)
        bottom.addWidget(self.countdown)
        self.autoswap = ImageCheckBox("Auto Swap")
        bottom.addWidget(self.autoswap)
        root.addWidget(bottom_widget)

        self.elements = {
                '-IFB-': _QtElement(self.ifb),
                '-ISB-': _QtElement(self.isb),
                '-STATEMSG-': _QtElement(self.status),
                '-SEARCH-': _QtElement(self.search_input),
                '-SWAP-': _QtElement(self.swap_btn),
                '-LIST-': _QtTableElement(self.table, self.manager),
                '-SELECTTEXT-': _QtElement(self.selected_label),
                '-AUTOSWAP-SPEED-': _QtElement(self.speed_slider),
                '-AUTOSWAP-SPEEDTXT-': _QtElement(self.speed_text),
                '-AUTOSWAP-COUNTDOWN-': _QtElement(self.countdown),
                '-AUTOSWAP-ENABLE-': _QtElement(self.autoswap),
        }

        self.swap_btn.clicked.connect(lambda: self.enqueue('-SWAP-'))
        self.search_input.textChanged.connect(self.apply_filter)
        self.search_input.returnPressed.connect(lambda: self.apply_filter(self.search_input.text()))
        self.speed_slider.valueChanged.connect(lambda _: self.enqueue('-AUTOSWAP-SPEED-'))
        self.autoswap.stateChanged.connect(lambda _: self.enqueue('-AUTOSWAP-ENABLE-'))
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.cellDoubleClicked.connect(lambda *_: self.enqueue('-LIST- Double'))
        self.table.horizontalHeader().sectionClicked.connect(lambda col: self.enqueue(('-LIST-', '+CLICKED+', (-1, col))))
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.selected_label.mouseDoubleClickEvent = lambda event: self.enqueue('-SELECTTEXT- Double')
        self.selected_label.mousePressEvent = lambda event: self.enqueue('-SELECTTEXT-')
        self.filtered_indices = list(range(len(self.manager.Rows)))
        self.populate_table(self.manager.Rows)

    def __getitem__(self, key):
        return self.elements[key]

    def enqueue(self, event):
        self._queue.append(event)

    def read(self, timeout = None):
        deadline = monotonic() + (float(timeout or 0) / 1000.0)
        while True:
            pump_qt_events()
            if self._closed:
                return 'Exit', self.values()
            if self._queue:
                return self._queue.pop(0), self.values()
            if timeout is None:
                sleep(0.01)
                continue
            if monotonic() >= deadline:
                return '__TIMEOUT__', self.values()
            sleep(0.005)

    def values(self):
        return {
                '-LIST-': self.selected_rows(),
                '-AUTOSWAP-SPEED-': self.speed_slider.value(),
                '-AUTOSWAP-ENABLE-': self.autoswap.isChecked(),
        }

    def refresh(self):
        pump_qt_events()

    def bind(self, *args, **kwargs):
        return None

    def closeEvent(self, event):
        self._closed = True
        super().closeEvent(event)

    def populate_table(self, rows):
        if len(rows) == len(self.manager.Rows) and all(row is self.manager.Rows[idx] for idx, row in enumerate(rows)):
            self.filtered_indices = list(range(len(rows)))
        elif not hasattr(self, 'filtered_indices') or len(self.filtered_indices) != len(rows):
            self.filtered_indices = list(range(len(rows)))
        self.table.setRowCount(0)
        for row_idx, row in enumerate(rows):
            self.table.insertRow(row_idx)
            source_idx = self.filtered_indices[row_idx] if row_idx < len(self.filtered_indices) else row_idx
            for col_idx, value in enumerate(row[:len(self.manager.TopRow)]):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, source_idx)
                self.table.setItem(row_idx, col_idx, item)
        self.apply_missing_package_marks()

    def apply_filter(self, text):
        query = (text or "").strip().lower()
        if not query:
            self.filtered_indices = list(range(len(self.manager.Rows)))
        else:
            terms = [term for term in query.split() if term]
            self.filtered_indices = []
            for idx, row in enumerate(self.manager.Rows):
                haystack = " ".join(str(value) for value in row).lower()
                if all(term in haystack for term in terms):
                    self.filtered_indices.append(idx)

        rows = [self.manager.Rows[idx] for idx in self.filtered_indices]
        self.populate_table(rows)

    def apply_missing_package_marks(self):
        if not hasattr(self.manager, 'emulator_config'):
            return
        packages_dir = self.manager.emulator_config.get('config', 'packagedir', fallback = "files/packages/")
        packages_dir = packages_dir.split(';', 1)[0].strip()
        if packages_dir.startswith(("'", '"')) and packages_dir.endswith(("'", '"')):
            packages_dir = packages_dir[1:-1]

        steam_pkgs = set()
        steamui_pkgs = set()
        red = QColor("#ff4040")
        visible_rows = [self.manager.Rows[idx] for idx in getattr(self, 'filtered_indices', range(len(self.manager.Rows)))]
        for row_idx, row in enumerate(visible_rows):
            steam_pkg_path, steamui_pkg_path = self.manager._resolve_package_paths(packages_dir, row[1], row[2], row[-1] if len(row) > 5 else None)
            missing = False
            steam_key = steam_pkg_path.lower()
            steamui_key = steamui_pkg_path.lower()
            if steam_key not in steam_pkgs:
                if not os.path.exists(steam_pkg_path):
                    missing = True
                else:
                    steam_pkgs.add(steam_key)
            if steamui_key not in steamui_pkgs:
                if not os.path.exists(steamui_pkg_path):
                    missing = True
                else:
                    steamui_pkgs.add(steamui_key)
            if missing:
                for col_idx in range(self.table.columnCount()):
                    item = self.table.item(row_idx, col_idx)
                    if item:
                        item.setForeground(red)

    def selected_rows(self):
        selected = []
        for idx in self.table.selectionModel().selectedRows():
            item = self.table.item(idx.row(), 0)
            if item is not None:
                selected.append(item.data(Qt.UserRole))
        return sorted(set(selected))

    def select_rows(self, rows):
        self.table.clearSelection()
        visible = getattr(self, 'filtered_indices', list(range(len(self.manager.Rows))))
        for source_row in rows:
            if source_row in visible:
                display_row = visible.index(source_row)
                if 0 <= display_row < self.table.rowCount():
                    self.table.selectRow(display_row)
                    self.table.scrollToItem(self.table.item(display_row, 0), QAbstractItemView.PositionAtCenter)

    def _selection_changed(self):
        rows = self.selected_rows()
        if rows:
            self.manager.multiple_rows = rows
            self.manager.row = rows[0]
            self.enqueue(('-LIST-', '+CLICKED+', (rows[0], 0)))

    def _context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLE)
        export_action = menu.addAction(self.manager.GetLocale('label_menu1_item3'))
        action = menu.exec_(self.table.viewport().mapToGlobal(pos))
        if action == export_action:
            self.enqueue('Export Blob')

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F and event.modifiers() & Qt.ControlModifier:
            self.search_input.setFocus()
            self.search_input.selectAll()
            return
        if event.key() == Qt.Key_Up:
            self.enqueue('UP_KEY')
            return
        if event.key() == Qt.Key_Down:
            self.enqueue('DOWN_KEY')
            return
        super().keyPressEvent(event)


class BlobManager(object):
    window = None

    def __init__(self) -> None:
        self.windowico = path.join(path.dirname(__file__), "icon.ico")

        self.FilesFolder = './files/'
        self.BlobsFolder = f'{self.FilesFolder}blobs/'
        self.CacheFolder = f'{self.FilesFolder}cache/'
        self.ExportLoggingEnabled = any(arg.lower() == '-logging' for arg in sys.argv[1:])
        self.ExportLogPath = Path('./blobmgr_export.log')
        if self.ExportLoggingEnabled:
            try:
                with open(self.ExportLogPath, 'a', encoding = 'utf-8') as f:
                    f.write(f"\n=== BlobMgr export session started {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            except Exception:
                pass
        self.row = None
        self.multiple_rows = None
        self._header_resize_in_progress = False
        self._header_resize_dragged = False
        self._last_header_resize_at = 0.0
        self.AutoSwapEnabled = False
        self.AutoSwapMultiplier = 1.0
        self.AutoSwapCurrentSecond = None
        self.AutoSwapNextSecond = None
        self.AutoSwapNextDue = None
        self.AutoSwapIntervalSeconds = None
        self.AutoSwapScheduledAt = None
        self.AutoSwapLastCountdownText = None
        self.matching_first_blob = None
        self.matching_second_blob = None

        # Table Header and Content.
        self.Rows = []
        self.SecondBlobs = []
        self.FirstBlobs = []
        self.LandMarks = {}
        self.Selected = None
        self.Language = ""
        self.config = configparser.ConfigParser()

        choice = DataSourceDialog().exec_choice()
        if choice is None:
            sys.exit(0)
        self.load_from_database = (choice == 'database')

        loader = LoadingWindow()

        EnglishDefault = {
                'label_swap':                'Swap',
                'label_custom':              'Custom',
                'label_yes':                 'Yes',
                'label_no':                  'No',
                'label_date':                'Date',
                'label_description':         'Description',
                'label_blobmgr':             'Blob Manager',
                'label_version':             'Version',
                'label_selected':            'Selected:',
                'label_selected_none':       'None',
                'label_use_preprocessed':    'USING PACKED BLOB FILE',
                'label_copyclip':            'SELECTION STORED TO CLIPBOARD',
                'label_blobinfo_title':      'Blob Information',
                'label_appsdetected':        'Apps Detected:',
                'label_subsdetected':        'Subs Detected:',
                'label_search_fail':         'Search didn\'t find anything.',
                'label_simulation_title':    'Time simulation',
                'label_simulation_play':     'Start',
                'label_simulation_pause':    'Pause',
                'label_simulation_unpause':  'Unpause',
                'label_simulation_stop':     'Stop',
                'label_simulation_date':     'Current Date:',
                'label_simulation_speed':    'Time Speed:',
                'label_simulation_speed2':   'How many seconds should pass per minute.',
                'label_installed_blob1':     'Installed FirstBlob: ',
                'label_installed_blob1_none':'This will display once you install a blob from...',
                'label_installed_blob2':     'Installed SecondBlob: ',
                'label_installed_blob2_none':'...the table below',
                'label_extract_success':     'SUCCESSFULLY EXTRACTED SELECTED BLOBS.',
                'label_swap_success':        'SUCCESSFULLY INSTALLED SELECTED BLOBS.',
                'label_swapping':            'INSTALLING SELECTED BLOB, ONE SECOND.',
                'label_extract_failure':     'FAILED TO EXPORT SELECTED BLOBS.',
                'label_swap_error1':         'NO FIRSTBLOBS! SWAP ABORTED.',
                'label_swap_error2':         'FAILED TO DETECT FIRSTBLOB! SWAP ABORTED.',
                'label_swap_error3':         'FAILED! COULD NOT WRITE/READ FILE. SWAP ABORTED',
                'label_error_title':         'Error.',
                'label_error_text1':         "Error! You need to run this program in the same folder as the emulator.\r\nFailed to find emulator.ini",
                'label_error_text2':         'Failed to preserve file dates of copied blobs.',
                'label_error_text3':         'The extraction destination must be a folder.',
                'label_error_generic':       'An error occured while performing the selected action\r\nPlease show BillySB a screenshot of the error below.\r\n',
                'label_menu1_item1':         '&Export',
                'label_menu1_item2_1':       '!&Packed',
                'label_menu1_item2_2':       '&Packed',
                'label_menu1_item3':         'Export Blob',
                'label_menu1_item4':         'Close',
        }

        # Configuration Management
        DefaultConfigAge = 39

        loader['-STATUS-'].update(value = 'Checking configurations..')
        if not self.DoesFileExist('./blobmanager.ini'):
            # Create settings file.
            self.config['settings'] = {
                    'ConfigAge':        DefaultConfigAge,
                    'DebugMode':        False,
                    'Language':         'english',
                    'WindowRefreshTime':0.25,
                    'WindowUpdateTime': 120
            }
            self.config['english'] = EnglishDefault
            try:
                with open('./blobmanager.ini', 'w') as configfile:
                    self.config.write(configfile)
            except:
                pass
        else:
            # Load settings file.
            self.config.read('./blobmanager.ini')
            try:
                if int(self.config['settings']['ConfigAge']) < DefaultConfigAge:
                    self.config['english'] = EnglishDefault
                    try:
                        with open('./blobmanager.ini', 'w') as configfile:
                            self.config.write(configfile)
                    except:
                        pass
            except Exception as ex:
                show_info('Legacy configuration detected.\r\nPlease delete blobmanager.ini')
        if self.config.getboolean('settings', 'DebugMode'):
            print('DebugMode enabled.')
        loader['-PBAR-'].update(current_count = 10)
        # Manually read the emulator.ini and remove comments starting with ';'
        with open('./emulator.ini', 'r') as f:
            lines = f.readlines()
        clean_lines = [line for line in lines if not line.strip().startswith(';')]

        # Write back the clean lines to a temporary config string
        config_string = ''.join(clean_lines)
        # Use ConfigParser to read from the cleaned config string
        self.emulator_config = configparser.ConfigParser()
        self.emulator_config.read_string(config_string)

        # Only load emulator.ini if database option is selected
        if self.load_from_database:
            # Read emulator.ini
            if not self.DoesFileExist('./emulator.ini'):
                show_error(self.GetLocale('label_error_text1'), self.GetLocale('label_error_title'))
                exit(2)
            else:
                if 'config' in self.emulator_config:
                    db_config = self.emulator_config['config']
                    self.database_host = db_config.get('database_host', '127.0.0.1')
                    self.database_port = db_config.getint('database_port', 3306)
                    self.database_username = db_config.get('database_username', 'stmserver')
                    self.database_password = db_config.get('database_password', 'stmserver')
                else:
                    show_error('Missing [config] section in emulator.ini', 'Error')
                    exit(2)

                # Read steam_date and steam_time from emulator.ini
                steam_date_raw = self.emulator_config.get('config', 'steam_date', fallback = None)
                steam_time_raw = self.emulator_config.get('config', 'steam_time', fallback = None)

                # Strip comments from the values
                steam_date_clean = strip_comments(steam_date_raw)
                steam_time_clean = strip_comments(steam_time_raw)

                self.steam_datetime = None

                if steam_date_clean and steam_time_clean:
                    # Normalize the date and time to standard formats
                    steam_date_normalized = normalize_date_format(steam_date_clean)
                    steam_time_normalized = normalize_time_format(steam_time_clean)

                    # Debug: Print normalized date and time
                    print(f"Normalized date string: '{steam_date_normalized}'")
                    print(f"Normalized time string: '{steam_time_normalized}'")

                    if steam_date_normalized and steam_time_normalized:
                        try:
                            # Debug: Print combined date and time before parsing
                            print(f"Combined datetime string: '{steam_date_normalized} {steam_time_normalized}'")

                            # Attempt to parse the combined date and time
                            self.steam_datetime = datetime.strptime(f"{steam_date_normalized} {steam_time_normalized}", '%Y-%m-%d %H:%M:%S')

                        except ValueError as e:
                            # Debug: Show specific error message
                            print(f"Error while parsing datetime: {e}")
                            show_error("Invalid date/time format in emulator.ini", "Error")
                    else:
                        show_error("Unable to normalize date/time format in emulator.ini", "Error")

        loader['-PBAR-'].update(current_count = 35)

        loader['-STATUS-'].update(value = 'Processing table data...')

        EnglishDefault['label_selected_none'] = 'None'
        self.WindowUpdateTime = 0.75
        self.WindowRefreshTime = 120
        try:
            self.WindowUpdateTime = int(self.config['settings']['WindowUpdateTime'])
        except:
            pass
        try:
            self.WindowRefreshTime = float(self.config['settings']['WindowRefreshTime'])
        except:
            pass

        self.Lang = self.config['settings']['Language']

        # Define table headers
        self.TopRow = [self.GetLocale('label_custom'), 'Steam', 'SteamUI', self.GetLocale('label_date'), self.GetLocale('label_description')]

        # Initialize data structures for efficient date handling
        self.FirstBlobDates = []  # List to store firstblob dates and filenames
        self.SecondBlobDates = []  # List to store secondblob dates and filenames

        if self.load_from_database:
            loader['-STATUS-'].update(value = 'Connecting to Database')
            loader['-PBAR-'].update(current_count = 35)
            # Connect to database
            self.ConnectToDatabase()
            loader['-STATUS-'].update(value = 'Processing table data...')
            # Populate rows from database
            self.PopulateRowsFromDatabase()
            loader['-PBAR-'].update(current_count = 75)
        else:
            loader['-STATUS-'].update(value = 'Sorting blobs by date...')
            try:
                self.BlobsFiles = sorted(Path('./files/blobs/').iterdir(), key = lambda x:x.name)
            except:
                show_error('No files/blobs/ folder found. Cannot continue.')
                exit(2)
            loader['-PBAR-'].update(current_count = 35)

            loader['-STATUS-'].update(value = 'Processing table data...')
            self.PopulateRows()
            loader['-PBAR-'].update(current_count = 75)

            loader['-STATUS-'].update(value = 'Parsing firstblob data...')
            self.FirstBlobThread()
            loader['-PBAR-'].update(current_count = 100)
        if self.load_from_database:
            blob_base = "Database Blobs"
        else:
            blob_base = "File Based Blobs"

        loader['-STATUS-'].update(value = 'Checking package files...')
        loader['-PBAR-'].update(current_count = 75)
        loader.bring_to_front()
        self.window = BlobManagerWindow(
                self,
                f"Billy {self.GetLocale('label_blobmgr')} - {self.GetLocale('label_version')} 1.14 --- {blob_base}"
        )
        loader['-STATUS-'].update(value = 'Checking package files... 100%')
        loader['-PBAR-'].update(current_count = 100)
        loader.close()
        self.window.show()
        self.window.refresh()

        self.LastSelected = None
        self.LastSelectedFirstBlob = None

        self.sort_state = {header:False for header in self.TopRow}  # Initialize sort state for each column

        self.last_message_row = None  # Initialize the tracking attribute
        # After self.FirstBlobThread() add this:
        if not self.load_from_database:
            # Set -IFB- and -ISB- to display first and second blob filenames based on timestamp
            try:
                # Get the most recent firstblob.bin and secondblob.bin based on their modification timestamps
                first_blob_file = Path(f'{self.FilesFolder}firstblob.bin')
                second_blob_file = Path(f'{self.FilesFolder}secondblob.bin')

                if first_blob_file.exists() and second_blob_file.exists():
                    # Get the modification time of firstblob.bin and secondblob.bin
                    first_blob_timestamp = first_blob_file.stat().st_mtime
                    second_blob_timestamp = second_blob_file.stat().st_mtime

                    # Look for matching files in the blobs folder
                    matching_first_blob = None
                    matching_second_blob = None

                    # Check all files in the blobs folder
                    for blob_file in Path(self.BlobsFolder).iterdir():
                        if blob_file.is_file():
                            # Check for firstblob.bin match
                            if blob_file.name.startswith("firstblob.bin.") and abs(blob_file.stat().st_mtime - first_blob_timestamp) < 1:
                                matching_first_blob = blob_file.name

                            # Check for secondblob.bin match
                            elif blob_file.name.startswith("secondblob.bin.") and abs(blob_file.stat().st_mtime - second_blob_timestamp) < 1:
                                matching_second_blob = blob_file.name

                    # Update -IFB- and -ISB- with the matched filenames
                    self.matching_first_blob = matching_first_blob
                    self.matching_second_blob = matching_second_blob
                    if matching_first_blob:
                        self.window['-IFB-'].update(value = f"Installed FirstBlob: {matching_first_blob}")
                    else:
                        self.window['-IFB-'].update(value = f"Installed FirstBlob: {self.GetLocale('label_installed_blob1_none')}")

                    if matching_second_blob:
                        self.window['-ISB-'].update(value = f"Installed SecondBlob: {matching_second_blob}")
                    else:
                        self.window['-ISB-'].update(value = f"Installed SecondBlob: {self.GetLocale('label_installed_blob2_none')}")
                        self.matching_second_blob = None

                else:
                    # Handle case where either firstblob.bin or secondblob.bin is missing
                    self.matching_first_blob = None
                    self.matching_second_blob = None
                    self.window['-IFB-'].update(value = f"Installed FirstBlob: {self.GetLocale('label_installed_blob1_none')}")
                    self.window['-ISB-'].update(value = f"Installed SecondBlob: {self.GetLocale('label_installed_blob2_none')}")

            except Exception as e:
                self.window['-STATEMSG-'].Update(value = f"Error reading blob files: {e}")

        # After self.PopulateRowsFromDatabase(), add this:
        if self.load_from_database:
            try:
                if self.steam_datetime:
                    # Reset the matching blobs
                    matching_firstblob = None
                    matching_secondblob = None

                    target_ts = self.steam_datetime.timestamp()

                    # Find the matching secondblob (most recent <= target timestamp).
                    for timestamp, filename in reversed(self.SecondBlobDates):
                        if timestamp <= target_ts:
                            matching_secondblob = filename
                            break  # Stop after finding the most recent match

                    # Firstblob must be resolved from the chosen secondblob timestamp, not independently from target_ts.
                    if matching_secondblob:
                        matching_firstblob = self._resolve_first_blob_for_second(matching_secondblob)

                    # Update the -IFB- and -ISB- text elements in the window with the matched blob filenames
                    if matching_firstblob:
                        self.matching_first_blob = matching_firstblob
                        self.window['-IFB-'].update(value = f"Installed FirstBlob: {matching_firstblob}")
                    else:
                        self.matching_first_blob = None
                        self.window['-IFB-'].update(value = f"Installed FirstBlob: {self.GetLocale('label_installed_blob1_none')}")

                    if matching_secondblob:
                        self.matching_second_blob = matching_secondblob
                        self.window['-ISB-'].update(value = f"Installed SecondBlob: {matching_secondblob}")
                    else:
                        self.matching_second_blob = None
                        self.window['-ISB-'].update(value = f"Installed SecondBlob: {self.GetLocale('label_installed_blob2_none')}")

            except Exception as e:
                self.window['-STATEMSG-'].Update(value = f"Error matching blobs from database: {e}")

    def WindowRefresher(self):
        while True:
            sleep(self.WindowRefreshTime)
            self.window.refresh()

    def _on_treeview_button_press(self, event):
        try:
            treeview = self.window['-LIST-'].Widget
            region = treeview.identify_region(event.x, event.y)
            self._header_resize_in_progress = (region == 'separator')
            self._header_resize_dragged = False
        except Exception:
            self._header_resize_in_progress = False
            self._header_resize_dragged = False

    def _on_treeview_drag(self, event):
        if self._header_resize_in_progress:
            self._header_resize_dragged = True

    def _on_treeview_button_release(self, event):
        if self._header_resize_in_progress and self._header_resize_dragged:
            self._last_header_resize_at = monotonic()
        self._header_resize_in_progress = False
        self._header_resize_dragged = False

    def _should_ignore_header_sort_click(self):
        return (monotonic() - self._last_header_resize_at) < 0.35

    def set_heading_color(self, element, pressed_color, highlight_color, disabled_color):
        return None

    def DoesFileExist(self, file):
        try:
            with open(file, 'rb') as f:
                pass
        except FileNotFoundError:
            return False
        else:
            return True

    def _normalize_version_value(self, value):
        return str(value).strip()

    def _steamui_display_value(self, steamui_value):
        value = self._normalize_version_value(steamui_value)
        if value in ('06001000', '6001000'):
            return '0.6.0.0/1.0.0.0'
        if value in ('06101100', '6101100'):
            return '0.6.1.0/1.1.0.0'
        return value

    def _steamui_raw_value(self, steamui_value):
        value = self._normalize_version_value(steamui_value)
        if value == '0.6.0.0/1.0.0.0':
            return '06001000'
        if value == '0.6.1.0/1.1.0.0':
            return '06101100'
        if value == '6001000':
            return '06001000'
        if value == '6101100':
            return '06101100'
        return value

    def _canonical_blob_filename(self, blob_filename):
        if blob_filename is None:
            return ''
        return str(blob_filename).split(' - ', 1)[0].strip()

    def _is_beta2_platform_blob(self, blob_filename):
        canonical = self._canonical_blob_filename(blob_filename)
        return canonical in {
                'secondblob.bin.2003-01-13 23_03_03',
                'secondblob.bin.2003-01-20 03_39_01',
                'secondblob.bin.2003-06-10 05_01_47',
                'secondblob.bin.2003-07-08 15_01_47',
        }

    def _resolve_package_paths(self, packages_dir, steam_version, steamui_version, blob_filename = None):
        steam_value = self._normalize_version_value(steam_version)
        steamui_raw = self._steamui_raw_value(steamui_version)

        # Early 2002 beta package layout: files live in packagedir/betav1/steam_{0|1}.pkg
        beta_pkg_name = None
        if steamui_raw == '06001000':
            beta_pkg_name = 'steam_0.pkg'
        elif steamui_raw == '06101100':
            beta_pkg_name = 'steam_1.pkg'

        if beta_pkg_name is not None:
            beta_pkg_path = f'{packages_dir}/betav1/{beta_pkg_name}'
            steam_pkg_path = beta_pkg_path
            steamui_pkg_path = beta_pkg_path
        elif self._is_beta2_platform_blob(blob_filename):
            # For specific beta2 blobs, both checks are resolved strictly in packagedir/betav2.
            # Steam uses steam_<version>.pkg and SteamUI uses PLATFORM_<steamui_version>.pkg.
            steam_pkg_path = f'{packages_dir}/betav2/steam_{steam_value}.pkg'
            steamui_pkg_path = f'{packages_dir}/betav2/PLATFORM_{steamui_raw}.pkg'
        else:
            steam_pkg_path = f'{packages_dir}/steam_{steam_value}.pkg'
            steamui_pkg_path = f'{packages_dir}/steamui_{steamui_raw}.pkg'

        return steam_pkg_path, steamui_pkg_path

    def GetLocale(self, variable):
        try:
            return self.config[self.Lang][variable]
        except:
            print(f'MISSING LANGUAGE STRING: {self.Lang}_{variable}')
            return f'{self.Lang}_{variable}'

    def LogExport(self, message):
        if not self.ExportLoggingEnabled:
            return
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        line = f"[{timestamp}] {message}"
        print(line)
        try:
            with open(self.ExportLogPath, 'a', encoding = 'utf-8') as f:
                f.write(line + '\n')
        except Exception:
            pass

    def LogExportException(self, context, ex):
        if not self.ExportLoggingEnabled:
            return
        self.LogExport(f"{context}: {ex}")
        try:
            trace = traceback.format_exc()
            with open(self.ExportLogPath, 'a', encoding = 'utf-8') as f:
                f.write(trace + '\n')
        except Exception:
            pass

    def GetFirstBlobTo_Unpacked(self, SecondTarget):
        # Find SecondBlobDate from precomputed list
        SecondBlobDate = None
        for date, filename in self.SecondBlobDates:
            if filename == SecondTarget:
                SecondBlobDate = date
                break
        if SecondBlobDate is None:
            return False

        # Use bisect to find the matching firstblob
        idx = bisect_right(self.FirstBlobTimestamps, SecondBlobDate) - 1
        if idx >= 0:
            FirstTarget = self.FirstBlobDates[idx][1]
            return FirstTarget
        else:
            return False

    def _extract_datetime_token(self, filename, prefix):
        if not filename.startswith(prefix):
            raise ValueError(f"Unexpected blob filename format: {filename}")
        token = filename[len(prefix):].split(' - ', 1)[0].strip()
        if ' (' in token:
            token = token.split(' (', 1)[0].strip()
        datetime.strptime(token, '%Y-%m-%d %H_%M_%S')
        return token

    def _timestamp_for_blob_name(self, filename, is_first_blob):
        source = self.FirstBlobDates if is_first_blob else self.SecondBlobDates
        for ts, name in source:
            if name == filename:
                return ts
        return None

    def _resolve_first_blob_for_second(self, second_blob_name):
        second_ts = self._timestamp_for_blob_name(second_blob_name, is_first_blob = False)
        if second_ts is None:
            try:
                dt_token = self._extract_datetime_token(second_blob_name, 'secondblob.bin.')
                second_ts = datetime.strptime(dt_token, '%Y-%m-%d %H_%M_%S').timestamp()
            except Exception:
                second_ts = None

        if second_ts is None:
            self.LogExport(f"Failed to resolve secondblob timestamp for '{second_blob_name}'")
            return False

        idx = bisect_right(self.FirstBlobTimestamps, second_ts) - 1
        if idx >= 0:
            return self.FirstBlobDates[idx][1]
        self.LogExport(f"No firstblob <= secondblob timestamp for '{second_blob_name}'")
        return False

    def _find_secondblob_timeline_index(self, second_blob_name):
        if not second_blob_name:
            return None
        for idx, (_, name) in enumerate(self.SecondBlobDates):
            if name == second_blob_name:
                return idx

        canonical_name = self._get_export_filename(second_blob_name)
        for idx, (_, name) in enumerate(self.SecondBlobDates):
            if self._get_export_filename(name) == canonical_name:
                return idx
        return None

    def _find_row_index_by_second_blob(self, second_blob_name):
        if not second_blob_name:
            return None
        for idx, row in enumerate(self.Rows):
            if row[-1] == second_blob_name:
                return idx

        canonical_name = self._get_export_filename(second_blob_name)
        for idx, row in enumerate(self.Rows):
            if self._get_export_filename(row[-1]) == canonical_name:
                return idx
        return None

    def _get_installed_second_blob(self):
        if self.matching_second_blob:
            return self.matching_second_blob
        try:
            installed_text = self.window['-ISB-'].get()
        except Exception:
            return None

        prefix = self.GetLocale('label_installed_blob2')
        if installed_text.startswith(prefix):
            value = installed_text[len(prefix):].strip()
        elif ':' in installed_text:
            value = installed_text.split(':', 1)[1].strip()
        else:
            value = installed_text.strip()

        if not value or value == self.GetLocale('label_installed_blob2_none'):
            return None
        return value

    def _set_auto_swap_speed_text(self):
        try:
            speed = int(round(float(self.AutoSwapMultiplier)))
        except Exception:
            speed = 1
        self.window['-AUTOSWAP-SPEEDTXT-'].update(value = f"{speed}x")

    def _clip_text_to_pixels(self, widget, text, max_width_px):
        if max_width_px <= 0:
            return text

        try:
            metrics = QFontMetrics(widget.font())
        except Exception:
            return text

        if metrics.horizontalAdvance(text) <= max_width_px:
            return text

        ellipsis = '...'
        ellipsis_px = metrics.horizontalAdvance(ellipsis)
        if ellipsis_px >= max_width_px:
            return ellipsis

        target_px = max_width_px - ellipsis_px
        low = 0
        high = len(text)
        while low < high:
            mid = (low + high + 1) // 2
            if metrics.horizontalAdvance(text[:mid]) <= target_px:
                low = mid
            else:
                high = mid - 1

        return f"{text[:low].rstrip()}{ellipsis}"

    def UpdateSelectedTextElement(self):
        if self.row is not None and 0 <= self.row < len(self.Rows):
            full_text = f"{self.GetLocale('label_selected')} {self.Rows[self.row][-1]}"
        else:
            full_text = f"{self.GetLocale('label_selected')} {self.GetLocale('label_selected_none')}"

        display_text = full_text
        try:
            selected_widget = self.window['-SELECTTEXT-'].Widget
            available_px = selected_widget.width() - 10
            if available_px > 20:
                display_text = self._clip_text_to_pixels(selected_widget, full_text, available_px)
        except Exception:
            pass

        self.window['-SELECTTEXT-'].Update(value = display_text)

    def _format_countdown(self, seconds_remaining):
        total_seconds = max(0, int(seconds_remaining + 0.999))
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _update_auto_swap_countdown(self):
        text = 'Next swap: --:--:--'
        if self.AutoSwapEnabled and self.AutoSwapNextDue is not None and self.AutoSwapNextSecond is not None:
            remaining = max(0.0, self.AutoSwapNextDue - monotonic())
            text = f"Next swap: {self._format_countdown(remaining)}"

        if text != self.AutoSwapLastCountdownText:
            self.window['-AUTOSWAP-COUNTDOWN-'].update(value = text)
            self.AutoSwapLastCountdownText = text

    def _set_auto_swap_controls(self, enabled):
        self.window['-AUTOSWAP-ENABLE-'].update(value = enabled)

    def _stop_auto_swap(self, status_message = None, uncheck = True):
        self.AutoSwapEnabled = False
        self.AutoSwapCurrentSecond = None
        self.AutoSwapNextSecond = None
        self.AutoSwapNextDue = None
        self.AutoSwapIntervalSeconds = None
        self.AutoSwapScheduledAt = None
        if uncheck:
            self._set_auto_swap_controls(False)
        self._update_auto_swap_countdown()
        if status_message:
            self.window['-STATEMSG-'].Update(value = status_message)

    def _schedule_next_auto_swap(self, current_second_blob):
        current_idx = self._find_secondblob_timeline_index(current_second_blob)
        if current_idx is None:
            self._stop_auto_swap('Auto Swap stopped: installed blob is not in the loaded list.')
            return False

        if current_idx + 1 >= len(self.SecondBlobDates):
            self._stop_auto_swap('Auto Swap stopped: reached newest blob.')
            return False

        current_ts, current_name = self.SecondBlobDates[current_idx]
        next_ts, next_name = self.SecondBlobDates[current_idx + 1]

        delta_seconds = max(0.0, float(next_ts - current_ts))
        speed = max(1.0, float(self.AutoSwapMultiplier))
        real_seconds = delta_seconds / speed if delta_seconds > 0 else 0.0

        # Avoid tight-looping when two blobs share an identical timestamp.
        if real_seconds <= 0:
            real_seconds = 0.1

        self.AutoSwapCurrentSecond = current_name
        self.AutoSwapNextSecond = next_name
        self.AutoSwapIntervalSeconds = delta_seconds
        self.AutoSwapScheduledAt = monotonic()
        self.AutoSwapNextDue = self.AutoSwapScheduledAt + real_seconds
        self._update_auto_swap_countdown()
        return True

    def StartAutoSwap(self, slider_multiplier = None):
        if slider_multiplier is None:
            try:
                slider_multiplier = self.window['-AUTOSWAP-SPEED-'].get()
            except Exception:
                slider_multiplier = 1

        self.UpdateAutoSwapMultiplier(slider_multiplier)

        installed_second = self._get_installed_second_blob()
        if not installed_second:
            self._stop_auto_swap('Auto Swap needs an installed secondblob first.', uncheck = True)
            return False

        self.AutoSwapEnabled = True
        self._set_auto_swap_speed_text()
        if not self._schedule_next_auto_swap(installed_second):
            return False

        self.window['-STATEMSG-'].Update(value = f'Auto Swap enabled at {int(self.AutoSwapMultiplier)}x')
        return True

    def UpdateAutoSwapMultiplier(self, multiplier_value):
        old_multiplier = self.AutoSwapMultiplier
        try:
            multiplier = float(multiplier_value)
        except Exception:
            multiplier = 1.0
        self.AutoSwapMultiplier = min(10.0, max(1.0, multiplier))
        self._set_auto_swap_speed_text()

        if not self.AutoSwapEnabled or self.AutoSwapNextSecond is None:
            return

        now = monotonic()
        old_speed = max(1.0, float(old_multiplier))
        total_delta = max(0.0, float(self.AutoSwapIntervalSeconds or 0.0))

        if self.AutoSwapScheduledAt is None:
            elapsed_blob_time = 0.0
        else:
            elapsed_real = max(0.0, now - self.AutoSwapScheduledAt)
            elapsed_blob_time = min(total_delta, elapsed_real * old_speed)

        remaining_blob_time = max(0.0, total_delta - elapsed_blob_time)
        remaining_real_time = remaining_blob_time / self.AutoSwapMultiplier if remaining_blob_time > 0 else 0.1
        self.AutoSwapScheduledAt = now
        self.AutoSwapNextDue = now + max(0.1, remaining_real_time)
        self._update_auto_swap_countdown()

    def ProcessAutoSwap(self):
        if not self.AutoSwapEnabled:
            return
        if self.AutoSwapNextDue is None or self.AutoSwapNextSecond is None:
            return
        self._update_auto_swap_countdown()
        if monotonic() < self.AutoSwapNextDue:
            return

        next_blob = self.AutoSwapNextSecond
        row_idx = self._find_row_index_by_second_blob(next_blob)
        if row_idx is None:
            self._stop_auto_swap(f"Auto Swap stopped: couldn't find row for {next_blob}.")
            return

        try:
            self.window['-LIST-'].update(select_rows = [row_idx])
            self.row = row_idx
            self.multiple_rows = [row_idx]
            self.UpdateSelectedTextElement()
            self.window['-SWAP-'].Update(disabled = True)
            self.SwapBlobs()
        except Exception as ex:
            self._stop_auto_swap(f'Auto Swap failed: {ex}')
            return

        installed_after_swap = self.matching_second_blob or next_blob
        self.AutoSwapCurrentSecond = installed_after_swap
        self._schedule_next_auto_swap(installed_after_swap)

    def _build_first_blob_from_database(self, first_blob_name):
        try:
            _install_sqlalchemy_mariadb_adapter()
            from utilities.database import ccdb
            from utilities import blobs as util_blobs
            _install_sqlalchemy_mariadb_adapter(ccdb)
        except Exception as ex:
            self.LogExportException("Import error while loading firstblob DB builders", ex)
            raise RuntimeError("Unable to load DB firstblob builder modules. Check SQLAlchemy/PyMySQL dependencies.") from ex

        first_token = self._extract_datetime_token(first_blob_name, 'firstblob.bin.')
        self.LogExport(f"Building firstblob from DB using timestamp '{first_token}'")
        blob_dict = ccdb.construct_blob_from_ccdb(
                self.database_host,
                self.database_port,
                self.database_username,
                self.database_password,
                first_token
        )
        if not blob_dict:
            raise RuntimeError(f"Could not assemble firstblob from database for {first_blob_name}")
        data = util_blobs.blob_serialize(blob_dict)
        self.LogExport(f"Built firstblob '{first_blob_name}' ({len(data)} bytes)")
        return data

    def _build_second_blob_from_database(self, second_blob_name):
        try:
            _install_sqlalchemy_mariadb_adapter()
            from utilities import cdr_manipulator
            from utilities import blobs as util_blobs
            _install_sqlalchemy_mariadb_adapter(cdr_manipulator)
        except Exception as ex:
            self.LogExportException("Import error while loading secondblob DB builders", ex)
            raise RuntimeError("Unable to load DB secondblob builder modules. Check SQLAlchemy/PyMySQL dependencies.") from ex

        second_token = self._extract_datetime_token(second_blob_name, 'secondblob.bin.')
        cddb = "BetaContentDescriptionDB" if second_token < "2003-09-09 18_50_46" else "ContentDescriptionDB"
        self.LogExport(f"Building secondblob from DB '{cddb}' using timestamp '{second_token}'")
        blob_dict = cdr_manipulator.construct_blob_from_cddb(
                self.database_host,
                self.database_port,
                self.database_username,
                self.database_password,
                cddb,
                second_token,
                self.CacheFolder
        )
        if not blob_dict:
            raise RuntimeError(f"Could not assemble secondblob from database for {second_blob_name}")

        # Export uses legacy uncompressed 0x0150 blob format to match historic blob files.
        data = util_blobs.blob_serialize(blob_dict)
        self.LogExport(f"Built secondblob '{second_blob_name}' ({len(data)} bytes uncompressed)")
        return data

    def _get_export_filename(self, blob_name):
        # Database/file listings may append human-readable descriptions after " - ".
        # Export should keep only the canonical blob filename portion.
        return blob_name.split(' - ', 1)[0].strip()

    def _write_export_pair(self, export_path, first_name, second_name, first_data, second_data, first_ts = None, second_ts = None):
        first_export_name = self._get_export_filename(first_name)
        second_export_name = self._get_export_filename(second_name)

        first_path = export_path / first_export_name
        second_path = export_path / second_export_name

        with open(second_path, 'wb') as f:
            f.write(second_data)
        with open(first_path, 'wb') as f:
            f.write(first_data)

        if first_ts is not None:
            try:
                utime(first_path, (first_ts, first_ts))
            except Exception:
                pass
        if second_ts is not None:
            try:
                utime(second_path, (second_ts, second_ts))
            except Exception:
                pass

        self.LogExport(
                f"Wrote export pair: '{first_export_name}' ({len(first_data)} bytes), "
                f"'{second_export_name}' ({len(second_data)} bytes) -> {export_path}"
        )

    def ExportBlobPair(self, second_blob_name, export_path):
        self.LogExport(f"Starting export for '{second_blob_name}' (DB mode: {self.load_from_database})")
        first_blob_name = self._resolve_first_blob_for_second(second_blob_name)
        if not first_blob_name:
            raise RuntimeError(f"Unable to resolve firstblob for {second_blob_name}")

        first_ts = self._timestamp_for_blob_name(first_blob_name, is_first_blob = True)
        second_ts = self._timestamp_for_blob_name(second_blob_name, is_first_blob = False)

        if self.load_from_database:
            first_data = self._build_first_blob_from_database(first_blob_name)
            second_data = self._build_second_blob_from_database(second_blob_name)
            self._write_export_pair(export_path, first_blob_name, second_blob_name, first_data, second_data, first_ts, second_ts)
            return first_blob_name

        first_source = Path(f'{self.BlobsFolder}{first_blob_name}')
        second_source = Path(f'{self.BlobsFolder}{second_blob_name}')
        self.LogExport(f"Reading file blobs from '{first_source}' and '{second_source}'")
        first_export_name = self._get_export_filename(first_blob_name)
        second_export_name = self._get_export_filename(second_blob_name)
        second_dest = export_path / second_export_name
        first_dest = export_path / first_export_name

        with open(second_dest, 'wb') as f:
            with open(second_source, 'rb') as src:
                f.write(src.read())
        with open(first_dest, 'wb') as f:
            with open(first_source, 'rb') as src:
                f.write(src.read())

        copystat(second_source, second_dest)
        copystat(first_source, first_dest)
        return first_blob_name

    def PopulateRows(self):
        CurrentYear = None  # On slow drives we should start from a offset year.
        for item in self.BlobsFiles:
            if not item.is_file():
                continue
            filename = item.name
            if filename.startswith("secondblob.bin"):
                    # Extract datetime from filename
                    # Expected format: "secondblob.bin.YYYY-MM-DD HH_MM_SS - description"
                try:
                    # Remove 'secondblob.bin.' prefix
                    name_part = filename[len("secondblob.bin."):]
                    # Split by ' - ' to separate datetime and description
                    parts = name_part.split(' - ', 1)
                    date_str = parts[0]
                    # Parse datetime from filename
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d %H_%M_%S')
                    # Format the date and time separately
                    date_part = date_obj.strftime('%Y/%m/%d')
                    time_part = date_obj.strftime('%H:%M:%S')

                    # Combine with a larger space between date and time
                    date_display = f"{date_part}   {time_part}"  #
                    description = parts[1] if len(parts) > 1 else ""
                    # Check if custom
                    is_custom = '(C)' in filename
                    new_row = [
                            self.GetLocale('label_yes') if is_custom else self.GetLocale('label_no'),
                            '',  # Placeholder for Steam version
                            '',  # Placeholder for SteamUI version
                            date_display,
                            description,
                            filename
                    ]
                    self.SecondBlobs.append(filename)
                    self.SecondBlobDates.append((date_obj.timestamp(), filename))
                    self.Rows.append(new_row)
                except Exception as e:
                    print(f"Error parsing secondblob filename '{filename}': {e}")
                    continue
            elif filename.startswith("firstblob.bin"):
                # Handle firstblob
                try:
                    # Remove 'firstblob.bin.' prefix
                    name_part = filename[len("firstblob.bin."):]
                    # Remove ' (C)' suffix if present
                    if ' (' in name_part:
                        name_part = name_part.split(' (')[0]
                    # Parse datetime from filename
                    date_obj = datetime.strptime(name_part, '%Y-%m-%d %H_%M_%S')
                    self.FirstBlobs.append(filename)
                    self.FirstBlobDates.append((date_obj.timestamp(), filename))
                    # Update landmarks based on year
                    if CurrentYear != date_obj.year:
                        self.LandMarks[date_obj.year] = filename
                        CurrentYear = date_obj.year
                except Exception as e:
                    print(f"Error parsing firstblob filename '{filename}': {e}")
                    continue

        # After populating, sort the lists
        self.FirstBlobDates.sort()
        self.SecondBlobDates.sort()
        self.FirstBlobTimestamps = [date for date, filename in self.FirstBlobDates]


    def FirstBlobThread(self):
        print('Read FirstBlob information for table data..')

        for i in range(len(self.Rows)):
            current_second = self.Rows[i][-1]
            SecondBlobDate = self._timestamp_for_blob_name(current_second, is_first_blob = False)
            if SecondBlobDate is None:
                try:
                    second_token = self._extract_datetime_token(current_second, 'secondblob.bin.')
                    SecondBlobDate = datetime.strptime(second_token, '%Y-%m-%d %H_%M_%S').timestamp()
                except Exception:
                    SecondBlobDate = None

            if SecondBlobDate is None:
                self.Rows[i][1] = 'Unknown'
                self.Rows[i][2] = 'Unknown'
                continue

            # Find the insertion point for SecondBlobDate in the sorted FirstBlobTimestamps
            idx = bisect_right(self.FirstBlobTimestamps, SecondBlobDate) - 1

            # Ensure we have a valid index and that the FirstBlobDate is not newer than SecondBlobDate
            if idx >= 0:
                # Check if the found FirstBlobDate at idx is either an exact match or older than SecondBlobDate
                if abs(self.FirstBlobTimestamps[idx] - SecondBlobDate) < 1 or self.FirstBlobTimestamps[idx] <= SecondBlobDate:
                    FirstTarget = self.FirstBlobDates[idx][1]
                else:
                    FirstTarget = None
            else:
                FirstTarget = None
            # Read first blob
            if FirstTarget is not None:
                try:
                    Info = ReadBlob(f'{self.BlobsFolder}{FirstTarget}')
                except Exception as e:
                    print(f"Error reading firstblob '{FirstTarget}': {e}")
                    Info = None
            else:
                Info = None

            # Update the table row with Steam and SteamUI versions
            if Info is None:
                self.Rows[i][1] = 'Unknown'
                self.Rows[i][2] = 'Unknown'
            else:
                self.Rows[i][1] = self._normalize_version_value(Info[0])
                self.Rows[i][2] = self._steamui_display_value(Info[1])

        print('Done!')

    def SwapBlobs(self):
        if self.load_from_database:
            try:
                # Get the selected row data from the table, which should include both first and second blob filenames
                selected_row = self.Rows[self.row]

                # Assuming second blob filename is stored in the last column of the row
                second_blob = selected_row[-1]  # Extract secondblob filename from the row

                # Resolve firstblob using strict rule: most recent firstblob <= selected secondblob timestamp.
                first_blob_filename = self._resolve_first_blob_for_second(second_blob)
                if not first_blob_filename:
                    self.window['-STATEMSG-'].Update(value = self.GetLocale('label_swap_error2'))
                    return

                second_blob_timestamp = self._timestamp_for_blob_name(second_blob, is_first_blob = False)
                if second_blob_timestamp is None:
                    second_token = self._extract_datetime_token(second_blob, 'secondblob.bin.')
                    second_blob_timestamp = datetime.strptime(second_token, '%Y-%m-%d %H_%M_%S').timestamp()
                date_obj = datetime.fromtimestamp(second_blob_timestamp)

                # Modify steam_date and steam_time in emulator.ini if necessary
                emulator_ini_path = Path('emulator.ini')

                date_formatted = date_obj.strftime('%Y-%m-%d')
                time_formatted = date_obj.strftime('%H_%M_%S')

                steam_date_exists = False
                steam_time_exists = False

                # Store the content of the file
                file_content = ""

                # Open the original emulator.ini file, read its contents, and prepare new content
                if emulator_ini_path.exists():
                    with open(emulator_ini_path, 'r', encoding = 'latin-1') as original_file:
                        for line in original_file:
                            stripped_line = line.strip()

                            # Uncomment and update steam_date and steam_time if found (either commented or uncommented)
                            if stripped_line.startswith(';steam_date') or stripped_line.startswith('steam_date'):
                                file_content += f'steam_date={date_formatted}\n'
                                steam_date_exists = True
                            elif stripped_line.startswith(';steam_time') or stripped_line.startswith('steam_time'):
                                file_content += f'steam_time={time_formatted}\n'
                                steam_time_exists = True
                            else:
                                file_content += line

                # If steam_date or steam_time were not found, append them at the end
                if not steam_date_exists:
                    file_content += f'steam_date={date_formatted}\n'
                if not steam_time_exists:
                    file_content += f'steam_time={time_formatted}\n'

                # Write all changes at once
                with open(emulator_ini_path, 'w', encoding = 'latin-1') as new_file:
                    new_file.write(file_content)
                # Print the blobs used
                print(f"Swapping done: FirstBlob: {first_blob_filename}, SecondBlob: {second_blob}")

                # Now, update the GUI to show the installed first and second blobs
                self.matching_first_blob = copy.deepcopy(first_blob_filename)
                self.matching_second_blob = copy.deepcopy(second_blob)
                self.window['-IFB-'].update(value = f"Installed FirstBlob: {first_blob_filename}")  # Correctly display first blob
                self.window['-ISB-'].update(value = f"Installed SecondBlob: {second_blob}")  # Correctly display second blob
                self.LastSelectedFirstBlob = first_blob_filename
                # Update the status message
                self.window['-STATEMSG-'].Update(value = 'Steam date and time updated in emulator.ini')
                self.last_message_row = self.row

            except ValueError:
                self.window['-STATEMSG-'].Update(value = 'Invalid date format in the selected row')
            except IndexError:
                self.window['-STATEMSG-'].Update(value = 'Selected entry does not have corresponding FirstBlob or SecondBlob')
            except Exception as e:
                self.window['-STATEMSG-'].Update(value = f"An unexpected error occurred: {e}")

        else:
            # Inform user
            self.window['-STATEMSG-'].Update(value = self.GetLocale('label_swapping'))

            # Required variables
            SecondTarget = self.Rows[self.row][-1]
            SecondBlobDate = self._timestamp_for_blob_name(SecondTarget, is_first_blob = False)
            if SecondBlobDate is None:
                self.window['-STATEMSG-'].Update(value = self.GetLocale('label_swap_error2'))
                return

            # Use bisect to find the matching firstblob
            idx = bisect_right(self.FirstBlobTimestamps, SecondBlobDate) - 1
            if idx >= 0:
                FirstTarget = self.FirstBlobDates[idx][1]
                IsSolved = True
            else:
                FirstTarget = None
                IsSolved = False

            if not IsSolved or FirstTarget is None:
                print(f'Failed to resolve FirstBlob for: {SecondTarget}')
                self.window['-STATEMSG-'].Update(value = self.GetLocale('label_swap_error2'))
                return

            try:
                File1 = open(f'{self.BlobsFolder}{SecondTarget}', 'rb')
                File2 = open(f'{self.BlobsFolder}{FirstTarget}', 'rb')

                with open(f'{self.FilesFolder}secondblob.bin', 'wb') as f:
                    f.write(File1.read())
                    f.flush()
                    File1.close()

                with open(f'{self.FilesFolder}firstblob.bin', 'wb') as f:
                    f.write(File2.read())
                    f.flush()
                    File2.close()

                try:
                    copystat(f'{self.BlobsFolder}{SecondTarget}', f'{self.FilesFolder}secondblob.bin')
                    copystat(f'{self.BlobsFolder}{FirstTarget}', f'{self.FilesFolder}firstblob.bin')
                except:
                    show_info(self.GetLocale('label_error_text2'))
            except Exception as ex:
                self.window['-STATEMSG-'].Update(value = f"{self.GetLocale('label_swap_error3')}\r\n{ex}")
            else:
                try:
                    osremove(f"{self.CacheFolder}secondblob.bin")
                except:
                    pass

                # Print the blobs used
                print(f"Swapping done: FirstBlob: {FirstTarget}, SecondBlob: {SecondTarget}")

                self.window['-STATEMSG-'].Update(value = self.GetLocale('label_swap_success'))
                self.window['-IFB-'].update(value = f"{self.GetLocale('label_installed_blob1')} {FirstTarget}")
                self.window['-ISB-'].update(value = f"{self.GetLocale('label_installed_blob2')} {SecondTarget}")
                self.matching_first_blob = copy.deepcopy(FirstTarget)
                self.matching_second_blob = copy.deepcopy(SecondTarget)
                # Update the tracking attribute
                self.last_message_row = self.row

    def ConnectToDatabase(self):
        try:
            db_url = URL.create(
                    "mysql+pymysql",
                    username = self.database_username,
                    password = self.database_password,
                    host = self.database_host,
                    port = self.database_port
            )
            self.engine = create_engine(db_url)
            self.connection = self.engine.connect()
        except Exception as e:
            show_error(f"Failed to connect to database: {e}")
            sys.exit(1)

    def PopulateRowsFromDatabase(self):
        # Clear previous rows and blobs
        self.Rows = []
        self.FirstBlobDates = []
        self.SecondBlobDates = []
        self.SecondBlobs = []  # Add this line to initialize SecondBlobs
        configurations_dict = {}
        try:
            # Fetch filename, steam_pkg, steamui_pkg from configurations table
            configurations_query = text("""
                SELECT filename, steam_pkg, steamui_pkg, ccr_blobdatetime 
                FROM ClientConfigurationDB.configurations
            """)
            configurations_result = self.connection.execute(configurations_query).fetchall()

            # Populate configurations_dict with parsed data
            for row in configurations_result:
                filename = row[0]

                # Only process filenames that start with 'firstblob.bin'
                if filename.startswith('firstblob.bin'):
                    date_str = filename.replace('firstblob.bin.', '').replace(' (C)', '')
                    parts = date_str.split(' - ', 1)
                    date_time_str = parts[0].strip()  # e.g., '2004-04-01 00_17_09'
                    try:
                        # Parse datetime from filename
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d %H_%M_%S')
                        timestamp = date_obj.timestamp()
                        configurations_dict[filename] = {
                                'steam_pkg':  row[1],  # Steam package version
                                'steamui_pkg':row[2],  # Steam UI package version
                                'date':       date_obj  # Parsed date for matching
                        }
                        # Store date and filename for sorting
                        self.FirstBlobDates.append((timestamp, filename))
                    except ValueError:
                        # Skip entries with invalid date formats
                        print(f"Skipping invalid filename format: {filename}")
                        continue
        except Exception as e:
            show_error(f"Failed to query configurations table: {e}")
            exit(1)
        # Sort and initialize timestamps for blobs
        self.FirstBlobDates.sort()
        self.FirstBlobTimestamps = [date for date, _ in self.FirstBlobDates]

        # Fetch data from filename table (secondblob.bin)
        try:
            filename_query = text("""
                SELECT 
                    filename, 
                    blob_datetime, 
                    comments, 
                    is_custom 
                FROM 
                    BetaContentDescriptionDB.filenames
                UNION
                SELECT 
                    filename, 
                    blob_datetime, 
                    comments, 
                    is_custom 
                FROM 
                    ContentDescriptionDB.filenames;
            """)
            filename_result = self.connection.execute(filename_query).fetchall()

            for row in filename_result:
                filename = row[0] or ''
                blob_datetime = row[1] or ''
                comments = row[2] or ''
                is_custom = row[3] or 0

                # Initialize display values
                steam_version = 'Unknown'
                steamui_version = 'Unknown'
                date_display = 'Unknown'

                if filename.startswith('secondblob.bin.'):
                    date_str = filename.replace('secondblob.bin.', '')

                    try:
                        # Split to separate datetime and description
                        parts = date_str.split(' - ', 1)
                        date_time_str = parts[0].strip()  # e.g., '2004-04-01 00_17_09'

                        # Parse datetime
                        date_obj = datetime.strptime(date_time_str, '%Y-%m-%d %H_%M_%S')
                        timestamp = date_obj.timestamp()
                        # Find the most recent firstblob that is <= current date_obj
                        matching_firstblobs = [
                                (fname, config['date'])
                                for fname, config in configurations_dict.items()
                                if config['date'] <= date_obj
                        ]
                        if matching_firstblobs:
                            # Select the firstblob with the latest date
                            matching_firstblobs.sort(key = lambda x:x[1], reverse = True)
                            matched_fname = matching_firstblobs[0][0]
                            steam_version = configurations_dict[matched_fname]['steam_pkg']
                            steamui_version = configurations_dict[matched_fname]['steamui_pkg']
                            self.SecondBlobDates.append((timestamp, filename))
                        # Format date for display
                        date_part = date_obj.strftime('%Y/%m/%d')
                        time_part = date_obj.strftime('%H:%M:%S')

                        # Combine with a larger space between date and time
                        date_display = f"{date_part}   {time_part}"
                    except ValueError:
                        print(f"Invalid date format in filename: {filename}")
                else:
                    print(f"Filename does not start with 'secondblob.bin.': {filename}")
                if steam_version != "7" and steamui_version != "16":
                    steam_version_display = self._normalize_version_value(steam_version)
                    steamui_version_display = self._steamui_display_value(steamui_version)
                    # Append the processed row to self.Rows
                    new_row = [
                            'Yes' if is_custom else 'No',  # Custom label
                            steam_version_display,  # Steam version
                            steamui_version_display,  # SteamUI version
                            date_display,  # Date
                            comments,  # Description
                            filename
                    ]
                    self.Rows.append(new_row)
                    self.SecondBlobs.append(filename)  # Add this line to keep track of secondblob filenames
        except Exception as e:
            show_error(f"Failed to query filename table: {e}")
            exit(1)
        # After populating the table rows, find matching first and second blob based on steam_date and steam_time
        # Update the text at the top of the window after finding matching blobs

    def sort_table(self, col_index):
        reverse = self.sort_state[self.TopRow[col_index]]  # Get current sort order

        # Define which columns should be sorted numerically
        numerical_columns = ['Steam', 'SteamUI']

        # Get the column name based on index
        column_name = self.TopRow[col_index]

        if column_name in numerical_columns:
            # Sort numerically
            def numeric_key(x):
                try:
                    return float(x[col_index])
                except ValueError:
                    return 0  # Assign a default value if conversion fails

            self.Rows.sort(key = numeric_key, reverse = reverse)

        elif column_name == self.GetLocale('label_date'):  # Assuming 'label_date' corresponds to the Date column
            def date_key(x):
                try:
                    # Parse the date string into a datetime object for sorting
                    date_obj = datetime.strptime(x[col_index], '%Y/%m/%d %H:%M:%S')
                    return date_obj.timestamp()  # Return the timestamp for correct date sorting
                except ValueError:
                    return 0  # Return 0 for invalid dates

            # Sort by the parsed dates
            self.Rows.sort(key = date_key, reverse = reverse)

        elif column_name == self.GetLocale('label_description'):  # Assuming 'label_description' corresponds to 'Description'
            if not reverse:  # Ascending
                def description_asc_key(x):
                    # Entries with descriptions have priority (0), others have lower priority (1)
                    has_description = 0 if x[4].strip() else 1
                    try:
                        # Parse the date string back to a datetime object
                        date_obj = datetime.strptime(x[3], '%Y/%m/%d %H:%M:%S')
                        date_ts = date_obj.timestamp()
                    except ValueError:
                        date_ts = 0  # Assign a default timestamp if parsing fails
                    return (has_description, date_ts)

                self.Rows.sort(key = description_asc_key, reverse = False)

            else:  # Descending
                def description_desc_key(x):
                    try:
                        # Parse the date string back to a datetime object
                        date_obj = datetime.strptime(x[3], '%Y/%m/%d %H:%M:%S')
                        date_ts = date_obj.timestamp()
                    except ValueError:
                        date_ts = 0  # Assign a default timestamp if parsing fails

                    # Entries with descriptions should be at the bottom (1), others at the top (0)
                    has_description = 1 if x[4].strip() else 0
                    # Negative timestamp for descending sort
                    return (-date_ts, has_description)

                self.Rows.sort(key = description_desc_key, reverse = False)

        else:
            # Sort as strings for all other columns
            self.Rows.sort(key = lambda x:x[col_index], reverse = reverse)

        # Toggle the sort order for the next click
        self.sort_state[self.TopRow[col_index]] = not reverse

        # Update the table with the sorted values
        self.window['-LIST-'].update(values = self.Rows)


Manager = BlobManager()
Manager._set_auto_swap_speed_text()


# Date validation function (only accepts mm/dd/yyyy or yyyy)
def validate_date(date_str):
    # Match mm/dd/yyyy or yyyy
    date_pattern = r"^(\d{4}/\d{2}/\d{2}|\d{4})$"
    if re.match(date_pattern, date_str):
        try:
            # If it's just a year, it's valid
            if len(date_str) == 4:
                return True
            # If it's in mm/dd/yyyy format, try to parse it
            datetime.strptime(date_str, "%Y/%m/%d")
            return True
        except ValueError:
            return False


def select_row(row_index):
    # Highlight the row in the table
    Manager.window['-LIST-'].update(select_rows=[row_index])
    Manager.row = row_index
    Manager.UpdateSelectedTextElement()
    Manager.window['-SWAP-'].Update(disabled=False)


def search_date_func(search_date_str, start_index):
    try:
        # Normalize the search date to mm/dd/yyyy format or just year if yyyy
        if len(search_date_str) == 4:  # Year format
            search_year = search_date_str
        else:  # Full date format
            search_date = datetime.strptime(search_date_str, "%Y/%m/%d").strftime("%Y/%m/%d")
    except ValueError:
        return False  # Invalid date format

    closest_index = None
    closest_diff = None

    for i in range(start_index, len(Manager.Rows)):
        date_str = Manager.Rows[i][3]  # Assuming date is column index 3

        # Normalize the table date by stripping time and formatting as mm/dd/yyyy
        try:
            table_date = datetime.strptime(date_str.split(" ")[0], "%Y/%m/%d").strftime("%Y/%m/%d")
        except ValueError:
            continue  # Skip rows with invalid or incorrectly formatted dates

        # If searching by year
        if len(search_date_str) == 4 and search_year == table_date[0:4]:  # Compare year
            select_row(i)
            return True

        # Exact date match
        if len(search_date_str) != 4 and search_date == table_date:
            select_row(i)
            return True

        # Find the closest date if no exact match
        if len(search_date_str) != 4:  # Only for full date search
            search_date_obj = datetime.strptime(search_date_str, "%Y/%m/%d")
            table_date_obj = datetime.strptime(table_date, "%Y/%m/%d")
            diff = (table_date_obj - search_date_obj).days
            if diff > 0 and (closest_diff is None or diff < closest_diff):
                closest_diff = diff
                closest_index = i

    # If no exact match, select the closest future date
    if closest_index is not None:
        select_row(closest_index)
        return True

    return False


def search_description(search_phrase, start_index):
    pattern = re.escape(search_phrase).replace('\\*', '.*')
    regex = re.compile(pattern, re.IGNORECASE)

    for i in range(start_index, len(Manager.Rows)):
        description = Manager.Rows[i][4]  # Assuming description is column index 4
        if regex.search(description):
            select_row(i)
            return True

    return False


def custom_popup(message):
    show_info(message, "Alert", Manager.window if 'Manager' in globals() else None)


def open_search_dialog():
    dialog = QDialog(Manager.window)
    dialog.setWindowTitle("Search")
    dialog.setModal(True)
    layout = QVBoxLayout(dialog)
    tabs = QTabWidget()
    layout.addWidget(tabs)

    desc_tab = QWidget()
    desc_layout = QVBoxLayout(desc_tab)
    desc_label = QLabel('Type in a search phrase (use * as a wildcard):')
    desc_input = NineSliceLineEdit()
    desc_btns = QHBoxLayout()
    desc_search = NineSliceButton("Search")
    desc_cancel = NineSliceButton("Cancel")
    for btn in (desc_search, desc_cancel):
        btn.setFixedSize(80, 24)
        btn.setStyleSheet(BTN_STYLE)
        desc_btns.addWidget(btn)
    desc_layout.addWidget(desc_label)
    desc_layout.addWidget(desc_input)
    desc_layout.addLayout(desc_btns)

    date_tab = QWidget()
    date_layout = QVBoxLayout(date_tab)
    date_label = QLabel('Type a date to search (formats: yyyy/mm/dd or yyyy):')
    date_input = NineSliceLineEdit()
    date_btns = QHBoxLayout()
    date_search = NineSliceButton("Search")
    date_cancel = NineSliceButton("Cancel")
    for btn in (date_search, date_cancel):
        btn.setFixedSize(80, 24)
        btn.setStyleSheet(BTN_STYLE)
        date_btns.addWidget(btn)
    date_layout.addWidget(date_label)
    date_layout.addWidget(date_input)
    date_layout.addLayout(date_btns)

    tabs.addTab(desc_tab, "Description Search")
    tabs.addTab(date_tab, "Date Search")
    dialog.setStyleSheet("QDialog { background: #4c5844; } QLabel { color: #ffffff; font-family: Tahoma; font-weight: bold; } QTabWidget::pane { border: 1px solid #292e23; } QTabBar::tab { background: #5a6a50; color: #ffffff; padding: 4px 10px; } QTabBar::tab:selected { background: #6a6f68; }")

    state = {'index': 0, 'no_more': False}

    def run_desc():
        phrase = desc_input.text()
        if state['no_more']:
            state['index'] = 0
            state['no_more'] = False
        found = search_description(phrase, state['index'])
        if found:
            state['index'] = Manager.row + 1
        else:
            custom_popup('No more matches found.')
            state['no_more'] = True
            state['index'] = 0

    def run_date():
        date_value = date_input.text()
        state['index'] = 0
        state['no_more'] = False
        if validate_date(date_value):
            found = search_date_func(date_value, state['index'])
            if found:
                state['index'] = Manager.row + 1
            else:
                custom_popup('No more matches found.')
                state['no_more'] = True
        else:
            custom_popup('Invalid date format. Please enter yyyy/mm/dd or yyyy.')

    desc_search.clicked.connect(run_desc)
    desc_input.returnPressed.connect(run_desc)
    date_search.clicked.connect(run_date)
    date_input.returnPressed.connect(run_date)
    desc_cancel.clicked.connect(dialog.close)
    date_cancel.clicked.connect(dialog.close)
    dialog.resize(420, 160)
    desc_input.setFocus()
    dialog.exec_()


def open_settings_dialog():
    custom_popup('Settings are not exposed in this Blob Manager build.')


# Function to handle selection changes
# Function to handle selection changes
def update_selected_text():
    if Manager.row is not None and Manager.row >= 0:
        Manager.UpdateSelectedTextElement()
        Manager.window['-SWAP-'].Update(disabled=False)
        # Clear the message only if a different row is selected
        if Manager.last_message_row != Manager.row:
            Manager.window['-STATEMSG-'].Update(value='')
            Manager.last_message_row = Manager.row

# Event loop with adjusted event handling
while True:
    event, values = Manager.window.read(Manager.WindowUpdateTime)
    if event == '__TIMEOUT__':
        Manager.ProcessAutoSwap()
        if Manager.row is not None and Manager.row >= 0:
            Manager.UpdateSelectedTextElement()

    if event == 'Exit':
        break
    elif event == '-SEARCH-' or event == 'CTRL+F' or event == '^f':
        open_search_dialog()
    elif event == '-SETTINGS-':
        open_settings_dialog()
    elif event == '-AUTOSWAP-SPEED-':
        Manager.UpdateAutoSwapMultiplier(values.get('-AUTOSWAP-SPEED-', 1))
    elif event == '-AUTOSWAP-ENABLE-':
        if values.get('-AUTOSWAP-ENABLE-', False):
            Manager.StartAutoSwap(values.get('-AUTOSWAP-SPEED-', 1))
        else:
            Manager._stop_auto_swap('Auto Swap disabled.', uncheck = False)
    elif isinstance(event, tuple):
        if event[0] == '-LIST-' and '+CLICKED+' in event[1]:
            row, col = event[2]
            if row == -1:  # Header row is clicked
                if Manager._should_ignore_header_sort_click():
                    continue
                Manager.sort_table(col)
            else:
                Manager.row = row
                update_selected_text()  # Update text when a row is clicked

        # Update multiple rows when using arrow keys or clicking
        if '-LIST-' in event and '-LIST-' in values and len(values['-LIST-']) > 0:
            Manager.multiple_rows = values['-LIST-'].copy()
            Manager.row = values['-LIST-'][0]
            update_selected_text()

    # Custom key handling for Up and Down arrows
    elif event == 'UP_KEY' or event == 'DOWN_KEY':
        current_index = Manager.row if Manager.row is not None else 0
        new_index = current_index - 1 if event == 'UP_KEY' else current_index + 1
        new_index = max(0, min(new_index, len(Manager.Rows) - 1))

        # Update the selected row in the list
        Manager.window['-LIST-'].update(select_rows = [new_index])
        Manager.row = new_index

        update_selected_text()  # Update the text display after moving with arrows

    elif '-SWAP-' == event:
        Manager.window['-SWAP-'].Update(disabled=True)
        Manager.SwapBlobs()
        if Manager.AutoSwapEnabled:
            Manager._schedule_next_auto_swap(Manager.matching_second_blob)
        continue
    if '-LIST- Double' in event:
        if values['-LIST-']:
            Manager.Selected = values['-LIST-'][0]
            Manager.window['-SWAP-'].Update(disabled=True)
            Manager.SwapBlobs()
            if Manager.AutoSwapEnabled:
                Manager._schedule_next_auto_swap(Manager.matching_second_blob)
        continue
    elif '-SELECTTEXT- Double' in event:
        try:
            second_blob = Manager.Rows[Manager.row][-1]
            matching_first_blob = Manager._resolve_first_blob_for_second(second_blob)
            if not matching_first_blob:
                matching_first_blob = "Unknown"

            out = f'SecondBlob: {second_blob}\r\nFirstBlob: {matching_first_blob}'

            clipboardcopy(out)
            Manager.window['-STATEMSG-'].Update(value=Manager.GetLocale('label_copyclip'))
        except:
            pass
        continue

    elif '-SELECTTEXT-' in event:
        try:
            clipboardcopy(Manager.Rows[Manager.row][-1])
            Manager.window['-STATEMSG-'].Update(value=Manager.GetLocale('label_copyclip'))
        except:
            pass
    elif 'Extract' in event or 'Export Blob' in event:
        folder_selected = QFileDialog.getExistingDirectory(Manager.window, "Select extraction destination")
        if folder_selected == '' or folder_selected == ():
            print('cancel')
        else:
            ThePath = Path(folder_selected)

            if ThePath.is_dir():
                selected_rows = []
                if values.get('-LIST-'):
                    selected_rows = values['-LIST-'].copy()
                elif Manager.multiple_rows:
                    selected_rows = Manager.multiple_rows.copy()
                elif Manager.row is not None:
                    selected_rows = [Manager.row]

                if not selected_rows:
                    Manager.window['-STATEMSG-'].Update(value = 'No blob selected to export.')
                    continue

                exported_count = 0
                total_count = len(selected_rows)
                failures = []
                for row in selected_rows:
                    second_name = Manager.Rows[row][-1]

                    try:
                        first_name = Manager.ExportBlobPair(second_name, ThePath)
                        print(f"Exported -> FirstBlob: {first_name}, SecondBlob: {second_name}, Path: {ThePath}")
                        exported_count += 1
                    except Exception as ex:
                        Manager.LogExportException(f"Extraction failed for '{second_name}'", ex)
                        failures.append(f"{second_name}: {ex}")

                if exported_count == total_count:
                    Manager.window['-STATEMSG-'].Update(value = Manager.GetLocale('label_extract_success'))
                elif exported_count > 0:
                    if Manager.ExportLoggingEnabled:
                        Manager.window['-STATEMSG-'].Update(
                                value = f"Exported {exported_count}/{total_count} blob set(s). See {Manager.ExportLogPath.name} for errors."
                        )
                    else:
                        Manager.window['-STATEMSG-'].Update(
                                value = f"Exported {exported_count}/{total_count} blob set(s)."
                        )
                else:
                    if failures:
                        first_error = failures[0]
                        if Manager.ExportLoggingEnabled:
                            Manager.window['-STATEMSG-'].Update(
                                    value = f"{Manager.GetLocale('label_extract_failure')} {first_error} (details in {Manager.ExportLogPath.name})"
                            )
                        else:
                            Manager.window['-STATEMSG-'].Update(
                                    value = f"{Manager.GetLocale('label_extract_failure')} {first_error}"
                            )
                    else:
                        Manager.window['-STATEMSG-'].Update(value = Manager.GetLocale('label_extract_failure'))
            else:
                custom_popup(Manager.GetLocale('label_error_text3'))

if Manager.load_from_database:
    # Close database connection if open, with error handling
    if hasattr(Manager, 'connection') and Manager.connection:
        try:
            Manager.connection.close()
        except OperationalError:
            print("Database connection could not be closed gracefully. Connection was already lost.")
        except Exception as e:
            print(f"An unexpected error occurred while closing the database connection: {e}")

    # Dispose of the engine if it's open, with error handling
    if hasattr(Manager, 'engine') and Manager.engine:
        try:
            Manager.engine.dispose()
        except OperationalError:
            print("Database engine disposal encountered an issue. Connection was already lost.")
        except Exception as e:
            print(f"An unexpected error occurred while disposing of the database engine: {e}")

# Close the GUI window
Manager.window.close()
