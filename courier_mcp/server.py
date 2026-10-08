"""Minimal MCP server over Streamable HTTP (JSON responses only, no SSE).

Implemented with the standard library because the MCP Python SDK is not in
the pinned dependency set. Covered: ``initialize``, ``notifications/*``,
``ping``, ``tools/list``, ``tools/call``. ``POST /mcp`` answers every request
with ``application/json``; ``GET /mcp`` is 405 (no server-initiated stream);
JSON-RPC batches are rejected. The server is stateless and issues no session id.

Auth: every MCP request needs ``Authorization: Bearer <COURIER_MCP_TOKEN>``.
With ``--allow-path-token`` the same token may instead be the last path
segment (``/mcp/<token>``) for clients that cannot send a header.
"""

from __future__ import annotations

import argparse
import hmac
import ipaddress
import json
import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import __version__
from .tools import TOOLS, Source, ToolError, call_tool, tool_result

TOKEN_ENV = "COURIER_MCP_TOKEN"
STATE_DIR_ENV = "COURIER_MCP_STATE_DIR"
MIN_TOKEN_LENGTH = 32
MAX_BODY_BYTES = 64 * 1024
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
SUPPORTED_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
DEFAULT_ORIGINS = ("https://grok.com", "https://www.grok.com")
INSTRUCTIONS = (
    "Courier read-only server. Use courier_status for the current automation state, "
    "list_missions/get_mission for missions, and list_receipts/receipts_summary for "
    "verified results. Nothing here can change state."
)


class ConfigError(Exception):
    """The server refuses to start. The message never contains the token."""


class Config:
    def __init__(self, source: Source, token: str | None, allow_path_token: bool, origins: tuple[str, ...]):
        self.source = source
        self.token = token
        self.allow_path_token = allow_path_token
        self.origins = origins


def handle_message(config: Config, message) -> dict | None:
    """One JSON-RPC message in, one response out (``None`` for notifications)."""
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _error(None, -32600, "Invalid Request")
    if "method" not in message:
        return None  # a response from the client; nothing to answer
    request_id = message.get("id")
    method = message.get("method")
    params = message.get("params") or {}
    if "id" not in message:
        return None  # notification, e.g. notifications/initialized
    if not isinstance(method, str) or not isinstance(params, dict):
        return _error(request_id, -32600, "Invalid Request")
    if method == "initialize":
        requested = params.get("protocolVersion")
        version = requested if requested in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[0]
        return _ok(request_id, {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "courier-mcp", "title": "Courier (read-only)", "version": __version__},
            "instructions": INSTRUCTIONS,
        })
    if method == "ping":
        return _ok(request_id, {})
    if method == "tools/list":
        return _ok(request_id, {"tools": TOOLS})
    if method == "tools/call":
        name = params.get("name")
        if not isinstance(name, str):
            return _error(request_id, -32602, "Invalid params: name")
        try:
            payload = call_tool(config.source, name, params.get("arguments"))
        except KeyError:
            return _error(request_id, -32602, "Unknown tool")
        except ToolError as exc:
            return _ok(request_id, tool_result({"error": "INVALID_ARGUMENTS", "detail": str(exc)}, is_error=True))
        except Exception:  # fail closed without leaking internals
            return _ok(request_id, tool_result({"error": "UNAVAILABLE"}, is_error=True))
        return _ok(request_id, tool_result(payload))
    return _error(request_id, -32601, "Method not found")


def _ok(request_id, result) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id, code, message) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def make_handler(config: Config):
    class Handler(BaseHTTPRequestHandler):
        server_version = "courier-mcp"
        sys_version = ""
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):  # never log paths: they may carry the token
            sys.stderr.write(f"courier-mcp {self.command} {getattr(self, '_status', '-')}\n")

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/healthz":
                return self._json(200, {"ok": True})
            if self._route(path) is not None:
                return self._send(405, b"", extra={"Allow": "POST"})
            return self._json(404, {"error": "not found"})

        def do_DELETE(self):
            self._send(405, b"", extra={"Allow": "POST"})

        do_PUT = do_PATCH = do_DELETE

        def do_POST(self):
            self._body_read = False
            path = self.path.split("?", 1)[0]
            route = self._route(path)
            if route is None:
                return self._json(404, {"error": "not found"})
            origin = self.headers.get("Origin")
            if origin is not None and origin not in config.origins:
                return self._json(403, {"error": "origin not allowed"})
            if not self._authorized(route):
                return self._json(401, {"error": "unauthorized"},
                                  extra={"WWW-Authenticate": 'Bearer realm="courier-mcp"'})
            version = self.headers.get("MCP-Protocol-Version")
            if version is not None and version not in SUPPORTED_VERSIONS:
                return self._json(400, _error(None, -32600, "Unsupported MCP-Protocol-Version"))
            ctype = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
            if ctype != "application/json":
                return self._json(415, _error(None, -32600, "Content-Type must be application/json"))
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                return self._json(411, _error(None, -32600, "Content-Length required"))
            if length < 0 or length > MAX_BODY_BYTES:
                return self._json(413, _error(None, -32600, "Request too large"))
            raw = self.rfile.read(length)
            self._body_read = True
            try:
                message = json.loads(raw.decode("utf-8"))
            except (UnicodeError, ValueError):
                return self._json(400, _error(None, -32700, "Parse error"))
            if isinstance(message, list):
                return self._json(400, _error(None, -32600, "Batch requests are not supported"))
            response = handle_message(config, message)
            if response is None:
                return self._send(202, b"")
            return self._json(200, response)

        def _route(self, path):
            if path == "/mcp":
                return "header"
            if config.allow_path_token and path.startswith("/mcp/"):
                return "path"
            return None

        def _authorized(self, route) -> bool:
            if config.token is None:
                return True  # demo on loopback only, enforced at start
            if route == "path":
                supplied = self.path.split("?", 1)[0][len("/mcp/"):]
            else:
                header = self.headers.get("Authorization") or ""
                if not header.startswith("Bearer "):
                    return False
                supplied = header[len("Bearer "):].strip()
            return hmac.compare_digest(supplied.encode("utf-8"), config.token.encode("utf-8"))

        def _json(self, status, body, extra=None):
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self._send(status, data, content_type="application/json", extra=extra)

        def _send(self, status, data, content_type=None, extra=None):
            self._status = status
            self.send_response(status)
            if self.command == "POST" and not getattr(self, "_body_read", False):
                # The request body was not consumed; reusing the connection would
                # parse it as the next request line.
                self.close_connection = True
                self.send_header("Connection", "close")
            if content_type:
                self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            if data:
                self.wfile.write(data)

    return Handler


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="courier_mcp", description="Read-only Courier MCP server.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Bind address (default 127.0.0.1).")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--state-dir", default=None,
                        help=f"Directory holding ledger_bridge_state.json (or ${STATE_DIR_ENV}).")
    parser.add_argument("--demo", action="store_true", help="Serve bundled synthetic demo data only.")
    parser.add_argument("--allow-path-token", action="store_true",
                        help="Also accept the token as the last path segment: /mcp/<token>.")
    parser.add_argument("--allow-origin", action="append", default=[],
                        help="Extra browser Origin to accept (repeatable).")
    return parser.parse_args(argv)


def build_config(args, environ) -> Config:
    token = environ.get(TOKEN_ENV) or None
    if token is not None and (len(token) < MIN_TOKEN_LENGTH or not token.isprintable() or " " in token):
        raise ConfigError(f"{TOKEN_ENV} must be at least {MIN_TOKEN_LENGTH} printable characters without spaces.")
    if not 0 <= args.port <= 65535:
        raise ConfigError("port out of range")
    state_dir = args.state_dir or environ.get(STATE_DIR_ENV) or None
    if args.demo:
        if state_dir is not None:
            raise ConfigError("--demo serves bundled demo data only; do not pass a state dir.")
        if token is None and not _is_loopback(args.host):
            raise ConfigError(f"--demo without {TOKEN_ENV} is allowed on a loopback address only.")
        if token is None and args.allow_path_token:
            raise ConfigError(f"--allow-path-token needs {TOKEN_ENV}.")
        source = Source(demo=True)
    else:
        if token is None:
            raise ConfigError(f"{TOKEN_ENV} is required (or use --demo).")
        if state_dir is None:
            raise ConfigError(f"--state-dir or {STATE_DIR_ENV} is required (or use --demo).")
        if not Path(state_dir).is_dir():
            raise ConfigError("state dir does not exist or is not a directory.")
        source = Source(state_dir=Path(state_dir).resolve())
    return Config(source, token, args.allow_path_token, DEFAULT_ORIGINS + tuple(args.allow_origin))


def make_server(config: Config, host: str, port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), make_handler(config))
    server.daemon_threads = True
    return server


def main(argv=None, environ=None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        config = build_config(args, os.environ if environ is None else environ)
    except ConfigError as exc:
        sys.stderr.write(f"courier-mcp: refusing to start: {exc}\n")
        return 2
    server = make_server(config, args.host, args.port)
    mode = "demo" if config.source.demo else "state-dir"
    auth = "bearer" if config.token else "none (loopback demo)"
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sys.stderr.write(f"courier-mcp {__version__} listening on {args.host}:{server.server_address[1]} "
                     f"mode={mode} auth={auth} path_token={config.allow_path_token} started={started}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
