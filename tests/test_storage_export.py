import zipfile

from wordspot.builder import plan_deck
from wordspot.db import Database
from wordspot.export import export_pdf, export_zip, grid_for, read_word_file
from wordspot.layout import generate_layout


def test_database_seeds_and_edits(tmp_path):
    db = Database(tmp_path / "t.sqlite3")
    decks = db.list_decks()
    assert len(decks) >= 8 and all(d.builtin for d in decks)
    assert len(db.list_layouts(8)) > 10
    deck_id = db.create_deck("Mine", ["one", "two"])
    db.set_words(deck_id, ["x", "y", "z"])
    assert db.get_words(deck_id) == ["x", "y", "z"]
    style = db.get_deck(deck_id).style
    style.bold = True
    db.save_style(deck_id, style)
    assert db.get_deck(deck_id).style.bold
    lay_id = db.add_layout(generate_layout(6, seed=1), "test")
    db.set_layout_enabled(lay_id, False)
    assert not [l for l in db.list_layouts(6) if l.id == lay_id][0].enabled
    db.delete_layout(lay_id)
    db.delete_deck(deck_id)
    db.delete_deck(decks[0].id)  # built-in decks can't be deleted
    assert len(db.list_decks()) == len(decks)
    db.close()
    # reopening doesn't duplicate the built-ins
    assert len(Database(tmp_path / "t.sqlite3").list_decks()) == len(decks)


def test_a4_grid():
    assert grid_for(90) == (2, 3)
    assert grid_for(62) == (3, 4)


def test_exports(tmp_path):
    db = Database(tmp_path / "t.sqlite3")
    deck = [d for d in db.list_decks() if d.builtin_key == "cew_y1"][0]
    deck.style.card_mm = 62
    plan = plan_deck(db.get_words(deck.id), deck.style, db.list_layouts())
    assert plan.card_count == 31
    pdf = tmp_path / "deck.pdf"
    export_pdf(pdf, plan, deck.style, deck.name)
    assert pdf.read_bytes()[:4] == b"%PDF"
    one = tmp_path / "one.pdf"
    export_pdf(one, plan, deck.style, deck.name, card_numbers=[5])
    assert one.stat().st_size < pdf.stat().st_size
    zpath = tmp_path / "deck.zip"
    export_zip(zpath, plan, deck.style, deck.name)
    names = zipfile.ZipFile(zpath).namelist()
    assert sum(n.endswith(".png") for n in names) == 31
    assert "cards/Card_01.png" in names and "README.txt" in names


def test_read_word_files(tmp_path):
    (tmp_path / "a.txt").write_text("cat\ndog, sun\n\nhat")
    assert read_word_file(tmp_path / "a.txt") == ["cat", "dog", "sun", "hat"]
    (tmp_path / "b.csv").write_text('"",x\n1,frog\n2,crab\n')
    assert read_word_file(tmp_path / "b.csv") == ["frog", "crab"]
    import openpyxl
    wb = openpyxl.Workbook()
    wb.active.append(["words"])
    wb.active.append(["ship"])
    wb.active.append(["shop"])
    wb.save(tmp_path / "c.xlsx")
    assert read_word_file(tmp_path / "c.xlsx") == ["ship", "shop"]
