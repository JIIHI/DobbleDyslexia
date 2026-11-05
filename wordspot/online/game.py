"""Rules for the online game (no networking here, so it is easy to test).

Every round, everyone in the room sees the same two cards.  The first
player to tap the one word that is on both cards wins the round.  A wrong
tap freezes that player for a moment so random tapping doesn't pay off.
One player on their own works the same way, against the clock.
"""

from __future__ import annotations

import random
import secrets
import time
from dataclasses import dataclass, field

from wordspot.builder import DeckPlan, clean_words, plan_deck
from wordspot.layout import Layout
from wordspot.render import CardSpec, fit_box_font_size, fit_font_size
from wordspot.style import RECT_RATIO, CardStyle, bubble_tint, soft_colour
from wordspot.wordlists import BUILTIN_DECKS

WRONG_FREEZE = 1.5      # seconds a player is frozen after a wrong tap
SHOW_ANSWER = 2.4       # seconds the found word stays highlighted
HINT_AFTER = 15         # seconds before the hint button appears
MAX_PLAYERS = 8
MAX_ROOMS = 60          # games that can exist at once on one server
ROOM_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # no I or O (look like 1 and 0)
AVATARS = ["🐶", "🐱", "🦊", "🐸", "🐼", "🐵", "🦁", "🐯", "🐨", "🐰", "🐙", "🦄",
           "🐢", "🐧", "🦖", "🐝"]


def deck_choices() -> list[dict]:
    return [{"key": d["key"], "name": d["name"], "count": len(d["words"])} for d in BUILTIN_DECKS]


def deck_words(key: str) -> list[str] | None:
    for d in BUILTIN_DECKS:
        if d["key"] == key:
            return list(d["words"])
    return None


@dataclass
class Player:
    id: str
    name: str
    avatar: str
    score: int = 0
    connected: bool = True
    frozen_until: float = 0.0
    times: list[float] = field(default_factory=list)

    def public(self) -> dict:
        return {"id": self.id, "name": self.name, "avatar": self.avatar,
                "score": self.score, "connected": self.connected}


@dataclass
class Settings:
    deck: str = "phase2"
    custom_words: list[str] = field(default_factory=list)
    rounds: int = 10
    shape: str = "round"
    font: str = "opendyslexic"
    words_per_card: int = 0
    colours: str = "colourful"
    circles: bool = True

    def public(self) -> dict:
        return {"deck": self.deck, "custom_count": len(self.custom_words), "rounds": self.rounds,
                "shape": self.shape, "font": self.font, "words_per_card": self.words_per_card,
                "colours": self.colours, "circles": self.circles}


# Colour schemes offered in the online game (navy is desktop-only for now).
ONLINE_COLOURS = ("colourful", "bright", "pastel", "black", "grey", "bw")
OUTLINE_STROKE = "#1f2937"   # thin dark ring round each word in black & white


def game_style(s: Settings, seed: int) -> CardStyle:
    """The card style for a game with these settings."""
    if not s.circles:
        bubbles = "none"
    elif s.colours == "bw":
        bubbles = "outline"
    else:
        bubbles = "soft"
    return CardStyle(seed=seed, card_shape=s.shape, font=s.font,
                     words_per_card=s.words_per_card, word_colours=s.colours,
                     bubble_style=bubbles,
                     background="#ffffff" if s.colours == "bw" else "#fdf6e3")


def card_payload(card: CardSpec, style: CardStyle) -> dict:
    """What a device needs to draw a card.  Font sizes are worked out here
    with the same font files the browser uses, as a fraction of the card."""
    words = []
    tint = bubble_tint(style.word_colours)

    def fill(colour: str) -> str:
        if style.bubble_style == "soft":
            return soft_colour(colour, style.background, tint)
        if style.bubble_style == "outline":
            return "#ffffff"
        return "transparent"

    if style.card_shape == "rect":
        # Same geometry as the printed rectangular cards (see render.py).
        W = 1000
        pad = W * 0.07
        inner_w, inner_h = W - 2 * pad, W * RECT_RATIO - 2 * pad
        size = min(fit_box_font_size(w.word, style.font, style.bold,
                                     int(w.w * inner_w * 0.86), int(w.h * inner_h * 0.6))
                   for w in card.words)
        for w in card.words:
            words.append({"w": w.word, "c": w.colour, "x": w.x, "y": w.y, "bw": w.w, "bh": w.h,
                          "a": 0, "fs": size / W, "f": fill(w.colour)})
    else:
        for w in card.words:
            ref = 1000
            fs = fit_font_size(w.word, style.font, style.bold, int(w.r * ref)) / ref
            words.append({"w": w.word, "c": w.colour, "x": round(w.x, 4), "y": round(w.y, 4),
                          "r": round(w.r, 4), "a": round(w.angle, 1), "fs": round(fs, 4),
                          "f": fill(w.colour)})
    payload = {"shape": style.card_shape, "bg": style.background,
               "bubbles": style.bubble_style, "words": words}
    if style.bubble_style == "outline":
        payload["stroke"] = OUTLINE_STROKE
    return payload


def deck_title(s: Settings) -> str:
    if s.deck == "custom":
        return "Own words"
    return next((d["name"] for d in BUILTIN_DECKS if d["key"] == s.deck), "Word Spot")


class Room:
    def __init__(self, code: str, layouts: list[Layout]):
        self.code = code
        self.layouts = layouts
        self.players: dict[str, Player] = {}
        self.host: str | None = None
        self.settings = Settings()
        self.phase = "lobby"          # lobby -> playing <-> answer -> finished
        self.round = 0
        self.total_rounds = 0
        self.cards: list[dict] = []
        self.answer: str | None = None
        self.winner: str | None = None
        self.round_started = 0.0
        self.answer_shown = 0.0
        self.hint = False
        self.last_active = time.time()
        self._order: list[CardSpec] = []
        self._style: CardStyle | None = None

    # ----------------------------------------------------------- players
    def add_player(self, name: str, avatar: str, player_id: str | None = None) -> Player:
        self.last_active = time.time()
        if player_id and player_id in self.players:
            p = self.players[player_id]
            p.connected = True
            return p
        if len(self.players) >= MAX_PLAYERS:
            raise ValueError("This game is full.")
        if self.phase in ("playing", "answer"):
            raise ValueError("This game has already started - wait for it to finish.")
        name = " ".join((name or "").split())[:16] or "Player"
        p = Player(id=player_id or secrets.token_urlsafe(8), name=name,
                   avatar=avatar if avatar in AVATARS else random.choice(AVATARS))
        self.players[p.id] = p
        if self.host is None or self.host not in self.players:
            self.host = p.id
        return p

    def disconnect(self, player_id: str) -> None:
        p = self.players.get(player_id)
        if not p:
            return
        p.connected = False
        if self.phase == "lobby":
            del self.players[player_id]
        if self.host == player_id:
            connected = [q.id for q in self.players.values() if q.connected]
            self.host = connected[0] if connected else None

    def connected_count(self) -> int:
        return sum(p.connected for p in self.players.values())

    # ---------------------------------------------------------- settings
    def update_settings(self, player_id: str, data: dict) -> None:
        if player_id != self.host or self.phase not in ("lobby", "finished"):
            return
        s = self.settings
        if data.get("deck") == "custom":
            words = clean_words([str(w)[:30] for w in data.get("custom_words", [])][:300])
            if len(words) >= 7:
                s.deck, s.custom_words = "custom", words
        elif deck_words(str(data.get("deck", ""))):
            s.deck = str(data["deck"])
        if data.get("rounds") in (5, 10, 20, 0):
            s.rounds = data["rounds"]
        if data.get("shape") in ("round", "rect"):
            s.shape = data["shape"]
        if data.get("font") in ("opendyslexic", "lexend", "andika"):
            s.font = data["font"]
        if data.get("words_per_card") in (0, 3, 4, 6, 8):
            s.words_per_card = data["words_per_card"]
        if data.get("colours") in ONLINE_COLOURS:
            s.colours = data["colours"]
        if isinstance(data.get("circles"), bool):
            s.circles = data["circles"]

    # -------------------------------------------------------------- game
    def start(self, player_id: str) -> None:
        if player_id != self.host or self.phase not in ("lobby", "finished"):
            return
        s = self.settings
        words = s.custom_words if s.deck == "custom" else deck_words(s.deck)
        style = game_style(s, random.randint(1, 10**9))
        plan = plan_deck(words or [], style, self.layouts)
        if len(plan.cards) < 2:
            return
        self._style = style
        self._order = plan.cards[:]
        random.shuffle(self._order)
        for p in self.players.values():
            p.score, p.times, p.frozen_until = 0, [], 0.0
        self.round = 0
        self.total_rounds = s.rounds or len(self._order) // 2
        self.total_rounds = min(self.total_rounds, len(self._order) // 2)
        self._next_round()

    def print_deck(self) -> tuple[DeckPlan, CardStyle, str]:
        """The whole deck, with this room's current settings, ready to print."""
        s = self.settings
        words = s.custom_words if s.deck == "custom" else deck_words(s.deck)
        style = game_style(s, random.randint(1, 10**9))
        return plan_deck(words or [], style, self.layouts), style, deck_title(s)

    def _next_round(self) -> None:
        self.round += 1
        if self.round > self.total_rounds:
            self.phase = "finished"
            self.cards = []
            return
        i = (self.round - 1) * 2
        a, b = self._order[i], self._order[i + 1]
        common = {w.word for w in a.words} & {w.word for w in b.words}
        self.answer = common.pop()
        self.cards = [card_payload(a, self._style), card_payload(b, self._style)]
        self.winner = None
        self.hint = False
        self.phase = "playing"
        self.round_started = time.time()

    def tap(self, player_id: str, round_no: int, word: str, now: float | None = None) -> str:
        """Returns 'win', 'wrong', 'frozen' or 'ignored'."""
        now = now or time.time()
        self.last_active = now
        p = self.players.get(player_id)
        if not p or self.phase != "playing" or round_no != self.round:
            return "ignored"
        if now < p.frozen_until:
            return "frozen"
        if word != self.answer:
            p.frozen_until = now + WRONG_FREEZE
            return "wrong"
        p.score += 1
        p.times.append(now - self.round_started)
        self.winner = p.id
        self.phase = "answer"
        self.answer_shown = now
        return "win"

    def ask_hint(self, player_id: str) -> bool:
        if (self.phase == "playing" and player_id in self.players
                and time.time() - self.round_started >= HINT_AFTER):
            self.hint = True
            return True
        return False

    def advance(self, now: float | None = None) -> bool:
        """Move on after the answer has been shown.  Returns True if it did."""
        now = now or time.time()
        if self.phase == "answer" and now - self.answer_shown >= SHOW_ANSWER:
            self._next_round()
            return True
        return False

    # ------------------------------------------------------------- state
    def public_state(self) -> dict:
        state = {
            "type": "state",
            "room": self.code,
            "phase": self.phase,
            "host": self.host,
            "players": [p.public() for p in self.players.values()],
            "settings": self.settings.public(),
            "round": self.round,
            "total_rounds": self.total_rounds,
            "cards": self.cards,
            "winner": self.winner,
            "elapsed": round(time.time() - self.round_started, 2) if self.phase == "playing" else None,
            "hint_after": HINT_AFTER,
            "hint": self.hint,
        }
        # Only reveal the answer once the round is won (or a hint is asked).
        if self.phase == "answer" or self.hint:
            state["answer"] = self.answer
        if self.phase == "answer" and self.winner:
            state["win_time"] = round(self.players[self.winner].times[-1], 1)
        if self.phase == "finished":
            state["results"] = sorted(
                ({**p.public(),
                  "avg": round(sum(p.times) / len(p.times), 1) if p.times else None,
                  "best": round(min(p.times), 1) if p.times else None,
                  "total": round(sum(p.times), 1)}
                 for p in self.players.values()),
                key=lambda r: -r["score"])
        return state


class Lobby:
    """All the rooms on this server."""

    def __init__(self, layouts: list[Layout]):
        self.layouts = layouts
        self.rooms: dict[str, Room] = {}

    def create(self) -> Room:
        if len(self.rooms) >= MAX_ROOMS:
            self.cleanup()
            if len(self.rooms) >= MAX_ROOMS:
                raise RuntimeError("The server is busy - please try again in a few minutes.")
        for _ in range(1000):
            code = "".join(secrets.choice(ROOM_LETTERS) for _ in range(4))
            if code not in self.rooms:
                room = Room(code, self.layouts)
                self.rooms[code] = room
                return room
        raise RuntimeError("No free room codes")

    def get(self, code: str) -> Room | None:
        return self.rooms.get((code or "").strip().upper())

    def cleanup(self, max_idle: float = 3 * 3600) -> None:
        now = time.time()
        for code, room in list(self.rooms.items()):
            if room.connected_count() == 0 and now - room.last_active > 120:
                del self.rooms[code]
            elif now - room.last_active > max_idle:
                del self.rooms[code]

