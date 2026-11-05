"""Web server for Word Spot online (FastAPI + WebSockets).

Run it with ``python -m wordspot.online`` and open the address it prints
on any phone, tablet or computer on the same wifi.
"""

from __future__ import annotations

import asyncio
import hmac
import io
import json
import os
import socket
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from wordspot.layout import Layout
from wordspot.online.game import AVATARS, Lobby, Room, deck_choices
from wordspot.paths import data_dir, fonts_dir

STATIC = Path(__file__).resolve().parent / "static"

# Family code: when set, only people who know it can START games (anyone with
# a 4-letter game code can still join one).  Set it on the host as an
# environment variable, e.g.  WORDSPOT_ACCESS_CODE=pancake42
ACCESS_CODE = os.environ.get("WORDSPOT_ACCESS_CODE", "").strip()

MAX_MESSAGE = 16_000          # bytes in one message from a device
MAX_MSGS_PER_SEC = 15         # per device; more than this and it's disconnected


class RateLimiter:
    """Allows ``limit`` events per ``window`` seconds for each key (IP address)."""

    def __init__(self, limit: int, window: float):
        self.limit, self.window = limit, window
        self.hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.time()
        q = self.hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        if len(self.hits) > 5000:  # forget old visitors
            for k in [k for k, v in self.hits.items() if not v or now - v[-1] > self.window]:
                del self.hits[k]
        return True


create_limit = RateLimiter(8, 60)     # new games per IP per minute
lookup_limit = RateLimiter(30, 60)    # game-code lookups / joins per IP per minute
code_limit = RateLimiter(10, 300)     # family-code guesses per IP per 5 minutes
print_limit = RateLimiter(4, 120)     # printable decks per IP per 2 minutes
print_slots = asyncio.Semaphore(2)    # decks being made at once (each takes a few seconds)


def client_ip(request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "?"


def code_ok(given: str | None) -> bool:
    if not ACCESS_CODE:
        return True
    return hmac.compare_digest((given or "").strip().lower().encode(), ACCESS_CODE.lower().encode())


def load_layouts() -> list[Layout]:
    items = json.loads((data_dir() / "layouts.json").read_text())
    return [Layout(circles=[tuple(c) for c in it["circles"]], name=it["name"]) for it in items]


lobby = Lobby(load_layouts())
sockets: dict[str, dict[str, WebSocket]] = {}  # room code -> player id -> socket


def lan_address() -> str | None:
    """This computer's address on the local network (for the join QR code)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return None if ip.startswith("127.") else ip
    except OSError:
        return None


async def broadcast(room: Room) -> None:
    state = room.public_state()
    for pid, ws in list(sockets.get(room.code, {}).items()):
        try:
            await ws.send_json({**state, "you": pid})
        except Exception:
            sockets.get(room.code, {}).pop(pid, None)


async def ticker() -> None:
    """Moves rounds on after the answer has been shown; tidies old rooms."""
    n = 0
    while True:
        await asyncio.sleep(0.2)
        for room in list(lobby.rooms.values()):
            if room.advance():
                await broadcast(room)
        n += 1
        if n % 300 == 0:
            lobby.cleanup()
            for code in list(sockets):
                if code not in lobby.rooms:
                    sockets.pop(code, None)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(ticker())
    yield
    task.cancel()


app = FastAPI(title="Word Spot", lifespan=lifespan, docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
app.mount("/fonts", StaticFiles(directory=fonts_dir()), name="fonts")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/robots.txt")
async def robots() -> PlainTextResponse:
    return PlainTextResponse("User-agent: *\nDisallow: /\n")


@app.middleware("http")
async def no_index(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@app.get("/manifest.webmanifest")
async def manifest() -> JSONResponse:
    return JSONResponse({
        "name": "Word Spot", "short_name": "Word Spot", "start_url": "/",
        "display": "standalone", "background_color": "#f4f5fb", "theme_color": "#4f46e5",
        "icons": [{"src": "/icon.png", "sizes": "1024x1024", "type": "image/png"}],
    }, media_type="application/manifest+json")


@app.get("/icon.png")
async def icon() -> FileResponse:
    return FileResponse(data_dir() / "icon.png")


@app.get("/api/info")
async def info(request: Request) -> dict:
    host = request.url.hostname or ""
    base = str(request.base_url).rstrip("/")
    if host in ("localhost", "127.0.0.1", "::1"):
        ip = lan_address()
        if ip:
            base = f"{request.url.scheme}://{ip}:{request.url.port or 80}"
    return {"decks": deck_choices(), "avatars": AVATARS, "join_base": base,
            "needs_code": bool(ACCESS_CODE)}


@app.post("/api/check-code")
async def check_code(request: Request) -> dict:
    if not code_limit.allow(client_ip(request)):
        raise HTTPException(429, "Too many tries - wait a few minutes.")
    return {"ok": code_ok(request.headers.get("x-family-code"))}


@app.post("/api/rooms")
async def create_room(request: Request) -> dict:
    ip = client_ip(request)
    if not code_ok(request.headers.get("x-family-code")):
        if not code_limit.allow(ip):
            raise HTTPException(429, "Too many tries - wait a few minutes.")
        raise HTTPException(403, "Wrong family code.")
    if not create_limit.allow(ip):
        raise HTTPException(429, "Too many new games - wait a minute.")
    try:
        return {"code": lobby.create().code}
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))


@app.get("/api/rooms/{code}")
async def room_info(code: str, request: Request) -> dict:
    if not lookup_limit.allow(client_ip(request)):
        raise HTTPException(429, "Too many tries - wait a minute.")
    room = lobby.get(code)
    if not room:
        raise HTTPException(404, "No game with that code")
    return {"code": room.code, "phase": room.phase, "players": room.connected_count()}


def make_pdf(room: Room) -> tuple[bytes, str]:
    from wordspot.export import render_cards, safe_name, write_pdf
    plan, style, title = room.print_deck()
    images = render_cards(plan.cards, style, len(plan.cards))
    buf = io.BytesIO()
    write_pdf(buf, images, style, title)
    return buf.getvalue(), safe_name(f"Word Spot - {title}")


@app.get("/print/{code}.pdf")
async def print_deck(code: str, request: Request) -> Response:
    """The whole deck as an A4 PDF, using the game's current settings."""
    if not print_limit.allow(client_ip(request)):
        raise HTTPException(429, "Too many decks - wait a couple of minutes.")
    room = lobby.get(code)
    if not room:
        raise HTTPException(404, "No game with that code")
    async with print_slots:
        pdf, name = await asyncio.to_thread(make_pdf, room)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{name}.pdf"'})


@app.get("/qr.svg")
async def qr(data: str) -> Response:
    import qrcode
    import qrcode.image.svg
    img = qrcode.make(data[:500], image_factory=qrcode.image.svg.SvgPathFillImage, box_size=10,
                      border=2)
    buf = io.BytesIO()
    img.save(buf)
    return Response(buf.getvalue(), media_type="image/svg+xml")


@app.websocket("/ws/{code}")
async def play(ws: WebSocket, code: str) -> None:
    await ws.accept()
    if not lookup_limit.allow(client_ip(ws)):
        await ws.send_json({"type": "error", "message": "Too many tries - wait a minute."})
        await ws.close()
        return
    room = lobby.get(code)
    if not room:
        await ws.send_json({"type": "error", "message": "No game with that code."})
        await ws.close()
        return
    q = ws.query_params
    try:
        player = room.add_player(q.get("name", ""), q.get("avatar", ""), q.get("pid") or None)
    except ValueError as exc:
        await ws.send_json({"type": "error", "message": str(exc)})
        await ws.close()
        return
    old = sockets.setdefault(room.code, {}).get(player.id)
    if old is not None and old is not ws:
        try:
            await old.close()
        except Exception:
            pass
    sockets[room.code][player.id] = ws
    await broadcast(room)
    try:
        recent: deque = deque()
        while True:
            text = await ws.receive_text()
            now = time.time()
            recent.append(now)
            while recent and now - recent[0] > 1:
                recent.popleft()
            if len(text) > MAX_MESSAGE or len(recent) > MAX_MSGS_PER_SEC:
                await ws.close(code=1008)
                break
            msg = json.loads(text)
            if not isinstance(msg, dict):
                continue
            kind = msg.get("type")
            if kind == "tap":
                result = room.tap(player.id, int(msg.get("round", -1)), str(msg.get("word", "")))
                if result == "win":
                    await broadcast(room)
                elif result in ("wrong", "frozen"):
                    await ws.send_json({"type": "tap_result", "result": result,
                                        "freeze": max(0.0, player.frozen_until - time.time())})
            elif kind == "settings":
                room.update_settings(player.id, msg.get("settings", {}))
                await broadcast(room)
            elif kind == "start":
                room.start(player.id)
                await broadcast(room)
            elif kind == "hint":
                if room.ask_hint(player.id):
                    await broadcast(room)
            elif kind == "ping":
                await ws.send_json({"type": "pong"})
    except (WebSocketDisconnect, RuntimeError, ValueError):
        pass
    finally:
        if sockets.get(room.code, {}).get(player.id) is ws:
            sockets[room.code].pop(player.id, None)
            room.disconnect(player.id)
            await broadcast(room)
