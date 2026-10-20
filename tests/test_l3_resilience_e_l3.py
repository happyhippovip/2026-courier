from unittest.mock import MagicMock, patch
from pathlib import Path
import pytest

from courier_worker.host import (
    WorkerHost, ExecutionSpec, Outcome, ContainmentError, OutboxFull
)
from courier_worker.service import WorkerLoop


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
