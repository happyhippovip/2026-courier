from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from courier_core.resource_watchdog import (
    ResourcePolicy,
    evaluate_resource_health,
    should_pause,
    ResourceHealthReport,
)


def test_evaluate_resource_health_normal(tmp_path: Path):
    policy = ResourcePolicy(
        max_rss_mb=64000.0,
        max_open_fds=100000,
        cooldown_seconds=60.0,
    )
    report = evaluate_resource_health(tmp_path, policy=policy)
    assert isinstance(report, ResourceHealthReport)
    assert report.state in ("NORMAL", "COOLDOWN")
    paused, reason = should_pause(report)
    assert paused is False
    assert reason is None


def test_evaluate_resource_health_detects_memory_breach(tmp_path: Path):
    # Set a tiny max_rss_mb (e.g. 0.001 MB) so current process exceeds it
    policy = ResourcePolicy(
        max_rss_mb=0.001,
        max_open_fds=100000,
        cooldown_seconds=60.0,
    )
    report = evaluate_resource_health(tmp_path, policy=policy)
    assert report.state == "PRESSURED"
    assert "memory-pressure" in report.pressure_reasons
    paused, reason = should_pause(report)
    assert paused is True
    assert reason == "memory-pressure"


def test_evaluate_resource_health_detects_fd_exhaustion(tmp_path: Path):
    policy = ResourcePolicy(
        max_rss_mb=64000.0,
        max_open_fds=0,  # Any open FD/handle triggers this
        cooldown_seconds=60.0,
    )
    report = evaluate_resource_health(tmp_path, policy=policy)
    assert report.state == "PRESSURED"
    assert "fd-exhaustion" in report.pressure_reasons
    paused, reason = should_pause(report)
    assert paused is True
    assert reason == "fd-exhaustion"


def test_cooldown_hysteresis_state(tmp_path: Path):
    # If cooldown timestamp is in the future, state is COOLDOWN
    now = time.time()
    future_cooldown = now + 10.0
    policy = ResourcePolicy(
        max_rss_mb=64000.0,
        max_open_fds=100000,
        cooldown_seconds=60.0,
    )
    report = evaluate_resource_health(tmp_path, policy=policy, cooldown_until=future_cooldown, now=now)
    assert report.state == "COOLDOWN"
    paused, _ = should_pause(report)
    assert paused is False  # Cooldown allows finishing or gentle continuation without pausing


def test_read_only_never_mutates_home(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    marker = home / "marker.txt"
    marker.write_text("immutable", encoding="utf-8")

    before_entries = list(home.iterdir())
    report = evaluate_resource_health(home)
    after_entries = list(home.iterdir())

    assert before_entries == after_entries


def test_cli_invocation_normal_and_pressured(tmp_path: Path):
    res_normal = subprocess.run(
        [sys.executable, "-m", "courier_core.resource_watchdog", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert res_normal.returncode == 0
    data_normal = json.loads(res_normal.stdout)
    assert data_normal["state"] in ("NORMAL", "COOLDOWN")

    # Pass an ultra-low memory limit via CLI to simulate pressured exit
    res_pressured = subprocess.run(
        [sys.executable, "-m", "courier_core.resource_watchdog", str(tmp_path), "--max-rss-mb", "0.0001"],
        capture_output=True,
        text=True,
    )
    assert res_pressured.returncode == 1
    data_pressured = json.loads(res_pressured.stdout)
    assert data_pressured["state"] == "PRESSURED"
    assert "memory-pressure" in data_pressured["pressure_reasons"]
