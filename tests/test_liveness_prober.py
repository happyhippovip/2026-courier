from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from courier_core.liveness_prober import (
    LivenessPolicy,
    probe_liveness,
    inspect_workers_liveness,
    LivenessReport,
)


def test_probe_liveness_working():
    policy = LivenessPolicy(warning_s=5.0, slow_s=10.0, probe_s=20.0, timeout_s=30.0)
    now = 1000.0
    last_hb = 999.0  # 1.0s ago

    report = probe_liveness(last_hb, current_time=now, policy=policy)
    assert isinstance(report, LivenessReport)
    assert report.state == "WORKING"
    assert report.should_ping is False
    assert report.should_revoke is False
    assert report.elapsed_s == 1.0


def test_probe_liveness_quiet():
    policy = LivenessPolicy(warning_s=5.0, slow_s=10.0, probe_s=20.0, timeout_s=30.0)
    now = 1000.0
    last_hb = 993.0  # 7.0s ago

    report = probe_liveness(last_hb, current_time=now, policy=policy)
    assert report.state == "QUIET"
    assert report.should_ping is False
    assert report.should_revoke is False
    assert report.elapsed_s == 7.0


def test_probe_liveness_slow():
    policy = LivenessPolicy(warning_s=5.0, slow_s=10.0, probe_s=20.0, timeout_s=30.0)
    now = 1000.0
    last_hb = 985.0  # 15.0s ago

    report = probe_liveness(last_hb, current_time=now, policy=policy)
    assert report.state == "SLOW"
    assert report.should_ping is True
    assert report.should_revoke is False


def test_probe_liveness_probing():
    policy = LivenessPolicy(warning_s=5.0, slow_s=10.0, probe_s=20.0, timeout_s=30.0)
    now = 1000.0
    last_hb = 975.0  # 25.0s ago

    report = probe_liveness(last_hb, current_time=now, policy=policy)
    assert report.state == "PROBING"
    assert report.should_ping is True
    assert report.should_revoke is False


def test_probe_liveness_failed_triggers_revocation():
    policy = LivenessPolicy(warning_s=5.0, slow_s=10.0, probe_s=20.0, timeout_s=30.0)
    now = 1000.0
    last_hb = 960.0  # 40.0s ago

    report = probe_liveness(last_hb, current_time=now, policy=policy)
    assert report.state == "FAILED"
    assert report.should_ping is False
    assert report.should_revoke is True


def test_probe_liveness_nan_or_invalid_timestamp_fails_closed():
    for invalid_hb in [float("nan"), float("-inf"), 0.0, -5.0]:
        report = probe_liveness(invalid_hb, current_time=1000.0)
        assert report.state == "FAILED"
        assert report.should_revoke is True


def test_inspect_multiple_workers():
    now = 1000.0
    workers = {
        "w-active": 999.0,
        "w-dead": 950.0,
    }
    reports = inspect_workers_liveness(workers, current_time=now)
    assert "w-active" in reports
    assert reports["w-active"].state == "WORKING"
    assert "w-dead" in reports
    assert reports["w-dead"].state == "FAILED"
    assert reports["w-dead"].should_revoke is True


def test_cli_invocation_healthy_and_revocation(tmp_path: Path):
    now = time.time()
    hb_file = tmp_path / "heartbeats.json"
    hb_file.write_text(json.dumps({
        "workers": {
            "w-live": now - 1.0,
        }
    }), encoding="utf-8")

    res = subprocess.run(
        [sys.executable, "-m", "courier_core.liveness_prober", str(hb_file)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["all_healthy"] is True

    # Stale worker
    hb_file_stale = tmp_path / "stale.json"
    hb_file_stale.write_text(json.dumps({
        "workers": {
            "w-dead": now - 100.0,
        }
    }), encoding="utf-8")

    res_stale = subprocess.run(
        [sys.executable, "-m", "courier_core.liveness_prober", str(hb_file_stale)],
        capture_output=True,
        text=True,
    )
    assert res_stale.returncode == 1
    data_stale = json.loads(res_stale.stdout)
    assert data_stale["all_healthy"] is False
    assert "w-dead" in data_stale["revocations_needed"]
