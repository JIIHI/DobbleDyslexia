"""Bubble Designer: grow new bubble layouts with the organic growth
simulation, and choose which saved layouts the cards may use."""

from __future__ import annotations

import random

from PySide6.QtCore import QPointF, QSize, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFrame, QGridLayout, QHBoxLayout,
                               QInputDialog, QLabel, QListWidget, QListWidgetItem, QMessageBox,
                               QPushButton, QSizePolicy, QSlider, QVBoxLayout, QWidget)

from wordspot.db import Database
from wordspot.layout import DEFAULT_FILL, Layout, grow
from wordspot.gui.widgets import LabeledCombo, ToggleSwitch, section_title

BUBBLE_COLOURS = ["#c7d2fe", "#fecaca", "#bbf7d0", "#e9d5ff", "#fed7aa", "#99f6e4",
                  "#fbcfe8", "#fde68a"]


def paint_layout(p: QPainter, circles, cx: float, cy: float, radius: float,
                 numbered: bool = False) -> None:
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor("#2b2b2b"), max(1.0, radius * 0.012)))
    p.setBrush(QColor("#fdf6e3"))
    p.drawEllipse(QPointF(cx, cy), radius, radius)
    p.setPen(QPen(QColor("#64748b"), max(0.8, radius * 0.006)))
    for i, (x, y, r) in enumerate(circles):
        p.setBrush(QBrush(QColor(BUBBLE_COLOURS[i % len(BUBBLE_COLOURS)])))
        p.drawEllipse(QPointF(cx + x * radius, cy + y * radius), r * radius, r * radius)
    if numbered:
        order = sorted(range(len(circles)), key=lambda i: -circles[i][2])
        p.setPen(QColor("#334155"))
        f = p.font()
        for rank, i in enumerate(order):
            x, y, r = circles[i]
            f.setPixelSize(max(9, int(r * radius * 0.45)))
            p.setFont(f)
            p.drawText(int(cx + x * radius - 40), int(cy + y * radius - 40), 80, 80,
                       Qt.AlignCenter, str(rank + 1))


def layout_icon(circles, size: int = 96) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    paint_layout(p, circles, size / 2, size / 2, size / 2 - 2)
    p.end()
    return QIcon(pix)


class LayoutCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.circles: list = []
        self.setMinimumSize(360, 360)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_circles(self, circles) -> None:
        self.circles = circles
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        side = min(self.width(), self.height()) - 16
        paint_layout(p, self.circles, self.width() / 2, self.height() / 2, side / 2,
                     numbered=True)


class BubbleDesigner(QDialog):
    def __init__(self, db: Database, per_card: int = 8, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Bubble Designer")
        self.resize(980, 640)
        self._frames = None
        self._current: Layout | None = None
        self.changed = False

        root = QHBoxLayout(self)
        root.setSpacing(18)

        # ---- left: grow a new layout
        left = QVBoxLayout()
        left.addWidget(section_title("Grow new bubbles"))
        intro = QLabel("Bubbles start as tiny seeds and grow until the card is full. "
                       "Crowded bubbles grow more slowly and push each other apart.")
        intro.setWordWrap(True)
        intro.setObjectName("hint")
        left.addWidget(intro)

        self.count = LabeledCombo("Number of bubbles (words per card)",
                                  {"8 bubbles": 8, "6 bubbles": 6, "4 bubbles": 4, "3 bubbles": 3})
        self.count.set_value(per_card)
        self.count.changed.connect(self._count_changed)
        left.addWidget(self.count)

        grid = QGridLayout()
        grid.setVerticalSpacing(4)
        self.variety = QSlider(Qt.Horizontal)
        self.variety.setRange(0, 150)
        self.variety.setValue(100)
        self.fill = QSlider(Qt.Horizontal)
        self.fill.setRange(0, 100)
        self.fill.setValue(DEFAULT_FILL)
        for row, (title, low, high, slider) in enumerate([
                ("Bubble sizes", "All the same", "Very mixed", self.variety),
                ("How full", "Roomy", "Packed", self.fill)]):
            lbl = QLabel(title)
            lbl.setObjectName("fieldLabel")
            grid.addWidget(lbl, row * 2, 0, 1, 3)
            grid.addWidget(QLabel(low), row * 2 + 1, 0)
            grid.addWidget(slider, row * 2 + 1, 1)
            grid.addWidget(QLabel(high), row * 2 + 1, 2)
        left.addLayout(grid)

        self.animate = ToggleSwitch("Watch them grow")
        self.animate.setChecked(True)
        left.addWidget(self.animate)

        self.canvas = LayoutCanvas()
        left.addWidget(self.canvas, 1)
        self.stats = QLabel(" ")
        self.stats.setObjectName("hint")
        self.stats.setAlignment(Qt.AlignCenter)
        left.addWidget(self.stats)

        buttons = QHBoxLayout()
        self.grow_btn = QPushButton("Grow bubbles")
        self.grow_btn.setObjectName("primary")
        self.grow_btn.clicked.connect(self.start_grow)
        self.save_btn = QPushButton("Save this layout")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_current)
        buttons.addWidget(self.grow_btn)
        buttons.addWidget(self.save_btn)
        left.addLayout(buttons)
        root.addLayout(left, 3)

        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setObjectName("divider")
        root.addWidget(line)

        # ---- right: saved layouts
        right = QVBoxLayout()
        self.saved_title = section_title("Saved layouts")
        right.addWidget(self.saved_title)
        hint = QLabel("Cards are made from the ticked layouts. Untick any you don't like. "
                      "Built-in layouts can be unticked but not deleted.")
        hint.setWordWrap(True)
        hint.setObjectName("hint")
        right.addWidget(hint)
        self.list = QListWidget()
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setIconSize(QSize(96, 96))
        self.list.setGridSize(QSize(124, 136))
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setMovement(QListWidget.Static)
        self.list.setWordWrap(True)
        self.list.itemChanged.connect(self._item_changed)
        self.list.currentItemChanged.connect(self._item_selected)
        right.addWidget(self.list, 1)
        row = QHBoxLayout()
        tick_all = QPushButton("Tick all")
        tick_all.clicked.connect(lambda: self._tick_all(True))
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self.delete_selected)
        row.addWidget(tick_all)
        row.addStretch(1)
        row.addWidget(self.delete_btn)
        right.addLayout(row)
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(self.reject)
        close.accepted.connect(self.accept)
        right.addWidget(close)
        root.addLayout(right, 2)

        self.timer = QTimer(self)
        self.timer.setInterval(15)
        self.timer.timeout.connect(self._next_frame)
        self._load_list()
        self.start_grow()

    # ----------------------------------------------------------- growing
    def _count_changed(self) -> None:
        self._load_list()
        self.start_grow()

    def start_grow(self) -> None:
        n = self.count.value()
        variety = self.variety.value() / 100
        fill = self.fill.value()
        self._frames = grow(n, variety, fill, seed=random.randint(0, 10**9))
        self._current = None
        self._last_frame = []
        self.save_btn.setEnabled(False)
        self._params = (variety, fill)
        if self.animate.isChecked():
            self.grow_btn.setEnabled(False)
            self.timer.start()
        else:
            last = None
            for last in self._frames:
                pass
            self._finish(last)

    def _next_frame(self) -> None:
        try:
            for _ in range(3):
                self._last_frame = next(self._frames)
        except StopIteration:
            # The generator's last frame is the cleaned-up final layout.
            self._finish(self._last_frame)
            return
        self.canvas.set_circles(self._last_frame)

    def _finish(self, circles) -> None:
        self.timer.stop()
        self.grow_btn.setEnabled(True)
        self._current = Layout(circles=list(circles), variety=self._params[0],
                               fill=int(self._params[1]))
        self.canvas.set_circles(self._current.circles)
        self.stats.setText(
            f"Biggest bubble is {self._current.size_ratio:.1f}x the smallest  ·  "
            f"bubbles cover {self._current.coverage * 100:.0f}% of the card")
        self.save_btn.setEnabled(self._current.is_valid(1e-4))

    def save_current(self) -> None:
        if not self._current:
            return
        existing = len([l for l in self.db.list_layouts(self._current.count) if not l.builtin])
        name, ok = QInputDialog.getText(self, "Save layout", "Name for this layout:",
                                        text=f"My layout {existing + 1}")
        if not ok:
            return
        self.db.add_layout(self._current, name.strip() or f"My layout {existing + 1}")
        self.changed = True
        self.save_btn.setEnabled(False)
        self._load_list(select_last=True)

    # ------------------------------------------------------- saved list
    def _load_list(self, select_last: bool = False) -> None:
        n = self.count.value()
        self.list.blockSignals(True)
        self.list.clear()
        layouts = self.db.list_layouts(n)
        for lay in layouts:
            item = QListWidgetItem(layout_icon(lay.circles), lay.name)
            item.setData(Qt.UserRole, lay)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if lay.enabled else Qt.Unchecked)
            item.setToolTip(f"{lay.name}\nBiggest bubble {lay.size_ratio:.1f}x the smallest"
                            + ("\nBuilt-in" if lay.builtin else ""))
            self.list.addItem(item)
        self.list.blockSignals(False)
        ticked = sum(l.enabled for l in layouts)
        self.saved_title.setText(f"Saved layouts - {n} bubbles ({ticked} of {len(layouts)} in use)")
        if select_last and self.list.count():
            self.list.setCurrentRow(self.list.count() - 1)
        self._item_selected(self.list.currentItem(), None)

    def _item_changed(self, item: QListWidgetItem) -> None:
        lay: Layout = item.data(Qt.UserRole)
        self.db.set_layout_enabled(lay.id, item.checkState() == Qt.Checked)
        self.changed = True
        self._load_list()

    def _item_selected(self, item, _prev) -> None:
        lay = item.data(Qt.UserRole) if item else None
        self.delete_btn.setEnabled(bool(lay and not lay.builtin))
        if lay and not self.timer.isActive():
            self.canvas.set_circles(lay.circles)
            self.stats.setText(f"{lay.name}  ·  biggest bubble is {lay.size_ratio:.1f}x the smallest")
            self.save_btn.setEnabled(False)

    def _tick_all(self, on: bool) -> None:
        for lay in self.db.list_layouts(self.count.value()):
            self.db.set_layout_enabled(lay.id, on)
        self.changed = True
        self._load_list()

    def delete_selected(self) -> None:
        item = self.list.currentItem()
        if not item:
            return
        lay: Layout = item.data(Qt.UserRole)
        if lay.builtin:
            return
        if QMessageBox.question(self, "Delete layout", f"Delete '{lay.name}'?") == QMessageBox.Yes:
            self.db.delete_layout(lay.id)
            self.changed = True
            self._load_list()

    def closeEvent(self, e) -> None:  # noqa: N802
        self.timer.stop()
        super().closeEvent(e)
