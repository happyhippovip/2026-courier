import json

from scripts.execute_p01_transmission import transmit_p01


def _outside(tmp_path, name):
    outside_dir = tmp_path / f"outside-{name}"
    outside_dir.mkdir()
    spec = outside_dir / "FINAL_P01_FOLLOWUP_SPEC.json"
    spec.write_text(
        json.dumps(
            {
                "current_status": "WAITING_FOR_HUMAN",
                "message_fingerprint": f"SECRET-{name}",
            }
        ),
        encoding="utf-8",
    )
    return outside_dir, spec


def _run(root):
    try:
        transmit_p01()
    except ValueError as exc:
        err = str(exc)
    else:
        err = None
    return err


def test_p01_spec_does_not_follow_a_symlink(tmp_path, monkeypatch):
    file_dir, file_spec = _outside(tmp_path, "file")
    file_root = tmp_path / "work-file"
    file_parent = file_root / "events/revenue-opportunities/market_intelligence"
    file_parent.mkdir(parents=True)
    (file_parent / "FINAL_P01_FOLLOWUP_SPEC.json").symlink_to(file_spec)
    monkeypatch.chdir(file_root)
    file_err = _run(file_root)
    file_saved = json.loads(file_spec.read_text(encoding="utf-8"))

    parent_dir, parent_spec = _outside(tmp_path, "parent")
    parent_root = tmp_path / "work-parent"
    parent_link = parent_root / "events/revenue-opportunities/market_intelligence"
    parent_link.parent.mkdir(parents=True)
    parent_link.symlink_to(parent_dir)
    monkeypatch.chdir(parent_root)
    parent_err = _run(parent_root)
    parent_saved = json.loads(parent_spec.read_text(encoding="utf-8"))

    local_root = tmp_path / "work-local"
    local_spec = local_root / "events/revenue-opportunities/market_intelligence/FINAL_P01_FOLLOWUP_SPEC.json"
    local_spec.parent.mkdir(parents=True)
    local_spec.write_text(
        json.dumps(
            {
                "current_status": "WAITING_FOR_HUMAN",
                "message_fingerprint": "SECRET-local",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(local_root)
    local_err = _run(local_root)
    local_saved = json.loads(local_spec.read_text(encoding="utf-8"))

    assert (
        file_err,
        file_saved["current_status"],
        file_saved["message_fingerprint"],
        parent_err,
        parent_saved["current_status"],
        parent_saved["message_fingerprint"],
        local_err,
        local_saved["current_status"],
        local_saved["message_fingerprint"],
    ) == (
        "refusing to follow a symlink",
        "WAITING_FOR_HUMAN",
        "SECRET-file",
        "refusing to follow a symlink",
        "WAITING_FOR_HUMAN",
        "SECRET-parent",
        None,
        "TRANSMITTED_BY_CHIEF",
        "SECRET-local",
    )
