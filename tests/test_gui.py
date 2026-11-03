"""Smoke test: the window opens, previews draw and the main controls work."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def wait_for(qapp, cond, timeout=20.0):
    import time
    end = time.time() + timeout
    while time.time() < end:
        qapp.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_main_window(qapp, tmp_path):
    from wordspot.db import Database
    from wordspot.gui.bubble_designer import BubbleDesigner
    from wordspot.gui.main_window import MainWindow

    win = MainWindow(Database(tmp_path / "t.sqlite3"))
    win.show()
    assert win.plan and win.plan.card_count == 57
    worker = win.preview_worker
    assert wait_for(qapp, lambda: worker.isFinished())

    # change a style option -> saved and re-planned
    win.c_per_card.combo.setCurrentIndex(win.c_per_card.combo.findData(4))
    assert wait_for(qapp, lambda: win.plan.card_count == 13)
    assert win.db.get_deck(win.deck.id).style.words_per_card == 4

    # search filters the cards
    word = win.plan.cards[0].words[0].word
    win.search.setText(word)
    visible = [win.card_view.item(i) for i in range(win.card_view.count())
               if not win.card_view.item(i).isHidden()]
    assert len(visible) == 4  # with 4 words per card, each word is on 4 cards

    # new deck with too few words shows no cards
    deck_id = win.db.create_deck("Tiny", ["a", "b"])
    win.load_decks(deck_id)
    assert win.plan.cards == [] and not win.pdf_btn.isEnabled()

    dlg = BubbleDesigner(win.db, 6, win)
    dlg.animate.setChecked(False)
    dlg.start_grow()
    assert dlg._current is not None and dlg._current.count == 6
    dlg.close()
    win.close()
