"""Work leases: at most one active write lease per mutable scope.

A lease binds a scope (for example a branch or a project folder) to one
holder (device + session + workkey) until it expires. Every grant of a scope
bumps a monotonically increasing fencing token; a write must present the
current token, so a holder whose lease was taken over after expiry cannot
write any more, even if it is still running.

SQLite with an immediate transaction makes acquire/renew/release atomic across
processes on one device. Time is injected so tests are deterministic.
"""
import math
import sqlite3
import time
from dataclasses import dataclass


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


def _validate_ttl(ttl_s):
    if not isinstance(ttl_s, (int, float)) or isinstance(ttl_s, bool) or math.isnan(ttl_s) or math.isinf(ttl_s) or ttl_s <= 0:
        raise ValueError(f"ttl_s must be a positive finite number, got {ttl_s!r}")


def _validate_str(val, name):
    if not isinstance(val, str) or not val.strip():
        raise ValueError(f"{name} must be a non-empty string, got {val!r}")


class LeaseStore:
    def __init__(self, path, clock=time.time):
        self.clock = clock
        self.db = sqlite3.connect(path, isolation_level=None, timeout=10)
        self.db.execute("CREATE TABLE IF NOT EXISTS lease (scope TEXT PRIMARY KEY, holder TEXT, workkey TEXT,"
                        " token INTEGER NOT NULL, expires_at REAL NOT NULL)")

    def close(self):
        self.db.close()

    def _row(self, scope):
        row = self.db.execute("SELECT scope, holder, workkey, token, expires_at FROM lease WHERE scope=?",
                              (scope,)).fetchone()
        return Lease(*row) if row else None

    def current(self, scope):
        _validate_str(scope, "scope")
        lease = self._row(scope)
        if lease and lease.holder is not None and lease.expires_at > self.clock():
            return lease
        return None

    def acquire(self, scope, holder, workkey, ttl_s):
        """Take the scope if it is free or expired. Re-acquire by the same holder renews."""
        _validate_str(scope, "scope")
        _validate_str(holder, "holder")
        _validate_str(workkey, "workkey")
        _validate_ttl(ttl_s)

        now = self.clock()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self._row(scope)
            if row and row.holder is not None and row.expires_at > now and row.holder != holder:
                raise LeaseConflict(f"{scope} is held by {row.holder} for {row.workkey} until {row.expires_at}")
            if row and row.holder == holder and row.expires_at > now:
                token = row.token
            else:
                token = (row.token if row else 0) + 1
            self.db.execute("INSERT INTO lease(scope, holder, workkey, token, expires_at) VALUES(?,?,?,?,?)"
                            " ON CONFLICT(scope) DO UPDATE SET holder=excluded.holder, workkey=excluded.workkey,"
                            " token=excluded.token, expires_at=excluded.expires_at",
                            (scope, holder, workkey, token, now + ttl_s))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise
        return Lease(scope, holder, workkey, token, now + ttl_s)

    def renew(self, lease, ttl_s):
        """Heartbeat. Fails if the lease expired or the token moved on."""
        if not isinstance(lease, Lease):
            raise ValueError(f"lease must be a Lease instance, got {lease!r}")
        _validate_ttl(ttl_s)

        now = self.clock()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self._row(lease.scope)
            if not row or row.token != lease.token or row.holder != lease.holder or row.expires_at <= now:
                raise StaleLease(f"lease on {lease.scope} token {lease.token} is no longer current")
            self.db.execute("UPDATE lease SET expires_at=? WHERE scope=?", (now + ttl_s, lease.scope))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise
        return Lease(lease.scope, lease.holder, lease.workkey, lease.token, now + ttl_s)

    def check_write(self, scope, token):
        """Fence: raise unless token is the current, unexpired token for scope."""
        _validate_str(scope, "scope")
        if not isinstance(token, int) or isinstance(token, bool) or token <= 0:
            raise StaleLease(f"token must be a positive integer, got {token!r}")
        lease = self.current(scope)
        if lease is None or lease.token != token:
            raise StaleLease(f"write to {scope} with token {token} refused")
        return lease

    def release(self, lease):
        if not isinstance(lease, Lease):
            return
        self.db.execute("UPDATE lease SET holder=NULL, workkey=NULL, expires_at=0 WHERE scope=? AND token=?"
                        " AND holder=?", (lease.scope, lease.token, lease.holder))
