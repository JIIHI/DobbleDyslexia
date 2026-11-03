"""The main Word Spot window."""

from __future__ import annotations

import random
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QColor, QDesktopServices, QIcon, QKeySequence, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QFileDialog, QFrame, QHBoxLayout, QInputDialog,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
                               QMenu, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
                               QScrollArea, QSplitter, QTabWidget, QVBoxLayout, QWidget)

from wordspot import APP_NAME, __version__
from wordspot.builder import DeckPlan, clean_words, plan_deck
from wordspot.db import Database, Deck
from wordspot.export import card_px, export_pdf, export_zip, read_word_file, safe_name
from wordspot.gui.bubble_designer import BubbleDesigner
from wordspot.gui.widgets import Collapsible, LabeledCombo, ToggleSwitch, section_title
from wordspot.gui.workers import PreviewWorker, TaskWorker
from wordspot.render import render_card
from wordspot.style import (BACKGROUNDS, BUBBLE_SIZES, BUBBLE_STYLES, CARD_SHAPES, CARD_SIZES_MM, FONTS,
                            LETTER_CASES, WORD_COLOURS, WORDS_PER_CARD, CardStyle)

THUMB = 230


def swatch_icon(colour: str) -> QIcon:
    pix = QPixmap(16, 16)
    pix.fill(QColor(colour))
    return QIcon(pix)


class MainWindow(QMainWindow):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.deck: Deck | None = None
        self.plan: DeckPlan | None = None
        self.layouts = db.list_layouts()
        self.generation = 0
        self.preview_worker: PreviewWorker | None = None
        self._old_workers: set[PreviewWorker] = set()
        self.task: TaskWorker | None = None
        self._loading = False

        self.setWindowTitle(APP_NAME)
        self.resize(1360, 860)
        self.setMinimumSize(1000, 640)

        self.refresh_timer = QTimer(self, singleShot=True, interval=250)
        self.refresh_timer.timeout.connect(self.refresh_preview)
        self.words_timer = QTimer(self, singleShot=True, interval=700)
        self.words_timer.timeout.connect(self.save_words)

        central = QWidget()
        central.setObjectName("central")
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_header())

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_deck_panel())
        splitter.addWidget(self._build_centre())
        splitter.addWidget(self._build_style_panel())
        splitter.setSizes([290, 760, 330])
        splitter.setStretchFactor(1, 1)
        outer.addWidget(splitter, 1)
        outer.addWidget(self._build_action_bar())
        self.setCentralWidget(central)
        self._build_menu()

        self.load_decks(select_id=int(self.db.get_setting("last_deck", "0") or 0))

    # ================================================================ layout
    def _build_header(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("header")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 12, 20, 12)
        title = QLabel(APP_NAME)
        title.setObjectName("appTitle")
        subtitle = QLabel("Spot the matching word - printable card games for children who find reading hard")
        subtitle.setObjectName("appSubtitle")
        lay.addWidget(title)
        lay.addSpacing(14)
        lay.addWidget(subtitle)
        lay.addStretch(1)
        help_btn = QPushButton("How to play")
        help_btn.setObjectName("flat")
        help_btn.clicked.connect(self.show_how_to_play)
        lay.addWidget(help_btn)
        return bar

    def _build_deck_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.addWidget(section_title("Card decks"))
        self.deck_list = QListWidget()
        self.deck_list.setObjectName("deckList")
        self.deck_list.setWordWrap(True)
        self.deck_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.deck_list.setTextElideMode(Qt.ElideRight)
        self.deck_list.currentItemChanged.connect(self._deck_selected)
        self.deck_list.itemDoubleClicked.connect(lambda _i: self.rename_deck())
        lay.addWidget(self.deck_list, 1)
        new_btn = QPushButton("+  New deck")
        new_btn.setObjectName("primary")
        new_btn.clicked.connect(self.new_deck)
        import_btn = QPushButton("Import word list...")
        import_btn.clicked.connect(self.import_deck)
        dup_btn = QPushButton("Copy")
        dup_btn.setToolTip("Make your own copy of this deck")
        dup_btn.clicked.connect(self.duplicate_deck)
        self.rename_btn = QPushButton("Rename")
        self.rename_btn.clicked.connect(self.rename_deck)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setObjectName("danger")
        self.delete_btn.clicked.connect(self.delete_deck)
        lay.addWidget(new_btn)
        lay.addWidget(import_btn)
        row = QHBoxLayout()
        row.addWidget(dup_btn)
        row.addWidget(self.rename_btn)
        row.addWidget(self.delete_btn)
        lay.addLayout(row)
        return panel

    def _build_centre(self) -> QWidget:
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(14, 14, 14, 0)
        self.deck_title = QLabel("")
        self.deck_title.setObjectName("deckTitle")
        self.deck_desc = QLabel("")
        self.deck_desc.setObjectName("hint")
        self.deck_desc.setWordWrap(True)
        lay.addWidget(self.deck_title)
        lay.addWidget(self.deck_desc)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # --- cards tab
        cards = QWidget()
        cl = QVBoxLayout(cards)
        cl.setContentsMargins(0, 10, 0, 0)
        top = QHBoxLayout()
        self.summary = QLabel("")
        self.summary.setObjectName("summary")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Find a card: type a word...")
        self.search.setClearButtonEnabled(True)
        self.search.setMaximumWidth(260)
        self.search.textChanged.connect(self._filter_cards)
        shuffle = QPushButton("Shuffle")
        shuffle.setToolTip("Make a fresh mix of colours, angles and bubble layouts")
        shuffle.clicked.connect(self.reshuffle)
        top.addWidget(self.summary, 1)
        top.addWidget(self.search)
        top.addWidget(shuffle)
        cl.addLayout(top)
        self.card_view = QListWidget()
        self.card_view.setObjectName("cardView")
        self.card_view.setViewMode(QListWidget.IconMode)
        self.card_view.setIconSize(QSize(THUMB, THUMB))
        self.card_view.setGridSize(QSize(THUMB + 22, THUMB + 34))
        self.card_view.setResizeMode(QListWidget.Adjust)
        self.card_view.setMovement(QListWidget.Static)
        self.card_view.setUniformItemSizes(True)
        self.card_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.card_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.card_view.customContextMenuRequested.connect(self._card_menu)
        self.card_view.itemDoubleClicked.connect(lambda _i: self.save_selected_png())
        cl.addWidget(self.card_view, 1)
        tip = QLabel("Tip: right-click a card (or select several) to re-print just those cards.")
        tip.setObjectName("hint")
        cl.addWidget(tip)
        self.tabs.addTab(cards, "Cards")

        # --- words tab
        words = QWidget()
        wl = QVBoxLayout(words)
        wl.setContentsMargins(0, 10, 0, 0)
        info = QLabel("One word per line. Changes are saved automatically. "
                      "8 words per card needs 57 different words, 6 per card needs 31, "
                      "4 per card needs 13 and 3 per card needs 7.")
        info.setWordWrap(True)
        info.setObjectName("hint")
        wl.addWidget(info)
        self.words_edit = QPlainTextEdit()
        self.words_edit.setObjectName("wordsEdit")
        self.words_edit.textChanged.connect(self._words_changed)
        wl.addWidget(self.words_edit, 1)
        row = QHBoxLayout()
        self.word_count = QLabel("")
        self.word_count.setObjectName("summary")
        add_file = QPushButton("Add words from file...")
        add_file.clicked.connect(self.add_words_from_file)
        sort_btn = QPushButton("Sort A-Z")
        sort_btn.clicked.connect(self.sort_words)
        self.restore_btn = QPushButton("Restore original words")
        self.restore_btn.clicked.connect(self.restore_words)
        row.addWidget(self.word_count, 1)
        row.addWidget(add_file)
        row.addWidget(sort_btn)
        row.addWidget(self.restore_btn)
        wl.addLayout(row)
        self.tabs.addTab(words, "Words")

        lay.addWidget(self.tabs, 1)
        return wrap

    def _build_style_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setObjectName("stylePanel")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QFrame()
        body.setObjectName("panel")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(10)

        lay.addWidget(section_title("Words"))
        self.c_font = LabeledCombo("Font", FONTS,
                                   tooltip="OpenDyslexic, Lexend and Andika are designed to be easier to read.")
        self.c_case = LabeledCombo("Letters", LETTER_CASES)
        self.c_colours = LabeledCombo("Word colours", WORD_COLOURS)
        self.t_bold = ToggleSwitch("Bold words")
        for w in (self.c_font, self.c_case, self.c_colours, self.t_bold):
            lay.addWidget(w)

        lay.addSpacing(6)
        lay.addWidget(section_title("Card"))
        self.c_shape = LabeledCombo(
            "Card shape", CARD_SHAPES,
            tooltip="Round cards are played from every side of the table, so words face every way.\n"
                    "Rectangular cards keep words upright - good for one-to-one work with an adult.")
        lay.addWidget(self.c_shape)
        self.c_background = LabeledCombo("Background", BACKGROUNDS,
                                         tooltip="Cream or pastel backgrounds reduce glare for many readers.")
        for i, colour in enumerate(BACKGROUNDS.values()):
            self.c_background.combo.setItemIcon(i, swatch_icon(colour))
        self.c_bubbles = LabeledCombo("Bubbles behind words", BUBBLE_STYLES)
        self.c_per_card = LabeledCombo("Words per card", WORDS_PER_CARD,
                                       tooltip="Fewer words per card makes an easier game.")
        self.t_border = ToggleSwitch("Card border")
        self.t_numbers = ToggleSwitch("Card numbers (in the corner)")
        self.t_guides = ToggleSwitch("Cut guides when no border")
        for w in (self.c_background, self.c_bubbles, self.c_per_card,
                  self.t_border, self.t_numbers, self.t_guides):
            lay.addWidget(w)

        lay.addSpacing(6)
        adv = Collapsible("Advanced settings")
        self.c_sizes = LabeledCombo("Bubble sizes", BUBBLE_SIZES,
                                    tooltip="Even sizes help children who struggle with very small words.")
        self.t_long_big = ToggleSwitch("Long words in big bubbles")
        self.c_card_mm = LabeledCombo("Printed card size", CARD_SIZES_MM)
        designer = self.designer_btn = QPushButton("Bubble Designer...")
        designer.clicked.connect(self.open_designer)
        for w in (self.c_sizes, self.t_long_big, self.c_card_mm, designer):
            adv.body_layout.addWidget(w)
        lay.addWidget(adv)
        lay.addStretch(1)

        for combo in (self.c_shape, self.c_font, self.c_case, self.c_colours, self.c_background,
                      self.c_bubbles, self.c_per_card, self.c_sizes, self.c_card_mm):
            combo.changed.connect(self._style_changed)
        for toggle in (self.t_bold, self.t_border, self.t_numbers, self.t_guides, self.t_long_big):
            toggle.toggled.connect(self._style_changed)

        scroll.setWidget(body)
        scroll.setMinimumWidth(300)
        return scroll

    def _build_action_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("actionBar")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 10, 20, 10)
        self.status = QLabel("")
        self.status.setObjectName("hint")
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(260)
        self.progress.setVisible(False)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(lambda: self.task and self.task.cancel())
        self.pdf_btn = QPushButton("Download A4 PDF")
        self.pdf_btn.setObjectName("bigPrimary")
        self.pdf_btn.setToolTip("All the cards laid out on A4 pages, ready to print and cut out")
        self.pdf_btn.clicked.connect(self.download_pdf)
        self.zip_btn = QPushButton("Download ZIP")
        self.zip_btn.setObjectName("big")
        self.zip_btn.setToolTip("Every card as its own picture (plus the A4 PDF) - handy for replacing lost cards")
        self.zip_btn.clicked.connect(self.download_zip)
        lay.addWidget(self.status, 1)
        lay.addWidget(self.progress)
        lay.addWidget(self.cancel_btn)
        lay.addWidget(self.zip_btn)
        lay.addWidget(self.pdf_btn)
        return bar

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        for text, slot, key in [
                ("New deck", self.new_deck, QKeySequence.New),
                ("Import word list...", self.import_deck, QKeySequence.Open),
                ("Download A4 PDF...", self.download_pdf, QKeySequence.Print),
                ("Download ZIP...", self.download_zip, None)]:
            act = QAction(text, self)
            if key is not None:
                act.setShortcut(key)
            act.triggered.connect(slot)
            file_menu.addAction(act)
        file_menu.addSeparator()
        quit_act = QAction("Quit", self)
        quit_act.setShortcut(QKeySequence.Quit)
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)
        tools = self.menuBar().addMenu("&Tools")
        act = QAction("Bubble Designer...", self)
        act.triggered.connect(self.open_designer)
        tools.addAction(act)
        act = QAction("Open data folder", self)
        act.triggered.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.db.path.parent))))
        tools.addAction(act)
        help_menu = self.menuBar().addMenu("&Help")
        act = QAction("How to play", self)
        act.triggered.connect(self.show_how_to_play)
        help_menu.addAction(act)
        act = QAction(f"About {APP_NAME}", self)
        act.triggered.connect(self.show_about)
        help_menu.addAction(act)

    # ================================================================= decks
    def load_decks(self, select_id: int | None = None) -> None:
        self.deck_list.blockSignals(True)
        self.deck_list.clear()
        decks = self.db.list_decks()
        last_builtin = None
        for deck in decks:
            if last_builtin is None or last_builtin != deck.builtin:
                header = QListWidgetItem("READY-MADE DECKS" if deck.builtin else "MY DECKS")
                header.setFlags(Qt.NoItemFlags)
                header.setData(Qt.UserRole, None)
                f = header.font()
                f.setBold(True)
                f.setPointSizeF(f.pointSizeF() * 0.85)
                header.setFont(f)
                header.setForeground(QColor("#64748b"))
                self.deck_list.addItem(header)
                last_builtin = deck.builtin
            item = QListWidgetItem(deck.name)
            item.setData(Qt.UserRole, deck.id)
            item.setToolTip(deck.description or deck.name)
            self.deck_list.addItem(item)
        if not any(not d.builtin for d in decks):
            header = QListWidgetItem("MY DECKS")
            header.setFlags(Qt.NoItemFlags)
            header.setForeground(QColor("#64748b"))
            f = header.font()
            f.setBold(True)
            f.setPointSizeF(f.pointSizeF() * 0.85)
            header.setFont(f)
            self.deck_list.addItem(header)
            hint = QListWidgetItem("  Click '+ New deck' to make your own")
            hint.setFlags(Qt.NoItemFlags)
            hint.setForeground(QColor("#94a3b8"))
            self.deck_list.addItem(hint)
        self.deck_list.blockSignals(False)
        target = None
        for i in range(self.deck_list.count()):
            it = self.deck_list.item(i)
            if it.data(Qt.UserRole) is None:
                continue
            if target is None or it.data(Qt.UserRole) == select_id:
                target = it
                if it.data(Qt.UserRole) == select_id:
                    break
        if target:
            self.deck_list.setCurrentItem(target)

    def _deck_selected(self, item: QListWidgetItem | None, _prev=None) -> None:
        if not item or item.data(Qt.UserRole) is None:
            return
        self.flush_words()
        self.deck = self.db.get_deck(item.data(Qt.UserRole))
        self.db.set_setting("last_deck", str(self.deck.id))
        self._loading = True
        self.deck_title.setText(self.deck.name)
        self.deck_desc.setText(self.deck.description)
        self.deck_desc.setVisible(bool(self.deck.description))
        self.words_edit.setPlainText("\n".join(self.db.get_words(self.deck.id)))
        self._apply_style_to_controls(self.deck.style)
        self.rename_btn.setEnabled(not self.deck.builtin)
        self.delete_btn.setEnabled(not self.deck.builtin)
        self.restore_btn.setVisible(self.deck.builtin)
        self._loading = False
        self._update_word_count()
        self.refresh_preview()

    def _ask_name(self, title: str, default: str) -> str | None:
        name, ok = QInputDialog.getText(self, title, "Deck name:", text=default)
        name = name.strip()
        return name if ok and name else None

    def new_deck(self) -> None:
        name = self._ask_name("New deck", "My word deck")
        if not name:
            return
        deck_id = self.db.create_deck(name, [])
        self.load_decks(deck_id)
        self.tabs.setCurrentIndex(1)
        self.words_edit.setFocus()

    def duplicate_deck(self) -> None:
        if not self.deck:
            return
        name = self._ask_name("Copy deck", f"{self.deck.name} (my copy)")
        if name:
            self.flush_words()
            self.load_decks(self.db.duplicate_deck(self.deck.id, name))

    def rename_deck(self) -> None:
        if not self.deck or self.deck.builtin:
            return
        name = self._ask_name("Rename deck", self.deck.name)
        if name:
            self.db.rename_deck(self.deck.id, name)
            self.load_decks(self.deck.id)

    def delete_deck(self) -> None:
        if not self.deck or self.deck.builtin:
            return
        if QMessageBox.question(self, "Delete deck",
                                f"Delete '{self.deck.name}' and its words?\nThis can't be undone."
                                ) != QMessageBox.Yes:
            return
        self.words_timer.stop()
        self.db.delete_deck(self.deck.id)
        self.deck = None
        self.load_decks()

    def import_deck(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import word list", str(Path.home()),
                                              "Word lists (*.txt *.csv *.xlsx);;All files (*)")
        if not path:
            return
        try:
            words = clean_words(read_word_file(path))
        except Exception as exc:
            QMessageBox.warning(self, "Import", f"Couldn't read that file:\n{exc}")
            return
        if not words:
            QMessageBox.warning(self, "Import", "No words found in that file.")
            return
        name = self._ask_name("Import word list", Path(path).stem.replace("_", " ").title())
        if name:
            self.load_decks(self.db.create_deck(name, words))

    # ================================================================= words
    def _words_changed(self) -> None:
        if self._loading:
            return
        self._update_word_count()
        self.words_timer.start()

    def current_words(self) -> list[str]:
        return [line.strip() for line in self.words_edit.toPlainText().splitlines() if line.strip()]

    def _update_word_count(self) -> None:
        raw = self.current_words()
        words = clean_words(raw)
        repeats = len(raw) - len(words)
        text = f"{len(words)} different words"
        if repeats:
            text += f" ({repeats} repeated - repeats are ignored)"
        self.word_count.setText(text)

    def flush_words(self) -> None:
        if self.words_timer.isActive():
            self.words_timer.stop()
            self.save_words()

    def save_words(self) -> None:
        if not self.deck:
            return
        self.db.set_words(self.deck.id, self.current_words())
        self.refresh_preview()

    def add_words_from_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Add words from file", str(Path.home()),
                                              "Word lists (*.txt *.csv *.xlsx);;All files (*)")
        if not path:
            return
        try:
            new = read_word_file(path)
        except Exception as exc:
            QMessageBox.warning(self, "Add words", f"Couldn't read that file:\n{exc}")
            return
        words = clean_words(self.current_words() + new)
        self.words_edit.setPlainText("\n".join(words))

    def sort_words(self) -> None:
        self.words_edit.setPlainText("\n".join(sorted(clean_words(self.current_words()),
                                                      key=str.lower)))

    def restore_words(self) -> None:
        if self.deck and self.deck.builtin:
            original = self.db.original_words(self.deck)
            if original is not None:
                self.words_edit.setPlainText("\n".join(original))

    # ================================================================= style
    def _apply_style_to_controls(self, s: CardStyle) -> None:
        self.c_shape.set_value(s.card_shape)
        self.c_font.set_value(s.font)
        self.c_case.set_value(s.letter_case)
        self.c_colours.set_value(s.word_colours)
        self.c_background.set_value(s.background)
        self.c_bubbles.set_value(s.bubble_style)
        self.c_per_card.set_value(s.words_per_card)
        self.c_sizes.set_value(s.bubble_sizes)
        self.c_card_mm.set_value(s.card_mm)
        for toggle, value in ((self.t_bold, s.bold), (self.t_border, s.card_border),
                              (self.t_numbers, s.card_numbers), (self.t_guides, s.cut_guides),
                              (self.t_long_big, s.long_words_big)):
            toggle.blockSignals(True)
            toggle.setChecked(value)
            toggle.blockSignals(False)
        self.t_guides.setEnabled(not s.card_border)
        self._shape_controls(s)

    def _style_from_controls(self) -> CardStyle:
        s = CardStyle(seed=self.deck.style.seed if self.deck else 1)
        s.card_shape = self.c_shape.value()
        s.font = self.c_font.value()
        s.letter_case = self.c_case.value()
        s.word_colours = self.c_colours.value()
        s.background = self.c_background.value()
        s.bubble_style = self.c_bubbles.value()
        s.words_per_card = self.c_per_card.value()
        s.bubble_sizes = self.c_sizes.value()
        s.card_mm = self.c_card_mm.value()
        s.bold = self.t_bold.isChecked()
        s.card_border = self.t_border.isChecked()
        s.card_numbers = self.t_numbers.isChecked()
        s.cut_guides = self.t_guides.isChecked()
        s.long_words_big = self.t_long_big.isChecked()
        return s

    def _style_changed(self, *_args) -> None:
        if self._loading or not self.deck:
            return
        self.deck.style = self._style_from_controls()
        self.t_guides.setEnabled(not self.deck.style.card_border)
        self._shape_controls(self.deck.style)
        self.db.save_style(self.deck.id, self.deck.style)
        self.refresh_timer.start()

    def _shape_controls(self, s: CardStyle) -> None:
        """Bubble layout settings only apply to round cards."""
        round_card = s.card_shape != "rect"
        for w in (self.c_sizes, self.t_long_big, self.designer_btn):
            w.setEnabled(round_card)
        self.c_bubbles.findChild(QLabel).setText(
            "Bubbles behind words" if round_card else "Boxes behind words")

    def reshuffle(self) -> None:
        if not self.deck:
            return
        self.deck.style.seed = random.randint(1, 999_999)
        self.db.save_style(self.deck.id, self.deck.style)
        self.refresh_preview()

    # =============================================================== preview
    def refresh_preview(self) -> None:
        if not self.deck:
            return
        if self.preview_worker:
            # Let the old worker finish in the background; keep a reference
            # so Qt doesn't destroy a running thread.
            old = self.preview_worker
            old.stop()
            self._old_workers.add(old)
            old.finished.connect(lambda o=old: self._old_workers.discard(o))
            self.preview_worker = None
        self.generation += 1
        words = self.db.get_words(self.deck.id)
        self.plan = plan_deck(words, self.deck.style, self.layouts)
        self.summary.setText(self.plan.summary())
        self.card_view.clear()
        placeholder = QPixmap(THUMB, THUMB)
        placeholder.fill(Qt.transparent)
        for card in self.plan.cards:
            item = QListWidgetItem(QIcon(placeholder), f"Card {card.number}")
            item.setData(Qt.UserRole, card.number)
            item.setToolTip(", ".join(w.word for w in card.words))
            self.card_view.addItem(item)
        has_cards = bool(self.plan.cards)
        self.pdf_btn.setEnabled(has_cards)
        self.zip_btn.setEnabled(has_cards)
        if not has_cards:
            self.status.setText("Add more words on the Words tab to make a deck.")
            return
        self.status.setText("")
        self._filter_cards(self.search.text())
        worker = PreviewWorker(self.generation, self.plan, self.deck.style, THUMB)
        worker.card_ready.connect(self._thumb_ready)
        self.preview_worker = worker
        worker.start()

    def _thumb_ready(self, generation: int, index: int, image) -> None:
        if generation != self.generation or index >= self.card_view.count():
            return
        self.card_view.item(index).setIcon(QIcon(QPixmap.fromImage(image)))

    def _filter_cards(self, text: str) -> None:
        text = text.strip().lower()
        shown = 0
        for i in range(self.card_view.count()):
            item = self.card_view.item(i)
            words = item.toolTip().lower().split(", ")
            hide = bool(text) and not any(w.startswith(text) for w in words)
            item.setHidden(hide)
            shown += not hide
        if text and self.plan:
            self.status.setText(f"{shown} card{'s' if shown != 1 else ''} with a word starting '{text}'")
        elif self.plan and self.plan.cards:
            self.status.setText("")

    def selected_card_numbers(self) -> list[int]:
        return sorted(item.data(Qt.UserRole) for item in self.card_view.selectedItems())

    def _card_menu(self, pos) -> None:
        item = self.card_view.itemAt(pos)
        if item and not item.isSelected():
            self.card_view.clearSelection()
            item.setSelected(True)
        numbers = self.selected_card_numbers()
        if not numbers:
            return
        label = f"card {numbers[0]}" if len(numbers) == 1 else f"{len(numbers)} cards"
        menu = QMenu(self)
        menu.addAction(f"Print {label} on A4 (PDF)...", self.print_selected)
        menu.addAction(f"Save {label} as picture (PNG)...", self.save_selected_png)
        menu.exec(self.card_view.viewport().mapToGlobal(pos))

    # ================================================================ export
    def _default_name(self, suffix: str) -> str:
        return str(Path.home() / "Downloads" / f"{safe_name(self.deck.name)}{suffix}") \
            if (Path.home() / "Downloads").exists() else str(Path.home() / f"{safe_name(self.deck.name)}{suffix}")

    def _run_task(self, func, *args, message: str, open_path: str | None = None, **kwargs) -> None:
        if self.task and self.task.isRunning():
            return
        self.task = TaskWorker(func, *args, message=message, **kwargs)
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self.cancel_btn.setVisible(True)
        self.pdf_btn.setEnabled(False)
        self.zip_btn.setEnabled(False)
        self.status.setText("Drawing cards...")
        self.task.progress.connect(lambda d, t: (self.progress.setMaximum(t), self.progress.setValue(d)))

        def done(msg: str, ok: bool) -> None:
            self.progress.setVisible(False)
            self.cancel_btn.setVisible(False)
            self.pdf_btn.setEnabled(True)
            self.zip_btn.setEnabled(True)
            self.status.setText(msg)
            if ok and open_path:
                box = QMessageBox(self)
                box.setWindowTitle(APP_NAME)
                box.setText(msg)
                open_btn = box.addButton("Show file", QMessageBox.AcceptRole)
                box.addButton(QMessageBox.Close)
                box.exec()
                if box.clickedButton() == open_btn:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(open_path).parent)))
            elif not ok:
                QMessageBox.warning(self, APP_NAME, msg)

        self.task.finished_ok.connect(lambda m: done(m, True))
        self.task.failed.connect(lambda m: done(m, False))
        self.task.start()

    def download_pdf(self) -> None:
        if not self.plan or not self.plan.cards:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save A4 PDF", self._default_name("_A4.pdf"),
                                              "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        self._run_task(export_pdf, path, self.plan, self.deck.style, self.deck.name,
                       message=f"Saved {self.plan.card_count} cards to {Path(path).name}",
                       open_path=path)

    def download_zip(self) -> None:
        if not self.plan or not self.plan.cards:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save ZIP", self._default_name("_cards.zip"),
                                              "ZIP archive (*.zip)")
        if not path:
            return
        if not path.lower().endswith(".zip"):
            path += ".zip"
        self._run_task(export_zip, path, self.plan, self.deck.style, self.deck.name,
                       message=f"Saved {self.plan.card_count} card pictures to {Path(path).name}",
                       open_path=path)

    def print_selected(self) -> None:
        numbers = self.selected_card_numbers()
        if not numbers or not self.plan:
            return
        suffix = f"_card_{numbers[0]}.pdf" if len(numbers) == 1 else "_selected_cards.pdf"
        path, _ = QFileDialog.getSaveFileName(self, "Save cards as A4 PDF",
                                              self._default_name(suffix), "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        self._run_task(export_pdf, path, self.plan, self.deck.style, self.deck.name,
                       card_numbers=numbers,
                       message=f"Saved {len(numbers)} card(s) to {Path(path).name}", open_path=path)

    def save_selected_png(self) -> None:
        numbers = self.selected_card_numbers()
        if not numbers or not self.plan:
            return
        if len(numbers) == 1:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save card picture", self._default_name(f"_card_{numbers[0]}.png"), "PNG (*.png)")
            if not path:
                return
            targets = {numbers[0]: path if path.lower().endswith(".png") else path + ".png"}
        else:
            folder = QFileDialog.getExistingDirectory(self, "Choose a folder for the card pictures",
                                                      str(Path.home()))
            if not folder:
                return
            targets = {n: str(Path(folder) / f"Card_{n}.png") for n in numbers}
        cards = {c.number: c for c in self.plan.cards}
        px = card_px(self.deck.style)
        for number, target in targets.items():
            render_card(cards[number], self.deck.style, px).save(target, dpi=(300, 300))
        self.status.setText(f"Saved {len(targets)} card picture(s).")

    # ================================================================= other
    def open_designer(self) -> None:
        per_card = self.plan.per_card if self.plan and self.plan.per_card else 8
        dlg = BubbleDesigner(self.db, per_card, self)
        dlg.exec()
        if dlg.changed:
            self.layouts = self.db.list_layouts()
            self.refresh_preview()

    def show_how_to_play(self) -> None:
        QMessageBox.information(self, "How to play", (
            "<h3>How to play</h3>"
            "<p>Every pair of cards has <b>exactly one</b> word in common.</p>"
            "<p><b>The Tower:</b> deal one card to each player, face down, and put the rest in a "
            "pile face up in the middle. Everyone turns their card over. The first to spot and "
            "<b>read out</b> the word their card shares with the middle card takes it. "
            "The player with the most cards at the end wins.</p>"
            "<p>Words point in every direction so that everyone around the table can read "
            "some of them - just like the cards themselves, there's no right way up.</p>"
            "<p><b>Quick tip for reluctant readers:</b> a player only wins the card when they say "
            "the word out loud, so reading becomes part of the race.</p>"
            "<p><b>Easier games:</b> choose fewer words per card, even bubble sizes or long words in big bubbles "
            "on the right.</p>"))

    def show_about(self) -> None:
        QMessageBox.about(self, f"About {APP_NAME}", (
            f"<h3>{APP_NAME} {__version__}</h3>"
            "<p>Make printable 'spot the matching word' card games for children with dyslexia, "
            "ADHD and other special educational needs.</p>"
            "<p>Fonts: OpenDyslexic, Lexend and Andika (SIL Open Font License).</p>"
            f"<p>Your decks are stored in:<br><code>{self.db.path}</code></p>"))

    def closeEvent(self, event) -> None:  # noqa: N802
        self.flush_words()
        for worker in [self.preview_worker, *self._old_workers]:
            if worker:
                worker.stop()
                worker.wait(3000)
        if self.task and self.task.isRunning():
            self.task.cancel()
            self.task.wait(5000)
        super().closeEvent(event)
