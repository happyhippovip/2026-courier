#!/usr/bin/env python3
"""Persistent Opportunity Queue & Smart Priority Engine (Mission 118).

Features:
- Durable Opportunity Queue persisted in events/opportunity-queue/
- Strict priority hierarchy (Production blockers > Approved production > Reliability > etc.)
- Evidence-based discovery & queue refill from local repo state
- Bounded task bundling for Antigravity builder
- Failure isolation & granular Circuit Breakers (events/circuit-breakers/)
- Model economy evaluation (determines if model call is required)
- Context hash deduplication
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import sys
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from scripts.canonical_authority import CanonicalAuthority

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


# Canonical contract for the bounded, local result family.  These values are
# intentionally owned here (at the queue trust boundary), rather than trusted
# merely because an untrusted durable result included them in its fingerprint.
LOCAL_RESULT_SCHEMA_VERSION = "1.0"
LOCAL_RESULT_TYPE = "LOCAL_VALIDATION_RESULT"
LOCAL_RESULT_HANDLER_STATUSES = {
    "DETERMINISTIC_LOCAL_VALIDATION": {"SUCCESS"},
    "DETERMINISTIC_LOCAL_NOOP": {"NOOP"},
}
LOCAL_RESULT_REQUIRED_FIELDS = {
    "schema_version",
    "result_type",
    "task_id",
    "opportunity_id",
    "claim_id",
    "generation",
    "status",
    "handler",
    "completed_at",
    "metadata",
    "result_fingerprint",
}


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def is_pid_alive(pid: int) -> bool:
    """Return whether a local process owner is still alive without signalling it."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


@dataclass
class Opportunity:
    opportunity_id: str
    source: str
    objective_id: str
    project: str
    description: str
    priority: int = 5  # 10 = Production blocker, 9 = Unfinished production, 8 = Reliability, 6 = Automation, 1 = Cosmetic
    expected_value: str = "Evidence-backed output"
    evidence: dict[str, Any] = field(default_factory=dict)
    required_capabilities: list[str] = field(default_factory=list)
    risk: str = "LOW"  # LOW, MEDIUM, HIGH
    estimated_cost: float = 0.0
    model_need: bool = False
    external_action_units: int = 0
    project_id: str = ""
    source_artifact: str = ""
    source_hash: str = ""
    evidence_type: str = ""
    production_stage: str = ""
    problem_or_goal: str = ""
    expected_output: str = ""
    risk_class: str = "LOW"
    cost_class: str = "ZERO_COST_LOCAL"
    required_capabilities: list[str] = field(default_factory=list)
    dedupe_fingerprint: str = ""
    heavy_job: bool = False
    status: str = "READY"  # CANDIDATE, READY, RUNNING, COMPLETED, NO_VALUE, BLOCKED, WAITING_FOR_HUMAN, CIRCUIT_OPEN, DEFERRED
    target_agent: str = "antigravity"
    allowed_scope: list[str] = field(default_factory=list)
    allowed_actions: list[str] = field(default_factory=lambda: ["READ"])
    created_at: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    dedupe_hash: str = ""

    def __post_init__(self):
        if not self.dedupe_hash:
            raw = f"{self.project}:{self.objective_id}:{self.description}:{json.dumps(self.allowed_scope, sort_keys=True)}"
            self.dedupe_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        if not self.dedupe_fingerprint:
            self.dedupe_fingerprint = self.dedupe_hash

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CircuitBreakerManager:
    """Tracks granular failure fingerprints and opens circuit breakers for affected branches only."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir
        self.breakers_dir = repo_dir / "events/circuit-breakers"
        self.breakers_dir.mkdir(parents=True, exist_ok=True)
        self.breakers: dict[str, dict] = {}
        self._load_all()

    def _load_all(self):
        for f in self.breakers_dir.glob("*.json"):
            data = load_json(f)
            if data and "breaker_id" in data:
                self.breakers[data["breaker_id"]] = data

    def record_failure(self, fingerprint: str, reason: str, max_consecutive: int = 2) -> bool:
        """Records a failure. Returns True if circuit is opened."""
        breaker = self.breakers.get(fingerprint, {
            "breaker_id": fingerprint,
            "consecutive_failures": 0,
            "status": "CLOSED",
            "opened_at": None,
            "reason": None,
        })
        breaker["consecutive_failures"] += 1
        breaker["last_failure_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        breaker["reason"] = reason

        if breaker["consecutive_failures"] >= max_consecutive:
            breaker["status"] = "OPEN"
            breaker["opened_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            save_json(self.breakers_dir / f"{fingerprint}.json", breaker)
            self.breakers[fingerprint] = breaker
            return True

        self.breakers[fingerprint] = breaker
        save_json(self.breakers_dir / f"{fingerprint}.json", breaker)
        return False

    def record_success(self, fingerprint: str) -> None:
        """Resets failure count on verified success."""
        if fingerprint in self.breakers:
            breaker = self.breakers[fingerprint]
            breaker["consecutive_failures"] = 0
            breaker["status"] = "CLOSED"
            breaker["opened_at"] = None
            save_json(self.breakers_dir / f"{fingerprint}.json", breaker)

    def is_circuit_open(self, fingerprint: str) -> bool:
        breaker = self.breakers.get(fingerprint)
        return bool(breaker and breaker.get("status") == "OPEN")

    def list_open_breakers(self) -> list[dict]:
        return [b for b in self.breakers.values() if b.get("status") == "OPEN"]


class OpportunityQueue:
    """Manages persistent, evidence-based opportunities with priority scoring and bundling."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir
        self.queue_dir = repo_dir / "events/opportunity-queue"
        self.claims_dir = self.queue_dir / "claims"
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.claims_dir.mkdir(parents=True, exist_ok=True)
        self.authority = CanonicalAuthority(locks_dir=repo_dir / "events" / "locks")
        self.circuit_manager = CircuitBreakerManager(repo_dir=repo_dir)
        self.opportunities: dict[str, Opportunity] = {}
        self._load_all()

    def _load_all(self):
        for f in self.queue_dir.glob("*.json"):
            data = load_json(f)
            if data and isinstance(data, dict) and "opportunity_id" in data:
                try:
                    self.opportunities[data["opportunity_id"]] = Opportunity(**data)
                except Exception:
                    pass

    def add_opportunity(self, opp: Opportunity) -> bool:
        """Adds opportunity if not duplicate by dedupe_hash."""
        for existing in self.opportunities.values():
            if existing.dedupe_hash == opp.dedupe_hash and existing.status in ("READY", "RUNNING", "COMPLETED"):
                return False

        self.opportunities[opp.opportunity_id] = opp
        save_json(self.queue_dir / f"{opp.opportunity_id}.json", opp.to_dict())
        return True

    def get_opportunity(self, opp_id: str) -> Opportunity | None:
        return self.opportunities.get(opp_id)

    def save_opportunity(self, opp: Opportunity) -> None:
        opp.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.opportunities[opp.opportunity_id] = opp
        save_json(self.queue_dir / f"{opp.opportunity_id}.json", opp.to_dict())

    def _claim_path(self, opportunity_id: str) -> Path:
        clean_id = opportunity_id.replace("/", "_").replace("\\", "_")
        return self.claims_dir / f"{clean_id}.claim.json"

    def _authority_scope(self, opportunity_id: str) -> str:
        return f"OPPORTUNITY:{opportunity_id}"

    def canonical_task_id(self, opportunity_id: str, generation: int) -> str:
        return f"TASK-OPP-{opportunity_id}-{generation}"

    def expected_result_fingerprint(self, opp: Opportunity, claim: dict[str, Any], result: dict[str, Any]) -> str:
        """Hash trusted task/claim identity plus the normalized result payload."""
        payload = {key: value for key, value in result.items() if key not in {
            "task_id", "opportunity_id", "claim_id", "generation", "result_fingerprint",
        }}
        binding = {
            "task_id": self.canonical_task_id(opp.opportunity_id, int(claim["state_version"])),
            "opportunity_id": opp.opportunity_id,
            "opportunity_fingerprint": opp.dedupe_fingerprint,
            "claim_id": claim["claim_id"],
            "generation": claim["state_version"],
            "payload": payload,
        }
        return hashlib.sha256(json.dumps(binding, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()

    def _record_blocked_recovery(self, opportunity_id: str, claim: dict[str, Any], mismatch: str, expected: str, observed: str) -> None:
        """Persist one non-sensitive, deduplicated failure record for a bad result."""
        evidence = {
            "status": "BLOCKED_RESULT_SCHEMA_MISMATCH" if mismatch.startswith("RESULT_SCHEMA") else "BLOCKED_IDENTITY_MISMATCH",
            "opportunity_id": opportunity_id,
            "claim_id": claim.get("claim_id"),
            "generation": claim.get("state_version"),
            "mismatch_class": mismatch,
            "expected_identity_fingerprint": expected,
            "observed_identity_fingerprint": observed,
        }
        dedupe = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode("utf-8")).hexdigest()
        evidence["recovery_fingerprint"] = dedupe
        evidence["recorded_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        directory = self.queue_dir / "blocked-recovery"
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{opportunity_id}-{dedupe}.json"
        if not target.exists():
            tmp = target.with_suffix(f".tmp.{os.getpid()}")
            tmp.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
            os.replace(tmp, target)

    def _validate_local_result_schema(self, result: Any) -> tuple[bool, str]:
        """Validate the single approved local-result family before fingerprint use."""
        if not isinstance(result, dict):
            return False, "RESULT_SCHEMA_MALFORMED"
        if set(result) != LOCAL_RESULT_REQUIRED_FIELDS:
            return False, "RESULT_SCHEMA_REQUIRED_FIELDS_MISMATCH"
        if result.get("schema_version") != LOCAL_RESULT_SCHEMA_VERSION:
            return False, "RESULT_SCHEMA_VERSION_UNSUPPORTED"
        if result.get("result_type") != LOCAL_RESULT_TYPE:
            return False, "RESULT_SCHEMA_TYPE_UNAPPROVED"
        if not all(isinstance(result.get(field), str) and result[field].strip() for field in (
            "task_id", "opportunity_id", "claim_id", "status", "handler", "completed_at", "result_fingerprint",
        )):
            return False, "RESULT_SCHEMA_STRING_FIELD_INVALID"
        if isinstance(result.get("generation"), bool) or not isinstance(result.get("generation"), int) or result["generation"] < 1:
            return False, "RESULT_SCHEMA_GENERATION_INVALID"
        if not isinstance(result.get("metadata"), dict):
            return False, "RESULT_SCHEMA_METADATA_INVALID"
        handler = result["handler"]
        allowed_statuses = LOCAL_RESULT_HANDLER_STATUSES.get(handler)
        if allowed_statuses is None:
            return False, "RESULT_SCHEMA_HANDLER_UNAPPROVED"
        if result["status"] not in {status for statuses in LOCAL_RESULT_HANDLER_STATUSES.values() for status in statuses}:
            return False, "RESULT_SCHEMA_STATUS_UNAPPROVED"
        if result["status"] not in allowed_statuses:
            return False, "RESULT_SCHEMA_STATUS_HANDLER_MISMATCH"
        try:
            datetime.datetime.fromisoformat(result["completed_at"].replace("Z", "+00:00"))
        except ValueError:
            return False, "RESULT_SCHEMA_COMPLETED_AT_INVALID"
        return True, "MATCH"

    def validate_durable_result(self, opp: Opportunity, claim: dict[str, Any], result: dict[str, Any]) -> tuple[bool, str, str]:
        """Fail closed unless result identity is derived from the current fence."""
        if not isinstance(result, dict):
            return False, "RESULT_SCHEMA_MALFORMED", ""
        expected_task = self.canonical_task_id(opp.opportunity_id, int(claim.get("state_version", 0)))
        if result.get("task_id") != expected_task:
            return False, "TASK_ID_MISMATCH", expected_task
        if result.get("opportunity_id") != opp.opportunity_id:
            return False, "OPPORTUNITY_ID_MISMATCH", opp.opportunity_id
        if result.get("claim_id") != claim.get("claim_id"):
            return False, "CLAIM_ID_MISMATCH", str(claim.get("claim_id", ""))
        if result.get("generation") != claim.get("state_version"):
            return False, "GENERATION_MISMATCH", str(claim.get("state_version", ""))
        schema_valid, schema_mismatch = self._validate_local_result_schema(result)
        if not schema_valid:
            return False, schema_mismatch, ""
        try:
            expected_fingerprint = self.expected_result_fingerprint(opp, claim, result)
        except (TypeError, ValueError):
            return False, "UNVERIFIABLE_RESULT_PAYLOAD", ""
        if result.get("result_fingerprint") != expected_fingerprint:
            return False, "RESULT_FINGERPRINT_MISMATCH", expected_fingerprint
        return True, "MATCH", expected_fingerprint

    def claim_opportunity(
        self,
        opportunity_id: str,
        claim_owner: str,
        lease_seconds: int = 900,
    ) -> tuple[bool, str, dict[str, Any]]:
        """Atomically claim one READY opportunity before it can be dispatched.

        The O_EXCL claim record is authoritative.  The visible opportunity status
        is updated only after ownership is established, so a crash cannot let a
        second supervisor infer ownership from a stale in-memory status.
        """
        claim_path = self._claim_path(opportunity_id)
        authority_scope = self._authority_scope(opportunity_id)
        task_id = f"OPPORTUNITY:{opportunity_id}"
        acquired, generation, authority_error = self.authority.acquire_scopes(
            owner_id=claim_owner,
            task_id=task_id,
            scopes=[authority_scope],
            ttl_seconds=lease_seconds,
        )
        if not acquired or generation is None:
            return False, "AUTHORITY_DENIED", {"opportunity_id": opportunity_id, "error": authority_error}

        now = datetime.datetime.now(datetime.timezone.utc)
        claim = {
            "opportunity_id": opportunity_id,
            "claim_owner": claim_owner,
            "claim_id": f"claim-{uuid.uuid4().hex}",
            "claimed_at": now.isoformat(),
            "lease_expires_at": (now + datetime.timedelta(seconds=lease_seconds)).isoformat(),
            "state_version": generation,
            "authority_generation": generation,
            "pid": os.getpid(),
        }

        existing_claim = load_json(claim_path) if claim_path.exists() else None
        opportunity_path = self.queue_dir / f"{opportunity_id}.json"
        current_data = load_json(opportunity_path) if opportunity_path.exists() else None
        current = Opportunity(**current_data) if current_data else self.get_opportunity(opportunity_id)
        if current:
            self.opportunities[opportunity_id] = current
        if not current or current.status != "READY":
            self.authority.release_scopes(claim_owner, [authority_scope], generation, task_id)
            if existing_claim:
                return False, "ALREADY_CLAIMED", existing_claim
            return False, "NOT_READY", {"opportunity_id": opportunity_id}

        try:
            fd = os.open(claim_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(claim, handle, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError:
            existing = load_json(claim_path) or {}
            # Owning a newer canonical generation proves this raw record cannot
            # belong to an active canonical claimant.  Legacy/unfenced records
            # remain fail-closed rather than guessed away.
            if isinstance(existing.get("authority_generation"), int) and existing["authority_generation"] < generation:
                try:
                    claim_path.unlink(missing_ok=True)
                    fd = os.open(claim_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
                    with os.fdopen(fd, "w", encoding="utf-8") as handle:
                        json.dump(claim, handle, indent=2)
                        handle.flush()
                        os.fsync(handle.fileno())
                    current.status = "RUNNING"
                    self.save_opportunity(current)
                    return True, "CLAIMED", claim
                except OSError:
                    pass
            self.authority.release_scopes(claim_owner, [authority_scope], generation, task_id)
            return False, "ALREADY_CLAIMED", existing

        current.status = "RUNNING"
        self.save_opportunity(current)
        return True, "CLAIMED", claim

    def release_opportunity_claim(self, opportunity_id: str, claim_id: str) -> bool:
        """Release only the exact claim owned by this caller; never unlink a newer claim."""
        claim_path = self._claim_path(opportunity_id)
        existing = load_json(claim_path)
        if not existing or existing.get("claim_id") != claim_id:
            return False
        try:
            # Keep the canonical fence while deleting the local claim.  Releasing
            # authority first would create a window where a new claimant could
            # write its claim and then have it unlinked by this stale releaser.
            renewed, _ = self.authority.renew_heartbeat(
                owner_id=str(existing.get("claim_owner", "")),
                scope=self._authority_scope(opportunity_id),
                generation=existing.get("authority_generation"),
            )
            if not renewed:
                return False
            if load_json(claim_path) and load_json(claim_path).get("claim_id") == claim_id:
                claim_path.unlink(missing_ok=True)
                released, _ = self.authority.release_scopes(
                    owner_id=str(existing.get("claim_owner", "")),
                    scopes=[self._authority_scope(opportunity_id)],
                    generation=existing.get("authority_generation"),
                    task_id=f"OPPORTUNITY:{opportunity_id}",
                )
                return released == 1
        except OSError:
            pass
        return False

    def list_opportunities(self, status: str | None = None) -> list[Opportunity]:
        opps = list(self.opportunities.values())
        if status:
            opps = [o for o in opps if o.status == status]
        return sorted(opps, key=lambda o: o.priority, reverse=True)

    def select_next_opportunity(self, visited_ids: set[str] | None = None) -> Opportunity | None:
        """Selects highest-priority actionable READY opportunity passing circuit breakers and cost gates."""
        visited = visited_ids or set()
        candidates = [
            o for o in self.opportunities.values()
            if o.status == "READY" and o.opportunity_id not in visited
        ]

        # Sort by priority descending, then created_at ascending
        candidates.sort(key=lambda o: (o.priority, o.created_at), reverse=True)

        for opp in candidates:
            fingerprint = f"fp_{opp.project}_{opp.objective_id}"
            if self.circuit_manager.is_circuit_open(fingerprint):
                opp.status = "CIRCUIT_OPEN"
                self.save_opportunity(opp)
                continue

            if opp.estimated_cost > 0.0:
                opp.status = "BLOCKED"
                self.save_opportunity(opp)
                continue

            # Verify scope files exist
            scope_valid = True
            for sf in opp.allowed_scope:
                p = self.repo_dir / sf if not Path(sf).is_absolute() else Path(sf)
                if not p.exists():
                    scope_valid = False
                    break
            if not scope_valid:
                continue

            return opp

        return None

    def is_admissible_zero_cost_local(self, opp: Opportunity) -> bool:
        """Return whether an opportunity may run in the unattended local lane.

        This is deliberately an admission check, not a dispatcher.  Keeping it
        on the canonical queue prevents supervisors from inventing their own
        relaxed interpretation of ``READY``.
        """
        if opp.status != "READY" or opp.risk not in ("LOW", "MEDIUM"):
            return False
        if opp.estimated_cost > 0.0 or opp.heavy_job or opp.model_need:
            return False
        if opp.external_action_units != 0:
            return False
        if opp.project in {"HUMAN_BRANCH", "MONEY_BRANCH", "CREATOR_FACTORY", "universuX"}:
            return False

        evidence = opp.evidence if isinstance(opp.evidence, dict) else {}
        blocked_flags = (
            "human_gate",
            "requires_human_approval",
            "payment_approval_required",
            "permission_required",
            "auth_required",
            "security_review_required",
            "publication_required",
            "upload_required",
            "paused",
        )
        if any(bool(evidence.get(flag)) for flag in blocked_flags):
            return False

        # The daemon has no general-purpose builder authority.  Its only
        # bounded executor is a deterministic local/read-only validation.
        allowed = set(opp.allowed_actions or [])
        if not allowed or not allowed.issubset({"READ", "LOCAL_VALIDATION"}):
            return False
        return True

    def select_next_admissible_zero_cost_local(self) -> Opportunity | None:
        """Select through the canonical queue, retaining all queue policy gates."""
        for opp in self.list_opportunities(status="READY"):
            if not self.is_admissible_zero_cost_local(opp):
                continue
            fingerprint = f"fp_{opp.project}_{opp.objective_id}"
            if self.circuit_manager.is_circuit_open(fingerprint):
                continue
            return opp
        return None

    def complete_claimed_opportunity(
        self,
        opportunity_id: str,
        claim_id: str,
        generation: int,
        result: dict[str, Any],
    ) -> bool:
        """Persist a result before completing exactly the matching fenced claim."""
        if not isinstance(result, dict) or not result.get("result_fingerprint"):
            return False
        claim_path = self._claim_path(opportunity_id)
        claim = load_json(claim_path)
        if not claim or claim.get("claim_id") != claim_id:
            return False
        if claim.get("state_version") != generation:
            return False
        renewed, _ = self.authority.renew_heartbeat(
            owner_id=str(claim.get("claim_owner", "")),
            scope=self._authority_scope(opportunity_id),
            generation=generation,
        )
        if not renewed:
            return False

        current = self.get_opportunity(opportunity_id)
        if not current or current.status != "RUNNING":
            return False
        valid, mismatch, expected = self.validate_durable_result(current, claim, result)
        if not valid:
            self._record_blocked_recovery(
                opportunity_id,
                claim,
                mismatch,
                expected,
                str(result.get("result_fingerprint") or result.get("task_id") or ""),
            )
            return False

        results_dir = self.queue_dir / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        result_path = results_dir / f"{opportunity_id}.result.json"
        if result_path.exists():
            existing = load_json(result_path)
            if not existing or existing.get("result_fingerprint") != result["result_fingerprint"]:
                return False
        else:
            tmp = result_path.with_suffix(f".tmp.{os.getpid()}")
            tmp.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            os.replace(tmp, result_path)

        current.status = "COMPLETED"
        self.save_opportunity(current)
        return self.release_opportunity_claim(opportunity_id, claim_id)

    def reconcile_durable_results(self) -> list[dict[str, Any]]:
        """Apply only results that exactly match the currently fenced claim.

        A result is written before completion.  After a crash this method is the
        sole recovery path: it never executes a handler and never lets a stale
        generation release or complete a replacement claim.
        """
        outcomes: list[dict[str, Any]] = []
        results_dir = self.queue_dir / "results"
        if not results_dir.is_dir():
            return outcomes

        for result_path in sorted(results_dir.glob("*.result.json")):
            result = load_json(result_path)
            if not isinstance(result, dict):
                outcomes.append({"status": "BLOCKED_CORRUPT_RESULT", "path": result_path.name})
                continue
            opportunity_id = result.get("opportunity_id")
            claim_id = result.get("claim_id")
            generation = result.get("generation")
            fingerprint = result.get("result_fingerprint")
            if not all(isinstance(value, str) and value for value in (opportunity_id, claim_id, fingerprint)) or not isinstance(generation, int):
                outcomes.append({"status": "BLOCKED_INVALID_RESULT_IDENTITY", "path": result_path.name})
                continue

            current = self.get_opportunity(opportunity_id)
            claim = load_json(self._claim_path(opportunity_id))
            if current and current.status == "COMPLETED":
                # Completion was durably applied before a crash but release was
                # interrupted.  Validate the same canonical result binding as
                # normal reconciliation before releasing the remaining fence.
                if claim and claim.get("claim_id") == claim_id and claim.get("state_version") == generation:
                    valid, mismatch, expected = self.validate_durable_result(current, claim, result)
                    if not valid:
                        self._record_blocked_recovery(
                            opportunity_id,
                            claim,
                            mismatch,
                            expected,
                            str(result.get("result_fingerprint") or result.get("task_id") or ""),
                        )
                        outcomes.append({
                            "status": "BLOCKED_RESULT_SCHEMA_MISMATCH" if mismatch.startswith("RESULT_SCHEMA") else "BLOCKED_IDENTITY_MISMATCH",
                            "opportunity_id": opportunity_id,
                            "mismatch": mismatch,
                        })
                        continue
                    released = self.release_opportunity_claim(opportunity_id, claim_id)
                    outcomes.append({"status": "RELEASE_RECONCILED" if released else "BLOCKED_RELEASE", "opportunity_id": opportunity_id})
                continue
            if not current or current.status != "RUNNING":
                outcomes.append({"status": "BLOCKED_NON_RUNNING_RESULT", "opportunity_id": opportunity_id})
                continue
            if not claim or claim.get("claim_id") != claim_id or claim.get("state_version") != generation:
                outcomes.append({"status": "BLOCKED_STALE_RESULT", "opportunity_id": opportunity_id})
                continue

            valid, mismatch, expected = self.validate_durable_result(current, claim, result)
            if not valid:
                self._record_blocked_recovery(
                    opportunity_id,
                    claim,
                    mismatch,
                    expected,
                    str(result.get("result_fingerprint") or result.get("task_id") or ""),
                )
                outcomes.append({
                    "status": "BLOCKED_RESULT_SCHEMA_MISMATCH" if mismatch.startswith("RESULT_SCHEMA") else "BLOCKED_IDENTITY_MISMATCH",
                    "opportunity_id": opportunity_id,
                    "mismatch": mismatch,
                })
                continue

            reconciled = self.complete_claimed_opportunity(opportunity_id, claim_id, generation, result)
            outcomes.append({"status": "RESULT_RECONCILED" if reconciled else "BLOCKED_RECONCILIATION", "opportunity_id": opportunity_id})
        return outcomes

    def bundle_opportunities(
        self,
        primary_opp: Opportunity,
        max_bundle_size: int = 3,
        claimed_opportunities: list[Opportunity] | None = None,
    ) -> tuple[dict, list[Opportunity]]:
        """Bundles compatible lightweight opportunities sharing project, risk, and context into one builder task."""
        bundled = list(claimed_opportunities) if claimed_opportunities is not None else [primary_opp]
        if claimed_opportunities is None and max_bundle_size > 1:
            for opp in self.list_opportunities(status="READY"):
                if opp.opportunity_id == primary_opp.opportunity_id:
                    continue
                if len(bundled) >= max_bundle_size:
                    break

                # Compatibility invariants: Same project, same risk, no heavy job, no cost, no auth/payment
                if (
                    opp.project == primary_opp.project
                    and opp.risk == primary_opp.risk
                    and not opp.heavy_job
                    and not primary_opp.heavy_job
                    and opp.estimated_cost == 0.0
                    and opp.target_agent == primary_opp.target_agent
                ):
                    bundled.append(opp)

        combined_scope = list(set(sum([o.allowed_scope for o in bundled], [])))
        combined_instructions = " && ".join([o.description for o in bundled])
        bundled_ids = [o.opportunity_id for o in bundled]

        task_id = f"BUNDLE-{primary_opp.project[:8]}-{uuid.uuid4().hex[:6]}"
        task_info = {
            "task_id": task_id,
            "objective_id": primary_opp.objective_id,
            "instruction": f"Bundled Execution ({len(bundled)} items): {combined_instructions}",
            "target_agent": primary_opp.target_agent,
            "allowed_scope": combined_scope,
            "allowed_actions": ["READ"],
            "risk_level": primary_opp.risk,
            "cost_class": "ZERO_COST_LOCAL",
            "cost_estimate": 0.0,
            "model_job_units": 1 if any(o.model_need for o in bundled) else 0,
            "external_action_units": sum(o.external_action_units for o in bundled),
            "bundled_opportunity_ids": bundled_ids,
        }

        return task_info, bundled

    def refill_from_evidence(self) -> int:
        """Discovers new actionable opportunities from local repository fixtures and configs."""
        discovered_count = 0

        # Source 1: Local Tool Fixtures & Project Bindings
        tools_cfg = self.repo_dir / "config/local_tools.json"
        if tools_cfg.exists():
            data = load_json(tools_cfg) or {}
            raw_tools = data.get("tools", [])
            tools_list = list(raw_tools.keys()) if isinstance(raw_tools, dict) else (raw_tools if isinstance(raw_tools, list) else [])
            for t in tools_list:
                tool_key = str(t).upper().replace('_', '-')
                opp_id = f"OPP-TOOL-{tool_key}"
                opp = Opportunity(
                    opportunity_id=opp_id,
                    source="LOCAL_TOOL_FIXTURE",
                    objective_id="KEEP_PRODUCTION_PIPELINE_HEALTHY",
                    project="2026-courier",
                    description=f"Validate tool interface and execution constraints for {t}",
                    priority=8,
                    expected_value=f"Ensures deterministic runner supports {t}",
                    evidence={"tool_name": str(t)},
                    allowed_scope=["config/local_tools.json"],
                    target_agent="antigravity",
                )
                if self.add_opportunity(opp):
                    discovered_count += 1

            bindings = data.get("project_bindings", {})
            if isinstance(bindings, dict):
                for p_name, p_info in bindings.items():
                    opp_id = f"OPP-BINDING-{p_name.upper().replace('-', '_')}"
                    opp = Opportunity(
                        opportunity_id=opp_id,
                        source="PROJECT_BINDING_FIXTURE",
                        objective_id="KEEP_PRODUCTION_PIPELINE_HEALTHY",
                        project="2026-courier",
                        description=f"Audit project binding and scene file availability for {p_name}",
                        priority=9,
                        expected_value=f"Confirms production project {p_name} is accessible",
                        evidence={"project_binding": p_info},
                        allowed_scope=["config/local_tools.json"],
                        target_agent="antigravity",
                    )
                    if self.add_opportunity(opp):
                        discovered_count += 1

        # Source 2: Social Channels & Content Manifests
        channels_cfg = self.repo_dir / "config/social_channels.json"
        if channels_cfg.exists():
            data = load_json(channels_cfg) or {}
            raw_channels = data.get("channels", [])
            if isinstance(raw_channels, list):
                for ch in raw_channels:
                    ch_id = ch.get("channel_id", ch.get("platform", "CHAN")) if isinstance(ch, dict) else str(ch)
                    ch_label = ch.get("channel_label", ch_id) if isinstance(ch, dict) else str(ch)
                    opp_id = f"OPP-CHANNEL-{ch_id.upper().replace('-', '_')}"
                    opp = Opportunity(
                        opportunity_id=opp_id,
                        source="SOCIAL_CHANNEL_CONFIG",
                        objective_id="PROCESS_APPROVED_CONTENT_QUEUE",
                        project="2026-courier",
                        description=f"Verify rendering format, tags and aspect rules for {ch_label}",
                        priority=9,
                        expected_value=f"Confirms output queue compatibility for {ch_label}",
                        evidence={"channel": ch},
                        allowed_scope=["config/social_channels.json"],
                        target_agent="antigravity",
                    )
                    if self.add_opportunity(opp):
                        discovered_count += 1

        # Source 3: Content Workflows & Production Step Pipelines
        wf_cfg = self.repo_dir / "config/content_workflows.json"
        if wf_cfg.exists():
            data = load_json(wf_cfg) or {}
            raw_wfs = data.get("workflows", [])
            if isinstance(raw_wfs, list):
                for wf in raw_wfs:
                    wf_id = wf.get("workflow_id", "wf")
                    steps = wf.get("production_steps", [])
                    for step in steps[:4]:  # First 4 pipeline steps
                        opp_id = f"OPP-WF-{wf_id.upper().replace('-', '_')}-STEP-{step}"
                        opp = Opportunity(
                            opportunity_id=opp_id,
                            source="CONTENT_WORKFLOW_PIPELINE",
                            objective_id="PROCESS_APPROVED_CONTENT_QUEUE",
                            project="2026-courier",
                            description=f"Validate pipeline stage {step} constraints for workflow {wf_id}",
                            priority=8,
                            expected_value=f"Ensures stage {step} schema conformance for {wf_id}",
                            evidence={"workflow": wf_id, "step": step},
                            allowed_scope=["config/content_workflows.json"],
                            target_agent="antigravity",
                        )
                        if self.add_opportunity(opp):
                            discovered_count += 1

        # Source 4: Reliability, Teamwork & Policy Checks
        policy_cfg = self.repo_dir / "config/teamwork_policy.json"
        if policy_cfg.exists():
            opp_id = "OPP-POLICY-HEAVY-JOB-CHECK"
            opp = Opportunity(
                opportunity_id=opp_id,
                source="TEAMWORK_POLICY",
                objective_id="IMPROVE_RELIABILITY",
                project="2026-courier",
                description="Audit heavy job concurrency invariants and lease timeout policy",
                priority=7,
                expected_value="Prevents resource contention during unattended sleep execution",
                evidence={"policy_file": "config/teamwork_policy.json"},
                allowed_scope=["config/teamwork_policy.json"],
                target_agent="antigravity",
            )
            if self.add_opportunity(opp):
                discovered_count += 1

            opp_id_routing = "OPP-POLICY-ROUTING-BOUNDARIES"
            opp_routing = Opportunity(
                opportunity_id=opp_id_routing,
                source="TEAMWORK_POLICY",
                objective_id="IMPROVE_RELIABILITY",
                project="2026-courier",
                description="Verify routine vs teamwork multi-agent routing boundaries",
                priority=7,
                expected_value="Ensures routine deterministic tasks run single-agent without team overhead",
                evidence={"policy_file": "config/teamwork_policy.json"},
                allowed_scope=["config/teamwork_policy.json"],
                target_agent="antigravity",
            )
            if self.add_opportunity(opp_routing):
                discovered_count += 1

            opp_id_safety = "OPP-POLICY-SAFETY-ZERO-COST"
            opp_safety = Opportunity(
                opportunity_id=opp_id_safety,
                source="TEAMWORK_POLICY",
                objective_id="IMPROVE_RELIABILITY",
                project="2026-courier",
                description="Audit zero cost and human gate safety boundary rules",
                priority=7,
                expected_value="Guarantees 0.00 EUR autonomous spend and strict gate compliance",
                evidence={"policy_file": "config/teamwork_policy.json"},
                allowed_scope=["config/teamwork_policy.json"],
                target_agent="antigravity",
            )
            if self.add_opportunity(opp_safety):
                discovered_count += 1

        return discovered_count

    def export_telemetry(self) -> dict[str, int]:
        """Returns live counters for Walking HQ and /api/state."""
        all_opps = list(self.opportunities.values())
        return {
            "READY": len([o for o in all_opps if o.status == "READY"]),
            "RUNNING": len([o for o in all_opps if o.status == "RUNNING"]),
            "BLOCKED": len([o for o in all_opps if o.status in ("BLOCKED", "CIRCUIT_OPEN")]),
            "WAITING_FOR_HUMAN": len([o for o in all_opps if o.status == "WAITING_FOR_HUMAN"]),
            "COMPLETED": len([o for o in all_opps if o.status == "COMPLETED"]),
            "TOTAL": len(all_opps),
        }
