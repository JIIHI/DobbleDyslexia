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
    "Pale grey": "#eef0f3",
    "Pale blue": "#e3f2fd",
    "Pale green": "#e8f5e9",
    "Pale pink": "#fce4ec",
    "Pale yellow": "#fff9c4",
    "Lilac": "#f1ebfa",
}

# Card colours offered in the online game: key -> colour.
CARD_COLOURS = {
    "cream": "#fdf6e3",
    "white": "#ffffff",
    "grey": "#eef0f3",
    "blue": "#e3f2fd",
    "green": "#e8f5e9",
    "pink": "#fce4ec",
    "yellow": "#fff9c4",
    "lilac": "#f1ebfa",
}

WORD_COLOURS = {
    "Colourful": "colourful",
    "Bright": "bright",
    "Pastel": "pastel",
    "All black": "black",
    "All dark grey": "grey",
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

# Strong, vivid colours - still readable on the pale backgrounds.
PALETTE_BRIGHT = [
    "#0061ff",  # blue
    "#e00000",  # red
    "#008a2e",  # green
    "#9b00e8",  # purple
    "#e05200",  # orange
    "#00838f",  # teal
    "#e6007a",  # pink
    "#b35c00",  # amber
    "#4f3cff",  # violet
    "#0077b6",  # sea blue
]

# Softer mid-tones - gentler on the eye but still readable as text.
PALETTE_PASTEL = [
    "#5b8bd9",  # blue
    "#d06560",  # red
    "#3f9660",  # green
    "#a07bd6",  # purple
    "#c67a3f",  # orange
    "#33958f",  # teal
    "#c7629a",  # pink
    "#b08850",  # sand
    "#7c83db",  # periwinkle
    "#7b8794",  # slate
]

# Word colour scheme -> the colours the words are drawn in.
SCHEME_COLOURS = {
    "colourful": PALETTE,
    "bright": PALETTE_BRIGHT,
    "pastel": PALETTE_PASTEL,
    "black": ["#111111"],
    "grey": ["#4b5563"],
    "navy": ["#1e3a8a"],
    "bw": ["#000000"],
}

# How strongly the word colour tints the soft bubble behind it (0 = invisible).
BUBBLE_TINT = {
    "colourful": 0.13,
    "bright": 0.12,
    "pastel": 0.30,
    "black": 0.08,
    "grey": 0.08,
    "navy": 0.10,
    "bw": 0.0,
}


def bubble_tint(word_colours: str) -> float:
    return BUBBLE_TINT.get(word_colours, 0.13)


def soft_colour(colour: str, background: str, amount: float) -> str:
    """The word colour mixed into the background, as ``#rrggbb``."""
    c = [int(colour.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(background.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(b[i] + (c[i] - b[i]) * amount):02x}" for i in range(3))


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
