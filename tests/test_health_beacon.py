"""Tests for Distributed Worker Health Beacon and Heartbeat Transmitter."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from courier_core.health_beacon import (
    HealthBeacon,
    BeaconPulse,
    emit_pulse,
    should_renew_lease,
    is_beacon_alive,
    main,
)


def test_generate_pulse_basic_telemetry():
    t0 = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)
    beacon = HealthBeacon(worker_id="windows-titan", host="titan-box")

    pulse = beacon.generate_pulse(current_item_id="P23", now=t0)
    assert pulse.worker_id == "windows-titan"
    assert pulse.host == "titan-box"
    assert pulse.current_item_id == "P23"
    assert pulse.timestamp == "2026-10-18T12:00:00Z"
    assert pulse.pid > 0
    assert pulse.rss_mb > 0.0
    assert pulse.renewal_recommended is False


def test_renewal_recommendation_when_near_expiry():
    t0 = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)
    # Threshold is 300s. Expiry in 100s -> should recommend renewal.
    expiry_near = (t0 + timedelta(seconds=100)).strftime("%Y-%m-%dT%H:%M:%SZ")

    beacon = HealthBeacon(worker_id="windows-titan", renewal_threshold_sec=300.0)
    assert beacon.should_renew_lease(expiry_near, now=t0) is True

    pulse = beacon.generate_pulse(
        current_item_id="P23",
        lease_expires_at=expiry_near,
        now=t0,
    )
    assert pulse.renewal_recommended is True

    # Expiry in 1000s -> should NOT recommend renewal yet
    expiry_far = (t0 + timedelta(seconds=1000)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert beacon.should_renew_lease(expiry_far, now=t0) is False


def test_emit_pulse_writes_atomically_to_disk(tmp_path):
    beacon_file = tmp_path / "beacon.json"
    beacon = HealthBeacon(
        worker_id="windows-titan",
        beacon_file=str(beacon_file),
    )

    t = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)
    pulse = beacon.emit_pulse(current_item_id="P23", now=t)

    assert beacon_file.exists()
    disk_data = json.loads(beacon_file.read_text(encoding="utf-8"))
    assert disk_data["worker_id"] == "windows-titan"
    assert disk_data["current_item_id"] == "P23"
    assert disk_data["timestamp"] == "2026-10-18T12:00:00Z"


def test_history_logging_when_configured(tmp_path):
    beacon_file = tmp_path / "beacon.json"
    history_file = tmp_path / "history.jsonl"
    beacon = HealthBeacon(
        worker_id="windows-titan",
        beacon_file=str(beacon_file),
        history_file=str(history_file),
    )

    beacon.emit_pulse(current_item_id="P23_step1")
    beacon.emit_pulse(current_item_id="P23_step2")

    assert history_file.exists()
    lines = [ln for ln in history_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 2
    assert "P23_step1" in lines[0]
    assert "P23_step2" in lines[1]


def test_is_beacon_alive_evaluates_freshness(tmp_path):
    beacon_file = tmp_path / "beacon.json"
    t0 = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)

    # Missing file -> not alive
    assert is_beacon_alive(str(beacon_file), max_age_sec=60.0, now=t0) is False

    # Fresh pulse (10s old) -> alive
    beacon = HealthBeacon(beacon_file=str(beacon_file))
    beacon.emit_pulse(now=t0)
    t_fresh = t0 + timedelta(seconds=10)
    assert is_beacon_alive(str(beacon_file), max_age_sec=60.0, now=t_fresh) is True

    # Stale pulse (120s old) -> not alive
    t_stale = t0 + timedelta(seconds=120)
    assert is_beacon_alive(str(beacon_file), max_age_sec=60.0, now=t_stale) is False


def test_cli_invocation_emit_and_check(tmp_path):
    beacon_file = tmp_path / "cli_beacon.json"

    # 1. Emit pulse
    code_emit = main([
        "emit",
        "--worker-id", "cli-titan",
        "--item", "P23_cli",
        "--beacon-file", str(beacon_file),
    ])
    assert code_emit == 0
    assert beacon_file.exists()

    # 2. Check liveness (should be fresh)
    code_check = main([
        "check",
        "--beacon-file", str(beacon_file),
        "--max-age", "60",
    ])
    assert code_check == 0
