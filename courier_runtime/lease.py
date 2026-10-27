"""Work leases: at most one active write lease per mutable scope.

A lease binds a scope (for example a branch or a project folder) to one
holder (device + session + workkey) until it expires. Every grant of a scope
bumps a monotonically increasing fencing token; a write must present the
current token, so a holder whose lease was taken over after expiry cannot
write any more, even if it is still running.

SQLite with an immediate transaction makes acquire/renew/release atomic across
processes on one device. Time is injected so tests are deterministic.
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


class LeaseConflict(Exception):
    """The scope is held by someone else."""


class StaleLease(Exception):
    """The caller's lease or fencing token is no longer current."""


@dataclass(frozen=True)
class Lease:
    scope: str
    holder: str
    workkey: str
    token: int
    expires_at: float


def canonicalize_scope(scope: str) -> str:
    """Canonicalize scope: normalize separators, strip trailing and redundant slashes."""
    s = str(scope).strip().replace("\\", "/")
    if "://" in s:
        scheme, rest = s.split("://", 1)
        parts = [p for p in rest.split("/") if p and p != "."]
        return f"{scheme}://{'/'.join(parts)}"
    parts = [p for p in s.split("/") if p and p != "."]
    return "/".join(parts)


def scopes_overlap(scope_a: str, scope_b: str) -> bool:
    """True if scope_a and scope_b refer to the same scope or one is a sub-scope of another."""
    ca = canonicalize_scope(scope_a)
    cb = canonicalize_scope(scope_b)
    if ca == cb:
        return True
    if ca.startswith(cb + "/"):
        return True
    if cb.startswith(ca + "/"):
        return True
    return False


def is_strict_ancestor(ancestor: str, descendant: str) -> bool:
    """True when ancestor strictly encloses descendant. A child is not an ancestor of its parent."""
    parent = canonicalize_scope(ancestor)
    child = canonicalize_scope(descendant)
    return child.startswith(parent + "/")


def token_ok(token) -> bool:
    """A fencing token is a positive int. Bool is not a token."""
    return isinstance(token, int) and not isinstance(token, bool) and token >= 1


def holder_ok(holder) -> bool:
    """A holder is a non-empty string. Bool is not a holder."""
    return isinstance(holder, str) and bool(holder) and "\x00" not in holder


def format_session_holder(device: str, pid: int, create_time: float, session_id: str) -> str:
    """Format structured session holder binding."""
    return f"{device}:{pid}:{create_time:.4f}:{session_id}"


def parse_session_holder(holder: str) -> dict | None:
    """Parse structured session holder binding if present."""
    parts = str(holder).split(":")
    if len(parts) >= 4:
        try:
            return {"device": parts[0], "pid": int(parts[1]), "create_time": float(parts[2]), "session_id": parts[3]}
        except ValueError:
            return None
    return None


def _refuse_symlink(path) -> None:
    """Refuse a lease database path, or a parent directory, that is a symlink."""
    candidate = Path(path)
    if candidate.is_symlink() or candidate.parent.is_symlink():
        raise OSError(f"{path}: refusing to follow a symlink")


class LeaseStore:
    def __init__(self, path, clock=time.time):
        self.clock = clock
        _refuse_symlink(path)
        self.db = sqlite3.connect(path, isolation_level=None, timeout=10)
        self.db.execute("CREATE TABLE IF NOT EXISTS lease (scope TEXT PRIMARY KEY, holder TEXT, workkey TEXT,"
                        " token INTEGER NOT NULL, expires_at REAL NOT NULL)")

    def close(self):
        self.db.close()

    def _row(self, scope):
        c_scope = canonicalize_scope(scope)
        row = self.db.execute("SELECT scope, holder, workkey, token, expires_at FROM lease WHERE scope=?",
                              (c_scope,)).fetchone()
        return Lease(*row) if row else None

    def current(self, scope):
        c_scope = canonicalize_scope(scope)
        lease = self._row(c_scope)
        if lease and lease.holder is not None and lease.expires_at > self.clock():
            return lease
        return None

    def acquire(self, scope, holder, workkey, ttl_s):
        """Take the scope if it is free or expired. Re-acquire by the same holder for the
        same workkey renews; a live lease for a different workkey conflicts even when the
        holder (device) is the same, so two workkeys never share one fencing token.
        Hierarchical scope overlap with another live lease raises LeaseConflict."""
        # O7-04: a writer lease needs a real owner id. None/"" would be stored as an
        # anonymous lease that every other anonymous caller shares (single writer broken).
        if not isinstance(holder, str) or not holder.strip():
            raise ValueError("lease holder must be a non-empty string")
        c_scope = canonicalize_scope(scope)
        now = self.clock()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            # Check all live leases for scope overlap
            rows = self.db.execute(
                "SELECT scope, holder, workkey, token, expires_at FROM lease WHERE expires_at > ? AND holder IS NOT NULL",
                (now,),
            ).fetchall()
            for r in rows:
                live_lease = Lease(*r)
                if scopes_overlap(live_lease.scope, c_scope):
                    if live_lease.holder != holder or live_lease.workkey != workkey:
                        raise LeaseConflict(
                            f"{c_scope} conflicts/overlaps with live lease on {live_lease.scope} held by {live_lease.holder} for {live_lease.workkey} until {live_lease.expires_at}"
                        )
            row = self._row(c_scope)
            live = row is not None and row.holder is not None and row.expires_at > now
            if live and (row.holder != holder or row.workkey != workkey):
                raise LeaseConflict(f"{c_scope} is held by {row.holder} for {row.workkey} until {row.expires_at}")
            if live:
                token = row.token
            else:
                # One monotonic sequence for every scope, so scope A's token
                # can never equal scope B's token.
                max_token = self.db.execute("SELECT COALESCE(MAX(token), 0) FROM lease").fetchone()[0]
                previous = row.token if row else 0
                if isinstance(max_token, bool) or not isinstance(max_token, int):
                    max_token = 0
                if isinstance(previous, bool) or not isinstance(previous, int):
                    previous = 0
                token = max(max_token, previous) + 1
            self.db.execute("INSERT INTO lease(scope, holder, workkey, token, expires_at) VALUES(?,?,?,?,?)"
                            " ON CONFLICT(scope) DO UPDATE SET holder=excluded.holder, workkey=excluded.workkey,"
                            " token=excluded.token, expires_at=excluded.expires_at",
                            (c_scope, holder, workkey, token, now + ttl_s))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise
        return Lease(c_scope, holder, workkey, token, now + ttl_s)

    def renew(self, lease, ttl_s):
        """Heartbeat. Fails if the lease expired or the token moved on."""
        c_scope = canonicalize_scope(lease.scope)
        now = self.clock()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self._row(c_scope)
            if not row or row.token != lease.token or row.holder != lease.holder or row.expires_at <= now:
                raise StaleLease(f"lease on {c_scope} token {lease.token} is no longer current")
            self.db.execute("UPDATE lease SET expires_at=? WHERE scope=?", (now + ttl_s, c_scope))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise
        return Lease(c_scope, lease.holder, lease.workkey, lease.token, now + ttl_s)

    def check_write(self, scope, token, holder=None, workkey=None):
        """Fence: token and, when presented, holder/workkey must match.

        The live exact scope matches, or a strict ancestor (enclosing parent)
        matches. A child lease never authorizes a write to its parent. Bool is
        not a token or a holder. When holder/workkey are omitted, only token and scope
        are checked so existing callers keep their token fence; production
        writers pass the holder and workkey.
        """
        c_scope = canonicalize_scope(scope)
        if not token_ok(token):
            raise StaleLease(f"write to {c_scope} refused: token is not a fencing token")
        if holder is not None and not holder_ok(holder):
            raise StaleLease(f"write to {c_scope} refused: holder is not a lease holder")

        def _matches(live: Lease) -> bool:
            if not token_ok(live.token) or live.token != token:
                return False
            if holder is not None and live.holder != holder:
                return False
            if workkey is not None and live.workkey != workkey:
                return False
            return True

        lease = self.current(c_scope)
        if lease is not None:
            if not _matches(lease):
                raise StaleLease(
                    f"write to {c_scope} with token {token} refused (current token is {lease.token})"
                )
            return lease
        rows = self.db.execute(
            "SELECT scope, holder, workkey, token, expires_at FROM lease WHERE expires_at > ? AND holder IS NOT NULL",
            (self.clock(),),
        ).fetchall()
        for r in rows:
            live = Lease(*r)
            # Only an enclosing parent may cover a child path. Overlap is not enough:
            # the child scope must not authorize the parent.
            if is_strict_ancestor(live.scope, c_scope) and _matches(live):
                return live
        raise StaleLease(f"write to {c_scope} with token {token} refused")

    def release(self, lease):
        c_scope = canonicalize_scope(lease.scope)
        self.db.execute("UPDATE lease SET holder=NULL, workkey=NULL, expires_at=0 WHERE scope=? AND token=?"
                        " AND holder=?", (c_scope, lease.token, lease.holder))


class FencedFileWriter:
    """Ensures that before writing to any path, the lease token and holder are verified."""
    def __init__(self, lease_store: LeaseStore, scope: str, token: int, holder: str | None = None, workkey: str | None = None):
        self.store = lease_store
        self.scope = canonicalize_scope(scope)
        self.token = token
        self.holder = holder
        self.workkey = workkey

    def check(self):
        return self.store.check_write(self.scope, self.token, holder=self.holder, workkey=self.workkey)


    def open(self, path, mode="w", *args, **kwargs):
        if any(m in mode for m in ("w", "a", "+", "x")):
            self.check()
            candidate = Path(path)
            if candidate.is_symlink() or candidate.parent.is_symlink():
                raise OSError(f"{path}: refusing to follow a symlink")
        return open(path, mode, *args, **kwargs)

