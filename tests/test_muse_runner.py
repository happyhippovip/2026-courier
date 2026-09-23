import json
import os
import sys
import time
from pathlib import Path
import pytest

from pre_courier_muse.muse_runner import (
    compute_fingerprint,
    load_json,
    save_json,
    resolve_output_path,
    acquire_lock,
    release_lock,
    is_another_instance_running,
    run_muse_cycle,
)


def test_compute_fingerprint_deterministic():
    task = {
        "objective": "Courier competitor delta research",
        "output_path": "research_a.md",
        "input_refs": "",
    }
    # Expected SHA256 from existing queue task A
    fp = compute_fingerprint(task)
    assert fp == "360c31ef9f053223b208e021c6e9ee52306c0c0f50d234ad107abb8e5e654a4e"


def test_load_json_missing_file(tmp_path):
    missing = tmp_path / "missing.json"
    assert load_json(missing, {"default": 1}) == {"default": 1}


def test_load_json_valid_file(tmp_path):
    valid = tmp_path / "valid.json"
    valid.write_text('{"status": "ok"}', encoding="utf-8")
    assert load_json(valid, {}) == {"status": "ok"}


def test_load_json_corrupt_file_quarantine(tmp_path):
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{ broken json ...", encoding="utf-8")
    loaded = load_json(corrupt, {"repaired": True})
    assert loaded == {"repaired": True}
    # Check that corrupt file was quarantined
    corrupt_files = list(tmp_path.glob("corrupt.json.corrupt.*"))
    assert len(corrupt_files) == 1
    assert corrupt_files[0].read_text(encoding="utf-8") == "{ broken json ..."


def test_save_json_atomic(tmp_path):
    target = tmp_path / "nested" / "state.json"
    save_json(target, {"key": "value"})
    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8")) == {"key": "value"}


def test_resolve_output_path_safe(tmp_path):
    safe = resolve_output_path(tmp_path, "sub/dir/output.md")
    assert safe == (tmp_path / "sub/dir/output.md").resolve()


def test_resolve_output_path_traversal_refused(tmp_path):
    with pytest.raises(ValueError, match="Scope escape"):
        resolve_output_path(tmp_path, "../../etc/passwd")


def test_acquire_and_release_lock(tmp_path):
    lock_file = tmp_path / "test.lock"
    fd1 = acquire_lock(lock_file)
    assert fd1 is not None

    # Second acquire should fail
    fd2 = acquire_lock(lock_file)
    assert fd2 is None

    # Release and acquire again
    release_lock(fd1)
    fd3 = acquire_lock(lock_file)
    assert fd3 is not None
    release_lock(fd3)


def test_run_muse_cycle_success(tmp_path):
    q_file = tmp_path / "queue.json"
    cp_file = tmp_path / "checkpoint.json"
    out_file = tmp_path / "out.md"

    tasks = [
        {
            "task_id": "test-1",
            "objective": "test objective",
            "output_path": "out.md",
            "status": "QUEUED",
        }
    ]
    save_json(q_file, tasks)
    save_json(cp_file, {"completed_fingerprints": []})

    # Mock runner python script
    mock_script = tmp_path / "mock_agy.py"
    mock_script.write_text(
        'import sys\nprint(\'{"sources": ["test_src"], "material_findings": "Found test evidence", "recommended_action": "Proceed"}\')\n',
        encoding="utf-8",
    )

    runner_cmd = [sys.executable, str(mock_script)]
    processed = run_muse_cycle(
        queue_path=q_file,
        checkpoint_path=cp_file,
        runner_cmd=runner_cmd,
        base_dir=tmp_path,
        timeout=10,
    )
    assert processed == 1

    updated_queue = load_json(q_file, [])
    assert updated_queue[0]["status"] == "COMPLETED"
    assert updated_queue[0]["material_findings"] == "Found test evidence"
    assert updated_queue[0]["sources"] == ["test_src"]

    cp = load_json(cp_file, {})
    assert updated_queue[0]["fingerprint"] in cp["completed_fingerprints"]
    assert out_file.exists()


def test_run_muse_cycle_skip_duplicate(tmp_path):
    q_file = tmp_path / "queue.json"
    cp_file = tmp_path / "checkpoint.json"

    task = {
        "task_id": "test-dup",
        "objective": "test objective",
        "output_path": "out.md",
        "status": "QUEUED",
    }
    fp = compute_fingerprint(task)
    save_json(q_file, [task])
    save_json(cp_file, {"completed_fingerprints": [fp]})

    processed = run_muse_cycle(
        queue_path=q_file,
        checkpoint_path=cp_file,
        base_dir=tmp_path,
        timeout=10,
    )
    assert processed == 1

    updated_queue = load_json(q_file, [])
    assert updated_queue[0]["status"] == "SKIPPED_DUPLICATE"


def test_run_muse_cycle_timeout_handling(tmp_path):
    q_file = tmp_path / "queue.json"
    cp_file = tmp_path / "checkpoint.json"

    tasks = [
        {
            "task_id": "test-slow",
            "objective": "slow objective",
            "output_path": "out_slow.md",
            "status": "QUEUED",
        }
    ]
    save_json(q_file, tasks)
    save_json(cp_file, {"completed_fingerprints": []})

    mock_script = tmp_path / "mock_sleep.py"
    mock_script.write_text("import time\ntime.sleep(5)\n", encoding="utf-8")

    runner_cmd = [sys.executable, str(mock_script)]
    processed = run_muse_cycle(
        queue_path=q_file,
        checkpoint_path=cp_file,
        runner_cmd=runner_cmd,
        base_dir=tmp_path,
        timeout=1,
    )
    assert processed == 1

    updated_queue = load_json(q_file, [])
    assert updated_queue[0]["status"] == "TIMEOUT"
    assert "timed out after 1s" in updated_queue[0]["error"]
