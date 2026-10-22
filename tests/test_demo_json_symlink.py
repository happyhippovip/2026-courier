import json

from scripts.run_demo_workflow import load_json, save_json


def _save(path):
    try:
        save_json(path, {"status": "written"})
    except ValueError as exc:
        return str(exc)
    return None


def _load(path):
    try:
        return ("loaded", load_json(path))
    except ValueError as exc:
        return ("raised", str(exc))


def test_demo_json_does_not_follow_a_symlink(tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text("SECRET-DEMO", encoding="utf-8")
    file_link = tmp_path / "link.json"
    file_link.symlink_to(outside)
    file_err = _save(file_link)

    outside_dir = tmp_path / "outside-dir"
    outside_dir.mkdir()
    (outside_dir / "keep.txt").write_text("SECRET-DIR", encoding="utf-8")
    parent = tmp_path / "inbox"
    parent.symlink_to(outside_dir)
    parent_err = _save(parent / "demo.json")

    read_outside = tmp_path / "read-outside.json"
    read_outside.write_text(json.dumps({"secret": "SECRET-READ"}), encoding="utf-8")
    read_link = tmp_path / "read.json"
    read_link.symlink_to(read_outside)
    loaded = _load(read_link)

    assert (
        file_err,
        outside.read_text(encoding="utf-8"),
        parent_err,
        (outside_dir / "demo.json").exists(),
        (outside_dir / "keep.txt").read_text(encoding="utf-8"),
        loaded,
    ) == (
        "refusing to follow a symlink",
        "SECRET-DEMO",
        "refusing to follow a symlink",
        False,
        "SECRET-DIR",
        ("raised", "refusing to follow a symlink"),
    )
