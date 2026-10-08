"""Packaged Windows host must keep a heartbeating run past the first lease window.

The copy under scripts/windows_worker/dist is what the Windows package runs.
integration/v1's courier_worker.host already extends the lease when a heartbeat
does not refuse. This snapshot did not, so a live unit became lease-lost and
its tree was killed while the task timeout was still open.
"""

import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGED_HOST = ROOT / "scripts" / "windows_worker" / "dist" / "courier_worker" / "host.py"
PY = sys.executable


def _load_packaged_host():
    spec = importlib.util.spec_from_file_location(
        "packaged_windows_courier_host", PACKAGED_HOST)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


H = _load_packaged_host()


def _spec(home: Path, *, argv, lease_ttl_s, timeout_s, dispatch="d-lease"):
    artifact_dir = home / "artifacts" / dispatch
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return H.ExecutionSpec(
        task_id="t-lease",
        attempt=1,
        dispatch_id=dispatch,
        worker_id="w1",
        result_id="r-" + dispatch,
        argv=tuple(argv),
        timeout_s=timeout_s,
        lease_ttl_s=lease_ttl_s,
        artifact_dir=str(artifact_dir),
        heartbeat_s=0.2,
    )


def test_successful_heartbeat_does_not_end_the_run_at_the_first_lease(tmp_path):
    host = H.WorkerHost(str(tmp_path), pressure_probe=lambda: None)
    spec = _spec(
        tmp_path,
        argv=[PY, "-c", "import time; time.sleep(2.2)"],
        lease_ttl_s=1.0,
        timeout_s=30.0,
    )
    beats = []

    def heartbeat(elapsed):
        beats.append(elapsed)
        return None  # packaged WorkerLoop heartbeat returns None, not False

    result = host.run_once(spec, on_heartbeat=heartbeat)
    assert beats, "the host never asked for a heartbeat"
    assert result.outcome == H.Outcome.COMPLETED
    assert result.returncode == 0


def test_refused_heartbeat_still_loses_the_lease(tmp_path):
    host = H.WorkerHost(str(tmp_path), pressure_probe=lambda: None)
    spec = _spec(
        tmp_path,
        argv=[PY, "-c", "import time; time.sleep(30)"],
        lease_ttl_s=1.0,
        timeout_s=60.0,
        dispatch="d-refuse",
    )
    started = time.monotonic()
    result = host.run_once(spec, on_heartbeat=lambda _elapsed: False)
    assert result.outcome == H.Outcome.LEASE_LOST
    assert result.retryable is True
    assert time.monotonic() - started < 1.0 + H.KILL_GRACE_S + 4.0


def test_one_unreadable_claim_does_not_freeze_a_later_claim(tmp_path):
    claims = tmp_path / "run" / "claims"
    claims.mkdir(parents=True)
    bad = claims / "dispatch-a.json"
    later = claims / "dispatch-b.json"
    bad.write_text(json.dumps({"owner_pid": "not-a-pid"}), encoding="utf-8")
    later.write_text(json.dumps({"owner_pid": 0}), encoding="utf-8")

    handled = H.run_orphan_gate(str(tmp_path))

    assert not bad.exists()
    assert (claims / "dispatch-a.json.corrupt").is_file()
    assert not later.exists()
    assert handled == 1
