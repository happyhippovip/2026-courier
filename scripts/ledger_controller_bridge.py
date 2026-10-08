"""One-shot idempotent bridge: coordination-ledger mission -> V1 controller packet.

A mission authorized and tracked by the coordination ledger (PR #153,
``scripts/coordination_ledger.py``) becomes exactly one V1 controller task;
a verified controller result returns to the ledger as a receipt event that
releases dependents. Nothing here executes work, retries, or runs a daemon:
it mints packets and translates receipts as pure data.

Ownership boundaries (read-only imports only):
- Ledger shapes come from ``scripts.coordination_ledger`` (read, never edited).
- Controller packets match ``courier_core.controller.Controller.create_task``
  ``TASK_FIELDS``; the caller passes the packet to the controller. This module
  never imports the controller, so it stays stdlib-only and replay-safe.

Idempotency: the packet's ``idempotency_key`` is derived from the ledger
mission (``ledger:<mission_id>:<mint_event_id>``). The controller maps that
key to one deterministic task id, so re-minting or replaying the same mint
cannot create a second task: the controller answers ``duplicate`` instead.

Fail-closed mapping (a failed or human-blocked controller outcome NEVER
becomes a ledger FINAL/DONE):
- verified COMPLETE  -> FINAL / DONE (ownership released, dependents freed)
- BLOCKED outcome, or any unverified outcome -> BLOCKED (stays owned: the
  outcome is uncertain and waits for a human decision, never retried blindly)
- verified FAILED     -> ERROR  (a verified terminal failure; the ledger may
  reassign only after ERROR per its own rules)
- anything else       -> refused (BridgeRefused), nothing minted or recorded
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Optional

IDEMPOTENCY_PREFIX = "ledger"
FINAL = "FINAL"
BLOCKED = "BLOCKED"
ERROR = "ERROR"
DONE = "DONE"


class BridgeRefused(ValueError):
    """The bridge declined: ineligible mission, bad spec, or unmappable outcome."""


def _mission_owner(mission: Mapping[str, Any]) -> Optional[str]:
    owner = mission.get("ownership")
    if isinstance(owner, str) and owner:
        return owner
    agent = mission.get("agent_id")
    if hasattr(agent, "value"):
        agent = agent.value
    return agent if isinstance(agent, str) and agent else None


def _mission_status(mission: Mapping[str, Any]) -> str:
    status = mission.get("status")
    if hasattr(status, "value"):
        status = status.value
    return status if isinstance(status, str) else ""


def eligible_for_mint(mission: Mapping[str, Any], all_missions: Mapping[str, Mapping[str, Any]],
                      owner: str) -> tuple[bool, str]:
    """A mission may mint exactly when it is WORKING, owned by the caller,
    and every dependency is DONE. Anything else is refused with a reason."""
    if not isinstance(mission, Mapping):
        return False, "MISSION_NOT_A_RECORD"
    if _mission_status(mission) != "WORKING":
        return False, "MISSION_NOT_WORKING"
    if _mission_owner(mission) != owner:
        return False, "NOT_OWNER"
    depends = mission.get("depends_on") or []
    if not isinstance(depends, list):
        return False, "BAD_DEPENDS_ON"
    for dep_id in depends:
        dep = all_missions.get(dep_id)
        if dep is None:
            return False, f"DEPENDENCY_UNKNOWN:{dep_id}"
        if _mission_status(dep) != DONE:
            return False, f"DEPENDENCY_NOT_DONE:{dep_id}"
    return True, "ELIGIBLE"


def idempotency_key(mission_id: str, mint_event_id: str) -> str:
    """One stable key per (mission, mint). Re-minting reuses the controller task."""
    if not mission_id or not mint_event_id:
        raise BridgeRefused("BAD_MINT_IDENTITY")
    return f"{IDEMPOTENCY_PREFIX}:{mission_id}:{mint_event_id}"


def mint_packet(mission: Mapping[str, Any], all_missions: Mapping[str, Mapping[str, Any]], *,
                owner: str, mint_event_id: str, adapter: str, params: Mapping[str, Any],
                effect_class: str, lease_ttl_s: int, max_attempts: int = 1,
                timeout_s: Optional[int] = None) -> dict:
    """Build a controller ``create_task`` body for an eligible mission.

    Work content (adapter/params/effect_class) always comes from the caller;
    the bridge gates eligibility and keys idempotency, never invents work.
    """
    ok, reason = eligible_for_mint(mission, all_missions, owner)
    if not ok:
        raise BridgeRefused(reason)
    mission_id = mission.get("mission_id")
    if not isinstance(mission_id, str) or not mission_id:
        raise BridgeRefused("BAD_MISSION_ID")
    if not isinstance(adapter, str) or not adapter:
        raise BridgeRefused("BAD_ADAPTER")
    if not isinstance(params, Mapping):
        raise BridgeRefused("BAD_PARAMS")
    if not isinstance(effect_class, str) or not effect_class:
        raise BridgeRefused("BAD_EFFECT_CLASS")
    if isinstance(lease_ttl_s, bool) or not isinstance(lease_ttl_s, int) or lease_ttl_s < 1:
        raise BridgeRefused("BAD_LEASE_TTL")
    if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts < 1:
        raise BridgeRefused("BAD_MAX_ATTEMPTS")
    body: dict[str, Any] = {
        "adapter": adapter,
        "params": dict(params),
        "effect_class": effect_class,
        "max_attempts": max_attempts,
        "lease_ttl_s": lease_ttl_s,
        "idempotency_key": idempotency_key(mission_id, mint_event_id),
    }
    if timeout_s is not None:
        if isinstance(timeout_s, bool) or not isinstance(timeout_s, int) or timeout_s < 1:
            raise BridgeRefused("BAD_TIMEOUT")
        body["timeout_s"] = timeout_s
    return body


def receipt_event_fields(mission: Mapping[str, Any], *, event_id: str, created_at: str,
                         controller_record: Mapping[str, Any]) -> dict:
    """Translate a verified controller result into ledger event fields.

    ``controller_record`` carries what the controller durably recorded, e.g.
    ``{"task_id": ..., "duplicate": bool, "controller_status": int,
    "verified": bool, "outcome": "COMPLETE"|"FAILED"|"BLOCKED",
    "result_id": ..., "source_sha": ...}``. Only verified COMPLETE becomes
    FINAL/DONE; every other outcome stays owned (BLOCKED) or errors (ERROR).
    """
    if not isinstance(mission, Mapping) or not mission.get("mission_id"):
        raise BridgeRefused("BAD_MISSION")
    if not event_id or not created_at:
        raise BridgeRefused("BAD_RECEIPT_IDENTITY")
    if not isinstance(controller_record, Mapping):
        raise BridgeRefused("BAD_CONTROLLER_RECORD")
    verified = controller_record.get("verified") is True
    outcome = controller_record.get("outcome")
    task_id = controller_record.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        raise BridgeRefused("BAD_TASK_ID")
    if verified and outcome == "COMPLETE":
        event_type, status = FINAL, DONE
    elif outcome == "BLOCKED" or not verified:
        event_type, status = BLOCKED, BLOCKED
    elif outcome == "FAILED":
        event_type, status = ERROR, ERROR
    else:
        raise BridgeRefused(f"UNMAPPABLE_OUTCOME:{outcome!r}")
    evidence = {
        "task_id": task_id,
        "duplicate": bool(controller_record.get("duplicate", False)),
        "controller_status": controller_record.get("controller_status"),
        "result_id": controller_record.get("result_id"),
        "source_sha": controller_record.get("source_sha"),
        "outcome": outcome,
    }
    payload_hash = hashlib.sha256(
        json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "event_id": event_id,
        "mission_id": mission["mission_id"],
        "agent_id": mission.get("agent_id"),
        "host_id": mission.get("host_id"),
        "event_type": event_type,
        "status": status,
        "depends_on": list(mission.get("depends_on") or []),
        "head": controller_record.get("source_sha"),
        "evidence_ref": f"controller:{task_id}:{controller_record.get('result_id')}",
        "created_at": created_at,
        "payload_hash": payload_hash,
        "test_evidence": json.dumps(evidence, sort_keys=True),
    }


def next_eligible(all_missions: Mapping[str, Mapping[str, Any]], owner: str) -> list[str]:
    """Distinct ready missions for one owner: WORKING, deps DONE, owned by the
    caller or released. Sorted for a deterministic pick order."""
    ready = []
    for mission_id in sorted(all_missions):
        mission = all_missions[mission_id]
        if not isinstance(mission, Mapping):
            continue
        if _mission_status(mission) != "WORKING":
            continue
        if _mission_owner(mission) not in (None, owner):
            continue
        depends = mission.get("depends_on") or []
        if any(_mission_status(all_missions.get(d, {})) != DONE for d in depends):
            continue
        ready.append(mission_id)
    return ready
