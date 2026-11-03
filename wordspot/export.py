"""Exporting decks: A4 PDF for printing, ZIP of single-card PNGs, and
importing word lists from files."""

from __future__ import annotations

import csv
import io
import re
import zipfile
from pathlib import Path
from typing import Callable, Iterable

from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from wordspot import APP_NAME
from wordspot.builder import DeckPlan
from wordspot.render import CardSpec, render_card
from wordspot.style import CardStyle

PRINT_DPI = 300
PAGE_MARGIN_MM = 6
GAP_MM = 4

Progress = Callable[[int, int], bool]  # (done, total) -> keep going?


def card_px(style: CardStyle, dpi: int = PRINT_DPI) -> int:
    return round(style.card_mm / 25.4 * dpi)


def render_cards(cards: Iterable[CardSpec], style: CardStyle, total: int,
                 progress: Progress | None = None, show_number: bool | None = None
                 ) -> list[tuple[int, Image.Image]]:
    out = []
    px = card_px(style)
    for i, card in enumerate(cards):
        out.append((card.number, render_card(card, style, px, show_number=show_number)))
        if progress and progress(i + 1, total) is False:
            raise InterruptedError("Export cancelled")
    return out


def grid_for(card_mm: float) -> tuple[int, int]:
    page_w, page_h = 210, 297
    cols = int((page_w - 2 * PAGE_MARGIN_MM + GAP_MM) // (card_mm + GAP_MM))
    rows = int((page_h - 2 * PAGE_MARGIN_MM + GAP_MM) // (card_mm + GAP_MM))
    return max(1, cols), max(1, rows)


def write_pdf(target, images: list[tuple[int, Image.Image]], style: CardStyle,
              title: str) -> None:
    """Lay the cards out on A4 pages (centred grid) and save as PDF."""
    page_w, page_h = A4
    d = style.card_mm * mm
    cols, rows = grid_for(style.card_mm)
    per_page = cols * rows
    grid_w = cols * d + (cols - 1) * GAP_MM * mm
    grid_h = rows * d + (rows - 1) * GAP_MM * mm
    x0 = (page_w - grid_w) / 2
    y_top = page_h - (page_h - grid_h) / 2
    pages = max(1, -(-len(images) // per_page))

    pdf = canvas.Canvas(target, pagesize=A4)
    pdf.setTitle(f"{APP_NAME} - {title}")
    pdf.setAuthor(APP_NAME)
    for p in range(pages):
        chunk = images[p * per_page:(p + 1) * per_page]
        for i, (number, img) in enumerate(chunk):
            col, row = i % cols, i // cols
            x = x0 + col * (d + GAP_MM * mm)
            y = y_top - (row + 1) * d - row * GAP_MM * mm
            buf = io.BytesIO()
            img.save(buf, "PNG")
            buf.seek(0)
            pdf.drawImage(ImageReader(buf), x, y, d, d, mask="auto")
            if style.cut_guides and not style.card_border:
                pdf.setStrokeColorRGB(0.75, 0.75, 0.75)
                pdf.setLineWidth(0.4)
                pdf.setDash(2, 2)
                pdf.circle(x + d / 2, y + d / 2, d / 2 - 0.3 * mm)
                pdf.setDash()
        pdf.setFont("Helvetica", 8)
        pdf.setFillColorRGB(0.55, 0.55, 0.55)
        pdf.drawCentredString(page_w / 2, 5 * mm,
                              f"{APP_NAME} - {title} - page {p + 1} of {pages}")
        pdf.showPage()
    pdf.save()


def export_pdf(path: Path | str, plan: DeckPlan, style: CardStyle, title: str,
               progress: Progress | None = None, card_numbers: list[int] | None = None) -> None:
    cards = [c for c in plan.cards if card_numbers is None or c.number in card_numbers]
    images = render_cards(cards, style, len(cards), progress)
    write_pdf(str(path), images, style, title)


def safe_name(text: str) -> str:
    return re.sub(r"[^\w\- ]+", "", text).strip().replace(" ", "_") or "deck"


def export_zip(path: Path | str, plan: DeckPlan, style: CardStyle, title: str,
               progress: Progress | None = None) -> None:
    """ZIP with one PNG per card (so a single lost card can be re-printed)
    plus the full A4 PDF."""
    images = render_cards(plan.cards, style, len(plan.cards), progress)
    width = len(str(len(images)))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for number, img in images:
            buf = io.BytesIO()
            img.save(buf, "PNG", dpi=(PRINT_DPI, PRINT_DPI))
            zf.writestr(f"cards/Card_{number:0{width}d}.png", buf.getvalue())
        pdf_buf = io.BytesIO()
        write_pdf(pdf_buf, images, style, title)
        zf.writestr(f"{safe_name(title)}_A4.pdf", pdf_buf.getvalue())
        words = "\n".join(
            f"Card {c.number}: " + ", ".join(w.word for w in c.words) for c in plan.cards)
        zf.writestr("README.txt", (
            f"{APP_NAME} - {title}\n\n"
            f"{plan.summary()}.\n"
            f"Each PNG is {style.card_mm} mm across when printed at {PRINT_DPI} dpi.\n"
            f"To replace a lost card, print just that PNG at 100% / actual size.\n\n"
            f"Words on each card:\n{words}\n"))


# ------------------------------------------------------------------ importing
_SKIP = {"word", "words", "x", "id", ""}


def _keep(cell: str) -> bool:
    cell = cell.strip()
    return cell.lower() not in _SKIP and not re.fullmatch(r"[\d.\s]+", cell)


def read_word_file(path: Path | str) -> list[str]:
    """Read words from a .txt, .csv or .xlsx file (one per line/cell)."""
    path = Path(path)
    suffix = path.suffix.lower()
    cells: list[str] = []
    if suffix in (".xlsx", ".xlsm"):
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        for ws in wb.worksheets[:1]:
            for row in ws.iter_rows(values_only=True):
                cells.extend(str(v) for v in row if v is not None)
    elif suffix == ".csv":
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for row in csv.reader(io.StringIO(text)):
            cells.extend(row)
    else:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        cells = re.split(r"[\n,;\t]+", text)
    return [c.strip() for c in cells if _keep(c)]
