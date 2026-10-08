import json
import pytest
from pathlib import Path
from courier_worker.host import (
    ContainmentError,
    ExecutionSpec,
    MAX_ARGV,
    MAX_ARGV_BYTES,
    MAX_ARTIFACTS,
    MAX_HEARTBEAT_S,
    MAX_TIMEOUT_S,
    MIN_HEARTBEAT_S,
    OUTBOX_CAP,
    OutboxFull,
    SpecError,
    collect_artifacts,
    outbox_read_all,
    outbox_remove,
    outbox_write,
    write_crash_report,
)

def make_spec(**kwargs):
    base = {
        "task_id": "t-1",
        "attempt": 1,
        "dispatch_id": "dsp-1",
        "worker_id": "w-1",
        "result_id": "res-1",
        "argv": ("python", "-c", "print(1)"),
        "timeout_s": 10.0,
        "lease_ttl_s": 30.0,
        "artifact_dir": "/tmp/art",
        "heartbeat_s": 1.0,
    }
    base.update(kwargs)
    return ExecutionSpec(**base)

def test_execution_spec_validation_bounds():
    # Attempt bounds
    with pytest.raises(SpecError, match="attempt must be an integer >= 1"):
        make_spec(attempt=0)
    with pytest.raises(SpecError, match="attempt must be an integer >= 1"):
        make_spec(attempt=True)  # bool is not allowed

    # Timeout bounds
    with pytest.raises(SpecError, match="timeout_s must be within"):
        make_spec(timeout_s=0.0)
    with pytest.raises(SpecError, match="timeout_s must be within"):
        make_spec(timeout_s=MAX_TIMEOUT_S + 1.0)

    # Lease TTL bounds
    with pytest.raises(SpecError, match="lease_ttl_s must be >= 1"):
        make_spec(lease_ttl_s=0.5)

    # Heartbeat bounds
    with pytest.raises(SpecError, match="heartbeat_s must be within"):
        make_spec(heartbeat_s=MIN_HEARTBEAT_S - 0.1)
    with pytest.raises(SpecError, match="heartbeat_s must be within"):
        make_spec(heartbeat_s=MAX_HEARTBEAT_S + 1.0)

    # String identifiers max length 200
    with pytest.raises(SpecError, match="task_id must be a non-empty string"):
        make_spec(task_id="x" * 201)
    with pytest.raises(SpecError, match="task_id must be a non-empty string"):
        make_spec(task_id="")

def test_execution_spec_argv_limits():
    # Exceeding MAX_ARGV
    with pytest.raises(SpecError, match="argv must be a non-empty argument list"):
        make_spec(argv=tuple("arg" for _ in range(MAX_ARGV + 1)))

    # Empty string inside argv
    with pytest.raises(SpecError, match="argv entries must be non-empty strings"):
        make_spec(argv=("python", ""))

    # Exceeding MAX_ARGV_BYTES
    huge_arg = "a" * (MAX_ARGV_BYTES + 1)
    with pytest.raises(SpecError, match="argv exceeds size bound"):
        make_spec(argv=(huge_arg,))

def test_collect_artifacts_limits(tmp_path):
    art_dir = tmp_path / "artifacts"
    art_dir.mkdir()
    
    # Non-existent dir returns ()
    assert collect_artifacts(str(tmp_path / "non_existent")) == ()

    # Creating MAX_ARTIFACTS + 1 (65) files raises ContainmentError
    for i in range(MAX_ARTIFACTS + 1):
        (art_dir / f"file_{i:02d}.txt").write_text("hello")
    with pytest.raises(ContainmentError, match="artifact set exceeds bounds"):
        collect_artifacts(str(art_dir))

def test_outbox_operations_and_cap(tmp_path):
    home = str(tmp_path)
    # Empty outbox
    assert outbox_read_all(home) == []

    # Write a payload
    payload = {"dispatch_id": "dsp-100", "task_id": "t-1", "result": "ok"}
    path = outbox_write(home, payload)
    assert path.exists()
    
    items = outbox_read_all(home)
    assert len(items) == 1
    assert items[0][1]["dispatch_id"] == "dsp-100"

    # Remove payload
    outbox_remove(home, "dsp-100")
    assert outbox_read_all(home) == []

    # Fill outbox up to OUTBOX_CAP (32)
    for i in range(OUTBOX_CAP):
        outbox_write(home, {"dispatch_id": f"dsp-cap-{i}", "val": i})
    
    assert len(outbox_read_all(home)) == OUTBOX_CAP

    # Exceeding OUTBOX_CAP raises OutboxFull
    with pytest.raises(OutboxFull, match="outbox holds 32 results"):
        outbox_write(home, {"dispatch_id": "dsp-cap-overflow", "val": 999})

def test_write_crash_report(tmp_path):
    art_dir = str(tmp_path / "crash_dir")
    spec = make_spec(dispatch_id="dsp-crash", artifact_dir=art_dir)
    stderr_file = tmp_path / "test.err"
    stderr_file.write_text("Fatal error occurred in worker process")
    
    report_path = write_crash_report(art_dir, spec, "crash", 137, 2.5, str(stderr_file))
    assert Path(report_path).exists()
    report_data = json.loads(Path(report_path).read_text(encoding="utf-8"))
    assert report_data["dispatch_id"] == "dsp-crash"
    assert report_data["outcome"] == "crash"
    assert report_data["returncode"] == 137
    assert "Fatal error occurred" in report_data["stderr_tail"]
