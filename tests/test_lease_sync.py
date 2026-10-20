import json
import time
import pytest
from pathlib import Path
from courier_core.lease_sync import (
    LeaseSynchronizer,
    LeaseState,
    KeepaliveStatus,
)


def test_keepalive_renews_before_expiry():
    renewals = []

    def mock_renew_fn(item_id: str, ttl: float) -> bool:
        renewals.append((item_id, ttl))
        return True

    syncer = LeaseSynchronizer(renew_fn=mock_renew_fn, renewal_threshold_seconds=10.0)

    # Lease expiring in 5 seconds (under 10s threshold)
    now = time.time()
    syncer.track_lease(
        item_id="task-long-1",
        holder="worker-a",
        expires_at=now + 5.0,
        ttl_seconds=30.0,
    )

    # Step should trigger renewal
    result = syncer.step()
    assert result["renewed"] == 1
    assert len(renewals) == 1
    assert renewals[0] == ("task-long-1", 30.0)

    lease = syncer.get_lease("task-long-1")
    assert lease.renewal_count == 1
    assert lease.status == KeepaliveStatus.HEALTHY
    assert lease.expires_at > now + 25.0


def test_keepalive_skips_when_fresh():
    renewals = []

    syncer = LeaseSynchronizer(
        renew_fn=lambda item, ttl: renewals.append(item) or True,
        renewal_threshold_seconds=10.0,
    )

    # Lease expiring in 100 seconds (above 10s threshold)
    syncer.track_lease(
        item_id="task-fresh",
        holder="worker-a",
        expires_at=time.time() + 100.0,
        ttl_seconds=30.0,
    )

    result = syncer.step()
    assert result["renewed"] == 0
    assert len(renewals) == 0


def test_lease_loss_detection_on_repeated_failures():
    # Always failing renewal
    syncer = LeaseSynchronizer(
        renew_fn=lambda item, ttl: False,
        renewal_threshold_seconds=10.0,
        max_consecutive_failures=3,
    )

    syncer.track_lease(
        item_id="task-lost",
        holder="worker-b",
        expires_at=time.time() + 5.0,
        ttl_seconds=30.0,
    )

    # 1st failure
    syncer.step()
    assert syncer.get_lease("task-lost").status == KeepaliveStatus.DEGRADED

    # 2nd failure
    syncer.step()
    assert syncer.get_lease("task-lost").status == KeepaliveStatus.DEGRADED

    # 3rd failure: reaches limit -> transitions to LOST
    syncer.step()
    lease = syncer.get_lease("task-lost")
    assert lease.status == KeepaliveStatus.LOST
    assert syncer.is_lease_valid("task-lost") is False


def test_already_expired_lease_marks_lost_without_renewal():
    called = []
    syncer = LeaseSynchronizer(renew_fn=lambda item, ttl: called.append(item) or True)
    syncer.track_lease("task-expired", "worker-x", expires_at=time.time() - 1.0, ttl_seconds=30.0)
    res = syncer.step()
    assert res["lost"] == 1
    assert res["renewed"] == 0
    assert called == []
    assert syncer.get_lease("task-expired").status == KeepaliveStatus.LOST


def test_heartbeat_beacon_pulse_emitted(tmp_path):
    beacon_file = tmp_path / "beacon.json"
    from courier_core.health_beacon import HealthBeacon

    beacon = HealthBeacon(worker_id="win-keepalive", beacon_file=beacon_file)
    syncer = LeaseSynchronizer(
        renew_fn=lambda item, ttl: True,
        renewal_threshold_seconds=10.0,
        beacon=beacon,
    )

    syncer.track_lease(
        item_id="task-beacon",
        holder="win-keepalive",
        expires_at=time.time() + 5.0,
        ttl_seconds=30.0,
    )

    syncer.step()
    assert beacon_file.exists()
    beacon_data = json.loads(beacon_file.read_text(encoding="utf-8"))
    assert beacon_data["worker_id"] == "win-keepalive"


def test_stop_keepalive():
    syncer = LeaseSynchronizer(renew_fn=lambda item, ttl: True)
    syncer.track_lease("task-stop", "worker-a", expires_at=time.time() + 5.0, ttl_seconds=30.0)

    assert syncer.get_lease("task-stop") is not None
    stopped = syncer.stop_lease("task-stop")
    assert stopped is True
    assert syncer.get_lease("task-stop") is None


def test_cli_invocation(tmp_path):
    import subprocess
    import sys

    manifest_file = tmp_path / "leases.json"
    manifest_file.write_text(
        json.dumps({
            "leases": [
                {
                    "item_id": "cli-task",
                    "holder": "cli-worker",
                    "expires_at": time.time() + 5.0,
                    "ttl_seconds": 30.0,
                }
            ]
        }),
        encoding="utf-8"
    )

    cmd = [
        sys.executable,
        "-m",
        "courier_core.lease_sync",
        "tick",
        "--leases",
        str(manifest_file),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    out = json.loads(proc.stdout)
    assert out["status"] == "SUCCESS"
    assert out["renewed"] == 1
