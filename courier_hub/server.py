"""Courier Desktop Hub server (lane L5): `python -m courier_hub`.

    python -m courier_hub --home <H> --controller http://127.0.0.1:<P> [--port 0] [--print-url]

The hub is a READER of canonical truth plus a thin, attributable relay for
human decisions. It never writes the journal and keeps no state of its own:

- Home and receipts are read from <H>/courier.db through a read-only
  journal connection (the controller's own projection), then turned into
  customer language by courier_hub.model.
- Human decisions go to the controller's real API (/v1/tasks/<id>/resolve
  and /cancel) with the desktop user's actor id. The controller decides
  whether the decision is valid; the hub only reports what it said.

Security: binds 127.0.0.1 only, refuses requests whose Host header is not the
hub itself (DNS rebinding), and requires an `X-Courier-Hub: 1` header plus a
JSON body on every POST, so a web page in the user's browser cannot forge a
decision (the custom header forces a CORS preflight the hub never answers).
"""

from __future__ import annotations

import argparse
import getpass
import http.client
import json
import logging
import os
import re
import socket
import sqlite3
import sys
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

from courier_core.build import build_identity
from courier_core.journal import Journal, JournalError
from courier_hub import model

log = logging.getLogger("courier.hub")

STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                ".mjs": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
                ".svg": "image/svg+xml"}
MAX_BODY_BYTES = 16 * 1024
CONTROLLER_TIMEOUT_S = 5.0
ACTOR_RE = re.compile(r"^[A-Za-z0-9_.:@-]{1,200}$")
_ITEM = re.compile(r"^/hub/api/items/([A-Za-z0-9_.:-]{1,200})$")
_SUPPORT = re.compile(r"^/hub/api/items/([A-Za-z0-9_.:-]{1,200})/support$")
_ITEM_ACTION = re.compile(r"^/hub/api/items/([A-Za-z0-9_.:-]{1,200})/(decision|stop)$")

STALE_CODES = {
    "stale_decision": "This changed since you opened it. Here is the current state.",
    "not_blocked": "This no longer needs a decision.",
    "decision_conflict": "Someone already made a different decision about this.",
    "cancel_requested": "Stop was already requested, so Courier won't try again.",
    "attempt_limit": "Courier can't try again: the attempt limit is reached.",
    "terminal": "This has already finished.",
    "actor_required": "Courier needs to know who is deciding.",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class TruthUnavailable(Exception):
    """The journal cannot be read (not created yet, or written by another build)."""


class NotSent(ConnectionError):
    """The controller could not be reached: the request was never delivered."""


class ResponseLost(ConnectionError):
    """The request may have reached the controller, but no answer came back."""


class Hub:
    """Reads canonical truth and relays human decisions. No state of its own."""

    def __init__(self, home: Path, controller_url: str, actor: Optional[str] = None,
                 timeout_s: float = CONTROLLER_TIMEOUT_S):
        self.home = Path(home)
        self.controller_url = controller_url.rstrip("/")
        self.actor = actor or default_actor()
        self.timeout_s = timeout_s
        # Derived-data cache keyed by the journal head: every runtime change appends an
        # event, so an unchanged head means an unchanged projection. Never authoritative.
        self._cache_lock = threading.Lock()
        self._cached = None  # (head_seq, view without status)

    # -- canonical truth (read-only) -------------------------------------------
    def _open(self) -> Journal:
        db = self.home / "courier.db"
        if not db.exists():
            raise TruthUnavailable("not_set_up")
        try:
            journal = Journal(db, readonly=True).open()
        except (sqlite3.DatabaseError, JournalError) as exc:
            raise TruthUnavailable("unreadable") from exc
        try:
            if not journal.projection_current():
                journal.close()
                raise TruthUnavailable("updating")
        except sqlite3.DatabaseError as exc:
            journal.close()
            raise TruthUnavailable("unreadable") from exc
        return journal

    def _read(self):
        journal = self._open()
        try:
            tasks = journal.tasks()
            head = journal.head()[0]
            events_by_task: dict = {}

            from courier_hub.model import pile_of, PILE_DONE
            active_ids = {t.task_id for t in tasks if pile_of(t) != PILE_DONE}
            done_tasks = [t for t in tasks if pile_of(t) == PILE_DONE]
            
            if done_tasks:
                rows = journal.conn.execute("SELECT task_id, MAX(seq) as m FROM events WHERE task_id IS NOT NULL GROUP BY task_id").fetchall()
                max_seqs = {row["task_id"]: row["m"] for row in rows}
                done_tasks.sort(key=lambda t: max_seqs.get(t.task_id, 0), reverse=True)
                keep_done = {t.task_id for t in done_tasks[:50]}
            else:
                keep_done = set()
                
            keep_ids = active_ids | keep_done
            
            if keep_ids:
                from courier_core.events import Event
                keep_list = list(keep_ids)
                chunk_size = 900
                for i in range(0, len(keep_list), chunk_size):
                    chunk = keep_list[i:i + chunk_size]
                    placeholders = ','.join('?' * len(chunk))
                    q = f"SELECT * FROM events WHERE task_id IN ({placeholders}) ORDER BY seq"
                    for row in journal.conn.execute(q, chunk):
                        events_by_task.setdefault(row["task_id"], []).append(Event.from_row(row))
                        
            return tasks, events_by_task, head
        except sqlite3.DatabaseError as exc:
            raise TruthUnavailable("unreadable") from exc
        finally:
            journal.close()

    def _head(self) -> tuple:
        journal = self._open()
        try:
            return tuple(journal.head())  # (seq, hash): a replaced journal never matches the cache
        except sqlite3.DatabaseError as exc:
            raise TruthUnavailable("unreadable") from exc
        finally:
            journal.close()

    def home_view(self) -> dict:
        status = self.status()
        try:
            head = self._head()
            with self._cache_lock:
                cached = self._cached
            if cached is not None and cached[0] == head:
                view = dict(cached[1])
            else:
                tasks, events_by_task, _ = self._read()
                view = model.home(tasks, events_by_task)
                view["head_seq"] = head[0]
                with self._cache_lock:
                    self._cached = (head, view)
                view = dict(view)
        except TruthUnavailable as exc:
            return {"status": status, "truth": exc.args[0], "head_seq": None,
                    "needs_you": [], "working": [], "done": [], "counts": {"needs_you": 0, "working": 0, "done": 0},
                    "read_at": utc_now()}
        view.update({"status": status, "truth": "ok", "read_at": utc_now()})
        return view

    def item_view(self, task_id: str) -> Optional[dict]:
        journal = self._open()
        try:
            task = journal.task(task_id)
            if task is None:
                return None
            events = list(journal.events(task_id=task_id))
        except sqlite3.DatabaseError as exc:
            raise TruthUnavailable("unreadable") from exc
        finally:
            journal.close()
        try:
            card, receipt = model.card(task, events), model.receipt(task, events)
        except ValueError:  # a state this hub does not know: still show what was recorded
            card, receipt = model.unrecognised_card(task), model.unrecognised_receipt(task, events)
        return {"card": card, "receipt": receipt, "support": model.support(task, events), "read_at": utc_now()}

    def support_export(self, task_id: str) -> Optional[dict]:
        """One item's support record, for the customer to save and send. Read-only;
        holds no token, credential, payload or other task's history."""
        item = self.item_view(task_id)
        if item is None:
            return None
        return {"kind": "courier.support_export", "version": 1, "exported_at": utc_now(),
                "hub_build": build_identity(), "item": item["support"], "receipt": item["receipt"]}

    def project_base_view(self, since_seq: int = 0) -> dict:
        """Personal Courier Project Base projection: piles, active workkeys,
        last verified result, what changed while away, next safe action, and durable context."""
        from courier_hub import project_base
        status = self.status()
        controller_st = status.get("controller", "unknown")
        try:
            journal = self._open()
            try:
                tasks = journal.tasks()
                head = tuple(journal.head())
                events_by_task: dict = {}
                all_events = []
                try:
                    for ev in journal.events():
                        all_events.append(ev)
                        if ev.task_id:
                            events_by_task.setdefault(ev.task_id, []).append(ev)
                except Exception:
                    pass
                return project_base.build_project_base(
                    tasks, events_by_task, all_events=all_events, head=head,
                    controller_status=controller_st, since_seq=since_seq,
                )
            finally:
                journal.close()
        except TruthUnavailable as exc:
            return {
                "truth": exc.args[0],
                "controller_status": controller_st,
                "counts": {"needs_you": 0, "working": 0, "done": 0, "active_workkeys": 0},
                "piles": {"needs_you": [], "working": [], "done": []},
                "current_workkeys": [],
                "last_verified_result": None,
                "away_summary": {"since_seq": since_seq, "events_count": 0, "milestones": []},
                "next_safe_action": {
                    "type": "TRUTH_UNAVAILABLE",
                    "urgency": "HIGH",
                    "title": "Truth unavailable",
                    "description": f"Journal truth is currently '{exc.args[0]}'.",
                    "task_id": None,
                    "actions_offered": [],
                },
                "durable_context": {
                    "repository": "happyhippovip/2026-courier",
                    "trunk_branch": "integration/v1",
                    "head_seq": 0,
                    "head_hash": "",
                    "total_tasks": 0,
                    "total_events": 0,
                    "project_memory": None,
                    "generated_at": utc_now(),
                },
                "read_at": utc_now(),
            }

    # -- controller (the only authority) ----------------------------------------
    def _token(self) -> Optional[str]:
        try:
            return (self.home / "run" / "controller.token").read_text(encoding="utf-8").strip() or None
        except OSError:
            return None

    def _call(self, method: str, path: str, body: Optional[dict] = None):
        token = self._token()
        if token is None:
            raise NotSent("no controller token")
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(self.controller_url + path, data=data, method=method,
                                         headers={"X-Courier-Token": token, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                return response.status, json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read() or b"{}")
            except ValueError:
                payload = {}
            return exc.code, payload
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (ConnectionRefusedError, socket.gaierror)):
                raise NotSent(str(exc)) from exc
            raise ResponseLost(str(exc)) from exc
        except ConnectionRefusedError as exc:
            raise NotSent(str(exc)) from exc
        except (OSError, ValueError, http.client.HTTPException) as exc:
            # Sent (or partly sent) but no usable answer: the outcome is unknown.
            raise ResponseLost(str(exc)) from exc

    def status(self) -> dict:
        checked = utc_now()
        if not (self.home / "courier.db").exists() and self._token() is None:
            return {"controller": "not_set_up", "checked_at": checked}
        try:
            code, body = self._call("GET", "/v1/health")
        except ConnectionError:
            return {"controller": "unreachable", "checked_at": checked}
        if code != 200:
            return {"controller": "unreachable", "checked_at": checked}
        mode = body.get("mode")
        return {"controller": "safe_mode" if mode == "degraded_readonly" else "running",
                "checked_at": checked, "head_seq": body.get("head_seq")}

    def decide(self, task_id: str, body: dict) -> tuple:
        decision, attempt = body.get("decision"), body.get("attempt")
        if decision not in model.DECISIONS:
            return 400, {"result": "invalid", "message": "Unknown decision."}
        if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
            return 400, {"result": "invalid", "message": "The decision must name the attempt it is about."}
        note = body.get("note")
        if note is not None and (not isinstance(note, str) or len(note) > 1000):
            return 400, {"result": "invalid", "message": "The note is too long."}
        default_reason = {"effect_confirmed": "Confirmed in the desktop hub: it happened",
                          "retry_authorized": "Authorised one more attempt in the desktop hub",
                          "cancel": "Chose to stop in the desktop hub"}[decision]
        reason = (note or "").strip() or default_reason
        return self._relay(task_id, "POST", f"/v1/tasks/{task_id}/resolve",
                           {"decision": decision, "actor": self.actor, "attempt": attempt, "reason": reason})

    def stop(self, task_id: str, body: dict) -> tuple:
        note = body.get("note")
        reason = (note.strip() if isinstance(note, str) and note.strip() else "Stopped in the desktop hub")[:1000]
        return self._relay(task_id, "POST", f"/v1/tasks/{task_id}/cancel", {"actor": self.actor, "reason": reason})

    def _relay(self, task_id: str, method: str, path: str, payload: dict) -> tuple:
        try:
            code, answer = self._call(method, path, payload)
        except NotSent:
            return 503, {"result": "offline",
                         "message": "Courier isn't reachable right now. Nothing was sent; try again when it's back."}
        except ResponseLost:
            # Never claim "nothing changed" here: the controller may have recorded it.
            return 504, {"result": "unknown",
                         "message": "Courier may have recorded this, but its answer was lost. "
                                    "The item below shows what Courier has recorded now.",
                         "item": self._safe_item(task_id)}
        error = answer.get("error") if isinstance(answer, dict) else None
        if code == 200:
            result = "already_recorded" if answer.get("duplicate") else "recorded"
        elif code == 409 and error in STALE_CODES:
            return 409, {"result": "stale", "code": error, "message": STALE_CODES[error],
                         "item": self._safe_item(task_id)}
        elif code == 404:
            return 404, {"result": "not_found", "message": "Courier has no record of this item."}
        elif code == 503:
            return 503, {"result": "unavailable",
                         "message": "Courier is in safe mode or shutting down. Nothing was changed."}
        else:
            return 502, {"result": "error", "message": "Courier refused this request. Nothing was changed."}
        return 200, {"result": result, "item": self._safe_item(task_id)}

    def _safe_item(self, task_id: str) -> Optional[dict]:
        # Called after the controller answered: a failed read here must never turn a
        # recorded decision into an error, so the item is simply left out.
        try:
            return self.item_view(task_id)
        except Exception:  # noqa: BLE001
            log.exception("hub could not read item %s after relaying", task_id)
            return None


def default_actor() -> str:
    try:
        user = getpass.getuser()
    except Exception:  # noqa: BLE001 - no login name available
        user = "unknown"
    cleaned = re.sub(r"[^A-Za-z0-9_.@-]", "_", user)[:150] or "unknown"
    return f"desktop:{cleaned}"


class HubServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, hub: Hub, port: int):
        super().__init__(("127.0.0.1", port), Handler)
        self.hub = hub
        bound = self.server_address[1]
        self.allowed_hosts = {f"127.0.0.1:{bound}", f"localhost:{bound}"}

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}/"


class Handler(BaseHTTPRequestHandler):
    server_version = "CourierHub/1"
    sys_version = ""
    timeout = 30

    def log_message(self, fmt, *args):  # quiet by default; no request bodies are logged
        log.debug("%s - %s", self.address_string(), fmt % args)

    def _send(self, status: int, payload=None, content_type: str = "application/json", raw: bytes = None,
              extra_headers: Optional[dict] = None):
        body = raw if raw is not None else (b"" if payload is None else json.dumps(payload).encode("utf-8"))
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
                         "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        if body and self.command != "HEAD":
            self.wfile.write(body)

    def _host_ok(self) -> bool:
        return self.headers.get("Host", "") in self.server.allowed_hosts

    def do_GET(self):
        if not self._host_ok():
            return self._send(421, {"error": "wrong_host"})
        path = urlsplit(self.path).path
        hub: Hub = self.server.hub
        try:
            if path == "/hub/api/home":
                return self._send(200, hub.home_view())
            if path == "/hub/api/status":
                return self._send(200, hub.status())
            if path == "/hub/api/project_base":
                from urllib.parse import parse_qs
                qs = parse_qs(urlsplit(self.path).query)
                try:
                    since_seq = int(qs.get("since_seq", ["0"])[0])
                except (ValueError, IndexError):
                    since_seq = 0
                return self._send(200, hub.project_base_view(since_seq=since_seq))
            match = _ITEM.match(path)
            if match:
                try:
                    item = hub.item_view(match.group(1))
                except TruthUnavailable as exc:
                    return self._send(503, {"result": "unavailable", "truth": exc.args[0]})
                return self._send(404, {"result": "not_found"}) if item is None else self._send(200, item)
            match = _SUPPORT.match(path)
            if match:
                try:
                    record = hub.support_export(match.group(1))
                except TruthUnavailable as exc:
                    return self._send(503, {"result": "unavailable", "truth": exc.args[0]})
                if record is None:
                    return self._send(404, {"result": "not_found"})
                return self._send(200, record, extra_headers={
                    "Content-Disposition": f'attachment; filename="courier-support-{match.group(1)}.json"'})
            return self._static(path)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception:  # noqa: BLE001 - never leak internals to the page
            log.exception("hub error on GET %s", path)
            self._send(500, {"result": "error", "message": "The hub hit an internal error."})

    def do_POST(self):
        if not self._host_ok():
            return self._send(421, {"error": "wrong_host"})
        if self.headers.get("X-Courier-Hub") != "1" or not (self.headers.get("Content-Type") or "").startswith(
                "application/json"):
            return self._send(403, {"error": "forbidden"})
        length = self.headers.get("Content-Length")
        if length is None or not (length.isascii() and length.isdigit()) or int(length) > MAX_BODY_BYTES:
            self.close_connection = True
            return self._send(413, {"error": "bad_length"})
        try:
            body = json.loads(self.rfile.read(int(length)) or b"{}")
        except ValueError:
            return self._send(400, {"error": "invalid_json"})
        if not isinstance(body, dict):
            return self._send(400, {"error": "invalid_json"})
        match = _ITEM_ACTION.match(urlsplit(self.path).path)
        if not match:
            return self._send(404, {"error": "not_found"})
        hub: Hub = self.server.hub
        try:
            task_id, action = match.group(1), match.group(2)
            status, payload = hub.decide(task_id, body) if action == "decision" else hub.stop(task_id, body)
            return self._send(status, payload)
        except Exception:  # noqa: BLE001
            log.exception("hub error on POST %s", self.path)
            # The controller may already have recorded it: never claim that nothing changed.
            self._send(500, {"result": "unknown",
                             "message": "The hub hit an internal error. Courier may have recorded this; "
                                        "the list shows what it has recorded now."})

    def _static(self, path: str):
        name = "index.html" if path in ("/", "/index.html") else path.lstrip("/")
        if "/" in name or "\\" in name or name.startswith("."):
            return self._send(404, {"error": "not_found"})
        file = STATIC_DIR / name
        if not file.is_file():
            return self._send(404, {"error": "not_found"})
        return self._send(200, raw=file.read_bytes(),
                          content_type=STATIC_TYPES.get(file.suffix, "application/octet-stream"))


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m courier_hub", description="Courier Desktop Hub")
    parser.add_argument("--home", default=os.environ.get("COURIER_HOME"), help="COURIER_HOME of the controller")
    parser.add_argument("--controller", required=True, help="controller base URL, e.g. http://127.0.0.1:8765")
    parser.add_argument("--port", type=int, default=0, help="hub port on 127.0.0.1 (0 = pick a free port)")
    parser.add_argument("--actor", default=None, help="who decides in this hub (default desktop:<login name>)")
    parser.add_argument("--print-url", action="store_true")
    parser.add_argument("--with-overlay", action="store_true", help="start the desktop robot overlay on the main thread")
    args = parser.parse_args(argv)
    if not args.home:
        parser.error("--home (or COURIER_HOME) is required")
    if args.actor is not None and not ACTOR_RE.match(args.actor):
        parser.error("--actor must be 1-200 characters of letters, digits and _.:@-")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    server = HubServer(Hub(Path(args.home), args.controller, actor=args.actor), args.port)
    if args.print_url:
        print(server.url, flush=True)
    log.info("desktop hub on %s (home %s)", server.url, args.home)
    stop = threading.Event()
    try:
        if args.with_overlay:
            t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.5}, daemon=True)
            t.start()
            
            from courier_overlay.state_machine import OverlayStateMachine
            from courier_overlay.layout_engine import LayoutEngine, WindowAdapter, Screen, Rect
            from courier_overlay.renderer_tk import TkinterRenderer
            
            class DesktopAdapter(WindowAdapter):
                def get_screen(self):
                    return Screen(1920, 1080, Rect(0, 0, 1920, 1080))
                def list_windows(self):
                    return []
                def move_window(self, wid, rect):
                    return True
            
            bus_path = Path(args.home) / "bus.jsonl"
            sm = OverlayStateMachine(str(bus_path))
            engine = LayoutEngine(DesktopAdapter())
            renderer = TkinterRenderer(engine)
            
            def _sync_loop():
                sm.sync()
                renderer.render(sm.get_snapshot())
                renderer.root.after(100, _sync_loop)
                
            _sync_loop()
            renderer.root.mainloop()
        else:
            server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        stop.set()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
