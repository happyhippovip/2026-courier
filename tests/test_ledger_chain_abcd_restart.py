"""A->B->C->D chain over verified inputs, plus restart with no duplicate work.

Reuses the synthetic contract harness from test_ledger_bridge_verified_inputs.
Synthetic adapter only: this proves the bridge/controller contract, not a
production model run.
"""

import hashlib
import json

from scripts import ledger_v1_bridge as bridge
from scripts.github_coordination import FileCoordinationStore
from tests.test_ledger_bridge_verified_inputs import (
    _bridge, _courier_cls, _created, _event, _finals, _spec, _wait_complete,
)

CHAIN = ["A", "B", "C", "D"]


def _setup(tmp_path):
    Courier = _courier_cls()
    home, logs = tmp_path / "home", tmp_path / "logs"
    home.mkdir()
    logs.mkdir()
    courier = Courier(home, logs)
    courier.start_controller(timeout=20)
    store = FileCoordinationStore(home / "coordination_ledger.jsonl")
    specs = {}
    for i, mid in enumerate(CHAIN):
        deps = [CHAIN[i - 1]] if i else []
        store.write_event(_event(f"{mid.lower()}-assign", mid, f"2026-10-08T04:00:0{i}Z", deps=deps))
        specs[mid] = _spec(f"unit-{mid.lower()}", deps or None)
    (home / "ledger_tasks.json").write_text(json.dumps(specs), encoding="utf-8")
    return courier, home


def _state(home):
    return json.loads((home / "ledger_bridge_state.json").read_text(encoding="utf-8"))


def _tick(courier, home):
    run = _bridge(home, courier.base_url)
    assert run.returncode == 0, run.stderr + run.stdout
    return run


def _step(courier, home, mid, known):
    """Post the next mission, run it to COMPLETE, finalize it in the ledger."""
    _tick(courier, home)
    created = _created(courier)
    new = [e["task_id"] for e in created if e["task_id"] not in known.values()]
    assert len(new) == 1, (mid, new)
    known[mid] = new[0]
    assert _state(home)["missions"][mid]["task_id"] == known[mid]
    worker = courier.start_worker()
    view = _wait_complete(courier, known[mid])
    courier.stop_worker_graceful(worker, timeout=15)
    _tick(courier, home)
    return view


def _check_link(courier, home, mid, upstream, known):
    posted = courier.api.get(f"/v1/tasks/{known[mid]}", timeout=5).json()
    up = courier.api.get(f"/v1/tasks/{known[upstream]}/result", timeout=5).json()
    art = up["artifacts"][0]
    assert art["sha256"] == hashlib.sha256((home / art["path"]).read_bytes()).hexdigest()
    assert posted["params"]["inputs"] == [{
        "mission_id": upstream, "task_id": known[upstream], "result_id": up["result_id"],
        "path": art["path"], "sha256": art["sha256"],
    }]
    digest = _state(home)["missions"][mid]["inputs_digest"]
    assert digest == bridge._inputs_digest(posted["params"]["inputs"])
    final = next(e for e in _finals(home) if e.mission_id == mid)
    assert f"inputs_digest={digest}" in final.evidence_ref


def test_chain_abcd_with_restart_reuses_verified_results(tmp_path):
    courier, home = _setup(tmp_path)
    try:
        known = {}
        _step(courier, home, "A", known)
        _step(courier, home, "B", known)
        before_finals = [e.event_id for e in _finals(home)]
        assert {e.mission_id for e in _finals(home)} == {"A", "B"}

        # Restart: controller killed and started again on the same home.
        courier.kill_controller()
        courier.start_controller(timeout=20)

        # Replays after restart: A/B must not be posted or rerun.
        _tick(courier, home)
        _tick(courier, home)
        assert [e.event_id for e in _finals(home)][:2] == before_finals

        _step(courier, home, "C", known)
        _step(courier, home, "D", known)

        # Each mission posted exactly once, across the restart.
        created = _created(courier)
        assert sorted(e["task_id"] for e in created) == sorted(known.values())
        for upstream, mid in zip(CHAIN, CHAIN[1:]):
            _check_link(courier, home, mid, upstream, known)

        # Final replay is a no-op; one FINAL per mission, no duplicates.
        _tick(courier, home)
        assert len(_created(courier)) == 4
        finals = [e.mission_id for e in _finals(home)]
        assert sorted(finals) == CHAIN
    finally:
        courier.close()


def test_changed_upstream_stops_chain_downstream(tmp_path):
    courier, home = _setup(tmp_path)
    try:
        known = {}
        _step(courier, home, "A", known)
        # B is posted by A's finalize tick; run it, then tamper before C is posted.
        task_b = next(e["task_id"] for e in _created(courier) if e["task_id"] != known["A"])
        worker = courier.start_worker()
        _wait_complete(courier, task_b)
        courier.stop_worker_graceful(worker, timeout=15)
        art = courier.api.get(f"/v1/tasks/{task_b}/result", timeout=5).json()["artifacts"][0]
        (home / art["path"]).write_bytes(b"tampered")

        run = _bridge(home, courier.base_url)
        assert run.returncode == bridge.EXIT_CONFIG
        assert "input_digest_mismatch" in run.stdout
        assert len(_created(courier)) == 2
        missions = _state(home)["missions"]
        assert "C" not in missions and "D" not in missions
        assert {e.mission_id for e in _finals(home)} <= {"A", "B"}
    finally:
        courier.close()
