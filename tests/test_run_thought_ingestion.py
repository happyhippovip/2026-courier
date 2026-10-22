import json

from scripts.run_thought_ingestion import run_ingestion


def test_rejected_dir_does_not_follow_a_symlink(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "bad.json").write_text(json.dumps({"secret": "SECRET-THOUGHT"}), encoding="utf-8")
    processed = tmp_path / "processed"
    memory = tmp_path / "memory"
    memory.mkdir()

    outside = tmp_path / "outside-rejected"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked = tmp_path / "linked-rejected"
    linked.symlink_to(outside, target_is_directory=True)

    parent_outside = tmp_path / "rejected-parent-outside"
    parent_outside.mkdir()
    (parent_outside / "keep.txt").write_text("keep", encoding="utf-8")
    linked_parent = tmp_path / "rejected-linked-parent"
    linked_parent.symlink_to(parent_outside, target_is_directory=True)

    def run(folder):
        try:
            run_ingestion(inbox, processed, folder, memory)
        except ValueError as exc:
            return str(exc)
        return "wrote"

    err_link = run(linked)
    leaked = sorted(p.name for p in outside.iterdir())
    err_parent = run(linked_parent / "rejected")
    parent_names = sorted(p.name for p in parent_outside.iterdir())
    plain = tmp_path / "plain-rejected"
    err_plain = run(plain)
    plain_names = sorted(p.name for p in plain.iterdir()) if plain.exists() else []
    assert (
        err_link,
        leaked,
        err_parent,
        parent_names,
        err_plain,
        "bad-rejected.json" in plain_names,
    ) == (
        "refusing to follow a symlink",
        ["keep.txt"],
        "refusing to follow a symlink",
        ["keep.txt"],
        "wrote",
        True,
    )
