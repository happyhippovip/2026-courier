import json

from scripts.run_content_production_pipeline import load_json, save_json, sha256_file


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


def _hash(path):
    try:
        return ("hashed", sha256_file(path))
    except ValueError as exc:
        return ("raised", str(exc))


def test_content_json_does_not_follow_a_symlink(tmp_path):
    save_outside = tmp_path / "save-outside.json"
    save_outside.write_text("SECRET-SAVE", encoding="utf-8")
    save_link = tmp_path / "save.json"
    save_link.symlink_to(save_outside)
    save_err = _save(save_link)

    outside_dir = tmp_path / "outside-dir"
    outside_dir.mkdir()
    (outside_dir / "keep.txt").write_text("SECRET-DIR", encoding="utf-8")
    parent = tmp_path / "inbox"
    parent.symlink_to(outside_dir)
    parent_err = _save(parent / "stage.json")

    load_outside = tmp_path / "load-outside.json"
    load_outside.write_text(json.dumps({"secret": "SECRET-LOAD"}), encoding="utf-8")
    load_link = tmp_path / "load.json"
    load_link.symlink_to(load_outside)
    loaded = _load(load_link)

    hash_outside = tmp_path / "hash-outside.txt"
    hash_outside.write_bytes(b"SECRET-HASH")
    hash_link = tmp_path / "hash.txt"
    hash_link.symlink_to(hash_outside)
    hashed = _hash(hash_link)

    assert (
        save_err,
        save_outside.read_text(encoding="utf-8"),
        parent_err,
        (outside_dir / "stage.json").exists(),
        (outside_dir / "keep.txt").read_text(encoding="utf-8"),
        loaded,
        hashed,
    ) == (
        "refusing to follow a symlink",
        "SECRET-SAVE",
        "refusing to follow a symlink",
        False,
        "SECRET-DIR",
        ("raised", "refusing to follow a symlink"),
        ("raised", "refusing to follow a symlink"),
    )
