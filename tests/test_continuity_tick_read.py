"""The continuity demo must tolerate a status file locked mid-replace."""

import json
from pathlib import Path

import scripts.continuity_demo as demo


def test_read_json_sharing_retries_permission_denied(tmp_path, monkeypatch):
    path = tmp_path / "ledger_tick.json"
    path.write_text(json.dumps({"passes": 3}), encoding="utf-8")
    real = Path.read_text
    calls = {"n": 0}

    def flaky(self, *args, **kwargs):
        if self == path and calls["n"] < 2:
            calls["n"] += 1
            raise PermissionError(13, "Permission denied", str(path))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", flaky)
    assert demo._read_json_sharing(path, attempts=5, pause_s=0)["passes"] == 3
    assert calls["n"] == 2


def test_read_json_sharing_gives_up_when_the_lock_stays(tmp_path, monkeypatch):
    path = tmp_path / "ledger_tick.json"
    path.write_text("{}", encoding="utf-8")

    def locked(self, *args, **kwargs):
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr(Path, "read_text", locked)
    try:
        demo._read_json_sharing(path, attempts=2, pause_s=0)
    except PermissionError:
        return
    raise AssertionError("a lasting lock must not become a successful read")
