"""Bubble layouts: where the word bubbles sit on a card.

This is a Python port of the "organic growth" simulation from the original
R project (``legacy/organic growth.R``).  Small seed circles are scattered
inside the card, then grow step by step.  Circles that are crowded by big
neighbours grow more slowly (inhibition), overlapping circles push each
other apart, and the card edge pushes everything back inside.  Growth
stops when the bubbles fill the chosen share of the card.

Two knobs are exposed to users:

* ``variety`` - 0 makes every bubble the same size, 1 matches the original
  R behaviour, larger values make the sizes more mixed.
* ``fill`` - how much of the card the bubbles cover (0-100).

Layouts are stored in unit coordinates: the card is a circle of radius 1
centred on (0, 0); each bubble is ``(x, y, r)``.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Iterator

# The simulation runs in the same units as the R version (card radius 550)
# so its tuned constants still make sense.
SIM_RADIUS = 550.0
STEPS = 300
RELAX_STEPS = 60
GAP = 0.012  # minimum gap between bubbles, as a fraction of card radius

# Best possible coverage for n equal circles packed in a circle.
MAX_DENSITY = {3: 0.646, 4: 0.686, 5: 0.685, 6: 0.667, 7: 0.778, 8: 0.733}

DEFAULT_VARIETY = 1.0
DEFAULT_FILL = 80


@dataclass
class Layout:
    circles: list[tuple[float, float, float]]
    name: str = ""
    variety: float = DEFAULT_VARIETY
    fill: int = DEFAULT_FILL
    id: int | None = None
    builtin: bool = False
    enabled: bool = True
    extra: dict = field(default_factory=dict)

    @property
    def count(self) -> int:
        return len(self.circles)

    @property
    def size_ratio(self) -> float:
        """Biggest bubble radius divided by the smallest."""
        radii = [c[2] for c in self.circles]
        return max(radii) / min(radii)

    @property
    def coverage(self) -> float:
        return sum(c[2] ** 2 for c in self.circles)

    def is_valid(self, tol: float = 1e-6) -> bool:
        cs = self.circles
        for i, (x, y, r) in enumerate(cs):
            if r <= 0 or math.hypot(x, y) + r > 1 + tol:
                return False
            for x2, y2, r2 in cs[i + 1:]:
                if math.hypot(x - x2, y - y2) < r + r2 - tol:
                    return False
        return True


def target_coverage(n: int, fill: float) -> float:
    dens = MAX_DENSITY.get(n, 0.65)
    return dens * (0.6 + 0.4 * max(0.0, min(100.0, fill)) / 100.0)


def _random_points(n: int, rng: random.Random) -> tuple[list[float], list[float]]:
    xs, ys = [], []
    for _ in range(n):
        angle = rng.uniform(0, 2 * math.pi)
        radius = math.sqrt(rng.uniform(0, SIM_RADIUS ** 2))
        xs.append(radius * math.cos(angle))
        ys.append(radius * math.sin(angle))
    return xs, ys


def _push_apart(xs: list[float], ys: list[float], radii: list[float], rng: random.Random) -> None:
    """One movement pass: overlapping bubbles repel, the edge pushes in."""
    n = len(radii)
    for i in range(n):
        fx = fy = 0.0
        for j in range(n):
            if i == j:
                continue
            dx, dy = xs[i] - xs[j], ys[i] - ys[j]
            dist = math.hypot(dx, dy)
            overlap = radii[i] + radii[j] - dist
            if overlap > 0:
                if dist < 1e-9:  # same spot: nudge in a random direction
                    a = rng.uniform(0, 2 * math.pi)
                    dx, dy, dist = math.cos(a), math.sin(a), 1.0
                fx += overlap * dx / dist
                fy += overlap * dy / dist
        dist_c = math.hypot(xs[i], ys[i])
        over_edge = dist_c + radii[i] - SIM_RADIUS
        if over_edge > 0 and dist_c > 1e-9:
            fx -= over_edge * xs[i] / dist_c
            fy -= over_edge * ys[i] / dist_c
        xs[i] += fx
        ys[i] += fy


def grow(n: int, variety: float = DEFAULT_VARIETY, fill: float = DEFAULT_FILL,
         seed: int | str | None = None) -> Iterator[list[tuple[float, float, float]]]:
    """Run the growth simulation, yielding the bubbles (unit coords) each step.

    The last value yielded is the finished, overlap-free layout.
    """
    rng = random.Random(seed)
    xs, ys = _random_points(n, rng)
    radii = [3.0] * n
    coverage = target_coverage(n, fill)

    def frame() -> list[tuple[float, float, float]]:
        return [(x / SIM_RADIUS, y / SIM_RADIUS, r / SIM_RADIUS) for x, y, r in zip(xs, ys, radii)]

    for _ in range(STEPS):
        # Inhibition from crowding.  As in the R original the running total
        # carries over from one circle to the next, which is what gives the
        # bubbles their spread of sizes.
        inhibition, running = [], 0.0
        for i in range(n):
            for j in range(n):
                if i != j:
                    dist = math.hypot(xs[i] - xs[j], ys[i] - ys[j])
                    running += radii[j] / (dist + 1)
            inhibition.append(running)
        top = max(inhibition) or 1.0
        norm_inhib = [v / top for v in inhibition]

        maturation = sum(r * r for r in radii) / (SIM_RADIUS ** 2)
        sign_g = coverage - maturation
        smallest = min(radii)
        for i in range(n):
            cap = 1.0 / (1.0 + math.exp(-0.05 * (radii[i] / smallest - 10)))
            radii[i] = max(1.0, radii[i] + (1.0 / cap - variety * norm_inhib[i]) * sign_g)

        _push_apart(xs, ys, radii, rng)
        yield frame()

    for _ in range(RELAX_STEPS):
        _push_apart(xs, ys, radii, rng)

    # Guarantee no overlaps and a small gap: shrink every bubble just enough.
    fitted = fit_inside(frame())
    xs = [c[0] * SIM_RADIUS for c in fitted]
    ys = [c[1] * SIM_RADIUS for c in fitted]
    radii = [c[2] * SIM_RADIUS for c in fitted]
    yield frame()


def fit_inside(circles: list[tuple[float, float, float]], gap: float = GAP
               ) -> list[tuple[float, float, float]]:
    """Shrink all bubbles by the same factor until none overlap and each
    keeps ``gap`` away from its neighbours and the card edge."""
    scale = 1.0
    for i, (x, y, r) in enumerate(circles):
        scale = min(scale, (1 - gap - math.hypot(x, y)) / r)
        for x2, y2, r2 in circles[i + 1:]:
            scale = min(scale, (math.hypot(x - x2, y - y2) - gap) / (r + r2))
    scale = max(scale, 0.05)
    return [(x, y, r * scale) for x, y, r in circles]


def generate_layout(n: int, variety: float = DEFAULT_VARIETY, fill: float = DEFAULT_FILL,
                    seed: int | str | None = None, attempts: int = 6) -> Layout:
    """Generate a finished layout.  Retries a few times to avoid layouts where
    a jammed bubble had to shrink a lot (which leaves tiny bubbles)."""
    best: Layout | None = None
    for attempt in range(attempts):
        final = None
        for final in grow(n, variety, fill, seed=f"{seed}-{attempt}" if seed is not None else None):
            pass
        layout = Layout(circles=final, variety=variety, fill=int(fill))
        if best is None or layout.coverage > best.coverage:
            best = layout
        if layout.coverage >= 0.85 * target_coverage(n, fill):
            break
    assert best is not None
    return best
