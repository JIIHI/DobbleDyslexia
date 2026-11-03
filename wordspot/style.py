"""Card style settings and the choices offered in the app."""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, fields

# label shown in the app -> value
FONTS = {
    "OpenDyslexic": "opendyslexic",
    "Lexend": "lexend",
    "Andika (single-storey a)": "andika",
}

BACKGROUNDS = {
    "Cream": "#fdf6e3",
    "White": "#ffffff",
    "Pale yellow": "#fff9c4",
    "Pale blue": "#e3f2fd",
    "Pale green": "#e8f5e9",
    "Pale pink": "#fce4ec",
}

WORD_COLOURS = {
    "Colourful": "colourful",
    "All black": "black",
    "All dark blue": "navy",
}

# Dark colours that stay readable on all the pale backgrounds.
PALETTE = [
    "#1d4ed8",  # blue
    "#b91c1c",  # red
    "#15803d",  # green
    "#7e22ce",  # purple
    "#c2410c",  # orange
    "#0f766e",  # teal
    "#be185d",  # pink
    "#92400e",  # brown
    "#4338ca",  # indigo
    "#374151",  # charcoal
]

CARD_SHAPES = {
    "Round - group play (words face every way)": "round",
    "Rectangle - one-to-one (words upright)": "rect",
}

LETTER_CASES = {
    "As typed": "as_typed",
    "lowercase": "lower",
    "UPPERCASE": "upper",
}

BUBBLE_STYLES = {
    "Hidden": "none",
    "Outline": "outline",
    "Soft colour": "soft",
}

BUBBLE_SIZES = {
    "Mixed sizes (classic)": "mixed",
    "More even": "even",
    "All the same": "same",
}

WORDS_PER_CARD = {
    "Automatic (as many as possible)": 0,
    "8 words - 57 cards": 8,
    "6 words - 31 cards": 6,
    "4 words - 13 cards": 4,
    "3 words - 7 cards": 3,
}

CARD_SIZES_MM = {
    "Large - 90 mm wide": 90,
    "Medium - 80 mm wide": 80,
    "Small - 62 mm wide": 62,
}

#: rectangular cards are this many times taller than they are wide
RECT_RATIO = 1.4


@dataclass
class CardStyle:
    font: str = "opendyslexic"
    card_shape: str = "round"
    bold: bool = False
    background: str = "#fdf6e3"
    word_colours: str = "colourful"
    letter_case: str = "as_typed"
    card_border: bool = True
    bubble_style: str = "none"
    bubble_sizes: str = "mixed"
    long_words_big: bool = True
    words_per_card: int = 0
    card_mm: int = 90
    card_numbers: bool = True
    cut_guides: bool = True
    seed: int = 1

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, text: str | None) -> "CardStyle":
        style = cls()
        if not text:
            style.seed = random.randint(1, 999_999)
            return style
        try:
            data = json.loads(text)
        except ValueError:
            return style
        known = {f.name for f in fields(cls)}
        for key, value in data.items():
            if key in known:
                setattr(style, key, value)
        return style
