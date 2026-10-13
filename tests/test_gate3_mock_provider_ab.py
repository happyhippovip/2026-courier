"""Gate 3 PRE-STAGE (MOCK): A -> B without a human through the real worker and
the real provider_exec path, with a MOCK provider CLI.

THIS IS NOT A GATE 3 PASS. The provider binary is a local Python script that
imitates ``muse exec --prompt-file F``; no model is called and nothing is
paid. It proves the wiring queue -> ledger -> bridge -> controller -> worker
-> adapter_runner -> provider_exec -> provider_output.txt -> controller
verifier -> FINAL -> next workkey, and measures HUMAN_RELAY_COUNT. Gate 3
still needs the same run with a real provider (plan section 8).
"""

import hashlib
import json
import os
import stat
import sys
import time
from collections import Counter
from pathlib import Path

from courier_core.work_queue import WorkQueue
from tests.test_gate2_two_workkeys import (
    AGENT, HOST, _courier_cls, _finals, _item, _queue_events, _start_worker, _state, _wait,
)

MOCK_MARKER = "MOCK_PROVIDER_NOT_A_MODEL"
RUNTIME_EVENT_PREFIXES = ("queue-assign-", "claim-", "started-", "final-", "partial-", "blocked-", "queue-resume-")

MOCK_CLI = f'''#!{sys.executable}
"""Mock muse CLI. Not a model. Echoes a deterministic digest of the prompt."""
import hashlib, sys
args = sys.argv[1:]
assert args[0] == "exec" and args[1] == "--prompt-file", args
for bad in ("--yolo", "--disable-sandbox", "--disable-approval", "--sandbox-network"):
    assert bad not in args, bad
prompt = open(args[2], encoding="utf-8").read()
digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
with open(__file__ + ".calls", "a", encoding="utf-8") as fh:
    fh.write(digest + "\\n")
print("{MOCK_MARKER} prompt_sha256=" + digest)
'''


def _spec(prompt):
    return {"adapter": "provider_exec",
            "params": {"provider": "muse", "prompt": prompt, "timeout_s": 60},
            "effect_class": "idempotent", "max_attempts": 1, "lease_ttl_s": 30}


def test_mock_provider_a_then_b_zero_human_relay(tmp_path, monkeypatch):
    mock = tmp_path / "mock_muse.py"
    mock.write_text(MOCK_CLI, encoding="utf-8")
    mock.chmod(mock.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("COURIER_PROVIDER_MUSE_BIN", str(mock))

    home, logs = tmp_path / "home", tmp_path / "logs"
    home.mkdir()
    logs.mkdir()
    items = tmp_path / "items"
    items.mkdir()
    (items / "WKA.json").write_text(json.dumps(_item("WKA", [])), encoding="utf-8")
    (items / "WKB.json").write_text(json.dumps(_item("WKB", ["WKA"])), encoding="utf-8")
    ledger = tmp_path / "queue.jsonl"
    prompts = {"WKA": "mock task A: say A", "WKB": "mock task B: say B"}
    (home / "work_queue_feed.json").write_text(json.dumps({
        "items_dir": str(items), "ledger": str(ledger), "holder": "worker-gate3", "ttl_s": 600,
        "specs": {k: _spec(v) for k, v in prompts.items()}}), encoding="utf-8")
    queue = WorkQueue(items_dir=items, ledger_path=ledger)

    courier = _courier_cls()(home, logs)
    human_relays = 0                      # incremented for every test action after start
    try:
        courier.start_controller(timeout=30)
        _start_worker(courier)            # last setup action; from here on: observe only

        def done():
            states = {i["id"]: i["status"] for i in queue.items()}
            missions = _state(home)["missions"]
            return (all(states[k] == "DONE" for k in prompts)
                    and all(missions.get(k, {}).get("status") == "FINAL_DONE" for k in prompts))

        _wait(courier, done, "WKA and WKB DONE via mock provider")

        # Measure HUMAN_RELAY_COUNT from the evidence, not from the test's word.
        created = [e for e in courier.all_events() if e["type"] == "TASK_CREATED"]
        assert len(created) == 2
        # A task counts as a human relay unless the bridge derived it from a
        # ledger claim; a ledger event counts unless the runtime wrote it.
        bridge_tasks = {m["task_id"] for m in _state(home)["missions"].values()}
        foreign_tasks = [e["task_id"] for e in created if e["task_id"] not in bridge_tasks]
        coord = [json.loads(l) for l in (home / "coordination_ledger.jsonl").read_text().splitlines()]
        foreign_events = [e["event_id"] for e in coord if not e["event_id"].startswith(RUNTIME_EVENT_PREFIXES)]
        measured = human_relays + len(foreign_tasks) + len(foreign_events)

        # Real provider_exec path: mock CLI called exactly twice, once per prompt.
        calls = (Path(str(mock) + ".calls")).read_text().split()
        assert sorted(calls) == sorted(hashlib.sha256(p.encode()).hexdigest() for p in prompts.values()), calls
        missions = _state(home)["missions"]
        for mission_id in prompts:
            task_id = missions[mission_id]["task_id"]
            types = Counter(e["type"] for e in courier.task_events(task_id))
            assert types["RESULT_ACCEPTED"] == 1 and types["TASK_COMPLETE"] == 1, (mission_id, types)
            ready = [json.loads(e["payload"]) for e in courier.task_events(task_id) if e["type"] == "RESULT_READY"]
            names = [a["path"] for p in ready for a in p.get("artifacts", [])]
            assert any(n.endswith("provider_output.txt") for n in names), names
        assert sorted(e.mission_id for e in _finals(home)) == ["WKA", "WKB"]
        seq = [(e["type"], e["item_id"]) for e in _queue_events(ledger) if e["type"] in ("CLAIM", "RELEASE")]
        assert seq == [("CLAIM", "WKA"), ("RELEASE", "WKA"), ("CLAIM", "WKB"), ("RELEASE", "WKB")]

        receipt = {"gate": "3", "status": "PRE_STAGE_MOCK_ONLY_NOT_GATE3_PASS",
                   "provider": "MOCK muse CLI (local script, no model, no cost)",
                   "HUMAN_RELAY_COUNT": measured, "foreign_events": foreign_events, "foreign_tasks": foreign_tasks,
                   "mock_calls": len(calls), "tasks": len(created)}
        out = Path(os.environ.get("GATE3_MOCK_RECEIPT", tmp_path / "gate3_mock_receipt.json"))
        out.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
        assert receipt["HUMAN_RELAY_COUNT"] == 0, receipt
        assert receipt["status"] != "PASS"
    finally:
        courier.close()
