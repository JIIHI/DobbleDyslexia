"""Turning a word list + style into the cards of a deck.

Everything is driven by the deck's ``seed``, so the same deck and style
always produce exactly the same cards.  That means a lost or chewed card
can be re-printed later and still match the rest of the set.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from wordspot.deck import DECK_SIZES, best_per_card, build_deck
from wordspot.layout import Layout, generate_layout
from wordspot.render import CardSpec, PlacedWord
from wordspot.style import PALETTE, SCHEME_COLOURS, CardStyle

# Biggest-to-smallest bubble ratio allowed by each "bubble sizes" choice.
SIZE_LIMITS = {"mixed": 99.0, "even": 1.3, "same": 1.08}
# Variety used when there are no saved layouts matching the choice.
FALLBACK_VARIETY = {"mixed": 1.0, "even": 0.4, "same": 0.0}


def clean_words(words: list[str]) -> list[str]:
    """Strip blanks and remove repeats (ignoring capital letters)."""
    seen: set[str] = set()
    result = []
    for w in words:
        w = " ".join(w.split())
        if w and w.lower() not in seen:
            seen.add(w.lower())
            result.append(w)
    return result


def apply_case(word: str, letter_case: str) -> str:
    if letter_case == "lower":
        return word.lower()
    if letter_case == "upper":
        return word.upper()
    return word


@dataclass
class DeckPlan:
    per_card: int | None
    words_used: list[str]
    total_words: int
    cards: list[CardSpec]

    @property
    def card_count(self) -> int:
        return len(self.cards)

    @property
    def needed(self) -> int | None:
        return DECK_SIZES.get(self.per_card) if self.per_card else None

    def summary(self) -> str:
        if not self.per_card:
            return (f"{self.total_words} words - you need at least 7 different words "
                    f"to make a deck.")
        msg = f"{self.card_count} cards with {self.per_card} words on each"
        if self.total_words > len(self.words_used):
            msg += f" (using {len(self.words_used)} of your {self.total_words} words)"
        return msg


# Rectangular cards: words sit in a grid of (columns, rows).
RECT_GRIDS = {8: (2, 4), 6: (2, 3), 4: (2, 2), 3: (1, 3)}
RECT_GAP = 0.05  # gap between word boxes, as a fraction of the card


def rect_boxes(n: int) -> list[tuple[float, float, float, float]]:
    """(centre x, centre y, width, height) of each word box, as fractions."""
    cols, rows = RECT_GRIDS[n]
    w = (1 - RECT_GAP * (cols - 1)) / cols
    h = (1 - RECT_GAP * (rows - 1)) / rows
    return [(c * (w + RECT_GAP) + w / 2, r * (h + RECT_GAP) + h / 2, w, h)
            for r in range(rows) for c in range(cols)]


def spread_angles(n: int, rng: random.Random) -> list[float]:
    """Random word angles, spread all the way round the card.

    Round cards are played from every side of the table, so each card needs
    words facing every player.  The circle is split into ``n`` equal slices,
    each word gets a random angle inside its own slice (starting from a
    random offset), and the slices are shuffled between the words.
    """
    slice_ = 360.0 / n
    offset = rng.uniform(0, 360)
    angles = [(offset + k * slice_ + rng.uniform(0.1, 0.9) * slice_) % 360 for k in range(n)]
    rng.shuffle(angles)
    return angles


def matching_layouts(layouts: list[Layout], per_card: int, bubble_sizes: str) -> list[Layout]:
    limit = SIZE_LIMITS.get(bubble_sizes, 99.0)
    return [l for l in layouts
            if l.enabled and l.count == per_card and l.size_ratio <= limit + 1e-9]


def plan_deck(words: list[str], style: CardStyle, layouts: list[Layout]) -> DeckPlan:
    words = clean_words(words)
    per_card = best_per_card(len(words), style.words_per_card or None)
    if per_card is None:
        return DeckPlan(None, [], len(words), [])

    seed = style.seed
    needed = DECK_SIZES[per_card]
    rng = random.Random(f"{seed}:choose")
    chosen = words[:] if len(words) == needed else rng.sample(words, needed)
    rng.shuffle(chosen)

    colour_rng = random.Random(f"{seed}:colours")
    palette = list(SCHEME_COLOURS.get(style.word_colours, PALETTE))
    colour_rng.shuffle(palette)
    colours = [palette[i % len(palette)] for i in range(needed)]

    pool = matching_layouts(layouts, per_card, style.bubble_sizes)
    template = build_deck(per_card)
    card_order = list(range(len(template)))
    random.Random(f"{seed}:order").shuffle(card_order)

    cards = []
    for number, idx in enumerate(card_order, start=1):
        crng = random.Random(f"{seed}:card:{number}")
        if style.card_shape == "rect":
            word_ids = template[idx][:]
            crng.shuffle(word_ids)
            placed = [PlacedWord(apply_case(chosen[wid], style.letter_case), colours[wid], 0.0,
                                 x, y, 0.0, w, h)
                      for wid, (x, y, w, h) in zip(word_ids, rect_boxes(per_card))]
            cards.append(CardSpec(number, placed))
            continue
        if pool:
            layout = crng.choice(pool)
        else:
            layout = generate_layout(per_card, FALLBACK_VARIETY.get(style.bubble_sizes, 1.0),
                                     seed=f"{seed}:layout:{number}")
        circles = list(layout.circles)
        # Spin the layout to a random angle and maybe mirror it so repeated
        # layouts don't look the same.
        turn = crng.uniform(0, 2 * math.pi)
        flip = crng.random() < 0.5
        cos_t, sin_t = math.cos(turn), math.sin(turn)
        circles = [((-x if flip else x) * cos_t - y * sin_t,
                    (-x if flip else x) * sin_t + y * cos_t, r) for x, y, r in circles]

        word_ids = template[idx][:]
        crng.shuffle(word_ids)
        if style.long_words_big:
            word_ids.sort(key=lambda i: len(chosen[i]), reverse=True)
            circles.sort(key=lambda c: c[2], reverse=True)
        else:
            crng.shuffle(circles)

        angles = spread_angles(len(word_ids), crng)
        placed = []
        for wid, (x, y, r), angle in zip(word_ids, circles, angles):
            placed.append(PlacedWord(apply_case(chosen[wid], style.letter_case),
                                     colours[wid], angle, x, y, r))
        cards.append(CardSpec(number, placed))

    return DeckPlan(per_card, chosen, len(words), cards)
