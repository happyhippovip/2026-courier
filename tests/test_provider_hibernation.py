import json
import pytest
from pathlib import Path
from scripts.provider_hibernation import (
    ContinuationCheckpoint,
    LaneHibernator,
    LaneState,
    Resource,
    load_continuation,
    save_continuation,
    should_hibernate,
)

def test_should_hibernate_truth_matrix():
    # 1. Local ready work remains -> Must not hibernate
    assert should_hibernate(["local-1"], ["prov-1"], circuits_open=True, fallback_available=False) is False
    # 2. No provider work waiting -> Must not hibernate
    assert should_hibernate([], [], circuits_open=True, fallback_available=False) is False
    # 3. Provider circuits still closed (available) -> Must not hibernate
    assert should_hibernate([], ["prov-1"], circuits_open=False, fallback_available=False) is False
    # 4. Authorized fallback available -> Must not hibernate
    assert should_hibernate([], ["prov-1"], circuits_open=True, fallback_available=True) is False
    # 5. Genuinely blocked: empty local, pending provider, circuits open, no fallback -> Hibernate
    assert should_hibernate([], ["prov-1"], circuits_open=True, fallback_available=False) is True

def test_lane_hibernator_resource_filtering():
    lane = LaneHibernator()
    released = []

    lane.register_resource("prov", "provider", release_hook=lambda n: released.append(n))
    lane.register_resource("watch", "watcher", release_hook=lambda n: released.append(n))
    lane.register_resource("ui", "ui", release_hook=lambda n: released.append(n))
    lane.register_resource("pty", "pty", release_hook=lambda n: released.append(n))
    lane.register_resource("desk", "human_desk", essential=True, release_hook=lambda n: released.append(n))

    cp = ContinuationCheckpoint(task_id="t-1")
    rep = lane.hibernate(cp)

    assert lane.state == LaneState.HIBERNATED
    assert "desk" in rep["retained"]
    assert "desk" not in rep["released"]
    assert set(rep["released"]) == {"prov", "watch", "ui", "pty"}
    assert released == ["prov", "watch", "ui", "pty"]

def test_release_hook_failure_fails_closed():
    lane = LaneHibernator()
    def bad_hook(name):
        raise RuntimeError("cannot release pty")

    lane.register_resource("pty", "pty", release_hook=bad_hook)
    cp = ContinuationCheckpoint(task_id="t-1")
    rep = lane.hibernate(cp)

    # State must remain ACTIVE because release failed
    assert lane.state == LaneState.ACTIVE
    assert "pty" in rep["failed"]

def test_resume_flow_and_reacquire():
    lane = LaneHibernator()
    reacquired = []

    lane.register_resource(
        "pty",
        "pty",
        release_hook=lambda n: None,
        reacquire_hook=lambda n: reacquired.append(n),
    )
    cp = ContinuationCheckpoint(task_id="t-1")
    lane.hibernate(cp)
    assert lane.state == LaneState.HIBERNATED

    resumed_cp = lane.resume()
    assert resumed_cp.task_id == "t-1"
    assert lane.state == LaneState.ACTIVE
    assert reacquired == ["pty"]
    assert lane.resources["pty"].released is False

def test_resume_failures():
    lane = LaneHibernator()
    # Cannot resume active lane
    with pytest.raises(RuntimeError, match="not HIBERNATED"):
        lane.resume()

    lane.state = LaneState.HIBERNATED
    # Cannot resume without checkpoint
    with pytest.raises(RuntimeError, match="no checkpoint"):
        lane.resume()

    # Reacquire hook failure aborts resume
    def fail_reacquire(n):
        raise RuntimeError("lock failed")
    lane.register_resource("pty", "pty", reacquire_hook=fail_reacquire)
    lane.resources["pty"].released = True
    lane.checkpoint = ContinuationCheckpoint(task_id="t-1")

    with pytest.raises(RuntimeError, match="lock failed"):
        lane.resume()
    assert lane.resources["pty"].released is True

def test_continuation_checkpoint_from_dict_resilience():
    # Non-dict inputs
    assert isinstance(ContinuationCheckpoint.from_dict(None), ContinuationCheckpoint)
    assert isinstance(ContinuationCheckpoint.from_dict([]), ContinuationCheckpoint)

    # Valid data
    data = {
        "project": "Courier",
        "task_id": "test-task",
        "attempt": 3,
        "completed_fingerprints": ["fp1", "fp2"],
        "extra_unknown_field": "ignored",
    }
    cp = ContinuationCheckpoint.from_dict(data)
    assert cp.task_id == "test-task"
    assert cp.attempt == 3
    assert cp.completed_fingerprints == ["fp1", "fp2"]

def test_lane_hibernator_serialization_roundtrip():
    lane = LaneHibernator()
    lane.register_resource("pty", "pty")
    cp = ContinuationCheckpoint(task_id="t-99", attempt=2)
    lane.hibernate(cp)

    d = lane.to_dict()
    assert d["state"] == "HIBERNATED"
    assert d["checkpoint"]["task_id"] == "t-99"

    restored = LaneHibernator.from_dict(d)
    assert restored.state == LaneState.HIBERNATED
    assert restored.checkpoint.task_id == "t-99"
    assert "pty" in restored.resources
    assert restored.resources["pty"].released is True

    # Bad state falls back to ACTIVE safely
    bad_dict = {"state": "INVALID_STATE"}
    assert LaneHibernator.from_dict(bad_dict).state == LaneState.ACTIVE
    assert LaneHibernator.from_dict(None).state == LaneState.ACTIVE

def test_save_and_load_continuation(tmp_path):
    target = tmp_path / "subdir" / "state.json"
    payload = {"lane": {"state": "HIBERNATED"}, "version": 1}

    save_continuation(target, payload)
    assert target.is_file()

    loaded = load_continuation(target)
    assert loaded == payload

    # Nonexistent file returns empty dict
    assert load_continuation(tmp_path / "missing.json") == {}

    # Corrupted file returns empty dict (fails closed)
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{invalid json", encoding="utf-8")
    assert load_continuation(corrupt) == {}
