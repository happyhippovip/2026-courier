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
    return any(i["id"] in specs for i in queue.list_ready(now=now))


def feed_once(home, agent_id: str, host_id: str, now=None) -> dict:
    home = Path(home)
    config = _read_json(home / CONFIG_NAME, None)
    if config is None:
        return {"outcome": "off"}

    from courier_core.work_queue import WorkQueue
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
    report = {"outcome": "idle", "released": [], "claimed": [], "assigned": [], "renewed": []}

    def assign(item_id: str) -> None:
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
        if mapping.get("status") == "FINAL_DONE":
            queue.release(item_id, holder, f"FINAL_DONE {mapping.get('task_id', '')}".strip(), now=now)
            report["released"].append(item_id)
            continue
        still_held.append(item_id)
        if item_id in specs:
            assign(item_id)
        queue.renew(item_id, holder, ttl, now=now)
        report["renewed"].append(item_id)

    if not still_held:
        for item in queue.list_ready(now=now):
            if item["id"] in specs:
                queue.claim(item["id"], holder, ttl, host=host_id, now=now)
                report["claimed"].append(item["id"])
                assign(item["id"])
                break

    if report["released"] or report["claimed"] or report["assigned"]:
        report["outcome"] = "fed"
    return report
