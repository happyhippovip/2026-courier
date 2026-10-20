import threading
import os
import json
from unittest.mock import MagicMock, patch
from pathlib import Path
import pytest

from courier_worker.host import (
    WorkerHost, ExecutionSpec, Outcome, ContainmentError, OutboxFull
)
from courier_worker.service import WorkerLoop, ControllerError
from courier_worker.host import outbox_write, outbox_read_all


def test_e_l3_2_oversized_artifacts_does_not_crash_host(tmp_path):
    """E-L3-2: Oversized artifacts raising ContainmentError must not crash WorkerHost._wait."""
    spec = ExecutionSpec(
        task_id="t-oversized",
        attempt=1,
        dispatch_id="dsp-oversized",
        worker_id="w-test",
        result_id="res-oversized",
        argv=["cmd.exe", "/c", "echo", "test"],
        timeout_s=10.0,
        lease_ttl_s=30.0,
        artifact_dir=str(tmp_path / "artifacts"),
    )
    Path(spec.artifact_dir).mkdir(parents=True, exist_ok=True)

    fake_run = MagicMock()
    fake_run.wait.return_value = 0
    fake_run.stderr_path = str(tmp_path / "stderr.log")
    Path(fake_run.stderr_path).write_text("stderr info", encoding="utf-8")

    host = WorkerHost(home=str(tmp_path))
    with patch("courier_worker.host.collect_artifacts", side_effect=ContainmentError("exceeds 10MB")):
        result = host._wait(spec, fake_run, on_heartbeat=None, is_cancelled=lambda: False)

    assert result.outcome == Outcome.CRASH
    assert result.returncode == 1
    assert result.artifacts == ()
    assert result.crash_report_path is not None
    assert Path(result.crash_report_path).is_file()


def test_e_l3_3_outbox_full_flushes_and_retries(tmp_path):
    """E-L3-3: OutboxFull triggers flush_outbox and retry instead of crashing host."""
    home = tmp_path / "worker_home"
    home.mkdir(parents=True, exist_ok=True)
    loop = WorkerLoop(home=str(home), base_url="http://127.0.0.1:8088", worker_id="w-test", heartbeat_s=1.0)
    loop._client = MagicMock()

    payload = {"dispatch_id": "dsp-123", "task_id": "t-123", "outcome": "completed"}

    calls = [0]
    def fake_outbox_write(h, p):
        calls[0] += 1
        if calls[0] == 1:
            raise OutboxFull("outbox holds 32 results")
        return Path(h) / "outbox" / "dsp-123.json"

    with patch("courier_worker.service.outbox_write", side_effect=fake_outbox_write), \
         patch.object(loop, "flush_outbox") as mock_flush, \
         patch("courier_worker.service.outbox_remove"):
        loop._deliver_payload(payload)

    assert mock_flush.called
    assert calls[0] == 2
    loop._client.deliver.assert_called_once_with(payload)


def test_e_l3_3_persistent_outbox_full_does_not_crash(tmp_path):
    """E-L3-3: Persistent OutboxFull returns safely without crashing host process."""
    home = tmp_path / "worker_home"
    home.mkdir(parents=True, exist_ok=True)
    loop = WorkerLoop(home=str(home), base_url="http://127.0.0.1:8088", worker_id="w-test", heartbeat_s=1.0)
    loop._client = MagicMock()

    payload = {"dispatch_id": "dsp-persistent", "task_id": "t-persistent", "outcome": "completed"}

    with patch("courier_worker.service.outbox_write", side_effect=OutboxFull("persistent outbox full")), \
         patch.object(loop, "flush_outbox"):
        # Must not raise OutboxFull
        loop._deliver_payload(payload)

    # Controller deliver was skipped because outbox persistence could not be established
    loop._client.deliver.assert_not_called()


def test_e_l3_4_poison_400_immediately_quarantined(tmp_path):
    """E-L3-4: HTTP 400 immediately quarantines poison result and cleans outbox."""
    home = tmp_path / "worker_home"
    home.mkdir(parents=True, exist_ok=True)
    loop = WorkerLoop(home=str(home), base_url="http://127.0.0.1:8088", worker_id="w-test", heartbeat_s=1.0)
    loop._client = MagicMock()
    loop._client.deliver.side_effect = ControllerError("result: status 400 Bad Request")

    payload = {"dispatch_id": "dsp-poison", "task_id": "t-poison", "outcome": "completed"}
    outbox_write(str(home), payload)

    assert len(outbox_read_all(str(home))) == 1

    remaining = loop.flush_outbox()
    assert remaining == 0
    # Outbox is clean!
    assert len(outbox_read_all(str(home))) == 0

    # Payload was moved to quarantine
    q_file = home / "outbox" / "quarantine" / "dsp-poison.json"
    assert q_file.is_file()
    meta_file = home / "outbox" / "quarantine" / "dsp-poison.meta.json"
    assert meta_file.is_file()
    assert "poison_400" in meta_file.read_text(encoding="utf-8")


def test_e_l3_4_persistent_error_quarantined_after_max_attempts(tmp_path):
    """E-L3-4: Persistent delivery errors are retried up to MAX_OUTBOX_DELIVERY_ATTEMPTS then quarantined."""
    home = tmp_path / "worker_home"
    home.mkdir(parents=True, exist_ok=True)
    loop = WorkerLoop(home=str(home), base_url="http://127.0.0.1:8088", worker_id="w-test", heartbeat_s=1.0)
    loop._client = MagicMock()
    loop._client.deliver.side_effect = ControllerError("result: status 500 Internal Server Error")

    payload = {"dispatch_id": "dsp-retry", "task_id": "t-retry", "outcome": "completed"}
    outbox_write(str(home), payload)

    # First 4 attempts: stays in outbox
    for i in range(1, 5):
        rem = loop.flush_outbox()
        assert rem == 1
        assert len(outbox_read_all(str(home))) == 1

    # 5th attempt: max attempts reached -> quarantined!
    rem = loop.flush_outbox()
    assert rem == 0
    assert len(outbox_read_all(str(home))) == 0

    q_file = home / "outbox" / "quarantine" / "dsp-retry.json"
    assert q_file.is_file()
    meta_file = home / "outbox" / "quarantine" / "dsp-retry.meta.json"
    assert meta_file.is_file()
    assert "max_attempts_exceeded (5)" in meta_file.read_text(encoding="utf-8")


def test_e_l3_5_recycled_owner_pid_detected_and_reaped(tmp_path):
    """E-L3-5: Recycled PID with divergent create_time is recognized as dead owner and reaped."""
    import os, json
    from courier_worker.host import _owner_alive, run_orphan_gate, _get_process_create_time

    current_pid = os.getpid()
    actual_create_time = _get_process_create_time(current_pid)
    assert actual_create_time is not None

    # Mismatched create_time simulates PID recycled after former owner's death
    bogus_create_time = actual_create_time - 3600.0  # 1 hour earlier
    assert not _owner_alive(current_pid, owner_create_time=bogus_create_time)

    # Place a claim record with mismatched create_time in claims directory
    claims_dir = tmp_path / "run" / "claims"
    claims_dir.mkdir(parents=True, exist_ok=True)
    claim_file = claims_dir / "dispatch-recycled-1.json"
    record = {
        "task_id": "t-recycled",
        "dispatch_id": "dsp-recycled",
        "worker_id": "w-recycled",
        "owner_pid": current_pid,
        "owner_create_time": bogus_create_time,
        "child_pid": 0,
    }
    claim_file.write_text(json.dumps(record), encoding="utf-8")

    # run_orphan_gate should reap this claim record because the owner was recycled
    reaped = run_orphan_gate(str(tmp_path))
    assert reaped == 1
    assert not claim_file.exists()


def test_e_l3_5_matching_owner_pid_and_create_time_preserved(tmp_path):
    """E-L3-5: Matching PID and create_time confirms genuine live owner and hands off."""
    import os, json
    from courier_worker.host import _owner_alive, run_orphan_gate, _get_process_create_time

    current_pid = os.getpid()
    actual_create_time = _get_process_create_time(current_pid)
    assert actual_create_time is not None

    # Exact matching create_time confirms authentic live owner
    assert _owner_alive(current_pid, owner_create_time=actual_create_time)

    claims_dir = tmp_path / "run" / "claims"
    claims_dir.mkdir(parents=True, exist_ok=True)
    claim_file = claims_dir / "dispatch-active-1.json"
    record = {
        "task_id": "t-active",
        "dispatch_id": "dsp-active",
        "worker_id": "w-active",
        "owner_pid": current_pid,
        "owner_create_time": actual_create_time,
        "child_pid": 0,
    }
    claim_file.write_text(json.dumps(record), encoding="utf-8")

    # Genuine active owner must NOT be reaped
    reaped = run_orphan_gate(str(tmp_path))
    assert reaped == 0
    assert claim_file.exists()


def test_e_l3_6_live_stdio_overflow_terminates_run_and_caps_files(tmp_path):
    """E-L3-6: Runaway stdout/stderr exceeding MAX_LIVE_STDIO_BYTES is terminated and capped without host crash."""
    from courier_worker.host import _cap_stdio_file, MAX_LIVE_STDIO_BYTES

    spec = ExecutionSpec(
        task_id="t-stdio-overflow",
        attempt=1,
        dispatch_id="dsp-stdio-overflow",
        worker_id="w-test",
        result_id="res-stdio-overflow",
        argv=["cmd.exe", "/c", "echo", "test"],
        timeout_s=10.0,
        lease_ttl_s=30.0,
        artifact_dir=str(tmp_path / "artifacts"),
    )
    Path(spec.artifact_dir).mkdir(parents=True, exist_ok=True)

    fake_run = MagicMock()
    # While waiting, simulate child alive (wait returns None)
    fake_run.wait.return_value = None
    fake_run.poll.return_value = None

    stdout_file = tmp_path / "overflow.out"
    stderr_file = tmp_path / "normal.err"

    # Write oversized stdout (> 10 MiB)
    oversized_bytes = MAX_LIVE_STDIO_BYTES + 1024 * 512
    with open(stdout_file, "wb") as f:
        f.seek(oversized_bytes - 1)
        f.write(b"X")

    stderr_file.write_text("standard log", encoding="utf-8")

    fake_run.stdout_path = str(stdout_file)
    fake_run.stderr_path = str(stderr_file)

    host = WorkerHost(home=str(tmp_path))
    result = host._wait(spec, fake_run, on_heartbeat=None, is_cancelled=lambda: False)

    # Process must be terminated fail-closed
    assert fake_run.terminate_tree.called
    assert result.outcome == Outcome.CRASH
    assert result.returncode == 1
    assert result.crash_report_path is not None

    crash_data = json.loads(Path(result.crash_report_path).read_text(encoding="utf-8"))
    assert crash_data.get("reason") == "stdio_overflow"

    # Verify stdout file was capped on disk to <= MAX_LIVE_STDIO_BYTES
    assert os.path.getsize(stdout_file) <= MAX_LIVE_STDIO_BYTES


def test_e_l3_6_completed_task_with_oversized_stdio_marked_crash_and_capped(tmp_path):
    """E-L3-6: Task exiting 0 but exceeding MAX_LIVE_STDIO_BYTES is rejected fail-closed as CRASH."""
    from courier_worker.host import MAX_LIVE_STDIO_BYTES

    spec = ExecutionSpec(
        task_id="t-stdio-completed",
        attempt=1,
        dispatch_id="dsp-stdio-completed",
        worker_id="w-test",
        result_id="res-stdio-completed",
        argv=["cmd.exe", "/c", "echo", "test"],
        timeout_s=10.0,
        lease_ttl_s=30.0,
        artifact_dir=str(tmp_path / "artifacts"),
    )
    Path(spec.artifact_dir).mkdir(parents=True, exist_ok=True)

    fake_run = MagicMock()
    fake_run.wait.return_value = 0  # Process exited with code 0
    fake_run.poll.return_value = 0

    stdout_file = tmp_path / "overflow_exit0.out"
    stderr_file = tmp_path / "err_exit0.err"

    with open(stdout_file, "wb") as f:
        f.seek(MAX_LIVE_STDIO_BYTES + 2048)
        f.write(b"Z")
    stderr_file.write_text("", encoding="utf-8")

    fake_run.stdout_path = str(stdout_file)
    fake_run.stderr_path = str(stderr_file)

    host = WorkerHost(home=str(tmp_path))
    result = host._wait(spec, fake_run, on_heartbeat=None, is_cancelled=lambda: False)

    assert result.outcome == Outcome.CRASH
    assert result.returncode == 1
    assert os.path.getsize(stdout_file) <= MAX_LIVE_STDIO_BYTES


def test_e_l3_6_cap_stdio_file_helper_preserves_tail(tmp_path):
    """E-L3-6: _cap_stdio_file correctly truncates oversized files and preserves the exact tail."""
    from courier_worker.host import _cap_stdio_file

    test_file = tmp_path / "sample.log"
    # Write 1000 bytes: 900 bytes of 'A' followed by 100 bytes of 'B'
    test_file.write_bytes(b"A" * 900 + b"B" * 100)
    assert os.path.getsize(test_file) == 1000

    _cap_stdio_file(str(test_file), max_bytes=100)
    assert os.path.getsize(test_file) == 100
    assert test_file.read_bytes() == b"B" * 100


def test_e_l3_7_claim_auth_failure_raises_authentication_error():
    """E-L3-7: ControllerClient.claim raises AuthenticationError on HTTP 401 and 403."""
    from courier_worker.service import ControllerClient, AuthenticationError

    client = ControllerClient("http://127.0.0.1:8088", "token-test")

    with patch.object(client, "_call", return_value=(401, {"error": "invalid token"})):
        with pytest.raises(AuthenticationError) as exc_info:
            client.claim("w-test")
        assert "401" in str(exc_info.value)

    with patch.object(client, "_call", return_value=(403, {"error": "forbidden"})):
        with pytest.raises(AuthenticationError) as exc_info:
            client.claim("w-test")
        assert "403" in str(exc_info.value)


def test_e_l3_7_iterate_handles_auth_failure_cleanly(tmp_path):
    """E-L3-7: WorkerLoop.iterate returns 'auth-failed' and does not masquerade as 'idle' on 401/403."""
    from courier_worker.service import WorkerLoop, AuthenticationError

    home = tmp_path / "worker_home"
    home.mkdir(parents=True, exist_ok=True)
    loop = WorkerLoop(home=str(home), base_url="http://127.0.0.1:8088", worker_id="w-test", heartbeat_s=1.0)
    loop._client = MagicMock()
    loop._client.claim.side_effect = AuthenticationError("claim rejected: 401")

    action = loop.iterate(threading.Event())
    assert action == "auth-failed"


def test_e_l3_7_start_and_heartbeat_raise_authentication_error():
    """E-L3-7: ControllerClient.start and heartbeat raise AuthenticationError on HTTP 401/403."""
    from courier_worker.service import ControllerClient, AuthenticationError

    client = ControllerClient("http://127.0.0.1:8088", "token-test")

    with patch.object(client, "_call", return_value=(401, {"error": "unauthorized"})):
        with pytest.raises(AuthenticationError):
            client.start("dsp-auth")
        with pytest.raises(AuthenticationError):
            client.heartbeat("w-test", ["dsp-auth"])

    with patch.object(client, "_call", return_value=(403, {"error": "forbidden"})):
        with pytest.raises(AuthenticationError):
            client.start("dsp-auth")
        with pytest.raises(AuthenticationError):
            client.heartbeat("w-test", ["dsp-auth"])


@pytest.mark.parametrize("bad_id", [
    "../escape",
    "..\\escape",
    "subdir/task1",
    "subdir\\task1",
    "task with spaces",
    "task;rm",
    "task$foo",
    "task#bar",
    "task|pipe",
])
def test_e_l3_11_execution_spec_rejects_path_traversal_and_unsafe_ids(bad_id, tmp_path):
    """E-L3-11: ExecutionSpec strictly rejects path traversal and unsafe characters in all IDs."""
    from courier_worker.host import ExecutionSpec, SpecError

    valid_kwargs = {
        "task_id": "t-safe",
        "attempt": 1,
        "dispatch_id": "dsp-safe",
        "worker_id": "w-safe",
        "result_id": "res-safe",
        "argv": ["cmd.exe", "/c", "echo", "hi"],
        "timeout_s": 10.0,
        "lease_ttl_s": 30.0,
        "artifact_dir": str(tmp_path / "artifacts"),
    }

    for id_field in ("task_id", "dispatch_id", "worker_id", "result_id"):
        kwargs = dict(valid_kwargs, **{id_field: bad_id})
        with pytest.raises(SpecError) as exc_info:
            ExecutionSpec(**kwargs)
        assert "unsafe characters or path traversal attempt" in str(exc_info.value)


def test_e_l3_11_execution_spec_accepts_valid_alphanumeric_ids(tmp_path):
    """E-L3-11: ExecutionSpec accepts standard alphanumeric IDs with dashes, dots, and underscores."""
    from courier_worker.host import ExecutionSpec

    spec = ExecutionSpec(
        task_id="t-123_abc.xyz",
        attempt=1,
        dispatch_id="dsp-456_def.uvw",
        worker_id="w-WIN_01.node",
        result_id="res-789_ghi.rst",
        argv=["cmd.exe", "/c", "echo", "hi"],
        timeout_s=10.0,
        lease_ttl_s=30.0,
        artifact_dir=str(tmp_path / "artifacts"),
    )
    assert spec.task_id == "t-123_abc.xyz"
    assert spec.dispatch_id == "dsp-456_def.uvw"
    assert spec.worker_id == "w-WIN_01.node"
    assert spec.result_id == "res-789_ghi.rst"
