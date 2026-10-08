import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from scripts.provider_hibernation import (
    ContinuationCheckpoint,
    LaneHibernator,
    LaneState,
    Resource,
    save_continuation,
    should_hibernate,
)


def test_should_hibernate_rules():
    # 1. Never hibernate while LOCAL_READY work remains
    assert should_hibernate(
        open_local_units=["unit-local-1"],
        open_provider_units=["unit-prov-1"],
        circuits_open=True,
        fallback_available=False,
    ) is False

    # 2. Never hibernate if no open provider units exist
    assert should_hibernate(
        open_local_units=[],
        open_provider_units=[],
        circuits_open=True,
        fallback_available=False,
    ) is False

    # 3. Never hibernate if any provider circuit still admits traffic (circuits_open=False)
    assert should_hibernate(
        open_local_units=[],
        open_provider_units=["unit-prov-1"],
        circuits_open=False,
        fallback_available=False,
    ) is False

    # 4. Never hibernate if an authorized fallback is available
    assert should_hibernate(
        open_local_units=[],
        open_provider_units=["unit-prov-1"],
        circuits_open=True,
        fallback_available=True,
    ) is False

    # 5. Genuinely quota-blocked: no local units, open provider units, circuits open, no fallback
    assert should_hibernate(
        open_local_units=[],
        open_provider_units=["unit-prov-1"],
        circuits_open=True,
        fallback_available=False,
    ) is True


def test_lane_hibernator_resource_filtering_and_lifecycle():
    hibernator = LaneHibernator()

    released_events = []
    reacquired_events = []

    def on_release(name):
        released_events.append(name)

    def on_reacquire(name):
        reacquired_events.append(name)

    # Register resources
    hibernator.register_resource("claude_session", "provider", essential=False, release_hook=on_release, reacquire_hook=on_reacquire)
    hibernator.register_resource("fs_watcher", "watcher", essential=False, release_hook=on_release, reacquire_hook=on_reacquire)
    hibernator.register_resource("human_desk_token", "human_desk", essential=True, release_hook=on_release, reacquire_hook=on_reacquire)
    hibernator.register_resource("terminal_ui", "ui", essential=False, release_hook=on_release, reacquire_hook=on_reacquire)

    cp = ContinuationCheckpoint(
        task_id="task-hibernate-42",
        repo_sha="abc12345",
        branch="lane/L2-provider",
        open_provider_units=["P101", "P102"],
    )

    persisted = []
    def mock_persist():
        persisted.append(True)

    report = hibernator.hibernate(cp, persist=mock_persist)

    assert hibernator.state == LaneState.HIBERNATED
    assert len(persisted) == 2  # Persisted before and after releasing
    assert "claude_session" in report["released"]
    assert "fs_watcher" in report["released"]
    assert "terminal_ui" in report["released"]
    assert "human_desk_token" in report["retained"]
    assert report["checkpoint_tasks"] == ["task-hibernate-42"]

    # Verify hooks called
    assert "claude_session" in released_events
    assert "human_desk_token" not in released_events

    # Resume lifecycle
    resumed_cp = hibernator.resume()
    assert hibernator.state == LaneState.ACTIVE
    assert resumed_cp.task_id == "task-hibernate-42"
    assert "claude_session" in reacquired_events
    assert "fs_watcher" in reacquired_events


def test_lane_hibernator_release_hook_failure_stays_active():
    hibernator = LaneHibernator()

    def faulty_release(name):
        raise RuntimeError("failed to close connection")

    hibernator.register_resource("bad_conn", "provider", essential=False, release_hook=faulty_release)

    cp = ContinuationCheckpoint(task_id="task-fail-1")
    report = hibernator.hibernate(cp)

    # Failed release aborts full transition to HIBERNATED to prevent leaking orphaned resources
    assert hibernator.state == LaneState.ACTIVE
    assert "bad_conn" in report["failed"]


def test_continuation_checkpoint_roundtrip_dict():
    cp = ContinuationCheckpoint(
        task_id="task-rt-99",
        workkey="WKEY-999",
        repo_sha="feedface",
        completed_fingerprints=["fp1", "fp2"],
        next_units=["unit1"],
    )

    data = cp.to_dict()
    restored = ContinuationCheckpoint.from_dict(data)

    assert restored.task_id == "task-rt-99"
    assert restored.workkey == "WKEY-999"
    assert restored.repo_sha == "feedface"
    assert restored.completed_fingerprints == ["fp1", "fp2"]
    assert restored.next_units == ["unit1"]


def test_lane_hibernator_serialization_roundtrip():
    hibernator = LaneHibernator()
    hibernator.register_resource("socket1", "pty", essential=False)
    hibernator.register_resource("desk1", "human_desk", essential=True)

    cp = ContinuationCheckpoint(task_id="task-serialize-1")
    hibernator.hibernate(cp)

    data = hibernator.to_dict()
    restored = LaneHibernator.from_dict(data)

    assert restored.state == LaneState.HIBERNATED
    assert restored.checkpoint.task_id == "task-serialize-1"
    assert "socket1" in restored.resources
    assert restored.resources["socket1"].released is True
    assert restored.resources["desk1"].released is False


def test_save_continuation_atomic_fsync(tmp_path):
    target_file = tmp_path / "checkpoints" / "lane_state.json"
    payload = {"status": "HIBERNATED", "tokens": 42}

    save_continuation(target_file, payload)

    assert target_file.exists()
    loaded = json.loads(target_file.read_text(encoding="utf-8"))
    assert loaded == payload
