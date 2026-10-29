import json
import subprocess
import time
from pathlib import Path

import pytest

from scripts import revenue_worker_adapter as adapter


class StopLoop(Exception):
    pass


def test_rejected_result_post_is_not_reported_complete(monkeypatch, tmp_path):
    """A result POST that is not accepted must not be logged as completed.

    The existing claim loop still runs again afterward.
    """
    monkeypatch.setattr(adapter, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(adapter, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(adapter, "CONFIG_PATH", tmp_path / "cfg.json")
    (tmp_path / "state").mkdir()
    (tmp_path / "logs").mkdir()
    adapter.CONFIG_PATH.write_text(json.dumps({
        "COURIER_SERVER": "http://local",
        "COURIER_API_KEY": "k",
        "WORKER_ID": "W1",
        "POLL_INTERVAL_SECONDS": 1,
    }), encoding="utf-8")

    claims = []

    def mock_http_post(config, endpoint, data=None):
        if endpoint == "/tasks/claim":
            claims.append(endpoint)
            if len(claims) == 1:
                return {"task_id": "T1", "attempt_id": "A1"}
            return None
        if endpoint == "/tasks/result":
            return None
        return {"ok": True}

    def mock_check_output(cmd, **kwargs):
        if "revenue_v1_safety_baseline.py" in str(cmd):
            work_dir = Path(cmd[-1])
            (work_dir / "report.json").write_text("{}", encoding="utf-8")
            (work_dir / "report.md").write_text("ok", encoding="utf-8")
            return b'{"result": "pass"}'
        raise OSError("no keychain")

    sleeps = []

    def mock_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) >= 2:
            raise StopLoop()

    monkeypatch.setattr(adapter, "http_post", mock_http_post)
    monkeypatch.setattr(subprocess, "check_output", mock_check_output)
    monkeypatch.setattr(time, "sleep", mock_sleep)

    with pytest.raises(StopLoop):
        adapter.main()

    log = (tmp_path / "logs" / "revenue_worker.log").read_text(encoding="utf-8")
    assert "Task T1 completed." not in log
    assert "not reporting completion" in log
    assert len(claims) >= 2


def test_accepted_result_post_is_reported_complete(monkeypatch, tmp_path):
    monkeypatch.setattr(adapter, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(adapter, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(adapter, "CONFIG_PATH", tmp_path / "cfg.json")
    (tmp_path / "state").mkdir()
    (tmp_path / "logs").mkdir()
    adapter.CONFIG_PATH.write_text(json.dumps({
        "COURIER_SERVER": "http://local",
        "COURIER_API_KEY": "k",
        "WORKER_ID": "W1",
        "POLL_INTERVAL_SECONDS": 1,
    }), encoding="utf-8")

    def mock_http_post(config, endpoint, data=None):
        if endpoint == "/tasks/claim":
            return {"task_id": "T9", "attempt_id": "A9"}
        if endpoint == "/tasks/result":
            return {"ok": True}
        return {"ok": True}

    def mock_check_output(cmd, **kwargs):
        if "revenue_v1_safety_baseline.py" in str(cmd):
            work_dir = Path(cmd[-1])
            (work_dir / "report.json").write_text("{}", encoding="utf-8")
            return b'{"result": "pass"}'
        raise OSError("no keychain")

    def mock_sleep(seconds):
        raise StopLoop()

    monkeypatch.setattr(adapter, "http_post", mock_http_post)
    monkeypatch.setattr(subprocess, "check_output", mock_check_output)
    monkeypatch.setattr(time, "sleep", mock_sleep)

    with pytest.raises(StopLoop):
        adapter.main()

    log = (tmp_path / "logs" / "revenue_worker.log").read_text(encoding="utf-8")
    assert "Task T9 completed." in log
