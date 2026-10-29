"""Permission Broker core: ask once for the smallest useful authority, reuse it
until it expires or is revoked, never widen it silently.

A Request is covered only if one active Grant covers every dimension. A
dimension missing from the grant is not covered; a wider value than granted
is not covered. Nothing here talks to an OS or provider; it decides and
records, so it is pure and fully testable.

Phase A adds principal binding, a provider-neutral capability registry, a
versioned workkey package, and fail-closed activation checks. It does not
activate policy, verify cryptographic signatures, or start agents.
AUTH_PROOF_STATUS stays PARTIAL until a verifier outside this file exists.
"""
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass, field, replace
from typing import Optional

from courier_runtime.lease import LeaseConflict, StaleLease

ACCESS_ORDER = {"read": 0, "write": 1, "execute": 2, "control": 3}
DATA_ORDER = {"public": 0, "project": 1, "personal": 2}

REQUESTED = "REQUESTED"
WAITING_FOR_USER_PERMISSION = "WAITING_FOR_USER_PERMISSION"
WAITING_FOR_OS_PERMISSION = "WAITING_FOR_OS_PERMISSION"
GRANTED = "GRANTED"
DENIED = "DENIED"
EXPIRED = "EXPIRED"
REVOKED = "REVOKED"

HOLD = "HOLD"
ACTIVE = "ACTIVE"
REJECT = "REJECT"
PENDING = "PENDING"
NOT_PROVEN = "NOT_PROVEN"
RO = "RO"
CONTINUITY_OK = "CONTINUITY_OK"
CHECKED = "CHECKED"
RECORDED = "RECORDED"
FENCED = "FENCED"
READY = "READY"
CLAIMED = "CLAIMED"
CANDIDATE = "CANDIDATE"

KNOWN_STOP = frozenset({"CLEAR", "HOLD", "STOP"})
CAPABILITIES = frozenset({
    "COORDINATE",
    "ISSUE_PREAPPROVED_LEASE",
    "VERIFY_LEASE",
    "WRITE_SCOPED_CODE",
    "REVIEW_INDEPENDENTLY",
    "RESUME_WORKKEY",
})
SIDE_EFFECTS = frozenset({"push", "merge", "deploy", "prod", "payment", "secrets"})
HOLD_PUSH = True
PRODUCTION_LOCKED = True

AUTH_PROOF_STATUS = "PARTIAL"
AUTH_PROOF_EXTRA_SCOPE = (
    "grants.py records an external verifier decision and refuses when that verifier "
    "is missing or does not accept. It does not check signatures, provider tokens, or "
    "account binding. Minimal extra scope, requiring its own Dennis-GO because it is "
    "outside the four Phase A paths: a verifier module that checks a real credential "
    "and returns AuthAttestation. A proof blob stored next to a grant is not accepted "
    "on its own."
)

REQUIRED_WORKKEY_FIELDS = (
    "workkey_id", "goal", "expected_effect", "priority", "owner_role", "current_writer",
    "reviewer", "repo", "base_sha", "head_sha", "host", "worktree", "file_scope",
    "lease_id", "lease_expiry", "fence", "human_grant_ref", "stop_and_spend_gates",
    "dependencies", "verified_tests", "known_blocker", "safe_next_action",
    "last_checkpoint_sha", "resume_instruction", "state_version", "source_refs",
)
NONEMPTY_WORKKEY_FIELDS = (
    "workkey_id", "goal", "expected_effect", "priority", "owner_role", "current_writer",
    "reviewer", "repo", "base_sha", "head_sha", "host", "worktree", "lease_id",
    "human_grant_ref", "safe_next_action", "last_checkpoint_sha", "resume_instruction",
)
WORKKEY_STATES = frozenset({
    "CANDIDATE", "READY", "CLAIMED", "IN_PROGRESS", "VERIFYING", "VERIFIED", "CLOSED",
    "BLOCKED", "HOLD",
})
WORKKEY_TRANSITIONS = {
    "CANDIDATE": {"READY", "BLOCKED", "HOLD"},
    "READY": {"CLAIMED", "BLOCKED", "HOLD"},
    "CLAIMED": {"IN_PROGRESS", "BLOCKED", "HOLD"},
    "IN_PROGRESS": {"VERIFYING", "BLOCKED", "HOLD"},
    "VERIFYING": {"VERIFIED", "BLOCKED", "HOLD"},
    "VERIFIED": {"CLOSED"},
    "CLOSED": set(),
    "BLOCKED": set(),
    "HOLD": set(),
}
FORBIDDEN_STATUS_PAIRS = frozenset({
    ("DELEGATED", "DONE"),
    ("LOCAL_PASS", "CI_PASS"),
    ("LEASE_ACTIVE", "AGENT_RUNNING"),
})

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
    owner_principal: str = ""
    bound_principal: str = ""
    scope_key: str = ""
    content_hash: str = ""


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
    owner_principal: str = ""
    bound_principal: str = ""
    scope_key: str = ""


@dataclass(frozen=True)
class AuthAttestation:
    """External verifier result. This module does not check the proof bytes."""

    principal_id: str
    accepted: bool
    verifier_id: str
    reason: str


@dataclass(frozen=True)
class PrincipalRecord:
    principal_id: str
    capabilities: frozenset
    host: str = ""
    auth_proven: bool = False
    spend_limit: Optional[float] = None
    cost: float = 0
    file_scopes: frozenset = frozenset()
    safety_ok: bool = True
    permitted: bool = True


@dataclass(frozen=True)
class WorkkeyPackage:
    workkey_id: str
    goal: str
    expected_effect: str
    priority: str
    owner_role: str
    current_writer: str
    reviewer: str
    repo: str
    base_sha: str
    head_sha: str
    host: str
    worktree: str
    file_scope: tuple
    lease_id: str
    lease_expiry: float
    fence: int
    human_grant_ref: str
    stop_and_spend_gates: dict
    dependencies: tuple
    verified_tests: dict
    known_blocker: str
    safe_next_action: str
    last_checkpoint_sha: str
    resume_instruction: str
    state_version: int
    source_refs: tuple
    state: str = CANDIDATE


@dataclass(frozen=True)
class ResumeView:
    """Everything needed to continue. Built only from a workkey package."""

    workkey_id: str
    goal: str
    expected_effect: str
    resume_instruction: str
    safe_next_action: str
    last_checkpoint_sha: str
    base_sha: str
    head_sha: str
    state_version: int
    state: str
    file_scope: tuple
    package_sha: str


@dataclass
class Decision:
    status: str
    reason: str
    evidence: dict = field(default_factory=dict)


def grant_content_hash(grant):
    """Public integrity hash of the authority scope. Not an authentication proof.

    Broker.grant also stores an HMAC seal under a process-local key. A caller
    who recomputes this hash cannot mint a sealed grant. AUTH_PROOF_STATUS
    stays PARTIAL: the seal is not a signature and not a provider credential.
    """
    body = {
        "grant_id": grant.grant_id,
        "project": grant.project,
        "capability": grant.capability,
        "resources": sorted(grant.resources),
        "host": grant.host,
        "provider_account": grant.provider_account,
        "data_class": grant.data_class,
        "access": grant.access,
        "effect_class": grant.effect_class,
        "expires_at": grant.expires_at,
        "once": grant.once,
        "granted_by": grant.granted_by,
        "source_request": grant.source_request,
        "owner_principal": grant.owner_principal,
        "bound_principal": grant.bound_principal,
        "scope_key": grant.scope_key,
    }
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def why_not_covered(grant, request, now):
    """None if grant covers request at time now, else the first uncovered dimension."""
    if grant.state != GRANTED:
        return f"grant is {grant.state}"
    if grant.expires_at is not None and now >= grant.expires_at:
        return "grant expired"
    if grant.once and grant.uses >= 1:
        return "one-time grant already used"
    if not grant.content_hash or grant.content_hash != grant_content_hash(grant):
        return "grant hash mismatch"
    for dim in ("project", "capability", "host", "provider_account", "effect_class"):
        if getattr(grant, dim) != getattr(request, dim):
            return f"{dim} differs ({getattr(request, dim)!r} not granted)"
    if not request.resources or not request.resources <= grant.resources:
        return f"resources {sorted(request.resources - grant.resources) or '[]'} not granted"
    if ACCESS_ORDER[request.access] > ACCESS_ORDER[grant.access]:
        return f"access {request.access} exceeds {grant.access}"
    if request.data_class not in DATA_ORDER or grant.data_class not in DATA_ORDER:
        return f"data class {request.data_class!r} is not a known privacy class"
    if DATA_ORDER[request.data_class] > DATA_ORDER[grant.data_class]:
        return f"data class {request.data_class} exceeds {grant.data_class}"
    if (grant.bound_principal or request.bound_principal) and grant.bound_principal != request.bound_principal:
        return f"bound_principal differs ({request.bound_principal!r} not granted)"
    if (grant.scope_key or request.scope_key) and grant.scope_key != request.scope_key:
        return f"scope_key differs ({request.scope_key!r} not granted)"
    return None


def attest(principal_id, proof, verifier):
    """Fail closed unless an external verifier accepts. Proof bytes are not inspected."""
    if verifier is None:
        return AuthAttestation(principal_id, False, "", "no external auth verifier; AUTH-PROOF partial")
    try:
        result = verifier(principal_id, proof)
    except Exception as exc:
        return AuthAttestation(principal_id, False, "", f"verifier failed closed: {type(exc).__name__}")
    if not isinstance(result, AuthAttestation) or result.principal_id != principal_id or not result.accepted:
        verifier_id = result.verifier_id if isinstance(result, AuthAttestation) else ""
        reason = result.reason if isinstance(result, AuthAttestation) and result.reason else "not accepted"
        return AuthAttestation(principal_id, False, verifier_id, reason)
    return result


def known_spend(value):
    """0 is a known limit. Missing, boolean, or negative is unknown and fail-closed."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return value >= 0


def equate_status(left, right):
    """DELEGATED is not DONE, LOCAL_PASS is not CI_PASS, LEASE_ACTIVE is not AGENT_RUNNING."""
    pair = (left, right)
    if pair in FORBIDDEN_STATUS_PAIRS or (right, left) in FORBIDDEN_STATUS_PAIRS:
        return Decision(REJECT, f"{left} is not {right}")
    if left == right:
        return Decision("MATCH", "same status")
    return Decision(REJECT, "not equivalent")


def _as_tuple(value, label):
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise TypeError(label)
    return tuple(value)


def _as_int(value, label):
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(label)
    return value


def package_body(package):
    return {
        "workkey_id": package.workkey_id,
        "goal": package.goal,
        "expected_effect": package.expected_effect,
        "priority": package.priority,
        "owner_role": package.owner_role,
        "current_writer": package.current_writer,
        "reviewer": package.reviewer,
        "repo": package.repo,
        "base_sha": package.base_sha,
        "head_sha": package.head_sha,
        "host": package.host,
        "worktree": package.worktree,
        "file_scope": list(package.file_scope),
        "lease_id": package.lease_id,
        "lease_expiry": package.lease_expiry,
        "fence": package.fence,
        "human_grant_ref": package.human_grant_ref,
        "stop_and_spend_gates": package.stop_and_spend_gates,
        "dependencies": list(package.dependencies),
        "verified_tests": package.verified_tests,
        "known_blocker": package.known_blocker,
        "safe_next_action": package.safe_next_action,
        "last_checkpoint_sha": package.last_checkpoint_sha,
        "resume_instruction": package.resume_instruction,
        "state_version": package.state_version,
        "source_refs": list(package.source_refs),
        "state": package.state,
    }


def package_sha(package):
    raw = json.dumps(package_body(package), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parse_workkey(data):
    """Validate a versioned workkey package. Chat history is not an input."""
    if not isinstance(data, dict):
        return None, Decision(HOLD, "workkey package is not an object")
    missing = [name for name in REQUIRED_WORKKEY_FIELDS if name not in data or data[name] is None]
    if missing:
        return None, Decision(HOLD, f"workkey field missing: {missing[0]}")
    for name in NONEMPTY_WORKKEY_FIELDS:
        if not isinstance(data[name], str) or not data[name]:
            return None, Decision(HOLD, f"workkey field empty: {name}")
    try:
        file_scope = _as_tuple(data["file_scope"], "file_scope")
        dependencies = _as_tuple(data["dependencies"], "dependencies")
        source_refs = _as_tuple(data["source_refs"], "source_refs")
        fence = _as_int(data["fence"], "fence")
        state_version = _as_int(data["state_version"], "state_version")
        if isinstance(data["lease_expiry"], bool) or not isinstance(data["lease_expiry"], (int, float)):
            raise TypeError("lease_expiry")
    except TypeError as exc:
        return None, Decision(HOLD, f"workkey field invalid: {exc}")
    if not isinstance(data["stop_and_spend_gates"], dict):
        return None, Decision(HOLD, "workkey field invalid: stop_and_spend_gates")
    if not isinstance(data["verified_tests"], dict):
        return None, Decision(HOLD, "workkey field invalid: verified_tests")
    if any(not isinstance(item, str) or not item for item in file_scope):
        return None, Decision(HOLD, "workkey field invalid: file_scope")
    state = data.get("state", CANDIDATE)
    if state not in WORKKEY_STATES:
        return None, Decision(HOLD, "workkey state unknown")
    package = WorkkeyPackage(
        workkey_id=data["workkey_id"], goal=data["goal"], expected_effect=data["expected_effect"],
        priority=data["priority"], owner_role=data["owner_role"], current_writer=data["current_writer"],
        reviewer=data["reviewer"], repo=data["repo"], base_sha=data["base_sha"], head_sha=data["head_sha"],
        host=data["host"], worktree=data["worktree"], file_scope=file_scope, lease_id=data["lease_id"],
        lease_expiry=float(data["lease_expiry"]), fence=fence, human_grant_ref=data["human_grant_ref"],
        stop_and_spend_gates=dict(data["stop_and_spend_gates"]), dependencies=dependencies,
        verified_tests=dict(data["verified_tests"]), known_blocker=data["known_blocker"],
        safe_next_action=data["safe_next_action"], last_checkpoint_sha=data["last_checkpoint_sha"],
        resume_instruction=data["resume_instruction"], state_version=state_version,
        source_refs=source_refs, state=state,
    )
    return package, Decision(CANDIDATE, "workkey parsed", evidence={"package_sha": package_sha(package)})


def resume_from_package(package):
    """Continue from the package alone. There is no chat argument."""
    return ResumeView(
        workkey_id=package.workkey_id, goal=package.goal, expected_effect=package.expected_effect,
        resume_instruction=package.resume_instruction, safe_next_action=package.safe_next_action,
        last_checkpoint_sha=package.last_checkpoint_sha, base_sha=package.base_sha,
        head_sha=package.head_sha, state_version=package.state_version, state=package.state,
        file_scope=package.file_scope, package_sha=package_sha(package),
    )


class Registry:
    def __init__(self):
        self._rows = {}

    def add(self, record):
        unknown = set(record.capabilities) - CAPABILITIES
        if unknown:
            raise ValueError(f"unknown capabilities: {sorted(unknown)}")
        self._rows[record.principal_id] = record

    def get(self, principal_id):
        return self._rows.get(principal_id)

    def records(self):
        return list(self._rows.values())


class Broker:
    """In-memory broker with an append-only event log (the ledger adapter writes it out)."""

    def __init__(self, clock):
        self.clock = clock
        self.grants = {}
        self.requests = {}
        self.events = []
        self._seal_key = secrets.token_bytes(32)
        self._seals = {}

    def _seal(self, grant):
        return hmac.new(self._seal_key, grant.content_hash.encode("utf-8"), hashlib.sha256).hexdigest()

    def seal_matches(self, grant):
        """True only for a hash this broker sealed. Empty or recomputed hashes fail."""
        if not grant.content_hash or grant.content_hash != grant_content_hash(grant):
            return False
        expected = self._seals.get(grant.grant_id)
        if not expected:
            return False
        return hmac.compare_digest(expected, self._seal(grant))

    def _event(self, kind, **data):
        self.events.append({"type": kind, "at": self.clock(), **data})

    def authorize(self, request):
        """Use an existing grant or open a request. Returns (grant_or_None, state, reason)."""
        now = self.clock()
        reasons = []
        for grant in self.grants.values():
            reason = why_not_covered(grant, request, now)
            if reason is None and not self.seal_matches(grant):
                reason = "grant seal missing"
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

    def grant(self, request, grant_id, expires_at, once=False, granted_by="user",
              owner_principal="", bound_principal="", scope_key=""):
        """Record the user's decision: exactly the requested scope, never wider."""
        if self.requests.get(request.request_id) not in (REQUESTED, WAITING_FOR_USER_PERMISSION,
                                                         WAITING_FOR_OS_PERMISSION):
            raise TransitionError(f"request {request.request_id} is not awaiting a decision")
        owner_principal = owner_principal or request.owner_principal
        bound_principal = bound_principal or request.bound_principal
        scope_key = scope_key or request.scope_key
        if bound_principal and granted_by == bound_principal:
            raise TransitionError("bound principal cannot grant itself")
        grant = Grant(grant_id=grant_id, project=request.project, capability=request.capability,
                      resources=frozenset(request.resources), host=request.host,
                      provider_account=request.provider_account, data_class=request.data_class,
                      access=request.access, effect_class=request.effect_class, expires_at=expires_at,
                      once=once, granted_by=granted_by, source_request=request.request_id,
                      owner_principal=owner_principal, bound_principal=bound_principal, scope_key=scope_key)
        grant = replace(grant, content_hash=grant_content_hash(grant))
        self._seals[grant_id] = self._seal(grant)
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


class Gate:
    """Fail-closed checks on top of Broker and LeaseStore.

    ACTIVE is returned only for a lease activation whose issuer, verifier, and
    writer are distinct proven principals, with a covering grant, a known spend
    limit, and a known CLEAR stop. Missing proof never becomes ACTIVE.
    Policy activation is not implemented.
    """

    def __init__(self, broker, leases, clock, *, owner_principal, auth_verifier=None,
                 stop_status=None, project="courier"):
        self.broker = broker
        self.leases = leases
        self.leases.extend_guard = self._extend_guard
        self.clock = clock
        self.owner_principal = owner_principal
        self.auth_verifier = auth_verifier
        self._stop = stop_status
        self.project = project
        self.registry = Registry()
        self.workkeys = {}
        self.replacements = {}
        self.coordinator_reachable = True
        self.flow_checks = {}

    def set_stop(self, status):
        self._stop = status

    def set_coordinator_reachable(self, reachable):
        self.coordinator_reachable = bool(reachable)

    def probe_stop(self):
        status = self._stop
        if callable(status):
            try:
                status = status()
            except Exception:
                return None
        if status not in KNOWN_STOP:
            return None
        return status

    def register(self, principal_id, capabilities, *, proof=None, host="", spend_limit=None,
                 cost=0, file_scopes=(), safety_ok=True, permitted=True):
        if not principal_id or not isinstance(principal_id, str):
            raise ValueError("principal_id required")
        caps = frozenset(capabilities)
        unknown = caps - CAPABILITIES
        if unknown:
            raise ValueError(f"unknown capabilities: {sorted(unknown)}")
        attestation = attest(principal_id, proof, self.auth_verifier)
        self.registry.add(PrincipalRecord(
            principal_id=principal_id, capabilities=caps, host=host, auth_proven=attestation.accepted,
            spend_limit=spend_limit, cost=cost, file_scopes=frozenset(file_scopes),
            safety_ok=safety_ok, permitted=permitted,
        ))
        return attestation

    def _proven(self, principal_id):
        record = self.registry.get(principal_id)
        return record is not None and record.auth_proven

    def _has(self, principal_id, capability):
        record = self.registry.get(principal_id)
        return record is not None and record.auth_proven and capability in record.capabilities

    def _card(self, *, missing_gate, workkey_id):
        package = self.workkeys.get(workkey_id)
        return {
            "type": "DENNIS_RESUME_CARD",
            "owner_role": "HUMAN_OWNER",
            "owner_principal": self.owner_principal,
            "workkey_id": workkey_id,
            "missing_gate": missing_gate,
            "safe_next_action": package.safe_next_action if package else "owner supplies the missing gate",
            "package_sha": package_sha(package) if package else "",
            "does_not_grant": ACTIVE,
        }

    def activation_request(self, *, writer, scope, host, request_id):
        return Request(
            request_id=request_id, project=self.project, capability="WRITE_SCOPED_CODE",
            resources=frozenset({scope}), host=host, provider_account="", data_class="project",
            access="write", effect_class="idempotent", bound_principal=writer, scope_key=scope,
        )

    def authorize_role(self, principal_id, role):
        if role not in CAPABILITIES:
            return Decision(REJECT, "provider name or unknown role is not authority")
        record = self.registry.get(principal_id)
        if record is None:
            return Decision(REJECT, "unknown identity")
        if role not in record.capabilities:
            return Decision(REJECT, "no capability")
        if not record.auth_proven:
            return Decision(HOLD, "auth not proven")
        return Decision(RECORDED, "capability present; not an activation")

    def rank_candidates(self, role, *, target_host):
        """Safety, permission, known spend, then cheapest, then host, then id."""
        eligible = []
        skipped = []
        if role not in CAPABILITIES:
            return (), tuple(record.principal_id for record in self.registry.records())
        for record in self.registry.records():
            if role not in record.capabilities or not record.permitted or not record.safety_ok:
                skipped.append(record.principal_id)
                continue
            if not record.auth_proven or not known_spend(record.spend_limit):
                skipped.append(record.principal_id)
                continue
            if record.cost > record.spend_limit:
                skipped.append(record.principal_id)
                continue
            eligible.append(record)
        eligible.sort(key=lambda record: (record.cost, 0 if record.host == target_host else 1, record.principal_id))
        return tuple(record.principal_id for record in eligible), tuple(skipped)

    def preauthorize_replacement(self, *, requested_by, principal_id, writer_principal, writer_scopes):
        if requested_by != self.owner_principal:
            return Decision(REJECT, "only the owner can preauthorize a replacement")
        if not self._proven(requested_by):
            return Decision(HOLD, "owner auth not proven")
        if not principal_id or principal_id == writer_principal:
            return Decision(REJECT, "replacement cannot be the writer")
        record = self.registry.get(principal_id)
        if record is None:
            return Decision(REJECT, "unknown replacement")
        if not record.auth_proven:
            return Decision(HOLD, "replacement auth not proven")
        if "COORDINATE" not in record.capabilities and "ISSUE_PREAPPROVED_LEASE" not in record.capabilities:
            return Decision(REJECT, "replacement lacks capability")
        self.replacements[principal_id] = frozenset(writer_scopes)
        return Decision(RECORDED, "replacement preauthorized outside writer scopes")

    def _replacement_outside(self, issuer, scope, writer):
        if issuer not in self.replacements or issuer == writer or scope in self.replacements[issuer]:
            return False
        return self._has(issuer, "COORDINATE") or self._has(issuer, "ISSUE_PREAPPROVED_LEASE")

    def _extend_guard(self, row, approver, verifier):
        """Same fail-closed rule as extend. Used by LeaseStore.renew.

        Three distinct principals, a known spend limit on the bound principal,
        and a CLEAR stop. Unknown spend or STOP/HOLD refuses the renew.
        """
        parties = {row.holder, row.principal} - {""}
        if not approver or not verifier or approver in parties or verifier in parties or approver == verifier:
            return False
        if not self._has(approver, "ISSUE_PREAPPROVED_LEASE"):
            return False
        if not (self._has(verifier, "VERIFY_LEASE") or self._has(verifier, "REVIEW_INDEPENDENTLY")):
            return False
        record = self.registry.get(row.principal or row.holder)
        if record is None or not known_spend(record.spend_limit):
            return False
        return self.probe_stop() == "CLEAR"

    def activate(self, *, issuer, verifier, writer, ack_principal, scope, workkey, ttl_s, host,
                 grant, spend_limit, requested_by, owner_authorizes=False):
        writer_rec = self.registry.get(writer)
        if writer_rec is None:
            return Decision(REJECT, "unknown writer")
        if ack_principal != writer:
            return Decision(PENDING, "ack principal is not the writer")
        if "WRITE_SCOPED_CODE" not in writer_rec.capabilities:
            return Decision(REJECT, "writer lacks WRITE_SCOPED_CODE")
        if not issuer or self.registry.get(issuer) is None:
            return Decision(REJECT, "unknown issuer")
        if issuer == writer or (verifier and (verifier == writer or verifier == issuer)):
            return Decision(REJECT, "anti-self-approval")
        if issuer in self.replacements and scope in self.replacements[issuer]:
            return Decision(REJECT, "replacement coordinator inside writer scope")
        if not known_spend(spend_limit):
            return Decision(HOLD, "spend unknown")
        if not known_spend(writer_rec.spend_limit):
            return Decision(HOLD, "spend unknown")
        if writer_rec.cost > spend_limit:
            return Decision(HOLD, "cost exceeds spend limit")
        stop = self.probe_stop()
        if stop is None:
            return Decision(HOLD, "stop not checkable; no new ACTIVE")
        if stop != "CLEAR":
            return Decision(HOLD, f"stop is {stop}; no new ACTIVE")
        if grant is None:
            return Decision(HOLD, "missing grant")
        stored = self.broker.grants.get(getattr(grant, "grant_id", None))
        if stored is None:
            return Decision(HOLD, "grant is not in the broker")
        if not self.broker.seal_matches(stored):
            return Decision(HOLD, "grant seal missing")
        request = self.activation_request(writer=writer, scope=scope, host=host, request_id="activate-" + scope)
        reason = why_not_covered(stored, request, self.clock())
        if reason:
            return Decision(HOLD, reason)
        if not writer_rec.auth_proven:
            return Decision(HOLD, "writer auth not proven")
        if not self.registry.get(issuer).auth_proven:
            return Decision(HOLD, "issuer auth not proven")
        if "ISSUE_PREAPPROVED_LEASE" not in self.registry.get(issuer).capabilities:
            return Decision(REJECT, "issuer lacks capability")
        verifier_ok = bool(verifier) and (
            self._has(verifier, "VERIFY_LEASE") or self._has(verifier, "REVIEW_INDEPENDENTLY")
        )
        if not verifier_ok:
            return Decision(HOLD, "no independent verifier", evidence={
                "card": self._card(missing_gate="independent verifier", workkey_id=workkey),
            })
        if not self.coordinator_reachable:
            if owner_authorizes and requested_by != self.owner_principal:
                return Decision(REJECT, "owner authorization principal mismatch")
            owner_ok = (
                owner_authorizes and requested_by == self.owner_principal and self._proven(self.owner_principal)
            )
            if not owner_ok and not self._replacement_outside(issuer, scope, writer):
                return Decision(HOLD, "coordinator unreachable; no owner or replacement authorization")
        current = self.leases.current(scope)
        if current is not None and current.holder != writer:
            return Decision(REJECT, "lease conflict")
        if current is not None and current.workkey != workkey:
            return Decision(REJECT, "workkey fence")
        if current is not None and current.host and host and current.host != host:
            return Decision(REJECT, "host fence")
        try:
            lease = self.leases.acquire(
                scope, writer, workkey, ttl_s, principal=writer, host=host, owner=self.owner_principal,
            )
        except LeaseConflict:
            return Decision(REJECT, "lease conflict")
        used = replace(stored, uses=stored.uses + 1)
        self.broker.grants[stored.grant_id] = used
        self.broker._event("GRANT_USED", grant_id=stored.grant_id, request_id=request.request_id)
        return Decision(ACTIVE, "activation match", evidence={"lease": lease, "grant_id": stored.grant_id})

    def extend(self, lease, ttl_s, *, approver, verifier):
        """Policy extend. Issuer, verifier, and writer must be three principals.

        Does not call renew when the approver is the writer, when spend is
        unknown, or when stop is not CLEAR. A principal-bound LeaseStore.renew
        uses this gate's extend guard, so those refusals hold on the store too.
        """
        parties = {lease.holder, lease.principal} - {""}
        if not approver or not verifier or approver in parties or verifier in parties or approver == verifier:
            return Decision(REJECT, "writer self-extend or self-approve")
        if not self._has(approver, "ISSUE_PREAPPROVED_LEASE"):
            return Decision(REJECT, "approver cannot issue")
        if not (self._has(verifier, "VERIFY_LEASE") or self._has(verifier, "REVIEW_INDEPENDENTLY")):
            return Decision(HOLD, "no independent verifier", evidence={
                "card": self._card(missing_gate="independent verifier", workkey_id=lease.workkey),
            })
        record = self.registry.get(lease.principal or lease.holder)
        if record is None or not known_spend(record.spend_limit):
            return Decision(HOLD, "spend unknown")
        stop = self.probe_stop()
        if stop is None:
            return Decision(HOLD, "stop not checkable; no extend")
        if stop != "CLEAR":
            return Decision(HOLD, f"stop is {stop}; no extend")
        renewed = self.leases.renew(lease, ttl_s, approver=approver, verifier=verifier)
        return Decision(RECORDED, "extended by distinct approver", evidence={"lease": renewed})

    def authorize_side_effect(self, effect, *, human_go, lease_active):
        if effect not in SIDE_EFFECTS:
            return Decision(REJECT, "unknown side effect")
        if not human_go:
            return Decision(REJECT, "human go required")
        if not lease_active:
            return Decision(REJECT, "lease required")
        return Decision(PENDING, "HOLD_PUSH; production locked; side effect not executed", evidence={
            "hold_push": HOLD_PUSH, "production_locked": PRODUCTION_LOCKED,
        })

    def write(self, scope, token, host=None, workkey=None, principal=None):
        try:
            lease = self.leases.check_write(scope, token, host=host, workkey=workkey, principal=principal)
        except StaleLease:
            return Decision(HOLD, "write fail-closed", evidence={"mode": "CHECKPOINT_RO"})
        return Decision(FENCED, "fence accepted", evidence={"mode": "WRITE", "lease": lease})

    def revoke(self, scope, token, *, by_principal):
        self.leases.revoke(scope, token)
        return Decision(HOLD, "revoked", evidence={"by_principal": by_principal})

    def submit_workkey(self, data):
        package, decision = parse_workkey(data)
        if package is None:
            return decision
        self.workkeys[package.workkey_id] = package
        return Decision(CANDIDATE, "workkey stored", evidence={
            "package_sha": package_sha(package), "workkey_id": package.workkey_id,
        })

    def _ready_block_reason(self, package):
        if not package.file_scope:
            return "scope missing"
        if package.reviewer == package.current_writer:
            return "reviewer is not independent"
        gates = package.stop_and_spend_gates
        if not isinstance(gates, dict) or "spend_limit" not in gates or not known_spend(gates.get("spend_limit")):
            return "spend limit missing"
        if gates.get("stop") not in KNOWN_STOP:
            return "stop unknown"
        if gates.get("stop") != "CLEAR":
            return "stop is not clear"
        if not isinstance(package.dependencies, tuple):
            return "dependencies not proven"
        tests = package.verified_tests
        if not isinstance(tests, dict) or any(key not in tests for key in ("exit", "time", "hash")):
            return "verified_tests incomplete"
        record = self.registry.get(package.current_writer)
        if record is None or not record.auth_proven or "WRITE_SCOPED_CODE" not in record.capabilities:
            return "identity not protected"
        return None

    def mark_ready(self, workkey_id):
        package = self.workkeys.get(workkey_id)
        if package is None:
            return Decision(HOLD, "missing workkey")
        if package.state != CANDIDATE:
            return Decision(REJECT, f"cannot ready from {package.state}")
        reason = self._ready_block_reason(package)
        if reason:
            return Decision(HOLD, reason, evidence={"state": package.state})
        self.workkeys[workkey_id] = replace(package, state=READY)
        return Decision(READY, "gates satisfied", evidence={"state": READY})

    def claim(self, workkey_id, *, live_base_sha, live_state_version):
        package = self.workkeys.get(workkey_id)
        if package is None:
            return Decision(HOLD, "missing workkey")
        if package.base_sha != live_base_sha or package.state_version != live_state_version:
            return Decision(NOT_PROVEN, "stale state_version or base_sha", evidence={"state": package.state})
        if package.state != READY:
            return Decision(REJECT, f"cannot claim from {package.state}")
        if self.probe_stop() != "CLEAR":
            return Decision(HOLD, "stop blocks claim", evidence={"state": package.state})
        self.workkeys[workkey_id] = replace(package, state=CLAIMED)
        return Decision(CLAIMED, "checkpoint proven", evidence={"state": CLAIMED})

    def transition(self, workkey_id, new_state):
        package = self.workkeys.get(workkey_id)
        if package is None:
            return Decision(HOLD, "missing workkey")
        if new_state not in WORKKEY_STATES:
            return Decision(REJECT, f"{new_state} is not a workkey state")
        if new_state in (READY, CLAIMED, "VERIFIED"):
            return Decision(REJECT, f"{new_state} has a gated entry")
        if new_state not in WORKKEY_TRANSITIONS[package.state]:
            return Decision(REJECT, f"{package.state} -> {new_state} is not allowed")
        self.workkeys[workkey_id] = replace(package, state=new_state)
        return Decision(new_state, "transition", evidence={"state": new_state})

    def verify_independent(self, workkey_id, *, verifier):
        package = self.workkeys.get(workkey_id)
        if package is None:
            return Decision(HOLD, "missing workkey")
        if package.state != "VERIFYING":
            return Decision(REJECT, "not verifying")
        if not verifier or verifier == package.current_writer:
            return Decision(REJECT, "verifier is not independent")
        if not (self._has(verifier, "VERIFY_LEASE") or self._has(verifier, "REVIEW_INDEPENDENTLY")):
            return Decision(HOLD, "no independent verifier", evidence={
                "card": self._card(missing_gate="independent verifier", workkey_id=workkey_id),
            })
        self.workkeys[workkey_id] = replace(package, state="VERIFIED")
        return Decision("VERIFIED", "independent verify", evidence={"state": "VERIFIED"})

    def resume(self, workkey_id):
        package = self.workkeys.get(workkey_id)
        if package is None:
            return Decision(HOLD, "missing workkey")
        return Decision(CONTINUITY_OK, "resumed from workkey alone", evidence={
            "resume": resume_from_package(package),
        })

    def write_as(self, workkey_id, principal_id):
        package = self.workkeys.get(workkey_id)
        if package is None:
            return Decision(HOLD, "missing workkey")
        record = self.registry.get(principal_id)
        matched = (
            record is not None and record.auth_proven and principal_id == package.current_writer
            and "WRITE_SCOPED_CODE" in record.capabilities
        )
        if not matched:
            if package.state == "VERIFIED":
                return Decision(RO, "no auth match; resume/read-only after verify")
            return Decision(HOLD, "no auth match; write refused")
        return Decision(PENDING, "auth match is not a write; lease fence still required")

    def start(self, workkey_id):
        package = self.workkeys.get(workkey_id)
        if package is None:
            return Decision(HOLD, "missing workkey")
        stop = self.probe_stop()
        if stop is None:
            return Decision(HOLD, "stop not checkable; no start", evidence={"state": package.state})
        if stop != "CLEAR":
            return Decision(HOLD, f"stop is {stop}; no start", evidence={"state": package.state})
        if package.state != READY:
            return Decision(HOLD, "workkey is not READY", evidence={"state": package.state})
        return Decision(PENDING, "READY and stop clear; agent not started", evidence={"state": package.state})

    def flow_through(self, workkey_id):
        """Check one READY workkey once. A second pass stops. This does not start an agent."""
        package = self.workkeys.get(workkey_id)
        if package is None or package.state != READY:
            return Decision(HOLD, "not a READY workkey")
        if self.flow_checks.get(workkey_id, 0) >= 1:
            return Decision(HOLD, "stop after exactly one READY check", evidence={
                "checks": self.flow_checks[workkey_id],
            })
        self.flow_checks[workkey_id] = 1
        if self.probe_stop() != "CLEAR":
            return Decision(HOLD, "stop gate", evidence={"checks": 1})
        return Decision(CHECKED, "one READY check", evidence={"checks": 1, "workkey_id": workkey_id})
