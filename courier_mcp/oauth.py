"""Minimal OAuth 2.1 authorization server for the read-only MCP endpoint.

Scope: one owner approves hosted MCP clients (for example a Grok custom
connector). Public clients only (``token_endpoint_auth_method: none``) with
PKCE S256. One fixed client id plus optional dynamic client registration
(RFC 7591). The approval password is the server's existing static token.

Authorization codes live in memory (single use, short-lived). Access and
refresh tokens are opaque random strings; only their SHA-256 hashes are kept,
in a JSON store written with mode 0600. Secrets, codes and tokens are never
logged. Wrong approval passwords are rate-limited.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import sys
import threading
import time
from collections import deque
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

FIXED_CLIENT_ID = "courier-grok"
SCOPE = "courier.read"
CODE_TTL = 120
ACCESS_TTL = 3600
REFRESH_TTL = 30 * 24 * 3600
FAIL_LIMIT = 5
FAIL_WINDOW = 600
MAX_FORM_BYTES = 16 * 1024
MAX_CLIENTS = 200
MAX_TOKENS = 2000
MAX_CODES = 200
ALLOWED_REDIRECT_DOMAINS = ("grok.com", "x.ai")
_VERIFIER = re.compile(r"^[A-Za-z0-9\-._~]{43,128}$")
_CHALLENGE = re.compile(r"^[A-Za-z0-9\-_]{43}$")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def redirect_allowed(uri) -> bool:
    if not isinstance(uri, str) or len(uri) > 2048:
        return False
    try:
        parts = urlparse(uri)
        port = parts.port
    except ValueError:
        return False
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or parts.username or parts.password or parts.fragment:
        return False
    if port not in (None, 443):
        return False
    return any(host == domain or host.endswith("." + domain) for domain in ALLOWED_REDIRECT_DOMAINS)


def _safe_host(uri) -> str:
    try:
        host = urlparse(uri).hostname or "-"
    except (ValueError, TypeError):
        host = "-"
    host = "".join(ch for ch in host if ch.isalnum() or ch in ".-")[:100]
    return host or "-"


class OAuthError(Exception):
    def __init__(self, error: str, description: str = "", status: int = 400):
        super().__init__(error)
        self.error = error
        self.description = description
        self.status = status


class OAuthServer:
    def __init__(self, public_url: str, password: str, store_path, clock=time.time, log=None):
        public_url = public_url.rstrip("/")
        parts = urlparse(public_url)
        if parts.scheme != "https" or not parts.hostname or parts.path or parts.query:
            raise ValueError("public URL must be https://host without a path")
        self.issuer = public_url
        self.resource = public_url + "/mcp"
        self._password = password.encode("utf-8")
        self._store_path = Path(store_path)
        self._clock = clock
        self._log = log or (lambda line: sys.stderr.write(line + "\n"))
        self._lock = threading.Lock()
        self._codes: dict[str, dict] = {}
        self._fails: deque = deque()
        self._store = self._load()

    # ---- metadata ----------------------------------------------------------
    def authorization_server_metadata(self) -> dict:
        return {
            "issuer": self.issuer,
            "authorization_endpoint": self.issuer + "/authorize",
            "token_endpoint": self.issuer + "/token",
            "registration_endpoint": self.issuer + "/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
            "scopes_supported": [SCOPE],
        }

    def protected_resource_metadata(self) -> dict:
        return {
            "resource": self.resource,
            "authorization_servers": [self.issuer],
            "scopes_supported": [SCOPE],
            "bearer_methods_supported": ["header"],
            "resource_name": "Courier (read-only)",
        }

    def www_authenticate(self) -> str:
        return (f'Bearer realm="courier-mcp", resource_metadata="{self.issuer}'
                f'/.well-known/oauth-protected-resource", scope="{SCOPE}"')

    # ---- store -------------------------------------------------------------
    def _load(self) -> dict:
        empty = {"clients": {}, "access": {}, "refresh": {}}
        try:
            if self._store_path.is_symlink():
                return empty
            raw = self._store_path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, ValueError):
            return empty
        if not isinstance(data, dict) or not all(isinstance(data.get(k), dict) for k in empty):
            return empty
        return {k: data[k] for k in empty}

    def _save(self) -> None:
        now = self._clock()
        for kind in ("access", "refresh"):
            table = self._store[kind]
            for key in [k for k, v in table.items() if v.get("exp", 0) <= now]:
                del table[key]
        tmp = self._store_path.with_name(self._store_path.name + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(self._store, handle, sort_keys=True)
        os.chmod(tmp, 0o600)
        os.replace(tmp, self._store_path)

    # ---- clients -----------------------------------------------------------
    def _client_ok(self, client_id, redirect_uri) -> bool:
        if not redirect_allowed(redirect_uri):
            return False
        if client_id == FIXED_CLIENT_ID:
            return True
        client = self._store["clients"].get(client_id) if isinstance(client_id, str) else None
        return bool(client) and redirect_uri in client.get("redirect_uris", [])

    def register(self, body) -> dict:
        if not isinstance(body, dict):
            raise OAuthError("invalid_client_metadata", "body must be a JSON object")
        uris = body.get("redirect_uris")
        if not isinstance(uris, list) or not uris or len(uris) > 5:
            raise OAuthError("invalid_redirect_uri", "redirect_uris required")
        for uri in uris:
            if not redirect_allowed(uri):
                self._log(f"courier-mcp oauth rejected redirect_uri host={_safe_host(uri)} at=register")
                raise OAuthError("invalid_redirect_uri", "redirect_uri host not allowed")
        method = body.get("token_endpoint_auth_method", "none")
        if method != "none":
            raise OAuthError("invalid_client_metadata", "only token_endpoint_auth_method none")
        with self._lock:
            if len(self._store["clients"]) >= MAX_CLIENTS:
                raise OAuthError("temporarily_unavailable", "client limit reached", status=503)
            client_id = "dcr-" + secrets.token_urlsafe(16)
            issued = int(self._clock())
            name = body.get("client_name") if isinstance(body.get("client_name"), str) else ""
            self._store["clients"][client_id] = {"redirect_uris": list(uris), "created": issued,
                                                 "client_name": name[:100]}
            self._save()
        return {
            "client_id": client_id,
            "client_id_issued_at": issued,
            "redirect_uris": list(uris),
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "scope": SCOPE,
        }

    # ---- authorize ---------------------------------------------------------
    def check_authorize(self, params: dict) -> dict:
        """Validate an authorization request. Raises OAuthError(redirectable=False) for bad client/redirect."""
        client_id = params.get("client_id")
        redirect_uri = params.get("redirect_uri")
        if not self._client_ok(client_id, redirect_uri):
            if redirect_uri is not None and not redirect_allowed(redirect_uri):
                self._log(f"courier-mcp oauth rejected redirect_uri host={_safe_host(redirect_uri)} at=authorize")
            raise OAuthError("invalid_request", "Unknown client or redirect address not allowed.")
        problem = None
        if params.get("response_type") != "code":
            problem = ("unsupported_response_type", "response_type must be code")
        elif params.get("code_challenge_method") != "S256" or not _CHALLENGE.match(params.get("code_challenge") or ""):
            problem = ("invalid_request", "PKCE S256 code_challenge required")
        elif params.get("scope") not in (None, "", SCOPE):
            problem = ("invalid_scope", f"only {SCOPE}")
        elif params.get("resource") not in (None, "", self.resource, self.issuer, self.issuer + "/"):
            problem = ("invalid_target", "unknown resource")
        if problem:
            raise OAuthError(problem[0], problem[1], status=302)
        return {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code_challenge": params["code_challenge"],
            "state": params.get("state") or "",
            "scope": SCOPE,
            "resource": params.get("resource") or "",
        }

    def error_redirect(self, request: dict, error: str, description: str = "") -> str:
        query = {"error": error, "iss": self.issuer}
        if description:
            query["error_description"] = description
        if request.get("state"):
            query["state"] = request["state"]
        return _append_query(request["redirect_uri"], query)

    def approve(self, request: dict, password: str) -> str:
        """Check the owner password and return the redirect URL carrying a code."""
        with self._lock:
            now = self._clock()
            while self._fails and self._fails[0] <= now - FAIL_WINDOW:
                self._fails.popleft()
            if len(self._fails) >= FAIL_LIMIT:
                raise OAuthError("locked", "Too many wrong passwords. Try again later.", status=429)
            if not hmac.compare_digest((password or "").encode("utf-8"), self._password):
                self._fails.append(now)
                raise OAuthError("wrong_password", "Wrong password.", status=401)
            for key in [k for k, v in self._codes.items() if v["exp"] <= now]:
                del self._codes[key]
            if len(self._codes) >= MAX_CODES:
                raise OAuthError("temporarily_unavailable", "Too many pending approvals.", status=503)
            code = secrets.token_urlsafe(32)
            self._codes[_hash(code)] = dict(request, exp=now + CODE_TTL)
        query = {"code": code, "iss": self.issuer}
        if request.get("state"):
            query["state"] = request["state"]
        return _append_query(request["redirect_uri"], query)

    # ---- token -------------------------------------------------------------
    def token(self, form: dict) -> dict:
        grant = form.get("grant_type")
        if grant == "authorization_code":
            return self._exchange_code(form)
        if grant == "refresh_token":
            return self._refresh(form)
        raise OAuthError("unsupported_grant_type")

    def _exchange_code(self, form) -> dict:
        code = form.get("code") or ""
        with self._lock:
            entry = self._codes.pop(_hash(code), None)  # single use, even on failure
            now = self._clock()
            if entry is None or entry["exp"] <= now:
                raise OAuthError("invalid_grant", "code invalid or expired")
            if form.get("client_id") != entry["client_id"] or form.get("redirect_uri") != entry["redirect_uri"]:
                raise OAuthError("invalid_grant", "client or redirect mismatch")
            verifier = form.get("code_verifier") or ""
            if not _VERIFIER.match(verifier) or not hmac.compare_digest(s256(verifier), entry["code_challenge"]):
                raise OAuthError("invalid_grant", "PKCE verification failed")
            return self._issue(entry["client_id"], now)

    def _refresh(self, form) -> dict:
        refresh = form.get("refresh_token") or ""
        with self._lock:
            now = self._clock()
            entry = self._store["refresh"].pop(_hash(refresh), None)  # rotate: old one is spent
            if entry is None or entry["exp"] <= now:
                self._save()
                raise OAuthError("invalid_grant", "refresh token invalid or expired")
            if form.get("client_id") not in (None, entry["client_id"]):
                self._save()
                raise OAuthError("invalid_grant", "client mismatch")
            return self._issue(entry["client_id"], now)

    def _issue(self, client_id, now) -> dict:
        if len(self._store["access"]) >= MAX_TOKENS or len(self._store["refresh"]) >= MAX_TOKENS:
            self._save()
            if len(self._store["access"]) >= MAX_TOKENS or len(self._store["refresh"]) >= MAX_TOKENS:
                raise OAuthError("temporarily_unavailable", "token limit reached", status=503)
        access = secrets.token_urlsafe(32)
        refresh = secrets.token_urlsafe(32)
        self._store["access"][_hash(access)] = {"client_id": client_id, "scope": SCOPE, "exp": now + ACCESS_TTL}
        self._store["refresh"][_hash(refresh)] = {"client_id": client_id, "scope": SCOPE, "exp": now + REFRESH_TTL}
        self._save()
        return {"access_token": access, "token_type": "Bearer", "expires_in": ACCESS_TTL,
                "refresh_token": refresh, "scope": SCOPE}

    def access_ok(self, token: str) -> bool:
        if not token:
            return False
        with self._lock:
            entry = self._store["access"].get(_hash(token))
            return bool(entry) and entry["exp"] > self._clock() and entry.get("scope") == SCOPE


def _append_query(uri: str, query: dict) -> str:
    separator = "&" if urlparse(uri).query else "?"
    return uri + separator + urlencode(query)


def parse_form(raw: bytes) -> dict:
    """application/x-www-form-urlencoded; duplicate keys are rejected."""
    try:
        text = raw.decode("utf-8")
        pairs = parse_qs(text, keep_blank_values=True, strict_parsing=bool(text), max_num_fields=32)
    except (UnicodeError, ValueError):
        raise OAuthError("invalid_request", "malformed form")
    if any(len(values) != 1 for values in pairs.values()):
        raise OAuthError("invalid_request", "duplicate parameter")
    return {key: values[0] for key, values in pairs.items()}


def query_params(path: str) -> dict:
    query = path.split("?", 1)[1] if "?" in path else ""
    return parse_form(query.encode("utf-8"))


_PAGE = """<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Courier – Zugriff erlauben</title>
<style>body{{font-family:system-ui,sans-serif;max-width:28rem;margin:3rem auto;padding:0 1rem;color:#111}}
.box{{border:1px solid #ccc;border-radius:12px;padding:1.25rem}}input[type=password]{{width:100%;padding:.6rem;font-size:1rem;box-sizing:border-box}}
button{{padding:.6rem 1rem;font-size:1rem;margin-top:.8rem;margin-right:.5rem}}.err{{color:#b00020}}.muted{{color:#555;font-size:.9rem}}</style></head>
<body><div class="box"><h2>Courier (nur lesen)</h2>{body}</div></body></html>"""


def consent_page(request: dict, error: str = "") -> str:
    hidden = "".join(
        f'<input type="hidden" name="{html.escape(k)}" value="{html.escape(v)}">'
        for k, v in (("client_id", request["client_id"]), ("redirect_uri", request["redirect_uri"]),
                     ("code_challenge", request["code_challenge"]), ("code_challenge_method", "S256"),
                     ("response_type", "code"), ("state", request["state"]), ("scope", request["scope"]),
                     ("resource", request["resource"]))
    )
    host = html.escape(_safe_host(request["redirect_uri"]))
    note = f'<p class="err">{html.escape(error)}</p>' if error else ""
    body = (
        f"<p><b>{html.escape(request['client_id'])}</b> möchte lesend auf Courier zugreifen: "
        f"Status, Missionen und Belege. Ändern kann es nichts.</p>"
        f'<p class="muted">Danach geht es zurück zu <b>{host}</b>.</p>{note}'
        f'<form method="post" action="/authorize" autocomplete="off">{hidden}'
        f'<label for="pw">Freigabe-Passwort</label><input id="pw" type="password" name="password" required autofocus>'
        f'<button type="submit" name="decision" value="allow">Erlauben</button>'
        f'<button type="submit" name="decision" value="deny" formnovalidate>Ablehnen</button></form>'
    )
    return _PAGE.format(body=body)


def message_page(title: str, text: str) -> str:
    return _PAGE.format(body=f"<p><b>{html.escape(title)}</b></p><p>{html.escape(text)}</p>")
