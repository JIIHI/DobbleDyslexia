"""Drawing a single card as an image (Pillow)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

from PIL import Image, ImageColor, ImageDraw, ImageFont

from wordspot.paths import fonts_dir
from wordspot.style import CardStyle

SUPERSAMPLE = 2
TEXT_FIT = 0.92  # share of a bubble's diameter a word may span (corner to corner)

_FONT_FILES = {
    "opendyslexic": ("OpenDyslexic-Regular.otf", "OpenDyslexic-Bold.otf", None),
    "lexend": ("Lexend.ttf", "Lexend.ttf", ("Regular", "Bold")),
    "andika": ("Andika-Regular.ttf", "Andika-Bold.ttf", None),
}


@lru_cache(maxsize=4096)
def get_font(name: str, bold: bool, size: int) -> ImageFont.FreeTypeFont:
    regular, bold_file, variations = _FONT_FILES.get(name, _FONT_FILES["opendyslexic"])
    font = ImageFont.truetype(str(fonts_dir() / (bold_file if bold else regular)), size)
    if variations:
        font.set_variation_by_name(variations[1] if bold else variations[0])
    return font


@lru_cache(maxsize=8192)
def fit_font_size(word: str, font: str, bold: bool, radius_px: int) -> int:
    """Largest font size whose text box fits inside a bubble of this radius.

    A box centred in a circle fits when its half-diagonal is within the
    radius.  That holds at every rotation, so rotated words fit too.
    """
    limit = radius_px * TEXT_FIT
    lo, hi = 4, max(8, radius_px * 3)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        left, top, right, bottom = get_font(font, bold, mid).getbbox(word, anchor="mm")
        if math.hypot(right - left, bottom - top) / 2 <= limit:
            lo = mid
        else:
            hi = mid - 1
    return lo


@dataclass
class PlacedWord:
    word: str
    colour: str
    angle: float
    x: float  # unit coordinates, card radius = 1
    y: float
    r: float


@dataclass
class CardSpec:
    number: int
    words: list[PlacedWord]


def _soft(colour: str, background: str, amount: float = 0.12) -> tuple[int, int, int]:
    c = ImageColor.getrgb(colour)
    b = ImageColor.getrgb(background)
    return tuple(round(b[i] + (c[i] - b[i]) * amount) for i in range(3))


def render_card(card: CardSpec, style: CardStyle, size_px: int,
                show_number: bool | None = None) -> Image.Image:
    """Draw one card.  The result is a square RGBA image, transparent
    outside the round card."""
    ss = SUPERSAMPLE if size_px < 800 else 1  # print sizes are sharp enough already
    size = size_px * ss
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    centre = size / 2
    border = max(2, round(size * 0.006)) if style.card_border else 0
    radius = size / 2 - max(border, 1) - ss  # leave a hair of room for anti-aliasing

    draw.ellipse(
        (centre - radius, centre - radius, centre + radius, centre + radius),
        fill=style.background,
        outline="#2b2b2b" if border else None,
        width=border or 1,
    )

    inner = radius - border  # bubbles live inside the border
    for pw in card.words:
        bx = centre + pw.x * inner
        by = centre + pw.y * inner
        br = pw.r * inner
        if style.bubble_style == "outline":
            draw.ellipse((bx - br, by - br, bx + br, by + br), outline="#b8c2cc",
                         width=max(1, round(size * 0.003)))
        elif style.bubble_style == "soft":
            draw.ellipse((bx - br, by - br, bx + br, by + br),
                         fill=_soft(pw.colour, style.background))

        font_size = fit_font_size(pw.word, style.font, style.bold, int(br))
        font = get_font(style.font, style.bold, font_size)
        left, top, right, bottom = font.getbbox(pw.word, anchor="mm")
        pad = 4 * ss
        w, h = right - left + 2 * pad, bottom - top + 2 * pad
        word_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(word_img).text((pad - left, pad - top), pw.word, font=font,
                                      fill=pw.colour, anchor="mm")
        if pw.angle:
            word_img = word_img.rotate(pw.angle, resample=Image.BICUBIC, expand=True)
        img.alpha_composite(word_img, (round(bx - word_img.width / 2), round(by - word_img.height / 2)))

    numbered = style.card_numbers if show_number is None else show_number
    if numbered:
        num_font = get_font("lexend", False, max(8, round(size * 0.028)))
        draw.text((size - 2 * ss, size - 2 * ss), str(card.number), font=num_font,
                  fill="#9aa5b1", anchor="rd")

    if ss > 1:
        img = img.resize((size_px, size_px), Image.LANCZOS)
    return img
