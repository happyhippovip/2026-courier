#!/usr/bin/env python3
"""Tests for scripts/task_routing.py."""

import json
from pathlib import Path
import pytest
from scripts.task_routing import route_task, route_task_detailed, main


def test_route_task_local_default():
    route = route_task({"can_run_local": True}, quiet=True)
    assert route in ("LOCAL_WINDOWS", "LOCAL_MAC")


def test_route_task_needs_hosted():
    route = route_task({"needs_hosted": True}, quiet=True)
    assert route == "GITHUB_HOSTED"


def test_route_task_ai_tiers():
    route_high = route_task({"can_run_local": False, "complexity": "high"}, quiet=True)
    assert route_high == "EXPENSIVE_AI_PROVIDER"

    route_cheap = route_task({"can_run_local": False, "complexity": "low"}, quiet=True)
    assert route_cheap == "CHEAP_AI_PROVIDER"


def test_route_task_mac_requirement():
    # If running on Windows, requires_mac routes to GITHUB_HOSTED
    res = route_task_detailed({"requires_mac": True})
    assert res["target_os"] == "mac"
    assert res["route"] in ("LOCAL_MAC", "GITHUB_HOSTED")


def test_route_task_linux_requirement_on_nt():
    res = route_task_detailed({"target_os": "linux"})
    assert res["target_os"] == "linux"
    assert res["route"] == "GITHUB_HOSTED"


def test_route_task_detailed_structure():
    detail = route_task_detailed({"can_run_local": True})
    assert "route" in detail
    assert "cost_tier" in detail
    assert "target_os" in detail
    assert "rationale" in detail


def test_main_cli_cannot_run_local(capsys):
    ret = main(["--cannot-run-local", "--complexity", "high", "--json"])
    assert ret == 0
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert data["route"] == "EXPENSIVE_AI_PROVIDER"
    assert data["cost_tier"] == "EXPENSIVE"


def test_main_cli_with_file(tmp_path: Path, capsys):
    req_file = tmp_path / "req.json"
    req_file.write_text(json.dumps({"needs_hosted": True}), encoding="utf-8")

    ret = main(["--file", str(req_file), "--json"])
    assert ret == 0
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert data["route"] == "GITHUB_HOSTED"
