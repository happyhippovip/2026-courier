"""Courier v1 controller process: `python -m courier_core.serve`.

    python -m courier_core.serve --home <H> --port <P> [--print-port]

- COURIER_HOME is used when --home is omitted. The controller binds
  127.0.0.1 only; --port 0 picks a free port (print it with --print-port).
- One controller per home: <H>/run/controller.lock is held for the life of
  the process (released by the OS if the process dies).
- <H>/run/controller.token holds the per-install API token (created once,
  owner-only permissions on POSIX). Every request must send it as
  X-Courier-Token. The token is never logged or echoed.
- POST /v1/shutdown, SIGTERM, SIGINT (and CTRL_BREAK on Windows) stop the
  controller gracefully: HTTP stops, background threads are joined,
  CONTROLLER_STOPPED is journaled and the journal is closed.

HTTP API (prefix /v1, JSON bodies, see tests/golden/README.md):
  GET  /health                 mode, head_seq (+ first_bad_seq when degraded)
  GET  /events                 SSE of every journal event, id = seq; resume with Last-Event-ID
  GET  /tasks/<id>             projection row of one task
  POST /tasks                  create a task (201, or 200 for a repeated idempotency_key)
  POST /claim                  {"worker_id"} -> lease (200) or 204 when there is no work
  POST /start                  {"dispatch_id"[, "worker_id"]}
  POST /heartbeat              {"worker_id", "dispatch_ids"} -> {"stop": [...], "cancel": [...]}
  POST /result                 {"dispatch_id", "result_id", "artifacts", "outcome"[, "retryable", "reason"]}
  POST /tasks/<id>/cancel
  POST /shutdown

Worker contract for cancellation (L3): when a heartbeat answer lists a
dispatch in "cancel" (or "stop"), the worker kills and reaps that dispatch's
process tree and then stops reporting it; the first heartbeat without it
confirms the stop and the controller journals TASK_CANCELLED.
"""

from __future__ import annotations

import argparse
import hmac
import json
import logging
import os
import re
import secrets
import signal
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from courier_core.controller import DEGRADED, ApiError, Controller

log = logging.getLogger("courier.serve")

MAX_BODY_BYTES = 1024 * 1024
SSE_KEEPALIVE_S = 15.0
MAX_EVENT_STREAMS = 32  # each SSE client holds one thread; bound them
TOKEN_HEADER = "X-Courier-Token"
_TASK_PATH = re.compile(r"^/v1/tasks/([A-Za-z0-9_.:-]{1,200})$")
_CANCEL_PATH = re.compile(r"^/v1/tasks/([A-Za-z0-9_.:-]{1,200})/cancel$")


# --------------------------------------------------------------------- files
class HomeLock:
    """Exclusive lock on <home>/run/controller.lock for the process lifetime."""

    def __init__(self, path: Path):
        self.path = path
        self._fh = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self.path, "a+b")
        try:
            if os.name == "nt":
                import msvcrt
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            return False
        self._fh = fh
        return True

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            if os.name == "nt":
                import msvcrt
                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            self._fh.close()
            self._fh = None


def load_or_create_token(path: Path) -> str:
    """Per-install token: reuse a valid existing one, else create it atomically."""
    try:
        token = path.read_text(encoding="utf-8").strip()
        if len(token) >= 32:
            return token
    except FileNotFoundError:
        pass
    token = secrets.token_urlsafe(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(token + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    return token


# ---------------------------------------------------------------------- HTTP
class ControllerServer(ThreadingHTTPServer):
    daemon_threads = True
    # POSIX: allow rebinding over TIME_WAIT after a restart. Windows: SO_REUSEADDR
    # would let another socket share the port, so use exclusive address use instead.
    allow_reuse_address = os.name != "nt"

    def __init__(self, port: int, controller: Controller, token: str):
        self.controller = controller
        self.token = token
        self.streams = threading.BoundedSemaphore(MAX_EVENT_STREAMS)
        super().__init__(("127.0.0.1", port), Handler)

    def server_bind(self):
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "Courier/1"
    sys_version = ""
    server: ControllerServer

    # -- plumbing -------------------------------------------------------------
    def log_message(self, fmt, *args):  # never logs headers (the token travels in one)
        log.debug("%s %s", self.address_string(), fmt % args)

    def _send(self, status: int, body: dict | None = None) -> None:
        data = b"" if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if data:
            self.wfile.write(data)

    def _authorized(self) -> bool:
        supplied = self.headers.get(TOKEN_HEADER, "")
        return hmac.compare_digest(supplied.encode("utf-8"), self.server.token.encode("utf-8"))

    def _read_json(self):
        length_header = self.headers.get("Content-Length")
        if self.headers.get("Transfer-Encoding") or (length_header is not None and not length_header.isdigit()):
            self.close_connection = True  # unread bytes must never be parsed as the next request
            raise ApiError(411, "length_required", "send a valid Content-Length; chunked bodies are not accepted")
        if length_header is None:
            self.close_connection = True
            return {}
        length = int(length_header)
        if length > MAX_BODY_BYTES:
            self.close_connection = True
            raise ApiError(413, "too_large", f"body exceeds {MAX_BODY_BYTES} bytes")
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiError(400, "invalid_json", "body is not valid UTF-8 JSON") from None

    def _dispatch(self, method: str) -> None:
        path = urlsplit(self.path).path
        controller = self.server.controller
        try:
            if not self._authorized():
                self.close_connection = True  # do not read or trust anything else on this connection
                raise ApiError(401, "unauthorized", "missing or invalid token")
            if method == "GET":
                if path == "/v1/health":
                    return self._send(200, controller.health())
                if path == "/v1/events":
                    return self._stream_events()
                match = _TASK_PATH.match(path)
                if match:
                    return self._send(200, controller.task_view(match.group(1)))
                raise ApiError(404, "not_found")
            body = self._read_json()
            if path == "/v1/tasks":
                status, payload = controller.create_task(body)
                return self._send(status, payload)
            if path == "/v1/claim":
                lease = controller.claim(body)
                return self._send(204) if lease is None else self._send(200, lease)
            if path == "/v1/start":
                return self._send(200, controller.start(body))
            if path == "/v1/heartbeat":
                return self._send(200, controller.heartbeat(body))
            if path == "/v1/result":
                status, payload = controller.result(body)
                return self._send(status, payload)
            if path == "/v1/shutdown":
                self._send(200, {"status": "STOPPING"})
                self.close_connection = True
                threading.Thread(target=self.server.request_stop, name="courier-shutdown", daemon=True).start()
                return None
            match = _CANCEL_PATH.match(path)
            if match:
                return self._send(200, controller.cancel(match.group(1)))
            raise ApiError(404, "not_found")
        except ApiError as exc:
            self._send(exc.status, exc.body())
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception:  # noqa: BLE001 - never leak internals to the client
            log.exception("unhandled error on %s %s", method, path)
            try:
                self._send(500, {"error": "internal", "message": "internal error; see controller log"})
            except OSError:
                self.close_connection = True

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._send(405, {"error": "method_not_allowed"})

    do_DELETE = do_PATCH = do_PUT

    # -- server-sent events ----------------------------------------------------
    def _stream_events(self) -> None:
        controller = self.server.controller
        query = parse_qs(urlsplit(self.path).query)
        raw = self.headers.get("Last-Event-ID") or (query.get("after") or ["0"])[0]
        if not raw.strip().isdigit():
            raise ApiError(400, "invalid_request", "Last-Event-ID must be a journal seq")
        last = int(raw.strip())
        if not self.server.streams.acquire(blocking=False):
            raise ApiError(503, "too_many_streams", f"at most {MAX_EVENT_STREAMS} event streams")
        try:
            self._pump_events(controller, last)
        finally:
            self.server.streams.release()

    def _pump_events(self, controller, last: int) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        idle = 0.0
        try:
            while not controller.stopping and not self.server.stopping.is_set():
                batch = controller.events_after(last)
                for event in batch:
                    data = json.dumps(_event_json(event), separators=(",", ":"))
                    self.wfile.write(f"id: {event.seq}\nevent: {event.type.value}\ndata: {data}\n\n".encode())
                    last = event.seq
                if batch:
                    self.wfile.flush()
                    idle = 0.0
                    continue
                controller.wait_for_change(last, 1.0)
                idle += 1.0
                if idle >= SSE_KEEPALIVE_S:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    idle = 0.0
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return


def _event_json(event) -> dict:
    return {"seq": event.seq, "event_id": event.event_id, "type": event.type.value, "task_id": event.task_id,
            "attempt": event.attempt, "dispatch_id": event.dispatch_id, "worker_id": event.worker_id,
            "result_id": event.result_id, "ts_utc": event.ts_utc, "payload": event.payload, "hash": event.hash}


# ----------------------------------------------------------------- lifecycle
class Service:
    """Controller + HTTP server + process lock, with one stop path."""

    def __init__(self, home: Path, port: int, controller: Controller | None = None):
        self.home = home
        self.lock = HomeLock(home / "run" / "controller.lock")
        if not self.lock.acquire():
            raise SystemExit(f"another Courier controller already owns {home}")
        try:
            self.controller = (controller or Controller(home)).boot()
            self.token = load_or_create_token(home / "run" / "controller.token")
            self.server = ControllerServer(port, self.controller, self.token)
        except BaseException:
            self.lock.release()
            raise
        self.server.stopping = threading.Event()
        self.server.request_stop = self.request_stop
        self._stopped = threading.Event()

    @property
    def port(self) -> int:
        return self.server.server_address[1]

    def request_stop(self) -> None:
        self.server.stopping.set()

    def run(self) -> None:
        """Serve until a stop is requested, then shut down within a bounded time."""
        self.controller.start_background()
        thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.2},
                                  name="courier-http", daemon=True)
        thread.start()
        try:
            while not self.server.stopping.wait(0.5):
                pass
        finally:
            self.shutdown()
            thread.join(timeout=5)

    def shutdown(self) -> None:
        if self._stopped.is_set():
            return
        self._stopped.set()
        self.server.stopping.set()
        self.server.shutdown()
        self.server.server_close()
        self.controller.stop()
        self.lock.release()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m courier_core.serve", description="Courier v1 controller")
    parser.add_argument("--home", default=os.environ.get("COURIER_HOME"),
                        help="Courier home directory (default: $COURIER_HOME)")
    parser.add_argument("--port", type=int, default=0, help="TCP port on 127.0.0.1 (0 = pick a free port)")
    parser.add_argument("--print-port", action="store_true", help="print the bound port on stdout")
    parser.add_argument("--log-level", default=os.environ.get("COURIER_LOG_LEVEL", "INFO"))
    args = parser.parse_args(argv)
    if not args.home:
        parser.error("--home or COURIER_HOME is required")
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")
    logging.basicConfig(level=args.log_level.upper(), stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    home = Path(args.home).expanduser().resolve()
    service = Service(home, args.port)
    for name in ("SIGTERM", "SIGINT", "SIGBREAK"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), lambda *_: service.request_stop())
    if args.print_port:
        print(service.port, flush=True)
    log.info("controller listening on 127.0.0.1:%d mode=%s home=%s", service.port, service.controller.mode, home)
    if service.controller.mode == DEGRADED:
        log.error("degraded_readonly: %s", service.controller.degraded_reason)
    service.run()
    log.info("controller stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
