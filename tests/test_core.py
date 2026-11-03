from itertools import combinations

import pytest

from wordspot.builder import clean_words, plan_deck
from wordspot.deck import DECK_SIZES, best_per_card, build_deck, check_deck
from wordspot.layout import fit_inside, generate_layout, Layout
from wordspot.render import render_card
from wordspot.style import CardStyle
from wordspot.wordlists import BUILTIN_DECKS


@pytest.mark.parametrize("per_card", sorted(DECK_SIZES))
def test_every_pair_of_cards_shares_one_word(per_card):
    cards = build_deck(per_card)
    assert len(cards) == DECK_SIZES[per_card]
    assert all(len(c) == per_card for c in cards)
    assert check_deck(cards)


def test_best_per_card():
    assert best_per_card(100) == 8
    assert best_per_card(45) == 6
    assert best_per_card(45, wanted=8) == 6
    assert best_per_card(100, wanted=4) == 4
    assert best_per_card(12) == 3
    assert best_per_card(6) is None


@pytest.mark.parametrize("n", [3, 4, 6, 8])
@pytest.mark.parametrize("variety", [0.0, 1.0, 1.4])
def test_layouts_never_overlap(n, variety):
    for seed in range(3):
        lay = generate_layout(n, variety, seed=seed)
        assert lay.count == n
        assert lay.is_valid()
    if variety == 0.0:
        assert lay.size_ratio < 1.05


def test_fit_inside_fixes_overlaps():
    circles = fit_inside([(0.0, 0.0, 0.6), (0.5, 0.0, 0.6)])
    assert Layout(circles=circles).is_valid()


def test_clean_words_removes_repeats_and_blanks():
    assert clean_words(["cat", " Cat ", "", "dog  ", "big   red"]) == ["cat", "dog", "big red"]


@pytest.mark.parametrize("spec", BUILTIN_DECKS, ids=lambda s: s["key"])
def test_builtin_decks_make_valid_games(spec):
    words = spec["words"]
    assert len(clean_words(words)) == len(words), "built-in deck has repeated words"
    plan = plan_deck(words, CardStyle(seed=3), [])
    assert plan.per_card in (6, 8)
    sets = [{w.word for w in c.words} for c in plan.cards]
    assert all(len(a & b) == 1 for a, b in combinations(sets, 2))


def test_same_seed_gives_same_cards():
    words = BUILTIN_DECKS[0]["words"]
    a = plan_deck(words, CardStyle(seed=11), [])
    b = plan_deck(words, CardStyle(seed=11), [])
    c = plan_deck(words, CardStyle(seed=12), [])
    assert [[w.word for w in x.words] for x in a.cards] == [[w.word for w in x.words] for x in b.cards]
    assert [[w.word for w in x.words] for x in a.cards] != [[w.word for w in x.words] for x in c.cards]


@pytest.mark.parametrize("font", ["opendyslexic", "lexend", "andika"])
def test_render_card(font):
    plan = plan_deck(BUILTIN_DECKS[5]["words"], CardStyle(seed=1, font=font, bubble_style="soft"), [])
    img = render_card(plan.cards[0], CardStyle(font=font), 300)
    assert img.size == (300, 300)
    assert img.getpixel((0, 0))[3] == 0          # outside the card is transparent
    assert img.getpixel((150, 150))[3] == 255    # card itself is solid


def test_too_few_words():
    plan = plan_deck(["a", "b", "c"], CardStyle(), [])
    assert plan.cards == [] and plan.per_card is None


def test_angles_face_every_way():
    import random as _r
    from wordspot.builder import spread_angles
    for seed in range(50):
        for n in (3, 4, 6, 8):
            angles = sorted(spread_angles(n, _r.Random(seed)))
            gaps = [b - a for a, b in zip(angles, angles[1:])] + [angles[0] + 360 - angles[-1]]
            # no big empty arc: every side of the table gets a word
            assert max(gaps) < 2 * 360 / n
            assert all(0 <= a < 360 for a in angles)


def test_cards_use_random_angles():
    plan = plan_deck(BUILTIN_DECKS[0]["words"], CardStyle(seed=2), [])
    angles = [w.angle for c in plan.cards for w in c.words]
    assert len({round(a) for a in angles}) > 200  # genuinely varied, not one direction


@pytest.mark.parametrize("per_card", [3, 4, 6, 8])
def test_rectangular_cards_have_upright_words(per_card):
    words = BUILTIN_DECKS[4]["words"]
    style = CardStyle(seed=5, card_shape="rect", words_per_card=per_card, bubble_style="soft")
    plan = plan_deck(words, style, [])
    assert plan.per_card == per_card
    assert all(w.angle == 0 for c in plan.cards for w in c.words)
    sets = [{w.word for w in c.words} for c in plan.cards]
    assert all(len(a & b) == 1 for a, b in combinations(sets, 2))
    img = render_card(plan.cards[0], style, 300)
    assert img.size == (300, 420)
    assert img.getpixel((150, 210))[3] == 255
