"""Small reusable Qt widgets and helpers."""

from __future__ import annotations

from PIL import Image
from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QSizePolicy,
                               QToolButton, QVBoxLayout, QWidget)

ACCENT = QColor("#4f46e5")


def pil_to_qimage(img: Image.Image) -> QImage:
    img = img.convert("RGBA")
    data = img.tobytes("raw", "RGBA")
    return QImage(data, img.width, img.height, img.width * 4, QImage.Format_RGBA8888).copy()


def pil_to_pixmap(img: Image.Image) -> QPixmap:
    return QPixmap.fromImage(pil_to_qimage(img))


class ToggleSwitch(QCheckBox):
    """An iOS-style on/off switch with a text label."""

    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self._pos = 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(120)
        self._anim.setEasingCurve(QEasingCurve.InOutQuad)
        self.toggled.connect(self._start_anim)

    def _start_anim(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def setChecked(self, checked: bool) -> None:  # noqa: N802 (Qt naming)
        super().setChecked(checked)
        self._pos = 1.0 if checked else 0.0
        self.update()

    def get_knob(self) -> float:
        return self._pos

    def set_knob(self, value: float) -> None:
        self._pos = value
        self.update()

    knob = Property(float, get_knob, set_knob)

    def sizeHint(self) -> QSize:  # noqa: N802
        fm = self.fontMetrics()
        return QSize(52 + fm.horizontalAdvance(self.text()) + 10, max(28, fm.height() + 8))

    def hitButton(self, pos) -> bool:  # noqa: N802
        return self.rect().contains(pos)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        h = 24
        w = 44
        y = (self.height() - h) / 2
        track = QRectF(0, y, w, h)
        off = QColor("#cbd5e1")
        colour = QColor(
            int(off.red() + (ACCENT.red() - off.red()) * self._pos),
            int(off.green() + (ACCENT.green() - off.green()) * self._pos),
            int(off.blue() + (ACCENT.blue() - off.blue()) * self._pos))
        if not self.isEnabled():
            colour = QColor("#e2e8f0")
        p.setPen(Qt.NoPen)
        p.setBrush(colour)
        p.drawRoundedRect(track, h / 2, h / 2)
        p.setBrush(QColor("white"))
        knob = h - 6
        p.drawEllipse(QRectF(3 + self._pos * (w - knob - 6), y + 3, knob, knob))
        p.setPen(self.palette().windowText().color())
        p.drawText(QRectF(w + 10, 0, self.width() - w - 10, self.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, self.text())


class LabeledCombo(QWidget):
    """A label above a combo box, built from a {label: value} mapping."""

    changed = Signal()

    def __init__(self, label: str, options: dict, parent: QWidget | None = None,
                 tooltip: str = ""):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)
        title = QLabel(label)
        title.setObjectName("fieldLabel")
        lay.addWidget(title)
        self.combo = QComboBox()
        self.combo.setCursor(Qt.PointingHandCursor)
        for text, value in options.items():
            self.combo.addItem(text, value)
        if tooltip:
            self.setToolTip(tooltip)
        lay.addWidget(self.combo)
        self.combo.currentIndexChanged.connect(lambda _i: self.changed.emit())

    def value(self):
        return self.combo.currentData()

    def set_value(self, value) -> None:
        idx = self.combo.findData(value)
        self.combo.blockSignals(True)
        self.combo.setCurrentIndex(max(0, idx))
        self.combo.blockSignals(False)


class Collapsible(QWidget):
    """A section with a clickable header that shows/hides its content."""

    def __init__(self, title: str, parent: QWidget | None = None, expanded: bool = False):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.button = QToolButton()
        self.button.setObjectName("collapseButton")
        self.button.setText(title)
        self.button.setCheckable(True)
        self.button.setChecked(expanded)
        self.button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.button.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.button.setCursor(Qt.PointingHandCursor)
        self.button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.body = QFrame()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 4, 0, 0)
        self.body_layout.setSpacing(10)
        self.body.setVisible(expanded)
        lay.addWidget(self.button)
        lay.addWidget(self.body)
        self.button.toggled.connect(self._toggle)

    def _toggle(self, on: bool) -> None:
        self.button.setArrowType(Qt.DownArrow if on else Qt.RightArrow)
        self.body.setVisible(on)


def section_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("sectionTitle")
    return label


def hbox(*widgets, spacing: int = 8) -> QHBoxLayout:
    lay = QHBoxLayout()
    lay.setSpacing(spacing)
    for w in widgets:
        if w is None:
            lay.addStretch(1)
        else:
            lay.addWidget(w)
    return lay
