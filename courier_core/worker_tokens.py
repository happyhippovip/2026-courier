"""Per-worker scoped tokens for the V1 worker pool.

A token authorizes one worker for a fixed set of scopes and a bounded
lifetime. Only salted hashes are stored: the plaintext token exists only
at mint time (returned once to the caller) and inside `verify`'s argument.
It is never written into a record, never logged, and never rendered.

- mint:    one worker_id, a tuple of scope strings, a TTL in seconds.
- verify:  constant-time hash comparison; fails closed on unknown,
           revoked, expired, or out-of-scope tokens.
- revoke:  by token_id (the public handle; the token itself is not needed).
- purge:   drops expired records; returns how many were dropped.

The store is in-memory only. There is no file, network, or logging call
in this module, so a token value has nowhere to leak to.
"""

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass, field

TOKEN_PREFIX = "cwt_"
_TOKEN_BYTES = 32
_SALT_BYTES = 16
_HASH = hashlib.sha256


@dataclass(frozen=True)
class TokenRecord:
    token_id: str
    worker_id: str
    scopes: tuple
    created_at: float
    expires_at: float
    salt: str
    token_hash: str
    revoked: bool = False


def _hash_token(token: str, salt: str) -> str:
    return _HASH((salt + token).encode("utf-8")).hexdigest()


class TokenStore:
    """Mint, verify, and revoke scoped worker tokens."""

    def __init__(self):
        self._records = {}

    def mint(self, worker_id, scopes=(), ttl_seconds=3600, *, now=None):
        """Create a token. Returns (token, record); the token is shown once."""
        if not worker_id:
            raise ValueError("worker_id is required")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        at = time.time() if now is None else now
        token = TOKEN_PREFIX + secrets.token_urlsafe(_TOKEN_BYTES)
        salt = secrets.token_hex(_SALT_BYTES)
        record = TokenRecord(
            token_id=secrets.token_hex(8),
            worker_id=worker_id,
            scopes=tuple(scopes),
            created_at=at,
            expires_at=at + ttl_seconds,
            salt=salt,
            token_hash=_hash_token(token, salt),
        )
        self._records[record.token_id] = record
        return token, record

    def verify(self, token, required_scope=None, *, now=None):
        """Return the live record for a valid token, else None (fail closed)."""
        if not token or not isinstance(token, str):
            return None
        at = time.time() if now is None else now
        for record in self._records.values():
            if record.revoked or record.expires_at <= at:
                continue
            if not hmac.compare_digest(record.token_hash, _hash_token(token, record.salt)):
                continue
            if required_scope is not None and required_scope not in record.scopes:
                return None
            return record
        return None

    def revoke(self, token_id):
        """Revoke by public handle. Returns True when a record was revoked."""
        record = self._records.get(token_id)
        if record is None or record.revoked:
            return False
        self._records[token_id] = TokenRecord(
            token_id=record.token_id,
            worker_id=record.worker_id,
            scopes=record.scopes,
            created_at=record.created_at,
            expires_at=record.expires_at,
            salt=record.salt,
            token_hash=record.token_hash,
            revoked=True,
        )
        return True

    def get(self, token_id):
        """Read a record by handle (hashes only; no token value exists here)."""
        return self._records.get(token_id)

    def purge_expired(self, *, now=None):
        """Drop expired records. Returns the number dropped."""
        at = time.time() if now is None else now
        expired = [tid for tid, r in self._records.items() if r.expires_at <= at]
        for tid in expired:
            del self._records[tid]
        return len(expired)

    def __len__(self):
        return len(self._records)
