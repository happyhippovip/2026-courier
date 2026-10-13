"""Physical snapshots must take human_relay_count from continuity_metrics."""

import json
from pathlib import Path


def test_sources_have_no_literal_relay_zero():
    for rel in ("scripts/run_physical.py", "scripts/run_physical_restart.py"):
        text = Path(rel).read_text(encoding="utf-8")
        assert '"human_relay_count": 0' not in text
        assert "human_relay_counter(" in text


def test_relay_counter_classifies_events():
    import scripts.run_physical as physical
    import scripts.run_physical_restart as restart

    assert physical.human_relay_counter([]) is None
    assert physical.human_relay_counter([{"kind": "human_relay", "actor": "human"}]) == 1
    assert physical.human_relay_counter([{"kind": "worker"}]) == 0
    assert restart.human_relay_counter([{"kind": "effect_confirmed", "actor": "human"}]) == 0
    assert restart.human_relay_counter([{"kind": "paste", "actor": "human"}]) == 1


def _run1(tmp_path, snapshot):
    evidence = tmp_path / "run1" / "evidence"
    evidence.mkdir(parents=True)
    (evidence / "run1_exit_code.txt").write_text("0\nSUCCESS\n", encoding="utf-8")
    data = dict(snapshot)
    data.setdefault("initial_state", {"process_a_status": "COMPLETE"})
    (evidence / "run1_state_snapshot.json").write_text(json.dumps(data), encoding="utf-8")
    return tmp_path / "run1"


def test_run2_snapshot_leaves_relay_unmeasured_without_events(tmp_path):
    import scripts.run_physical_restart as restart

    run1 = _run1(tmp_path, {"final_status": "SUCCESS", "candidate_sha": "abc123"})
    evidence = tmp_path / "run2"
    assert restart.execute_run2("abc123", str(run1), str(evidence)) == 0
    snapshot = json.loads((evidence / "run2_state_snapshot.json").read_text(encoding="utf-8"))
    assert snapshot["execution_counters"]["human_relay_count"] is None
    assert snapshot["execution_counters"]["process_a"] == 0


def test_run2_snapshot_counts_a_classified_relay(tmp_path):
    import scripts.run_physical_restart as restart

    run1 = _run1(tmp_path, {
        "final_status": "SUCCESS",
        "candidate_sha": "abc123",
        "human_events": [{"kind": "paste", "actor": "human"}],
    })
    evidence = tmp_path / "run2"
    assert restart.execute_run2("abc123", str(run1), str(evidence)) == 0
    snapshot = json.loads((evidence / "run2_state_snapshot.json").read_text(encoding="utf-8"))
    assert snapshot["execution_counters"]["human_relay_count"] == 1
