import json

from scripts import revenue_worker_adapter


def _load(monkeypatch, tmp_path, config_path):
    monkeypatch.setattr(revenue_worker_adapter, "CONFIG_PATH", config_path)
    monkeypatch.setattr(revenue_worker_adapter, "LOGS_DIR", tmp_path / "logs")
    (tmp_path / "logs").mkdir(exist_ok=True)
    monkeypatch.delenv("COURIER_SERVER", raising=False)
    monkeypatch.delenv("COURIER_API_KEY", raising=False)

    def fail_keychain(*_args, **_kwargs):
        raise OSError("no keychain")

    monkeypatch.setattr(revenue_worker_adapter.subprocess, "check_output", fail_keychain)
    try:
        config = revenue_worker_adapter.get_config()
    except ValueError as exc:
        return ("raised", str(exc), None)
    return ("loaded", None, config.get("COURIER_API_KEY"))


def test_revenue_config_does_not_follow_a_symlink(monkeypatch, tmp_path):
    file_outside = tmp_path / "outside-file.json"
    file_outside.write_text(
        json.dumps({"COURIER_SERVER": "http://local", "COURIER_API_KEY": "SECRET-FILE"}),
        encoding="utf-8",
    )
    file_link = tmp_path / "config-file.json"
    file_link.symlink_to(file_outside)
    file_seen = _load(monkeypatch, tmp_path, file_link)

    parent_dir = tmp_path / "outside-dir"
    parent_dir.mkdir()
    parent_file = parent_dir / "revenue_worker_config.json"
    parent_file.write_text(
        json.dumps({"COURIER_SERVER": "http://local", "COURIER_API_KEY": "SECRET-PARENT"}),
        encoding="utf-8",
    )
    parent_link = tmp_path / "inbox"
    parent_link.symlink_to(parent_dir)
    parent_seen = _load(monkeypatch, tmp_path, parent_link / "revenue_worker_config.json")

    local = tmp_path / "local-config.json"
    local.write_text(
        json.dumps({"COURIER_SERVER": "http://local", "COURIER_API_KEY": "LOCAL-KEY"}),
        encoding="utf-8",
    )
    local_seen = _load(monkeypatch, tmp_path, local)

    assert (
        file_seen,
        parent_seen,
        local_seen,
        file_outside.read_text(encoding="utf-8"),
        parent_file.read_text(encoding="utf-8"),
    ) == (
        ("raised", "refusing to follow a symlink", None),
        ("raised", "refusing to follow a symlink", None),
        ("loaded", None, "LOCAL-KEY"),
        json.dumps({"COURIER_SERVER": "http://local", "COURIER_API_KEY": "SECRET-FILE"}),
        json.dumps({"COURIER_SERVER": "http://local", "COURIER_API_KEY": "SECRET-PARENT"}),
    )
