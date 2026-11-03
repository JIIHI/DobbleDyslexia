"""The maths behind the game: every pair of cards shares exactly one word.

A deck with ``n`` words per card is the finite projective plane of order
``q = n - 1``.  It has ``q*q + q + 1`` cards and the same number of words.
The construction below works when ``q`` is prime, which gives the deck
sizes the app offers (3, 4, 6 and 8 words per card).
"""

from __future__ import annotations

from itertools import combinations

#: words per card -> number of cards (and number of different words needed)
DECK_SIZES: dict[int, int] = {3: 7, 4: 13, 6: 31, 8: 57}


def words_needed(per_card: int) -> int:
    if per_card not in DECK_SIZES:
        raise ValueError(f"Unsupported words per card: {per_card}")
    return DECK_SIZES[per_card]


def best_per_card(word_count: int, wanted: int | None = None) -> int | None:
    """Largest supported deck that ``word_count`` words can fill.

    If ``wanted`` is given and there are enough words for it, use it.
    Returns ``None`` when there are too few words for even the smallest deck.
    """
    if wanted and word_count >= DECK_SIZES.get(wanted, 10**9):
        return wanted
    options = [n for n, need in sorted(DECK_SIZES.items()) if word_count >= need]
    if not options:
        return None
    if wanted:
        smaller = [n for n in options if n <= wanted]
        if smaller:
            return smaller[-1]
    return options[-1]


def build_deck(per_card: int) -> list[list[int]]:
    """Return the cards as lists of word indices (0-based)."""
    words_needed(per_card)
    q = per_card - 1
    cards: list[list[int]] = []
    # Words 0 .. q*q-1 are grid points (x, y) -> x*q + y.
    # Words q*q .. q*q+q-1 are the "slopes" m, word q*q+q is "vertical".
    for m in range(q):
        for c in range(q):
            card = [x * q + ((m * x + c) % q) for x in range(q)]
            card.append(q * q + m)
            cards.append(card)
    for x in range(q):
        card = [x * q + y for y in range(q)]
        card.append(q * q + q)
        cards.append(card)
    cards.append([q * q + m for m in range(q)] + [q * q + q])
    return cards


def check_deck(cards: list[list[int]]) -> bool:
    """True if every pair of cards shares exactly one word."""
    sets = [set(c) for c in cards]
    if any(len(s) != len(c) for s, c in zip(sets, cards)):
        return False
    return all(len(a & b) == 1 for a, b in combinations(sets, 2))
