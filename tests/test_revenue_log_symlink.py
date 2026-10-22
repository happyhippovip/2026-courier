from scripts import revenue_worker_adapter


def _write(monkeypatch, logs_dir):
    monkeypatch.setattr(revenue_worker_adapter, "LOGS_DIR", logs_dir)
    try:
        revenue_worker_adapter.write_log("hello")
    except ValueError as exc:
        return str(exc)
    return None


def test_revenue_log_does_not_follow_a_symlink(monkeypatch, tmp_path, capsys):
    outside = tmp_path / "outside.log"
    outside.write_text("SECRET-LOG", encoding="utf-8")
    file_dir = tmp_path / "file-logs"
    file_dir.mkdir()
    (file_dir / "revenue_worker.log").symlink_to(outside)
    file_err = _write(monkeypatch, file_dir)

    outside_dir = tmp_path / "outside-dir"
    outside_dir.mkdir()
    (outside_dir / "keep.txt").write_text("SECRET-DIR", encoding="utf-8")
    parent = tmp_path / "linked-logs"
    parent.symlink_to(outside_dir)
    parent_err = _write(monkeypatch, parent)

    local = tmp_path / "local-logs"
    local.mkdir()
    local_err = _write(monkeypatch, local)
    local_text = (local / "revenue_worker.log").read_text(encoding="utf-8")

    assert (
        file_err,
        outside.read_text(encoding="utf-8"),
        parent_err,
        (outside_dir / "revenue_worker.log").exists(),
        (outside_dir / "keep.txt").read_text(encoding="utf-8"),
        local_err,
        "hello" in local_text,
    ) == (
        "refusing to follow a symlink",
        "SECRET-LOG",
        "refusing to follow a symlink",
        False,
        "SECRET-DIR",
        None,
        True,
    )
    capsys.readouterr()
