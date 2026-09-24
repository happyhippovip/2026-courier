import json
import os
import sys
import tempfile

from scripts.agent_session_manager import (
    register_task,
    cleanup_session,
    audit_orphans,
    get_process_info,
    main,
)


def test_agent_session_manager_register_and_cleanup(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp_dir:
        reg_file = os.path.join(tmp_dir, "monitors.json")

        # Mock process info and kill_pid to isolate
        monkeypatch.setattr("scripts.agent_session_manager.get_process_info", lambda pid: f"1234.000:proc_{pid}")
        monkeypatch.setattr("scripts.agent_session_manager.kill_pid", lambda pid: True)

        ok = register_task(4321, "worker-agent", "monitor-queue", registry_path=reg_file)
        assert ok is True

        with open(reg_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["worker-agent"]) == 1
        assert data["worker-agent"][0]["pid"] == 4321

        killed = cleanup_session("worker-agent", registry_path=reg_file)
        assert killed == 1

        with open(reg_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "worker-agent" not in data


def test_agent_session_manager_audit_orphans(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp_dir:
        reg_file = os.path.join(tmp_dir, "monitors.json")

        with open(reg_file, "w", encoding="utf-8") as f:
            json.dump({
                "owner-1": [
                    {"pid": 1111, "purpose": "dead", "proc_info": "old_info"},
                    {"pid": 2222, "purpose": "alive", "proc_info": "alive_info"},
                ]
            }, f)

        # Mock: 1111 returns different or None, 2222 returns alive_info
        def mock_info(pid):
            if pid == 2222:
                return "alive_info"
            return None

        monkeypatch.setattr("scripts.agent_session_manager.get_process_info", mock_info)

        audit_orphans(registry_path=reg_file)

        with open(reg_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert len(data["owner-1"]) == 1
        assert data["owner-1"][0]["pid"] == 2222
