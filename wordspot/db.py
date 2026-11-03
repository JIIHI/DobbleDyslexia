"""SQLite storage for decks, words, bubble layouts and app settings."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from wordspot.layout import Layout
from wordspot.paths import data_dir, user_data_dir
from wordspot.style import CardStyle
from wordspot.wordlists import BUILTIN_DECKS

SCHEMA = """
CREATE TABLE IF NOT EXISTS decks (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    builtin_key TEXT UNIQUE,
    style       TEXT,
    position    INTEGER NOT NULL DEFAULT 0,
    created     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS words (
    id       INTEGER PRIMARY KEY,
    deck_id  INTEGER NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    word     TEXT NOT NULL,
    position INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS words_deck ON words(deck_id, position);
CREATE TABLE IF NOT EXISTS layouts (
    id       INTEGER PRIMARY KEY,
    name     TEXT NOT NULL,
    n        INTEGER NOT NULL,
    circles  TEXT NOT NULL,
    variety  REAL NOT NULL DEFAULT 1.0,
    fill     INTEGER NOT NULL DEFAULT 80,
    builtin  INTEGER NOT NULL DEFAULT 0,
    enabled  INTEGER NOT NULL DEFAULT 1,
    created  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

BUILTIN_VERSION = "1"


@dataclass
class Deck:
    id: int
    name: str
    description: str
    builtin_key: str | None
    style: CardStyle

    @property
    def builtin(self) -> bool:
        return self.builtin_key is not None


class Database:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else user_data_dir() / "wordspot.sqlite3"
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self._seed()

    def close(self) -> None:
        self.conn.close()

    # ---------------------------------------------------------------- seeding
    def _seed(self) -> None:
        if self.get_setting("builtin_version") == BUILTIN_VERSION:
            return
        with self.conn:
            for pos, spec in enumerate(BUILTIN_DECKS):
                row = self.conn.execute("SELECT id FROM decks WHERE builtin_key = ?",
                                        (spec["key"],)).fetchone()
                if row is None:
                    style = CardStyle.from_json(None)
                    cur = self.conn.execute(
                        "INSERT INTO decks(name, description, builtin_key, style, position) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (spec["name"], spec["description"], spec["key"], style.to_json(), pos))
                    self._write_words(cur.lastrowid, spec["words"])
            if not self.conn.execute("SELECT 1 FROM layouts WHERE builtin = 1").fetchone():
                path = data_dir() / "layouts.json"
                for item in json.loads(path.read_text()):
                    self.conn.execute(
                        "INSERT INTO layouts(name, n, circles, variety, fill, builtin) "
                        "VALUES (?, ?, ?, ?, ?, 1)",
                        (item["name"], len(item["circles"]), json.dumps(item["circles"]),
                         item.get("variety", 1.0), item.get("fill", 80)))
            self._set_setting("builtin_version", BUILTIN_VERSION)

    # ------------------------------------------------------------------ decks
    def _deck(self, row: sqlite3.Row) -> Deck:
        return Deck(row["id"], row["name"], row["description"], row["builtin_key"],
                    CardStyle.from_json(row["style"]))

    def list_decks(self) -> list[Deck]:
        rows = self.conn.execute(
            "SELECT * FROM decks ORDER BY builtin_key IS NULL, position, id").fetchall()
        return [self._deck(r) for r in rows]

    def get_deck(self, deck_id: int) -> Deck | None:
        row = self.conn.execute("SELECT * FROM decks WHERE id = ?", (deck_id,)).fetchone()
        return self._deck(row) if row else None

    def create_deck(self, name: str, words: list[str] | None = None,
                    style: CardStyle | None = None, description: str = "") -> int:
        style = style or CardStyle.from_json(None)
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO decks(name, description, style, position) VALUES (?, ?, ?, 1000)",
                (name, description, style.to_json()))
            self._write_words(cur.lastrowid, words or [])
        return cur.lastrowid

    def duplicate_deck(self, deck_id: int, name: str) -> int:
        deck = self.get_deck(deck_id)
        return self.create_deck(name, self.get_words(deck_id), deck.style, deck.description)

    def rename_deck(self, deck_id: int, name: str) -> None:
        with self.conn:
            self.conn.execute("UPDATE decks SET name = ? WHERE id = ?", (name, deck_id))

    def delete_deck(self, deck_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM decks WHERE id = ? AND builtin_key IS NULL", (deck_id,))

    def save_style(self, deck_id: int, style: CardStyle) -> None:
        with self.conn:
            self.conn.execute("UPDATE decks SET style = ? WHERE id = ?", (style.to_json(), deck_id))

    def get_words(self, deck_id: int) -> list[str]:
        rows = self.conn.execute("SELECT word FROM words WHERE deck_id = ? ORDER BY position",
                                 (deck_id,)).fetchall()
        return [r["word"] for r in rows]

    def set_words(self, deck_id: int, words: list[str]) -> None:
        with self.conn:
            self._write_words(deck_id, words)

    def _write_words(self, deck_id: int, words: list[str]) -> None:
        self.conn.execute("DELETE FROM words WHERE deck_id = ?", (deck_id,))
        self.conn.executemany("INSERT INTO words(deck_id, word, position) VALUES (?, ?, ?)",
                              [(deck_id, w, i) for i, w in enumerate(words)])

    def original_words(self, deck: Deck) -> list[str] | None:
        for spec in BUILTIN_DECKS:
            if spec["key"] == deck.builtin_key:
                return list(spec["words"])
        return None

    # ---------------------------------------------------------------- layouts
    def _layout(self, row: sqlite3.Row) -> Layout:
        return Layout(circles=[tuple(c) for c in json.loads(row["circles"])], name=row["name"],
                      variety=row["variety"], fill=row["fill"], id=row["id"],
                      builtin=bool(row["builtin"]), enabled=bool(row["enabled"]))

    def list_layouts(self, n: int | None = None) -> list[Layout]:
        if n is None:
            rows = self.conn.execute("SELECT * FROM layouts ORDER BY n, builtin DESC, id")
        else:
            rows = self.conn.execute("SELECT * FROM layouts WHERE n = ? ORDER BY builtin DESC, id",
                                     (n,))
        return [self._layout(r) for r in rows.fetchall()]

    def add_layout(self, layout: Layout, name: str) -> int:
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO layouts(name, n, circles, variety, fill) VALUES (?, ?, ?, ?, ?)",
                (name, layout.count, json.dumps([list(c) for c in layout.circles]),
                 layout.variety, layout.fill))
        return cur.lastrowid

    def set_layout_enabled(self, layout_id: int, enabled: bool) -> None:
        with self.conn:
            self.conn.execute("UPDATE layouts SET enabled = ? WHERE id = ?", (int(enabled), layout_id))

    def delete_layout(self, layout_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM layouts WHERE id = ? AND builtin = 0", (layout_id,))

    # --------------------------------------------------------------- settings
    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self.conn:
            self._set_setting(key, value)

    def _set_setting(self, key: str, value: str) -> None:
        self.conn.execute("INSERT INTO settings(key, value) VALUES (?, ?) "
                          "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))
