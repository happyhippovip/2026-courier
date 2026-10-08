"""Cross-session discovery and safe claim/resume over the coordination ledger.

A fresh worker with no chat history calls ``discover_resumable`` against shared
truth (GitHub issue ledger or JSONL mirror) and then ``claim_mission``.  Claims
are idempotent (deterministic event ids) and verified by re-reading shared truth,
so two racing workers can never both become the writer.
"""
import dataclasses
import hashlib
from datetime import datetime, timezone
from typing import List, Optional

from scripts.coordination_ledger import (
    AgentID,
    CoordinationEvent,
    CoordinationReducer,
    EventType,
    HostID,
    MissionStatus,
    parse_timestamp,
)

RESUME = "RESUME"      # Our own PARTIAL/WORKING checkpoint survived a lost session.
REASSIGN = "REASSIGN"  # Mission ended in ERROR; any known worker may take it over.

CLAIMED = "CLAIMED"
CONFLICT = "CONFLICT"
NOT_RESUMABLE = "NOT_RESUMABLE"
UNKNOWN_AUTHORITY = "UNKNOWN_AUTHORITY"
WRITE_FAILED = "WRITE_FAILED"


@dataclasses.dataclass
class ResumeCheckpoint:
    mission_id: str
    mode: str
    owner: Optional[str]
    branch: Optional[str]
    head: Optional[str]
    pr: Optional[str]
    evidence_ref: Optional[str]
    test_evidence: Optional[str]
    next_action: Optional[str]
    latest_event_id: str
    updated_at: str
    depends_on: List[str]

    def to_dict(self):
        return dataclasses.asdict(self)


@dataclasses.dataclass
class ClaimResult:
    outcome: str
    mission_id: str
    event_id: Optional[str] = None
    checkpoint: Optional[ResumeCheckpoint] = None
    reason: str = ""

    def to_dict(self):
        data = dataclasses.asdict(self)
        return data


DEFAULT_LEASE_TTL_S = 1800.0  # 30 minutes


def reduce_store(store, lease_ttl_s: Optional[float] = DEFAULT_LEASE_TTL_S) -> CoordinationReducer:
    reducer = CoordinationReducer(lease_ttl_s=lease_ttl_s)
    for event in store.read_events():
        reducer.apply(event)
    return reducer


def _deps_done(reducer: CoordinationReducer, mission: dict) -> bool:
    for dep in mission.get("depends_on") or []:
        dep_m = reducer.get_mission(dep)
        if not dep_m or dep_m["status"] != MissionStatus.DONE:
            return False
    return True


def _checkpoint(mission: dict, mode: str) -> ResumeCheckpoint:
    return ResumeCheckpoint(
        mission_id=mission["mission_id"],
        mode=mode,
        owner=mission.get("ownership"),
        branch=mission.get("branch"),
        head=mission.get("head"),
        pr=mission.get("pr"),
        evidence_ref=mission.get("evidence_ref"),
        test_evidence=mission.get("test_evidence"),
        next_action=mission.get("next_action"),
        latest_event_id=mission["latest_event_id"],
        updated_at=mission["updated_at"],
        depends_on=list(mission.get("depends_on") or []),
    )


def discover_resumable(reducer: CoordinationReducer, agent_id: AgentID) -> List[ResumeCheckpoint]:
    """Missions this agent may safely continue, reconstructed only from shared truth."""
    if not isinstance(agent_id, AgentID) or agent_id == AgentID.UNKNOWN:
        return []
    found: List[ResumeCheckpoint] = []
    for mission in reducer.get_all_missions().values():
        if not _deps_done(reducer, mission):
            continue
        status = mission["status"]
        if status == MissionStatus.WORKING and mission.get("ownership") == agent_id.value:
            found.append(_checkpoint(mission, RESUME))
        elif status == MissionStatus.ERROR:
            found.append(_checkpoint(mission, REASSIGN))
        # DONE, BLOCKED (human gate) and missions owned by others are never offered.
    found.sort(key=lambda c: (c.mode != RESUME, c.updated_at, c.mission_id))
    return found


def claim_event_id(mission_id: str, base_event_id: str, agent_id: AgentID) -> str:
    """Deterministic: retrying the same claim on the same checkpoint is a no-op replay."""
    digest = hashlib.sha256(f"{mission_id}|{base_event_id}|{agent_id.value}".encode("utf-8")).hexdigest()
    return f"claim-{digest[:24]}"


def _claim_timestamp(mission: dict, now: Optional[datetime]) -> str:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    floor = parse_timestamp(mission["updated_at"])
    # Never emit a claim older than the checkpoint it builds on (host clock skew).
    if floor is not None and current < floor:
        current = floor
    return current.isoformat().replace("+00:00", "Z")


def claim_mission(
    store,
    agent_id: AgentID,
    host_id: HostID,
    mission_id: str,
    now: Optional[datetime] = None,
) -> ClaimResult:
    """Claim/resume ``mission_id`` for ``agent_id`` and verify against re-read shared truth."""
    if (
        not isinstance(agent_id, AgentID) or agent_id == AgentID.UNKNOWN
        or not isinstance(host_id, HostID) or host_id == HostID.UNKNOWN
    ):
        return ClaimResult(UNKNOWN_AUTHORITY, mission_id, reason="Unknown worker authority fails closed.")

    reducer = reduce_store(store)
    offered = {c.mission_id: c for c in discover_resumable(reducer, agent_id)}
    checkpoint = offered.get(mission_id)
    if checkpoint is None:
        mission = reducer.get_mission(mission_id)
        owner = mission.get("ownership") if mission else None
        if mission and owner and owner != agent_id.value and mission["status"] == MissionStatus.WORKING:
            return ClaimResult(CONFLICT, mission_id, reason=f"Mission owned by {owner}.")
        return ClaimResult(NOT_RESUMABLE, mission_id, reason="Mission not offered to this worker by shared truth.")

    mission = reducer.get_mission(mission_id)
    latest = next((e for e in reducer.events if e.event_id == checkpoint.latest_event_id), None)
    if (
        checkpoint.mode == RESUME
        and latest is not None
        and latest.event_id.startswith("claim-")
        and latest.agent_id == agent_id
    ):
        # Our own claim is already the newest truth: a retry must add no effect.
        return ClaimResult(CLAIMED, mission_id, event_id=latest.event_id, checkpoint=checkpoint)
    event_id = claim_event_id(mission_id, checkpoint.latest_event_id, agent_id)
    event_type = EventType.STARTED if checkpoint.mode == RESUME else EventType.ASSIGNED
    event = CoordinationEvent(
        event_id=event_id,
        mission_id=mission_id,
        agent_id=agent_id,
        host_id=host_id,
        event_type=event_type,
        status=MissionStatus.WORKING,
        depends_on=list(mission.get("depends_on") or []),
        head=mission.get("head"),
        evidence_ref=mission.get("evidence_ref") or "",
        created_at=_claim_timestamp(mission, now),
        payload_hash=hashlib.sha256(event_id.encode("utf-8")).hexdigest(),
        branch=mission.get("branch"),
        pr=mission.get("pr"),
        test_evidence=mission.get("test_evidence"),
        next_action=mission.get("next_action"),
        ownership=agent_id.value,
    )

    if event_id not in reducer.processed_event_ids:
        if not store.write_event(event):
            return ClaimResult(WRITE_FAILED, mission_id, event_id=event_id, reason="Shared ledger write failed.")

    verified = reduce_store(store).get_mission(mission_id)
    if (
        verified
        and verified.get("ownership") == agent_id.value
        and verified["status"] == MissionStatus.WORKING
        and verified["latest_event_id"] == event_id
    ):
        return ClaimResult(CLAIMED, mission_id, event_id=event_id, checkpoint=checkpoint)
    owner = verified.get("ownership") if verified else None
    return ClaimResult(CONFLICT, mission_id, event_id=event_id, reason=f"Shared truth owner after claim: {owner}.")


def reap_expired_missions(
    store,
    reaper_agent: AgentID,
    reaper_host: HostID,
    lease_ttl_s: float = DEFAULT_LEASE_TTL_S,
    now: Optional[datetime] = None,
) -> List[CoordinationEvent]:
    """Inspect shared truth and transition WORKING missions with expired leases to ERROR/CANCELLED.

    Writes a deterministic cancellation event for each expired mission, making it
    safely available for reassignment via discover_resumable / claim_mission with zero
    duplicate writers.
    """
    if (
        not isinstance(reaper_agent, AgentID) or reaper_agent == AgentID.UNKNOWN
        or not isinstance(reaper_host, HostID) or reaper_host == HostID.UNKNOWN
    ):
        return []

    reducer = reduce_store(store, lease_ttl_s=lease_ttl_s)
    curr_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    reaped_events: List[CoordinationEvent] = []

    for mission in reducer.get_all_missions().values():
        if mission["status"] != MissionStatus.WORKING:
            continue
        last_ts = parse_timestamp(mission["updated_at"])
        if last_ts is None:
            continue
        elapsed = (curr_time - last_ts).total_seconds()
        if elapsed < lease_ttl_s:
            continue

        mission_id = mission["mission_id"]
        latest_event_id = mission["latest_event_id"]
        event_id = f"reap-{mission_id}-{latest_event_id}"
        if event_id in reducer.processed_event_ids:
            continue

        cancel_event = CoordinationEvent(
            event_id=event_id,
            mission_id=mission_id,
            agent_id=reaper_agent,
            host_id=reaper_host,
            event_type=EventType.CANCELLED,
            status=MissionStatus.ERROR,
            depends_on=list(mission.get("depends_on") or []),
            head=mission.get("head"),
            evidence_ref=f"lease_expired:{int(elapsed)}s",
            created_at=curr_time.isoformat().replace("+00:00", "Z"),
            payload_hash=hashlib.sha256(event_id.encode("utf-8")).hexdigest(),
            branch=mission.get("branch"),
            pr=mission.get("pr"),
            test_evidence=mission.get("test_evidence"),
            next_action=f"Reassigned after lease expiry (idle {int(elapsed)}s)",
            ownership=None,
        )
        if store.write_event(cancel_event):
            reaped_events.append(cancel_event)

    return reaped_events

