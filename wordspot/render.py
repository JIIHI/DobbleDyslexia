"""Drawing a single card as an image (Pillow)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

from PIL import Image, ImageColor, ImageDraw, ImageFont

from wordspot.paths import fonts_dir
from wordspot.style import RECT_RATIO, CardStyle, bubble_tint

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
    x: float  # round cards: unit coordinates, card radius = 1
    y: float  # rectangular cards: centre as a fraction of card width/height
    r: float
    w: float = 0.0  # rectangular cards: box size as a fraction of card width/height
    h: float = 0.0


@dataclass
class CardSpec:
    number: int
    words: list[PlacedWord]


def _soft(colour: str, background: str, amount: float = 0.12) -> tuple[int, int, int]:
    c = ImageColor.getrgb(colour)
    b = ImageColor.getrgb(background)
    return tuple(round(b[i] + (c[i] - b[i]) * amount) for i in range(3))


@lru_cache(maxsize=8192)
def fit_box_font_size(word: str, font: str, bold: bool, box_w: int, box_h: int) -> int:
    """Largest font size whose upright text fits inside a box."""
    lo, hi = 4, max(8, box_h * 3)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        left, top, right, bottom = get_font(font, bold, mid).getbbox(word, anchor="mm")
        if right - left <= box_w and bottom - top <= box_h:
            lo = mid
        else:
            hi = mid - 1
    return lo


def card_height(style: CardStyle, width_px: int) -> int:
    return round(width_px * RECT_RATIO) if style.card_shape == "rect" else width_px


def render_card(card: CardSpec, style: CardStyle, size_px: int,
                show_number: bool | None = None) -> Image.Image:
    """Draw one card ``size_px`` wide.  Round cards are square images,
    transparent outside the circle; rectangular cards are taller."""
    if style.card_shape == "rect":
        return _render_rect(card, style, size_px, show_number)
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
                         fill=_soft(pw.colour, style.background, bubble_tint(style.word_colours)))

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


def _render_rect(card: CardSpec, style: CardStyle, width_px: int,
                 show_number: bool | None) -> Image.Image:
    ss = SUPERSAMPLE if width_px < 800 else 1
    W = width_px * ss
    H = card_height(style, width_px) * ss
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    border = max(2, round(W * 0.006)) if style.card_border else 0
    edge = max(border, 1) + ss
    corner = round(W * 0.06)
    draw.rounded_rectangle((edge, edge, W - edge, H - edge), radius=corner,
                           fill=style.background, outline="#2b2b2b" if border else None,
                           width=border or 1)

    pad = W * 0.07
    inner_w, inner_h = W - 2 * pad, H - 2 * pad
    # Every word on a rectangular card gets the same size: calmer and fairer.
    size = min((fit_box_font_size(pw.word, style.font, style.bold,
                                  int(pw.w * inner_w * 0.86), int(pw.h * inner_h * 0.6))
                for pw in card.words), default=10)
    for pw in card.words:
        cx, cy = pad + pw.x * inner_w, pad + pw.y * inner_h
        bw, bh = pw.w * inner_w, pw.h * inner_h
        box = (cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2)
        if style.bubble_style == "outline":
            draw.rounded_rectangle(box, radius=round(bh * 0.25), outline="#b8c2cc",
                                   width=max(1, round(W * 0.003)))
        elif style.bubble_style == "soft":
            draw.rounded_rectangle(box, radius=round(bh * 0.25),
                                   fill=_soft(pw.colour, style.background, bubble_tint(style.word_colours)))
        draw.text((cx, cy), pw.word, font=get_font(style.font, style.bold, size),
                  fill=pw.colour, anchor="mm")

    numbered = style.card_numbers if show_number is None else show_number
    if numbered:
        num_font = get_font("lexend", False, max(8, round(W * 0.03)))
        draw.text((W - corner, H - edge - round(W * 0.02)), str(card.number), font=num_font,
                  fill="#9aa5b1", anchor="rb")

    if ss > 1:
        img = img.resize((width_px, H // ss), Image.LANCZOS)
    return img
