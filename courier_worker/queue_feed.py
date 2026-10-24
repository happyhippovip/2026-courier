"""Connect the canonical work queue to the ledger motor (one bounded pass).

courier_core.work_queue (PR #296) holds claimable workkeys with leases, and
scripts.ledger_v1_bridge (PR #267/#349) runs ledger missions on the V1
controller. Until now nothing in the runtime moved a workkey from the queue
into the ledger or released it after a verified FINAL, so a second distinct
workkey needed a human relay. ``feed_once`` is that missing link:

1. a held workkey whose mission reached FINAL_DONE is released (checkpoint);
2. a held workkey without a ledger mission gets its spec and ASSIGNED event
   (restart after claim, before assign);
3. a held, unfinished workkey has its lease renewed;
4. when the holder holds nothing, the lowest-id READY workkey that has a
   task spec is claimed and assigned.

It is opt-in (``<home>/work_queue_feed.json``), file-only, never talks to the
controller, and is idempotent: a repeated pass appends nothing new. It is not
a scheduler; LedgerTick calls it once before each bridge pass.

Leases expire, missions may not. A claim is made with ``announce`` and the
mission is ATTACHed in the shared queue before its ASSIGNED event is written,
so for another holder's expired lease:

- not attached (announced claim): nothing was handed off, take it over;
- attached: ask ``probe(item_id, attached)`` for the controller state of that
  mission. COMPLETE_VERIFIED settles the workkey, FAILED/CANCELLED frees it;
  anything else, no probe, or an error leaves it (``foreign_expired``);
- a legacy claim without ``announce`` is never taken over.

A human can always free such a workkey with ``work_queue reclaim``; the old
holder then does not pick it up again (``reclaimed_away``).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

CONFIG_NAME = "work_queue_feed.json"
DEFAULT_TTL_S = 3600


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except (json.JSONDecodeError, UnicodeDecodeError):
        _quarantine_corrupt(path)
        return default


def _quarantine_corrupt(path: Path) -> None:
    """Move an unreadable state file aside (best effort) so the next pass
    starts from the default instead of crashing again."""
    try:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path.rename(path.with_name(f"{path.name}.corrupt-{stamp}"))
    except OSError:
        pass


def _atomic_write(path: Path, data) -> None:
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, sort_keys=True, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _utc(now=None) -> str:
    moment = now or datetime.now(timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def has_open_work(home, now=None) -> bool:
    """True when the opt-in queue has a held or a READY workkey with a task spec."""
    home = Path(home)
    config = _read_json(home / CONFIG_NAME, None)
    if config is None:
        return False
    from courier_core.work_queue import WorkQueue

    holder = config["holder"]
    specs = config.get("specs") or {}
    queue = WorkQueue(items_dir=config["items_dir"], ledger_path=config["ledger"])
    if any(i.get("status") == "CLAIMED" and (i.get("lease") or {}).get("holder") == holder
           for i in queue.items(now=now)):
        return True
    return any(i["id"] in specs and _may_try(i, holder) for i in queue.list_ready(now=now))


def _may_try(item: dict, holder: str) -> bool:
    """Whether this holder could take the READY item without a probe answer."""
    if (item.get("reclaimed") or {}).get("from") == holder:
        return False
    expired = item.get("expired_lease") or {}
    if expired.get("holder") in (None, holder):
        return True
    return not item.get("attached") and bool(expired.get("announce"))


FINAL_STATES = ("COMPLETE_VERIFIED", "FAILED", "CANCELLED")


def feed_once(home, agent_id: str, host_id: str, now=None, probe=None) -> dict:
    home = Path(home)
    config = _read_json(home / CONFIG_NAME, None)
    if config is None:
        return {"outcome": "off"}

    from courier_core.work_queue import WorkQueue, WorkQueueError
    from scripts.coordination_ledger import (
        AgentID, CoordinationEvent, EventType, HostID, MissionStatus,
    )
    from scripts.coordination_resume import reduce_store
    from scripts.github_coordination import FileCoordinationStore

    holder = config["holder"]
    ttl = int(config.get("ttl_s", DEFAULT_TTL_S))
    specs = config.get("specs") or {}
    queue = WorkQueue(items_dir=config["items_dir"], ledger_path=config["ledger"])
    store = FileCoordinationStore(home / "coordination_ledger.jsonl")
    bridge_state = _read_json(home / "ledger_bridge_state.json", {"missions": {}})
    missions = bridge_state.get("missions") or {}
    report = {"outcome": "idle", "released": [], "claimed": [], "assigned": [], "renewed": [],
              "foreign_expired": [], "reconciled": [], "reclaimed_away": [], "parked": [], "lost": []}

    def assign(item_id: str) -> None:
        # Announce the hand-off in the shared queue first: a crash after this line leaves an
        # attached workkey that nobody takes over blindly; a crash before it left nothing to run.
        queue.attach(item_id, holder, f"{agent_id}/{host_id}", now=now)
        reducer = reduce_store(store)
        if reducer.get_mission(item_id) is not None:
            return
        tasks_path = home / "ledger_tasks.json"
        tasks = _read_json(tasks_path, {})
        if tasks.get(item_id) != specs[item_id]:
            tasks[item_id] = specs[item_id]
            _atomic_write(tasks_path, tasks)
        store.write_event(CoordinationEvent(
            event_id=f"queue-assign-{item_id}", mission_id=item_id,
            agent_id=AgentID(agent_id), host_id=HostID(host_id),
            event_type=EventType.ASSIGNED, status=MissionStatus.WORKING, depends_on=[],
            head="work_queue", evidence_ref=f"work_queue:{item_id}:{holder}",
            created_at=_utc(now), payload_hash="work_queue", ownership=agent_id,
        ))
        report["assigned"].append(item_id)

    held = [i for i in queue.items(now=now)
            if i.get("status") == "CLAIMED" and (i.get("lease") or {}).get("holder") == holder]
    still_held = []
    for item in held:
        item_id = item["id"]
        mapping = missions.get(item_id) or {}
        try:
            if mapping.get("status") == "FINAL_DONE":
                queue.release(item_id, holder, f"FINAL_DONE {mapping.get('task_id', '')}".strip(), now=now)
                report["released"].append(item_id)
                continue
            if mapping.get("status") in ("ERROR", "BLOCKED"):
                # The mission ended without a verified FINAL. Renewing forever would hold this
                # holder on it; park it for a human (work_queue reclaim) and take other work.
                reason = f"{mapping['status']} {mapping.get('reason') or ''} {mapping.get('task_id') or ''}"
                queue.park(item_id, holder, " ".join(reason.split())[:200], now=now)
                report["parked"].append(item_id)
                continue
            if item_id in specs:
                assign(item_id)
            queue.renew(item_id, holder, ttl, now=now)
        except WorkQueueError:
            # The lease ran out between listing and writing and another holder took it.
            report["lost"].append(item_id)
            continue
        still_held.append(item_id)
        report["renewed"].append(item_id)

    if not still_held:
        ready = queue.list_ready(now=now)
        # Our own expired, attached work first: its mission may still run and only we may resume it.
        ready.sort(key=lambda i: ((i.get("expired_lease") or {}).get("holder") != holder, i["id"]))
        for item in ready:
            if (item.get("reclaimed") or {}).get("from") == holder:
                # A human took this workkey away from us; do not quietly pick it up again.
                report["reclaimed_away"].append(item["id"])
                continue
            expired = item.get("expired_lease") or {}
            if expired.get("holder") not in (None, holder):
                # Another holder's lease expired, but its mission may still be running in another
                # home. Taking it over would assign the mission again under a new claim, i.e. a
                # second controller task. Never replay on expiry alone.
                decision = _foreign_expired(queue, item, expired, holder, probe, now)
                if decision == "settled":
                    report["reconciled"].append(item["id"])
                    continue
                if decision == "wait":
                    report["foreign_expired"].append(item["id"])
                    continue
                if decision == "freed":
                    report["reconciled"].append(item["id"])
            if item["id"] in specs:
                try:
                    queue.claim(item["id"], holder, ttl, host=host_id, now=now, announce=True)
                except WorkQueueError:                   # another home was faster: not ours
                    report["foreign_expired"].append(item["id"])
                    continue
                report["claimed"].append(item["id"])
                try:
                    assign(item["id"])
                except WorkQueueError:                   # lost before ATTACH: nothing was handed off
                    report["claimed"].remove(item["id"])
                    report["lost"].append(item["id"])
                break

    if report["released"] or report["claimed"] or report["assigned"] or report["reconciled"] or report["parked"]:
        report["outcome"] = "fed"
    return report


def _foreign_expired(queue, item, expired, holder, probe, now) -> str:
    """``take`` (never handed off), ``freed``/``settled`` (reconciled), or ``wait``."""
    attached = item.get("attached")
    if not attached:
        return "take" if expired.get("announce") else "wait"   # a legacy claim may have assigned
    if probe is None:
        return "wait"
    try:
        observed = probe(item["id"], dict(attached))
    except Exception:                                # unreachable or unclear: fail closed
        return "wait"
    if observed not in FINAL_STATES:
        return "wait"
    from courier_core.work_queue import WorkQueueError
    try:
        queue.reconcile(item["id"], observed, f"{attached['holder']} {observed}", holder, now=now)
    except WorkQueueError:                           # another home reconciled first: look again next pass
        return "wait"
    return "settled" if observed == "COMPLETE_VERIFIED" else "freed"
