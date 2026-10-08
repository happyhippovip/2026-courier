"""Permission Broker core: ask once for the smallest useful authority, reuse it
until it expires or is revoked, never widen it silently.

A Request is covered only if one active Grant covers every dimension. A
dimension missing from the grant is not covered; a wider value than granted
is not covered. Nothing here talks to an OS or provider; it decides and
records, so it is pure and fully testable.
"""
from dataclasses import dataclass, field, replace
from typing import Optional

ACCESS_ORDER = {"read": 0, "write": 1, "execute": 2, "control": 3}
DATA_ORDER = {"public": 0, "project": 1, "personal": 2}

REQUESTED = "REQUESTED"
WAITING_FOR_USER_PERMISSION = "WAITING_FOR_USER_PERMISSION"
WAITING_FOR_OS_PERMISSION = "WAITING_FOR_OS_PERMISSION"
GRANTED = "GRANTED"
DENIED = "DENIED"
EXPIRED = "EXPIRED"
REVOKED = "REVOKED"

TRANSITIONS = {
    REQUESTED: {WAITING_FOR_USER_PERMISSION, WAITING_FOR_OS_PERMISSION, GRANTED, DENIED},
    WAITING_FOR_USER_PERMISSION: {GRANTED, DENIED},
    WAITING_FOR_OS_PERMISSION: {GRANTED, DENIED, WAITING_FOR_USER_PERMISSION},
    GRANTED: {EXPIRED, REVOKED},
    DENIED: set(), EXPIRED: set(), REVOKED: set(),
}


class TransitionError(Exception):
    pass


@dataclass(frozen=True)
class Grant:
    grant_id: str
    project: str
    capability: str
    resources: frozenset          # exact resource values covered, e.g. {"api.github.com:443"}
    host: str
    provider_account: str         # "" when no provider is involved
    data_class: str
    access: str
    effect_class: str
    expires_at: Optional[float]      # None only for project-duration grants
    once: bool = False
    granted_by: str = "user"
    source_request: str = ""
    state: str = GRANTED
    uses: int = 0


@dataclass(frozen=True)
class Request:
    request_id: str
    project: str
    capability: str
    resources: frozenset
    host: str
    provider_account: str
    data_class: str
    access: str
    effect_class: str


def why_not_covered(grant, request, now):
    """None if grant covers request at time now, else the first uncovered dimension."""
    if grant.state != GRANTED:
        return f"grant is {grant.state}"
    if grant.expires_at is not None and now >= grant.expires_at:
        return "grant expired"
    if grant.once and grant.uses >= 1:
        return "one-time grant already used"
    for dim in ("project", "capability", "host", "provider_account", "effect_class"):
        if getattr(grant, dim) != getattr(request, dim):
            return f"{dim} differs ({getattr(request, dim)!r} not granted)"
    if not request.resources or not request.resources <= grant.resources:
        return f"resources {sorted(request.resources - grant.resources) or '[]'} not granted"
    if request.access not in ACCESS_ORDER:
        return f"access {request.access!r} is not a known access level"
    if grant.access not in ACCESS_ORDER:
        return f"grant access {grant.access!r} is not a known access level"
    if ACCESS_ORDER[request.access] > ACCESS_ORDER[grant.access]:
        return f"access {request.access} exceeds {grant.access}"
    if request.data_class not in DATA_ORDER:
        return f"data class {request.data_class!r} is not a known data class"
    if grant.data_class not in DATA_ORDER:
        return f"grant data class {grant.data_class!r} is not a known data class"
    if DATA_ORDER[request.data_class] > DATA_ORDER[grant.data_class]:
        return f"data class {request.data_class} exceeds {grant.data_class}"
    return None


class Broker:
    """In-memory broker with an append-only event log (the ledger adapter writes it out)."""

    def __init__(self, clock):
        self.clock = clock
        self.grants = {}
        self.requests = {}
        self.events = []

    def _event(self, kind, **data):
        self.events.append({"type": kind, "at": self.clock(), **data})

    def authorize(self, request):
        """Use an existing grant or open a request. Returns (grant_or_None, state, reason)."""
        now = self.clock()
        reasons = []
        for grant in self.grants.values():
            reason = why_not_covered(grant, request, now)
            if reason is None:
                used = replace(grant, uses=grant.uses + 1)
                self.grants[grant.grant_id] = used
                self._event("GRANT_USED", grant_id=grant.grant_id, request_id=request.request_id)
                return used, GRANTED, None
            reasons.append(reason)
        self.requests[request.request_id] = REQUESTED
        self._event("GRANT_REQUESTED", request_id=request.request_id, capability=request.capability,
                    resources=sorted(request.resources), access=request.access)
        return None, REQUESTED, "; ".join(reasons) or "no grant"

    def move(self, request_id, new_state):
        old = self.requests[request_id]
        if new_state not in TRANSITIONS[old]:
            raise TransitionError(f"{old} -> {new_state} is not allowed")
        self.requests[request_id] = new_state
        self._event("REQUEST_" + new_state, request_id=request_id)

    def grant(self, request, grant_id, expires_at, once=False, granted_by="user"):
        """Record the user's decision: exactly the requested scope, never wider."""
        if self.requests.get(request.request_id) not in (REQUESTED, WAITING_FOR_USER_PERMISSION,
                                                         WAITING_FOR_OS_PERMISSION):
            raise TransitionError(f"request {request.request_id} is not awaiting a decision")
        grant = Grant(grant_id=grant_id, project=request.project, capability=request.capability,
                      resources=frozenset(request.resources), host=request.host,
                      provider_account=request.provider_account, data_class=request.data_class,
                      access=request.access, effect_class=request.effect_class, expires_at=expires_at,
                      once=once, granted_by=granted_by, source_request=request.request_id)
        self.grants[grant_id] = grant
        self.requests[request.request_id] = GRANTED
        self._event("GRANT_GIVEN", grant_id=grant_id, request_id=request.request_id, granted_by=granted_by)
        return grant

    def deny(self, request_id):
        self.move(request_id, DENIED)

    def revoke(self, grant_id):
        grant = self.grants[grant_id]
        if REVOKED not in TRANSITIONS[grant.state]:
            raise TransitionError(f"{grant.state} -> {REVOKED} is not allowed")
        self.grants[grant_id] = replace(grant, state=REVOKED)
        self._event("GRANT_REVOKED", grant_id=grant_id)

    def expire_due(self):
        now = self.clock()
        for gid, grant in list(self.grants.items()):
            if grant.state == GRANTED and grant.expires_at is not None and now >= grant.expires_at:
                self.grants[gid] = replace(grant, state=EXPIRED)
                self._event("GRANT_EXPIRED", grant_id=gid)
