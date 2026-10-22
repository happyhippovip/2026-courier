import json

from scripts.run_bodyguards import load_json


def _load(path):
    try:
        return ("loaded", load_json(path))
    except ValueError as exc:
        return ("raised", str(exc))


def test_bodyguard_load_does_not_follow_a_symlink(tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps({"secret": "SECRET-LOAD"}), encoding="utf-8")
    link = tmp_path / "state.json"
    link.symlink_to(outside)

    outside_dir = tmp_path / "outside-dir"
    outside_dir.mkdir()
    (outside_dir / "state.json").write_text(json.dumps({"secret": "SECRET-DIR"}), encoding="utf-8")
    parent = tmp_path / "linked"
    parent.symlink_to(outside_dir)

    local = tmp_path / "local.json"
    local.write_text(json.dumps({"status": "standby"}), encoding="utf-8")

    assert (
        _load(link),
        _load(parent / "state.json"),
        _load(local),
    ) == (
        ("raised", "refusing to follow a symlink"),
        ("raised", "refusing to follow a symlink"),
        ("loaded", {"status": "standby"}),
    )
