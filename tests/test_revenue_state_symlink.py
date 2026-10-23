import json

from scripts import revenue_worker_adapter


class _StopLoop(Exception):
    pass


def _claim_once(monkeypatch, tmp_path):
    calls = {"n": 0}

    def http_post(_config, endpoint, _data=None):
        if endpoint == "/tasks/claim":
            calls["n"] += 1
            if calls["n"] == 1:
                return {"task_id": "T1", "attempt_id": "A1"}
            return None
        return {}

    def check_output(cmd, **_kwargs):
        return b'{"result": "pass"}'

    def sleep(_seconds):
        raise _StopLoop()

    monkeypatch.setattr(revenue_worker_adapter, "http_post", http_post)
    monkeypatch.setattr(revenue_worker_adapter.subprocess, "check_output", check_output)
    monkeypatch.setattr(revenue_worker_adapter.time, "sleep", sleep)
    tmp_path.mkdir(parents=True, exist_ok=True)
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "COURIER_SERVER": "http://local",
                "COURIER_API_KEY": "LOCAL-KEY",
                "WORKER_ID": "W1",
                "POLL_INTERVAL_SECONDS": 1,
            }
        ),
        encoding="utf-8",
    )
    logs = tmp_path / "logs"
    logs.mkdir(exist_ok=True)
    monkeypatch.setattr(revenue_worker_adapter, "CONFIG_PATH", config)
    monkeypatch.setattr(revenue_worker_adapter, "LOGS_DIR", logs)
    monkeypatch.delenv("COURIER_SERVER", raising=False)
    monkeypatch.delenv("COURIER_API_KEY", raising=False)
    try:
        revenue_worker_adapter.main()
    except _StopLoop:
        return "stopped"
    except ValueError as exc:
        return str(exc)
    return None


def test_revenue_state_does_not_follow_a_symlink(monkeypatch, tmp_path):
    outside = tmp_path / "outside"
    task_dir = outside / "T1"
    task_dir.mkdir(parents=True)
    (outside / "keep.txt").write_text("SECRET-DIR", encoding="utf-8")
    (task_dir / "secret.txt").write_text("SECRET-TASK", encoding="utf-8")
    linked = tmp_path / "state"
    linked.symlink_to(outside)
    monkeypatch.setattr(revenue_worker_adapter, "STATE_DIR", linked)
    linked_err = _claim_once(monkeypatch, tmp_path / "linked-run")

    local_state = tmp_path / "local-state"
    local_state.mkdir()
    monkeypatch.setattr(revenue_worker_adapter, "STATE_DIR", local_state)
    local_err = _claim_once(monkeypatch, tmp_path / "local-run")

    assert (
        linked_err,
        (task_dir / "secret.txt").exists(),
        (task_dir / "secret.txt").read_text(encoding="utf-8") if (task_dir / "secret.txt").exists() else None,
        (task_dir / "task.json").exists(),
        (outside / "keep.txt").read_text(encoding="utf-8"),
        local_err,
        (local_state / "T1" / "task.json").exists(),
    ) == (
        "stopped",
        True,
        "SECRET-TASK",
        False,
        "SECRET-DIR",
        "stopped",
        True,
    )
