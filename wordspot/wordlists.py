"""Built-in decks, based on the UK phonics progression (Letters and Sounds)
and the National Curriculum (England) common exception words.

A full deck of 8 words per card needs 57 different words.  Shorter lists
still work: the app picks the biggest deck the list can fill
(6 per card = 31 words, 4 per card = 13 words, 3 per card = 7 words).
"""

from __future__ import annotations


def _w(text: str) -> list[str]:
    return [w.strip() for w in text.replace("\n", ",").split(",") if w.strip()]


BUILTIN_DECKS: list[dict] = [
    {
        "key": "phase2",
        "name": "Phase 2 - first sounds (CVC)",
        "description": "Simple three-letter words using s a t p i n m d g o c k ck e u r h b f l ff ll ss.",
        "words": _w("""
            sat, pat, tap, pin, tin, nap, map, man, mat, dad, dig, dog, got, cat, can,
            cap, kit, kid, sock, kick, duck, neck, red, hen, pen, ten, bed, leg, peg, sun,
            run, bun, cup, mud, rug, hug, hat, hot, hop, hit, bag, big, bat, bin, bus,
            fan, fig, fun, fog, fit, lip, log, lap, let, off, puff, bell, doll, fill, hill,
            kiss, mess, miss, pig, pot, top, rat, mop, nut, dip, sit, pan, back, rock
        """),
    },
    {
        "key": "phase3",
        "name": "Phase 3 - digraphs (sh, ch, ai, ee...)",
        "description": "j v w x y z qu ch sh th ng ai ee igh oa oo ar or ur ow oi ear air ure er.",
        "words": _w("""
            jam, jet, van, vet, web, wig, box, fox, six, yes, yell, zip, buzz, quiz, quick,
            chip, chin, chop, much, shop, ship, fish, dish, rush, thin, moth, them, with,
            ring, sing, king, long, rain, wait, tail, feet, see, tree, need, night, light,
            high, boat, coat, road, moon, zoom, book, look, cook, car, park, farm, fork,
            horn, corn, burn, turn, hurt, cow, how, town, coin, oil, boil, ear, hear, near,
            fair, hair, pair, sure, letter, hammer
        """),
    },
    {
        "key": "phase4",
        "name": "Phase 4 - blends (fr, st, mp...)",
        "description": "Words with adjacent consonants: frog, stop, jump, string.",
        "words": _w("""
            frog, crab, drum, flag, swim, stop, step, spot, trip, clap, plum, pram, sniff,
            black, help, milk, jump, tent, hand, lamp, pond, nest, desk, best, belt, gift,
            crisp, frost, plant, stamp, twist, blend, grand, string, street, scrub, train,
            green, sleep, toast, float, storm, start, spoon, sport, chimp, drink, think,
            brush, cloth, skunk, trunk, shrink, melt, went, soft, lost, crash, fresh,
            smell, sweet, bright, clown
        """),
    },
    {
        "key": "phase5",
        "name": "Phase 5 - new spellings (ay, ou, a-e...)",
        "description": "ay ou ie ea oy ir ue aw wh ph ew oe au ey and split digraphs a-e e-e i-e o-e u-e.",
        "words": _w("""
            day, play, say, way, out, about, cloud, shout, pie, tie, cried, eat, sea,
            dream, team, boy, toy, enjoy, girl, bird, first, shirt, blue, glue, true, saw,
            draw, crawl, when, what, which, wheel, phone, photo, new, grew, chew, few, toe,
            goes, haul, launch, key, donkey, cake, make, game, these, theme, bike, time,
            like, home, bone, rope, cube, tune, huge, cute, snake, smile, stone, flute
        """),
    },
    {
        "key": "hfw100",
        "name": "100 high-frequency words",
        "description": "The 100 words children meet most often in books.",
        "words": _w("""
            the, and, a, to, said, in, he, I, of, it, was, you, they, on, she, is, for,
            at, his, but, that, with, all, we, can, are, up, had, my, her, what, there,
            out, this, have, went, be, like, some, so, not, then, were, go, little, as,
            no, mum, one, them, do, me, down, dad, big, when, it's, see, looked, very,
            look, don't, come, will, into, back, from, children, him, Mr, get, just, now,
            came, oh, about, got, their, people, your, put, could, house, old, too, by,
            day, made, time, I'm, if, help, Mrs, called, here, off, asked, saw, make, an
        """),
    },
    {
        "key": "cew_y1",
        "name": "Year 1 tricky words",
        "description": "Year 1 common exception words (National Curriculum). 45 words: makes a 6-per-card deck.",
        "words": _w("""
            the, a, do, to, today, of, said, says, are, were, was, is, his, has, I, you,
            your, they, be, he, me, she, we, no, go, so, by, my, here, there, where, love,
            come, some, one, once, ask, friend, school, put, push, pull, full, house, our
        """),
    },
    {
        "key": "cew_y2",
        "name": "Year 2 tricky words",
        "description": "Year 2 common exception words (National Curriculum).",
        "words": _w("""
            door, floor, poor, because, find, kind, mind, behind, child, children, wild,
            climb, most, only, both, old, cold, gold, hold, told, every, everybody, even,
            great, break, steak, pretty, beautiful, after, fast, last, past, father,
            class, grass, pass, plant, path, bath, hour, move, prove, improve, sure,
            sugar, eye, could, should, would, who, whole, any, many, clothes, busy,
            people, water, again, half, money, Mr, Mrs, parents, Christmas
        """),
    },
    {
        "key": "days_numbers",
        "name": "Days, months, colours and numbers",
        "description": "Days of the week, months, colour words and numbers to twenty.",
        "words": _w("""
            Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday,
            January, February, March, April, May, June, July, August, September,
            October, November, December,
            red, blue, green, yellow, orange, purple, pink, brown, black, white, grey,
            one, two, three, four, five, six, seven, eight, nine, ten, eleven, twelve,
            thirteen, fourteen, fifteen, sixteen, seventeen, eighteen, nineteen, twenty,
            first, second, third, today, tomorrow, yesterday, week
        """),
    },
]
