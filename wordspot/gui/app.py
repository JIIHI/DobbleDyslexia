"""Application start-up: fonts, theme and the main window."""

from __future__ import annotations

import sys

from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication

from wordspot import APP_ID, APP_NAME
from wordspot.db import Database
from wordspot.paths import data_dir, fonts_dir

STYLE_SHEET = """
* { font-size: 13px; }
QWidget#central, QMainWindow { background: #f4f5fb; }
QFrame#header { background: #4f46e5; }
QLabel#appTitle { color: white; font-size: 24px; font-weight: 700; }
QLabel#appSubtitle { color: #e0e7ff; font-size: 13px; }
QFrame#panel { background: white; border: none; }
QScrollArea#stylePanel { border: none; background: white; }
QLabel#sectionTitle { font-size: 15px; font-weight: 700; color: #1e1b4b; padding-top: 4px; }
QLabel#fieldLabel { color: #475569; font-size: 12px; font-weight: 600; }
QLabel#hint { color: #64748b; font-size: 12px; }
QLabel#summary { color: #1e293b; font-size: 14px; font-weight: 600; }
QLabel#deckTitle { font-size: 22px; font-weight: 700; color: #1e1b4b; }
QFrame#actionBar { background: white; border-top: 1px solid #e2e8f0; }

QPushButton {
    background: #eef2ff; color: #3730a3; border: 1px solid #c7d2fe;
    border-radius: 8px; padding: 7px 14px; font-weight: 600;
}
QPushButton:hover { background: #e0e7ff; }
QPushButton:pressed { background: #c7d2fe; }
QPushButton:disabled { background: #f1f5f9; color: #94a3b8; border-color: #e2e8f0; }
QPushButton#primary, QPushButton#bigPrimary {
    background: #4f46e5; color: white; border: 1px solid #4338ca;
}
QPushButton#primary:hover, QPushButton#bigPrimary:hover { background: #4338ca; }
QPushButton#primary:disabled, QPushButton#bigPrimary:disabled { background: #a5b4fc; border-color: #a5b4fc; }
QPushButton#bigPrimary, QPushButton#big { font-size: 15px; padding: 11px 22px; border-radius: 10px; }
QPushButton#danger { color: #b91c1c; background: #fef2f2; border-color: #fecaca; }
QPushButton#danger:hover { background: #fee2e2; }
QPushButton#danger:disabled { background: #f1f5f9; color: #94a3b8; border-color: #e2e8f0; }
QPushButton#flat { background: transparent; color: white; border: 1px solid #a5b4fc; }
QPushButton#flat:hover { background: #4338ca; }

QComboBox, QLineEdit {
    background: white; border: 1px solid #cbd5e1; border-radius: 7px; padding: 6px 8px;
    min-height: 18px;
}
QComboBox:focus, QLineEdit:focus, QPlainTextEdit:focus { border: 2px solid #6366f1; }
QComboBox QAbstractItemView { background: white; selection-background-color: #e0e7ff;
    selection-color: #1e1b4b; }

QListWidget#deckList { border: none; background: white; font-size: 14px; outline: 0; }
QListWidget#deckList::item { padding: 8px 8px; border-radius: 8px; color: #1e293b; }
QListWidget#deckList::item:selected { background: #e0e7ff; color: #312e81; font-weight: 600; }
QListWidget#deckList::item:hover:!selected { background: #f1f5f9; }

QListWidget#cardView { background: #f4f5fb; border: none; outline: 0; }
QListWidget#cardView::item { border-radius: 12px; padding: 4px; color: #475569; }
QListWidget#cardView::item:selected { background: #e0e7ff; color: #312e81; }
QListWidget#cardView::item:hover:!selected { background: #eceefe; }

QPlainTextEdit#wordsEdit {
    background: white; border: 1px solid #cbd5e1; border-radius: 10px; padding: 8px;
    font-size: 16px;
}
QTabWidget::pane { border: none; }
QTabBar::tab { padding: 8px 20px; font-size: 14px; font-weight: 600; color: #64748b;
    border: none; border-bottom: 3px solid transparent; background: transparent; }
QTabBar::tab:selected { color: #4f46e5; border-bottom: 3px solid #4f46e5; }
QToolButton#collapseButton { border: none; font-size: 15px; font-weight: 700; color: #1e1b4b;
    padding: 4px 0; text-align: left; background: transparent; }
QProgressBar { border: 1px solid #cbd5e1; border-radius: 6px; text-align: center; height: 18px;
    background: #f1f5f9; }
QProgressBar::chunk { background: #6366f1; border-radius: 5px; }
QSlider::groove:horizontal { height: 6px; background: #e2e8f0; border-radius: 3px; }
QSlider::sub-page:horizontal { background: #818cf8; border-radius: 3px; }
QSlider::handle:horizontal { background: #4f46e5; width: 18px; height: 18px; margin: -6px 0;
    border-radius: 9px; }
QSplitter::handle { background: #e2e8f0; width: 1px; }
QFrame#divider { color: #e2e8f0; }
QListWidget { background: white; border: 1px solid #e2e8f0; border-radius: 8px; }
"""


def load_fonts() -> str:
    family = ""
    for path in sorted(fonts_dir().glob("*.[ot]tf")):
        fid = QFontDatabase.addApplicationFont(str(path))
        if fid >= 0 and path.name.startswith("Lexend"):
            family = QFontDatabase.applicationFontFamilies(fid)[0]
    return family


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    QApplication.setApplicationName(APP_NAME)
    QApplication.setOrganizationName(APP_ID)
    app = QApplication(argv)
    app.setStyle("Fusion")
    family = load_fonts()
    if family:
        app.setFont(QFont(family, 10))
    app.setStyleSheet(STYLE_SHEET)
    icon = data_dir() / "icon.png"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))

    from wordspot.gui.main_window import MainWindow
    window = MainWindow(Database())
    window.show()
    return app.exec()
