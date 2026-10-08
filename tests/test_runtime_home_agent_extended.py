import json
import pytest
from pathlib import Path

from courier_runtime.home_agent import (
    HomeAgent,
    LocalGrants,
    why_refused,
    CATALOG,
    ACCESS_ORDER,
    submit,
)


def test_catalog_structure():
    assert "host_health" in CATALOG
    assert "surface_status" in CATALOG
    assert "reclaim_idle_surfaces" in CATALOG
    assert "git_pull_repo" in CATALOG

    for action, (access, desc) in CATALOG.items():
        assert access in ACCESS_ORDER
        assert isinstance(desc, str) and len(desc) > 0


def test_why_refused_forbidden_command_keys():
    g = LocalGrants(max_access="control", allowed_actions=frozenset({"host_health"}))

    # Test "command" and "script" rejection
    assert why_refused({"action": "host_health", "command": "whoami"}, g) == "jobs may not carry commands"
    assert why_refused({"action": "host_health", "script": "evil.sh"}, g) == "jobs may not carry commands"


def test_home_agent_nonexistent_inbox(tmp_path):
    # If inbox folder does not exist yet, run_once returns empty receipts gracefully
    agent = HomeAgent(tmp_path / "mailbox", "pc-test", LocalGrants(), handlers={})
    assert agent.run_once() == []


def test_submit_helper(tmp_path):
    root = tmp_path / "mb"
    out_path = submit(root, "host-a", "job-123", "host_health", {"detail": True})
    assert out_path.exists()
    assert out_path.name == "job-123.json"
    content = json.loads(out_path.read_text(encoding="utf-8"))
    assert content["action"] == "host_health"
    assert content["params"] == {"detail": True}
