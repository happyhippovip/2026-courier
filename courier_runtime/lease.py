"""Work leases: at most one active write lease per mutable scope.

A lease binds a scope (for example a branch or a project folder) to one
holder (device + session + workkey) until it expires. Every grant of a scope
bumps a monotonically increasing fencing token; a write must present the
current token, so a holder whose lease was taken over after expiry cannot
write any more, even if it is still running.

SQLite with an immediate transaction makes acquire/renew/release atomic across
processes on one device. Time is injected so tests are deterministic.

Cross-host: LeaseConflict is local to this one SQLite file. Two hosts that
each open their own file (Mac and Windows) are not fenced. assess_cross_host
reports that gap as BLOCKED / NEED_SCOPE. It is not a global lock.
"""
import os
import sqlite3
import time
from dataclasses import dataclass


class LeaseConflict(Exception):
    """The scope is held by someone else inside this store."""


class StaleLease(Exception):
    """The caller's lease or fencing token is no longer current."""


@dataclass(frozen=True)
class Lease:
    scope: str
    holder: str
    workkey: str
    token: int
    expires_at: float
    principal: str = ""
    host: str = ""
    owner: str = ""
    revoked: int = 0


CROSS_HOST_PROOF = "BLOCKED"
CROSS_HOST_EXTRA_SCOPE = (
    "LeaseConflict is enforced only inside one SQLite file. Two hosts with two "
    "local lease databases can both acquire the same scope. Minimal extra scope, "
    "outside these four paths and requiring its own Dennis-GO: one shared "
    "compare-and-swap lease authority that both hosts open. A second local SQLite "
    "file is not that authority. A GitHub status comment is not that authority."
)
_NOT_A_GLOBAL_LOCK = (
    "This is not a global lock. LeaseConflict fences only one SQLite file; a second "
    "host with its own file can also hold the same scope."
)


@dataclass(frozen=True)
class CrossHostAssessment:
    status: str
    code: str
    same_store: bool
    local_conflict: bool
    concurrent_holders: bool
    guarantees: str
    does_not_guarantee: str
    minimal_extra_scope: str
    detail: str


class LeaseStore:
    def __init__(self, path, clock=time.time):
        self.path = path
        self.clock = clock
        self.db = sqlite3.connect(path, isolation_level=None, timeout=10)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS lease ("
            "scope TEXT PRIMARY KEY, holder TEXT, workkey TEXT, token INTEGER NOT NULL, "
            "expires_at REAL NOT NULL, principal TEXT NOT NULL DEFAULT '', "
            "host TEXT NOT NULL DEFAULT '', owner TEXT NOT NULL DEFAULT '', "
            "revoked INTEGER NOT NULL DEFAULT 0)"
        )
        cols = {row[1] for row in self.db.execute("PRAGMA table_info(lease)")}
        for name, decl in (
            ("principal", "TEXT NOT NULL DEFAULT ''"),
            ("host", "TEXT NOT NULL DEFAULT ''"),
            ("owner", "TEXT NOT NULL DEFAULT ''"),
            ("revoked", "INTEGER NOT NULL DEFAULT 0"),
        ):
            if name not in cols:
                self.db.execute(f"ALTER TABLE lease ADD COLUMN {name} {decl}")

    def close(self):
        self.db.close()

    def _row(self, scope):
        row = self.db.execute(
            "SELECT scope, holder, workkey, token, expires_at, principal, host, owner, revoked "
            "FROM lease WHERE scope=?",
            (scope,),
        ).fetchone()
        return Lease(*row) if row else None

    def _active(self, row, now):
        return row is not None and row.holder is not None and not row.revoked and row.expires_at > now

    def current(self, scope):
        lease = self._row(scope)
        if self._active(lease, self.clock()):
            return lease
        return None

    def acquire(self, scope, holder, workkey, ttl_s, principal="", host="", owner=""):
        """Take the scope if it is free or expired. Re-acquire by the same holder renews.

        A live lease stays bound to its workkey. A different workkey, host, or
        principal on that live row is a conflict inside this store only.
        """
        now = self.clock()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self._row(scope)
            if self._active(row, now) and row.holder != holder:
                raise LeaseConflict(f"{scope} is held by {row.holder} for {row.workkey} until {row.expires_at}")
            if self._active(row, now) and row.holder == holder:
                if row.workkey != workkey:
                    raise LeaseConflict(f"workkey fence: {scope} is bound to {row.workkey}")
                if host and row.host and host != row.host:
                    raise LeaseConflict(f"host fence: {scope} is bound to {row.host}")
                if principal and row.principal and principal != row.principal:
                    raise LeaseConflict(f"principal fence: {scope} is bound to {row.principal}")
                token = row.token
                principal = principal or row.principal
                host = host or row.host
                owner = owner or row.owner
            else:
                token = (row.token if row else 0) + 1
            self.db.execute(
                "INSERT INTO lease(scope, holder, workkey, token, expires_at, principal, host, owner, revoked) "
                "VALUES(?,?,?,?,?,?,?,?,0) "
                "ON CONFLICT(scope) DO UPDATE SET holder=excluded.holder, workkey=excluded.workkey, "
                "token=excluded.token, expires_at=excluded.expires_at, principal=excluded.principal, "
                "host=excluded.host, owner=excluded.owner, revoked=0",
                (scope, holder, workkey, token, now + ttl_s, principal, host, owner),
            )
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise
        return Lease(scope, holder, workkey, token, now + ttl_s, principal, host, owner, 0)

    def renew(self, lease, ttl_s, approver=None):
        """Heartbeat. Fails if the lease expired, was revoked, or the token moved on.

        A row with an empty principal keeps the pre-existing same-holder heartbeat.
        A principal-bound row refuses a missing approver or an approver who is the
        holder. That is not the full three-role check; Gate.extend does that.
        """
        now = self.clock()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self._row(lease.scope)
            if (not row or row.revoked or row.token != lease.token or row.holder != lease.holder
                    or row.expires_at <= now):
                raise StaleLease(f"lease on {lease.scope} token {lease.token} is no longer current")
            if row.principal and (not approver or approver in {row.principal, row.holder}):
                raise LeaseConflict("writer self-extend rejected")
            self.db.execute("UPDATE lease SET expires_at=? WHERE scope=?", (now + ttl_s, lease.scope))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise
        return Lease(lease.scope, lease.holder, lease.workkey, lease.token, now + ttl_s,
                     lease.principal, lease.host, lease.owner, 0)

    def check_write(self, scope, token, host=None, workkey=None, principal=None):
        """Fence: raise unless token is the current, unexpired token for scope.

        Host, workkey, and principal are checked when the caller presents them
        and the stored lease bound that dimension.
        """
        lease = self.current(scope)
        if lease is None or lease.token != token:
            raise StaleLease(f"write to {scope} with token {token} refused")
        if host is not None and lease.host and host != lease.host:
            raise StaleLease(f"host fence: {host} != {lease.host}")
        if workkey is not None and workkey != lease.workkey:
            raise StaleLease(f"workkey fence: {workkey} != {lease.workkey}")
        if principal is not None and lease.principal and principal != lease.principal:
            raise StaleLease(f"principal fence: {principal} != {lease.principal}")
        return lease

    def access_mode(self, scope, token):
        """Expired, revoked, or stale tokens may checkpoint read-only. They may not write."""
        try:
            self.check_write(scope, token)
        except StaleLease:
            return "CHECKPOINT_RO"
        return "WRITE"

    def revoke(self, scope, token, by_principal=None):
        """Immediate fail-closed. A matching token is enough; the row stops being current."""
        del by_principal
        now = self.clock()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self._row(scope)
            if not row or row.token != token:
                raise StaleLease(f"revoke of {scope} token {token} refused")
            self.db.execute(
                "UPDATE lease SET revoked=1, expires_at=? WHERE scope=? AND token=?",
                (now, scope, token),
            )
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise
        return self._row(scope)

    def release(self, lease):
        self.db.execute("UPDATE lease SET holder=NULL, workkey=NULL, expires_at=0 WHERE scope=? AND token=?"
                        " AND holder=?", (lease.scope, lease.token, lease.holder))


def assess_cross_host(store_a, store_b, scope, holder_a, holder_b, workkey, ttl_s,
                      principal_a="", principal_b="", host_a="", host_b=""):
    """Show what one SQLite file fences, and what two files do not.

    Same file: the second acquire raises LeaseConflict. That result is local
    only. Different files: both acquires succeed. That result is BLOCKED /
    NEED_SCOPE, never a cross-host pass.
    """
    same = os.path.abspath(store_a.path) == os.path.abspath(store_b.path)
    store_a.acquire(
        scope, holder_a, workkey, ttl_s, principal=principal_a, host=host_a,
    )
    conflict = False
    try:
        store_b.acquire(
            scope, holder_b, workkey, ttl_s, principal=principal_b, host=host_b,
        )
    except LeaseConflict:
        conflict = True
    held_a = store_a.current(scope)
    held_b = store_b.current(scope)
    concurrent = (
        not conflict and held_a is not None and held_b is not None and held_a.holder != held_b.holder
    )
    if same and conflict and not concurrent:
        status, code = "LOCAL_ONLY", "LEASE_CONFLICT"
        guarantees = "At most one active holder inside this one SQLite file."
        detail = f"{scope} stayed with {held_a.holder if held_a else holder_a}; the other acquire conflicted."
    else:
        status, code = "BLOCKED", "NEED_SCOPE"
        guarantees = "No cross-host guarantee; separate stores can both hold the scope."
        detail = f"{scope} is held in more than one store." if concurrent else "cross-host fence is not proven"
    return CrossHostAssessment(
        status=status, code=code, same_store=same, local_conflict=conflict, concurrent_holders=concurrent,
        guarantees=guarantees, does_not_guarantee=_NOT_A_GLOBAL_LOCK,
        minimal_extra_scope=CROSS_HOST_EXTRA_SCOPE, detail=detail,
    )
