# Word Spot

Printable "spot the matching word" card games for children who find reading
hard: dyslexia, ADHD and other special educational needs.

Every pair of cards shares **exactly one** word. Players race to find it and
read it out loud, so a child's competitive streak does the reading practice
for them.

Word Spot is a desktop app for **Mac and Windows**.

## Download

Ready-made apps are built automatically by GitHub Actions:

1. Open the repository's **Actions** tab and click the latest **Build apps** run.
2. Under **Artifacts**, download one of:
   * `WordSpot-mac-AppleSilicon` (Macs with an M1 chip or newer)
   * `WordSpot-mac-Intel` (older Macs)
   * `WordSpot-windows`
3. Unzip it.
   * **Mac:** drag *Word Spot* into Applications. The first time, **right-click
     the app and choose Open**, then click Open again. This is needed because
     the app isn't signed with a paid Apple developer certificate.
   * **Windows:** open the *Word Spot* folder and run *Word Spot.exe*. If
     SmartScreen shows a warning, click *More info*, then *Run anyway*.

When a version tag such as `v1.0.0` is pushed, the same files are attached
to a GitHub Release, which gives a simpler download link to share.

## What it does

* **Ready-made decks** follow UK phonics: Phase 2 to Phase 5, the 100
  high-frequency words, the Year 1 and Year 2 common exception words, and
  days, months, colours and numbers.
* **Your own decks:** type or paste words, or import a `.txt`, `.csv` or
  `.xlsx` file. You can edit the ready-made decks too ("Restore original words"
  puts them back).
* **Easier or harder games:** 8 words per card (57 cards), or 6, 4 or 3 words
  per card for younger or struggling readers.
* **Reading-friendly styling:** three fonts designed for readability
  (OpenDyslexic, Lexend, Andika), cream and pastel backgrounds, colourful or
  plain words, lowercase or UPPERCASE, and a card border on or off.
* **Words face every way:** round cards are played from all sides of the
  table, so word angles are always random and spread all the way round each
  card. Every player gets some words facing them.
* **Round or rectangular cards:** round cards are for group play, with words
  facing every way. Rectangular cards keep every word upright and the same
  size, which suits one-to-one work with an adult. They print 4 to a page at
  the large size, or 9 at the small size.
* **Download A4 PDF:** all the cards laid out on A4 (6 round cards to a page at the large size), ready to print and cut.
* **Download ZIP:** every card as its own PNG, plus the PDF. When a card gets
  lost or chewed, just print that one again.
* **Re-print one card:** right-click any card in the preview. You can also
  type a word in *Find a card* to locate it.
* **Advanced settings:** even-sized bubbles for children who struggle with
  small words, long words in big bubbles, and printed card size.
* **Bubble Designer:** watch the organic growth simulation grow new bubble
  layouts, save the ones you like and untick the ones you don't.

The same deck always produces the same cards, so a replacement printed months
later still matches the set. *Shuffle* makes a fresh mix.

Decks and settings are kept in a small SQLite database in your user folder:

* Mac: `~/Library/Application Support/WordSpot/`
* Windows: `%APPDATA%\WordSpot\`

## Play on iPads, phones and computers (Word Spot online)

Word Spot also runs as a web game, with no app to install.

* **Everyone sees the same two cards.** The first player to tap the one word
  that is on **both** cards wins the point, then the next pair is dealt.
* **Play on my own:** one child plays against the clock and tries to beat
  their personal best.
* **Play with someone:** the child who starts gets a 4-letter code and a QR
  code. Other players scan it or type the code. Any number can join, up to 8.
* A wrong tap freezes that player for 1.5 seconds, so random tapping doesn't
  pay off.
* When someone finds the word, every device **reads it aloud**. Tap 🔊 to
  turn this off.
* A 💡 hint button appears if nobody finds the word for 15 seconds.
* Round cards (words face every way) or straight cards (words upright), the
  three reading fonts, built-in decks or your own word list.
* Nothing is stored about the children. Games disappear when they finish.

### Run it at home

On the computer, with Python 3 installed:

* **Mac:** double-click `start-online-game.command`
* **Windows:** double-click `start-online-game.bat`
* or run `pip install -r requirements-server.txt`, then `python -m wordspot.online`

It prints an address such as `http://192.168.1.20:8000`. Open that in Safari
or Chrome on each iPad, phone or computer on the same wifi. On an iPad, tap
*Share*, then *Add to Home Screen*, and it opens like an app. Keep the
computer awake while the children play.

### Put it online

To play from anywhere, follow **[deploy/HOSTING-GUIDE.md](deploy/HOSTING-GUIDE.md)**.
It sets up a small Hetzner cloud server (about €4–5 a month) with HTTPS, a
family code, automatic security updates and nightly updates from GitHub,
using `deploy/cloud-config.yaml`. The `Dockerfile` also works on any other
container host.

## Running from source

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python run_wordspot.py
```

Run the tests with `python -m pytest`. Build the app for the computer you're
on with `pyinstaller wordspot.spec`; the result appears in `dist/`. A Mac app
can only be built on a Mac and a Windows app only on Windows, which is why
GitHub Actions builds both.

## Project layout

| Path | What it is |
| --- | --- |
| `wordspot/deck.py` | The maths: projective-plane decks where each pair of cards shares one word |
| `wordspot/layout.py` | Organic bubble-growth simulation (ported from the original R code) |
| `wordspot/builder.py` | Turns words + style into cards (deterministic from the deck's seed) |
| `wordspot/render.py` | Draws a card with Pillow |
| `wordspot/export.py` | A4 PDF, ZIP and word-list import |
| `wordspot/db.py` | SQLite storage |
| `wordspot/wordlists.py` | Built-in word decks |
| `wordspot/gui/` | The PySide6 (Qt) interface and Bubble Designer |
| `wordspot/online/` | The web game: rules (`game.py`), server (`server.py`) and the page (`static/`) |
| `scripts/` | Regenerate built-in layouts (`generate_layouts.py`) and icons (`make_icon.py`) |
| `legacy/` | The original R scripts |

## Fonts

OpenDyslexic, Lexend and Andika are bundled under the SIL Open Font License
(see the `*-OFL.txt` files in `wordspot/fonts/`).
