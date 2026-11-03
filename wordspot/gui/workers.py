"""Background threads so the window never freezes while drawing cards."""

from __future__ import annotations

import traceback

from PySide6.QtCore import QThread, Signal

from wordspot.builder import DeckPlan
from wordspot.gui.widgets import pil_to_qimage
from wordspot.render import render_card
from wordspot.style import CardStyle


class PreviewWorker(QThread):
    """Draws small preview images of every card."""

    card_ready = Signal(int, int, object)  # generation, index, QImage

    def __init__(self, generation: int, plan: DeckPlan, style: CardStyle, size_px: int):
        super().__init__()
        self.generation = generation
        self.plan = plan
        self.style = style
        self.size_px = size_px
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        for i, card in enumerate(self.plan.cards):
            if self._stop:
                return
            img = render_card(card, self.style, self.size_px)
            self.card_ready.emit(self.generation, i, pil_to_qimage(img))


class TaskWorker(QThread):
    """Runs an export function that takes a ``progress`` callback."""

    progress = Signal(int, int)
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, func, *args, message: str = "Done", **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.message = message
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def _progress(self, done: int, total: int) -> bool:
        self.progress.emit(done, total)
        return not self._cancel

    def run(self) -> None:
        try:
            self.func(*self.args, progress=self._progress, **self.kwargs)
        except InterruptedError:
            self.failed.emit("Cancelled.")
        except Exception as exc:  # report anything to the user rather than crash
            traceback.print_exc()
            self.failed.emit(f"Something went wrong: {exc}")
        else:
            self.finished_ok.emit(self.message)
