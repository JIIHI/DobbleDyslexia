"""Web server for Word Spot online (FastAPI + WebSockets).

Run it with ``python -m wordspot.online`` and open the address it prints
on any phone, tablet or computer on the same wifi.
"""

from __future__ import annotations

import asyncio
import io
import json
import socket
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from wordspot.layout import Layout
from wordspot.online.game import AVATARS, Lobby, Room, deck_choices
from wordspot.paths import data_dir, fonts_dir

STATIC = Path(__file__).resolve().parent / "static"


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
    return {"decks": deck_choices(), "avatars": AVATARS, "join_base": base}


@app.post("/api/rooms")
async def create_room() -> dict:
    return {"code": lobby.create().code}


@app.get("/api/rooms/{code}")
async def room_info(code: str) -> dict:
    room = lobby.get(code)
    if not room:
        raise HTTPException(404, "No game with that code")
    return {"code": room.code, "phase": room.phase, "players": room.connected_count()}


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
        while True:
            msg = await ws.receive_json()
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
