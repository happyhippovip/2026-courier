#!/usr/bin/env python3
"""Local preview relay. Listens on 127.0.0.1 only. Not a public chat."""

from __future__ import annotations

import json
import mimetypes
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PUBLIC = Path(__file__).resolve().parent / "public"
HOST = "127.0.0.1"
PORT = 8765
TTL = 30.0
LOCK = threading.Lock()
WAKE = threading.Condition(LOCK)
CLIENTS: dict[str, dict] = {}
EVENTS: list[dict] = []
SEQ = 0
EMOTES = {"Funke", "Glut", "Mond"}
FIGURES = {"gold", "cyan", "clay"}


def clean(value: str, limit: int) -> str:
    text = "".join(ch for ch in str(value) if ch.isprintable() and ch not in "<>")
    return " ".join(text.split())[:limit]


def stamp() -> float:
    return time.time()


def push(kind: str, fields: dict) -> None:
    global SEQ
    SEQ += 1
    EVENTS.append({"n": SEQ, "kind": kind, **fields})
    if len(EVENTS) > 300:
        del EVENTS[:150]
    WAKE.notify_all()


def prune() -> None:
    dead = [key for key, person in CLIENTS.items() if stamp() - person["seen"] > TTL]
    for key in dead:
        name = CLIENTS[key]["name"]
        del CLIENTS[key]
        push("leave", {"id": key, "name": name})


def people() -> list[dict]:
    return [
        {
            "id": key,
            "name": person["name"],
            "x": person["x"],
            "y": person["y"],
            "figure": person.get("figure", "gold"),
            "bubble": person.get("bubble", ""),
        }
        for key, person in CLIENTS.items()
    ]


def payload_for(cid: str, events: list[dict]) -> dict:
    you = CLIENTS.get(cid)
    return {
        "cursor": SEQ,
        "events": events,
        "people": people(),
        "you": None
        if you is None
        else {
            "id": cid,
            "name": you["name"],
            "x": you["x"],
            "y": you["y"],
            "figure": you.get("figure", "gold"),
            "bubble": you.get("bubble", ""),
        },
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        return

    def send_json(self, code: int, body: dict) -> None:
        raw = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0 or length > 4000:
            return {}
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/lounge/events":
            self.events(parse_qs(parsed.query))
            return
        self.static(parsed.path)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        body = self.read_json()
        if path == "/api/lounge/join":
            self.join(body)
        elif path == "/api/lounge/line":
            self.line(body)
        elif path == "/api/lounge/emote":
            self.emote(body)
        elif path == "/api/lounge/move":
            self.move(body)
        else:
            self.send_json(404, {"error": "not found"})

    def join(self, body: dict) -> None:
        name = clean(body.get("name", ""), 24)
        if not name:
            self.send_json(400, {"error": "name"})
            return
        with WAKE:
            prune()
            cid = uuid.uuid4().hex[:8]
            figure = body.get("figure") if body.get("figure") in FIGURES else "gold"
            CLIENTS[cid] = {
                "name": name,
                "x": 16,
                "y": 58,
                "figure": figure,
                "bubble": "",
                "seen": stamp(),
            }
            push("join", {"id": cid, "name": name})
            since = [event for event in EVENTS if event["n"] == SEQ]
            self.send_json(200, {"id": cid, **payload_for(cid, since)})

    def touch(self, cid: str) -> bool:
        person = CLIENTS.get(cid)
        if person is None:
            return False
        person["seen"] = stamp()
        return True

    def line(self, body: dict) -> None:
        text = clean(body.get("text", ""), 80)
        cid = str(body.get("id", ""))
        with WAKE:
            prune()
            if not text or not self.touch(cid):
                self.send_json(400, {"error": "line"})
                return
            CLIENTS[cid]["bubble"] = text
            push("line", {"id": cid, "name": CLIENTS[cid]["name"], "text": text})
            self.send_json(200, {"ok": True, "cursor": SEQ})

    def emote(self, body: dict) -> None:
        emote = str(body.get("emote", ""))
        cid = str(body.get("id", ""))
        with WAKE:
            prune()
            if emote not in EMOTES or not self.touch(cid):
                self.send_json(400, {"error": "emote"})
                return
            push("emote", {"id": cid, "name": CLIENTS[cid]["name"], "emote": emote})
            self.send_json(200, {"ok": True, "cursor": SEQ})

    def move(self, body: dict) -> None:
        cid = str(body.get("id", ""))
        try:
            x = float(body.get("x"))
            y = float(body.get("y"))
        except (TypeError, ValueError):
            self.send_json(400, {"error": "move"})
            return
        x = max(8.0, min(88.0, x))
        y = max(16.0, min(78.0, y))
        with WAKE:
            prune()
            if not self.touch(cid):
                self.send_json(400, {"error": "move"})
                return
            CLIENTS[cid]["x"] = x
            CLIENTS[cid]["y"] = y
            push("move", {"id": cid, "x": x, "y": y})
            self.send_json(200, {"ok": True, "cursor": SEQ})

    def events(self, query: dict) -> None:
        cid = (query.get("id") or [""])[0]
        try:
            since = int((query.get("since") or ["0"])[0])
        except ValueError:
            since = 0
        deadline = stamp() + 8
        with WAKE:
            if cid not in CLIENTS:
                self.send_json(404, {"error": "unknown"})
                return
            CLIENTS[cid]["seen"] = stamp()
            while stamp() < deadline:
                found = [event for event in EVENTS if event["n"] > since]
                if found:
                    self.send_json(200, payload_for(cid, found))
                    return
                remaining = deadline - stamp()
                if remaining <= 0:
                    break
                WAKE.wait(timeout=min(0.5, remaining))
            self.send_json(200, payload_for(cid, []))

    def static(self, path: str) -> None:
        rel = "index.html" if path in {"", "/"} else path.lstrip("/")
        target = (PUBLIC / rel).resolve()
        if not str(target).startswith(str(PUBLIC.resolve())) or not target.is_file():
            self.send_error(404)
            return
        mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        raw = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)


def main() -> None:
    if not PUBLIC.is_dir():
        raise SystemExit("missing website/public; run ./build_site.sh first")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"local relay http://{HOST}:{PORT}/  (127.0.0.1 only)")
    server.serve_forever()


if __name__ == "__main__":
    main()
