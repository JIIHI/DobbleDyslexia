import pytest

pytest.importorskip("fastapi")

from wordspot.online.game import WRONG_FREEZE, Lobby  # noqa: E402
from wordspot.online.server import app, load_layouts  # noqa: E402


def answer_of(room):
    a, b = room.cards
    return ({w["w"] for w in a["words"]} & {w["w"] for w in b["words"]}).pop()


def test_round_flow_and_scoring():
    lobby = Lobby(load_layouts())
    room = lobby.create()
    sam = room.add_player("Sam", "🐶")
    ava = room.add_player("Ava", "🐸")
    assert room.host == sam.id
    room.update_settings(ava.id, {"rounds": 5})      # only the host can change settings
    assert room.settings.rounds == 10
    room.update_settings(sam.id, {"rounds": 5, "shape": "rect"})
    room.start(sam.id)
    assert room.phase == "playing" and room.total_rounds == 5
    assert "answer" not in room.public_state()       # answer isn't sent while playing

    ans = answer_of(room)
    assert ans == room.answer
    wrong = next(w["w"] for w in room.cards[0]["words"] if w["w"] != ans)
    assert room.tap(ava.id, 1, wrong, now=100.0) == "wrong"
    assert room.tap(ava.id, 1, ans, now=100.5) == "frozen"       # still frozen
    assert room.tap(sam.id, 1, ans, now=101.0) == "win"
    assert room.tap(ava.id, 1, ans, now=100.0 + WRONG_FREEZE + 1) == "ignored"  # round over
    assert sam.score == 1 and ava.score == 0
    assert room.public_state()["answer"] == ans

    clock = 200.0
    for r in range(2, 6):
        clock += 10
        assert room.advance(now=clock)
        assert room.round == r
        assert room.tap(ava.id, r, answer_of(room), now=clock + 1) == "win"
    assert room.advance(now=clock + 10)
    assert room.phase == "finished"
    results = room.public_state()["results"]
    assert results[0]["name"] == "Ava" and results[0]["score"] == 4


def test_solo_and_custom_words():
    room = Lobby(load_layouts()).create()
    leo = room.add_player("Leo", "🦊")
    room.update_settings(leo.id, {"deck": "custom", "custom_words": ["a", "b", "c", "d", "e", "f", "g"]})
    assert room.settings.deck == "custom"
    room.start(leo.id)
    assert room.phase == "playing" and room.total_rounds == 3   # 7 cards -> 3 pairs
    assert len(room.cards[0]["words"]) == 3


def test_websocket_game():
    from fastapi.testclient import TestClient
    with TestClient(app) as client:
        code = client.post("/api/rooms").json()["code"]
        assert client.get(f"/api/rooms/{code}").status_code == 200
        assert client.get("/api/rooms/ZZZZ").status_code == 404
        assert client.get("/").status_code == 200
        assert client.get("/qr.svg", params={"data": "http://x"}).text.startswith("<?xml")
        with client.websocket_connect(f"/ws/{code}?name=Sam&avatar=🐶") as a:
            sa = a.receive_json()
            with client.websocket_connect(f"/ws/{code}?name=Ava&avatar=🐸") as b:
                b.receive_json()
                a.receive_json()
                a.send_json({"type": "start"})
                state = a.receive_json()
                assert state["phase"] == "playing"
                b.receive_json()
                cards = state["cards"]
                ans = ({w["w"] for w in cards[0]["words"]} & {w["w"] for w in cards[1]["words"]}).pop()
                b.send_json({"type": "tap", "round": 1, "word": ans})
                won = b.receive_json()
                assert won["phase"] == "answer" and won["answer"] == ans
                assert [p["score"] for p in won["players"] if p["name"] == "Ava"] == [1]
        assert sa["you"]


def test_family_code_and_limits(monkeypatch):
    from fastapi.testclient import TestClient
    import wordspot.online.server as srv
    monkeypatch.setattr(srv, "ACCESS_CODE", "Pancake42")
    monkeypatch.setattr(srv, "create_limit", srv.RateLimiter(3, 60))
    monkeypatch.setattr(srv, "code_limit", srv.RateLimiter(100, 60))
    with TestClient(srv.app) as client:
        assert client.get("/api/info").json()["needs_code"] is True
        assert client.post("/api/rooms").status_code == 403
        assert client.post("/api/rooms", headers={"X-Family-Code": "wrong"}).status_code == 403
        ok = client.post("/api/rooms", headers={"X-Family-Code": " pancake42 "})
        assert ok.status_code == 200
        # joining only needs the game code, not the family code
        with client.websocket_connect(f"/ws/{ok.json()['code']}?name=Friend") as ws:
            assert ws.receive_json()["phase"] == "lobby"
        for _ in range(2):
            client.post("/api/rooms", headers={"X-Family-Code": "pancake42"})
        assert client.post("/api/rooms", headers={"X-Family-Code": "pancake42"}).status_code == 429
        assert client.get("/robots.txt").text.startswith("User-agent")


def test_message_flood_disconnects():
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    import wordspot.online.server as srv
    with TestClient(srv.app) as client:
        code = client.post("/api/rooms").json()["code"]
        with client.websocket_connect(f"/ws/{code}?name=Spam") as ws:
            ws.receive_json()
            with pytest.raises(WebSocketDisconnect):
                for _ in range(200):
                    ws.send_json({"type": "ping"})
                    ws.receive_json()


def test_room_cap():
    from wordspot.online import game
    lobby = Lobby(load_layouts())
    for _ in range(game.MAX_ROOMS):
        lobby.create().add_player("x", "🐶")
    with pytest.raises(RuntimeError):
        lobby.create()


def test_colour_and_circle_settings():
    room = Lobby(load_layouts()).create()
    sam = room.add_player("Sam", "🐶")
    ava = room.add_player("Ava", "🐸")
    assert room.settings.colours == "colourful" and room.settings.circles is True

    room.update_settings(ava.id, {"colours": "pastel", "circles": False})   # not the host
    assert room.settings.colours == "colourful" and room.settings.circles is True

    room.update_settings(sam.id, {"colours": "rainbow", "circles": "yes"})  # nonsense ignored
    assert room.settings.colours == "colourful" and room.settings.circles is True

    room.update_settings(sam.id, {"colours": "pastel", "circles": False})
    pub = room.public_state()["settings"]
    assert pub["colours"] == "pastel" and pub["circles"] is False


@pytest.mark.parametrize("shape", ["round", "rect"])
@pytest.mark.parametrize("colours,circles", [
    ("colourful", True), ("colourful", False), ("bright", True), ("pastel", True),
    ("black", True), ("grey", False), ("bw", True), ("bw", False)])
def test_card_payload_reflects_colours_and_circles(shape, colours, circles):
    from wordspot.style import SCHEME_COLOURS
    room = Lobby(load_layouts()).create()
    sam = room.add_player("Sam", "🐶")
    room.update_settings(sam.id, {"shape": shape, "colours": colours, "circles": circles})
    room.start(sam.id)
    card = room.cards[0]
    assert card["shape"] == shape
    assert card["bg"] == ("#ffffff" if colours == "bw" else "#fdf6e3")
    for w in card["words"]:
        assert w["c"] in SCHEME_COLOURS[colours]
    if not circles:
        assert card["bubbles"] == "none"
        assert all(w["f"] == "transparent" for w in card["words"])   # still tappable
        assert "stroke" not in card
    elif colours == "bw":
        assert card["bubbles"] == "outline" and card["stroke"]
        assert all(w["f"] == "#ffffff" for w in card["words"])
    else:
        assert card["bubbles"] == "soft"
        assert all(w["f"].startswith("#") and w["f"] not in (card["bg"], w["c"])
                   for w in card["words"])


def test_pastel_bubbles_are_stronger():
    from wordspot.style import bubble_tint
    assert bubble_tint("pastel") > bubble_tint("colourful") > bubble_tint("black")
