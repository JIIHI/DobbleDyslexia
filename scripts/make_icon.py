"""Draw the app icon (wordspot/data/icon.png, .ico and .icns).

    python scripts/make_icon.py
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from wordspot.render import get_font  # noqa: E402

S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((40, 40, S - 40, S - 40), radius=220, fill="#4f46e5")
d.ellipse((130, 130, S - 130, S - 130), fill="#fdf6e3", outline="#1e1b4b", width=18)
bubbles = [((420, 400), 165, "#fecaca"), ((650, 600), 140, "#bbf7d0"),
           ((380, 680), 110, "#c7d2fe"), ((680, 330), 95, "#fde68a")]
for (x, y), r, c in bubbles:
    d.ellipse((x - r, y - r, x + r, y + r), fill=c)
font = get_font("opendyslexic", True, 150)
d.text((420, 400), "cat", font=font, fill="#b91c1c", anchor="mm")
small = get_font("opendyslexic", True, 105)
word = Image.new("RGBA", (400, 220), (0, 0, 0, 0))
ImageDraw.Draw(word).text((200, 110), "sun", font=small, fill="#15803d", anchor="mm")
word = word.rotate(-25, resample=Image.BICUBIC, expand=True)
img.alpha_composite(word, (650 - word.width // 2, 600 - word.height // 2))

out = ROOT / "wordspot" / "data"
img.save(out / "icon.png")
img.save(out / "icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
img.save(out / "icon.icns")
print("icons written to", out)
