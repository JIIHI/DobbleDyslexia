"""Regenerate wordspot/data/layouts.json - the built-in bubble layouts.

Includes the three hand-made layouts from the original R project
(legacy/circles.xlsx) plus a pool grown with the organic growth simulation
for every deck size and a range of size varieties.

    python scripts/generate_layouts.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from wordspot.layout import Layout, fit_inside, generate_layout  # noqa: E402

VARIETIES = [0.0, 0.2, 0.4, 0.7, 1.0, 1.0, 1.3]
PER_VARIETY = 4


def classic_layouts() -> list[dict]:
    try:
        import openpyxl
    except ImportError:
        print("openpyxl not installed - skipping the classic R layouts")
        return []
    ws = openpyxl.load_workbook(ROOT / "legacy" / "circles.xlsx").active
    groups: dict[int, list] = {}
    for big_id, _cid, x, y, r, big_r in list(ws.values)[1:]:
        groups.setdefault(int(big_id), []).append((x / big_r, y / big_r, r / big_r))
    out = []
    for big_id, circles in sorted(groups.items()):
        circles = fit_inside(circles)
        if Layout(circles=circles).is_valid():
            out.append({"name": f"Classic {big_id} (from R)", "variety": 1.0, "fill": 90,
                        "circles": [[round(v, 5) for v in c] for c in circles]})
    return out


def main() -> None:
    layouts = classic_layouts()
    for n in (3, 4, 6, 8):
        for vi, variety in enumerate(VARIETIES):
            for k in range(PER_VARIETY):
                lay = generate_layout(n, variety, seed=f"builtin-{n}-{vi}-{k}")
                assert lay.is_valid(), (n, variety, k)
                layouts.append({
                    "name": f"{n} bubbles #{vi * PER_VARIETY + k + 1}",
                    "variety": variety, "fill": lay.fill,
                    "circles": [[round(v, 5) for v in c] for c in lay.circles],
                })
    out = ROOT / "wordspot" / "data" / "layouts.json"
    out.write_text(json.dumps(layouts, indent=0))
    print(f"wrote {len(layouts)} layouts to {out}")


if __name__ == "__main__":
    main()
