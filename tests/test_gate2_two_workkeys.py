"""Gate 2: two distinct queue workkeys run one after the other, no human relay.

Queue (#296) -> queue_feed claim + ASSIGNED -> LedgerTick (#349) -> bridge
(#267) -> controller -> synthetic worker -> result -> FINAL -> queue release
(checkpoint) -> claim of the second workkey -> result B -> worker restart
without a second effect.

The synthetic adapter is the contract proof, not a provider: no paid model
call. It does not prove a production provider run (Gate 3).
"""

import hashlib
import importlib.util
import json
import time
from collections import Counter
from pathlib import Path

from courier_core.events import effect_key
from courier_core.work_queue import WorkQueue
from courier_worker.queue_feed import feed_once
from scripts.coordination_ledger import EventType
from scripts.coordination_resume import reduce_store
from scripts.github_coordination import FileCoordinationStore

REPO = Path(__file__).resolve().parents[1]
AGENT = "GOOGLE_WINDOWS"
HOST = "WINDOWS_REMOTE"
HOLDER = "worker-gate2"
GOAL_ID = "goal.gate2.two"
GOAL_FP = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
TICK_INTERVAL_S = 1.0
TIMEOUT_S = 120.0


def _courier_cls():
    path = REPO / "tests" / "golden" / "golden_harness.py"
    spec = importlib.util.spec_from_file_location("gate2_golden_harness", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Courier


def _item(item_id, deps):
    return {"id": item_id, "title": f"synthetic {item_id}", "lane": "L1",
            "branch": f"lane/L1-{item_id.lower()}", "files_scope": [f"out/{item_id}/"],
            "depends_on": deps, "acceptance": ["synthetic artifact"], "provider_hints": [],
            "status": "READY", "lease": None}


def _spec(unit):
    return {"adapter": "synthetic",
            "params": {"sleep_s": 0, "write": "out.txt", "content": unit, "hang": False,
                       "fail_transient_n": 0, "fault_attempts": [1]},
            "effect_class": "idempotent", "max_attempts": 2, "lease_ttl_s": 10,
            "estimated_cost_eur": 0.0,
            "goal_id": GOAL_ID, "goal_fingerprint": GOAL_FP}


def _setup_queue(tmp_path, home):
    items = tmp_path / "items"
    items.mkdir()
    (items / "WKA.json").write_text(json.dumps(_item("WKA", [])), encoding="utf-8")
    (items / "WKB.json").write_text(json.dumps(_item("WKB", ["WKA"])), encoding="utf-8")
    ledger = tmp_path / "queue.jsonl"
    (home / "work_queue_feed.json").write_text(json.dumps({
        "items_dir": str(items), "ledger": str(ledger), "holder": HOLDER, "ttl_s": 600,
        "specs": {"WKA": _spec("unit-a"), "WKB": _spec("unit-b")},
    }), encoding="utf-8")
    return WorkQueue(items_dir=items, ledger_path=ledger), ledger


def _queue_events(ledger):
    if not ledger.exists():
        return []
    return [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line]


def _finals(home):
    reducer = reduce_store(FileCoordinationStore(home / "coordination_ledger.jsonl"))
    return [e for e in reducer.events if e.event_type == EventType.FINAL]


def _state(home):
    path = home / "ledger_bridge_state.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"missions": {}}


def _wait(courier, predicate, what):
    deadline = time.monotonic() + TIMEOUT_S
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.2)
    raise AssertionError(f"timed out waiting for {what}\n" + courier.log_tail("controller.log")
                         + "\n" + "\n".join(courier.log_tail(f"worker-{i}.log")
                                            for i in range(len(courier.workers))))


def _start_worker(courier):
    worker = courier._spawn(
        ["courier_worker.host", "--home", str(courier.home), "--controller", courier.base_url,
         "--max-tasks", "1", "--heartbeat", "0.5",
         "--ledger-agent-id", AGENT, "--ledger-host-id", HOST,
         "--ledger-tick-interval", str(TICK_INTERVAL_S), "--ledger-tick-timeout", "60"],
        f"worker-{len(courier.workers)}.log", new_group=True)
    courier.workers.append(worker)
    return worker


def test_feed_once_is_idempotent_and_waits_for_final(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    queue, ledger = _setup_queue(tmp_path, home)
    first = feed_once(home, AGENT, HOST)
    assert first["claimed"] == ["WKA"] and first["assigned"] == ["WKA"]
    claims = [e for e in _queue_events(ledger) if e["type"] == "CLAIM"]
    again = feed_once(home, AGENT, HOST)
    assert again["claimed"] == [] and again["assigned"] == [] and again["renewed"] == ["WKA"]
    assert [e for e in _queue_events(ledger) if e["type"] == "CLAIM"] == claims
    assert json.loads((home / "ledger_tasks.json").read_text())["WKA"] == _spec("unit-a")
    assert "WKB" not in json.loads((home / "ledger_tasks.json").read_text())
    reducer = reduce_store(FileCoordinationStore(home / "coordination_ledger.jsonl"))
    assert reducer.get_mission("WKA") is not None and reducer.get_mission("WKB") is None
    # A mission that is not FINAL_DONE is never released.
    assert not [e for e in _queue_events(ledger) if e["type"] == "RELEASE"]


def test_feed_is_off_without_config(tmp_path):
    assert feed_once(tmp_path, AGENT, HOST) == {"outcome": "off"}


def test_two_distinct_workkeys_then_restart_without_double_effect(tmp_path):
    home, logs = tmp_path / "home", tmp_path / "logs"
    home.mkdir()
    logs.mkdir()
    queue, ledger = _setup_queue(tmp_path, home)
    courier = _courier_cls()(home, logs)
    try:
        courier.start_controller(timeout=30)
        _start_worker(courier)

        def done():
            items = {i["id"]: i for i in queue.items()}
            missions = _state(home)["missions"]
            return (all(items[k]["status"] == "DONE" for k in ("WKA", "WKB"))
                    and all(missions.get(k, {}).get("status") == "FINAL_DONE" for k in ("WKA", "WKB")))

        _wait(courier, done, "WKA and WKB DONE in queue and FINAL_DONE in ledger")

        # Order: claim A, release A (checkpoint), only then claim B, release B.
        seq = [(e["type"], e["item_id"]) for e in _queue_events(ledger) if e["type"] in ("CLAIM", "RELEASE")]
        assert seq == [("CLAIM", "WKA"), ("RELEASE", "WKA"), ("CLAIM", "WKB"), ("RELEASE", "WKB")], seq

        created = [e for e in courier.all_events() if e["type"] == "TASK_CREATED"]
        task_ids = [e["task_id"] for e in created]
        assert len(task_ids) == 2 and len(set(task_ids)) == 2
        assert len({effect_key(t) for t in task_ids}) == 2
        for task_id in task_ids:
            types = Counter(e["type"] for e in courier.task_events(task_id))
            assert types["RESULT_ACCEPTED"] == 1 and types["TASK_COMPLETE"] == 1, (task_id, types)
        missions = _state(home)["missions"]
        for mission, unit in (("WKA", "unit-a"), ("WKB", "unit-b")):
            digest = hashlib.sha256(unit.encode()).hexdigest()
            ready = [json.loads(e["payload"]) for e in courier.task_events(missions[mission]["task_id"])
                     if e["type"] == "RESULT_READY"]
            assert any(a.get("sha256") == digest for p in ready for a in p.get("artifacts", [])), ready
        assert sorted(e.mission_id for e in _finals(home)) == ["WKA", "WKB"]

        # Restart: hard kill, new worker, several ticks. Nothing new may happen.
        before_queue = _queue_events(ledger)
        before_events = len(created)
        before_finals = len(_finals(home))
        courier.kill_worker()
        _start_worker(courier)
        time.sleep(TICK_INTERVAL_S * 6)
        assert feed_once(home, AGENT, HOST)["outcome"] == "idle"
        assert _queue_events(ledger) == before_queue
        assert len([e for e in courier.all_events() if e["type"] == "TASK_CREATED"]) == before_events
        assert len(_finals(home)) == before_finals
        for task_id in task_ids:
            types = Counter(e["type"] for e in courier.task_events(task_id))
            assert types["RESULT_ACCEPTED"] == 1 and types["TASK_COMPLETE"] == 1, (task_id, types)
    finally:
        courier.close()
