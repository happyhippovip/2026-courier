import json
from pathlib import Path

from scripts import ingest_docs


def test_ingest_does_not_follow_a_symlink(tmp_path, monkeypatch):
    def run(root: Path):
        monkeypatch.chdir(root)
        try:
            ingest_docs.main()
            return None
        except ValueError as exc:
            return str(exc)

    output_root = tmp_path / "output-case"
    docs = output_root / "docs"
    docs.mkdir(parents=True)
    (docs / "note.md").write_text("# Title\nhello\n", encoding="utf-8")
    outside = tmp_path / "outside.jsonl"
    outside.write_text("SECRET-OUTPUT\n", encoding="utf-8")
    (docs / "ingestion_ready.jsonl").symlink_to(outside)
    output_err = run(output_root)
    output_body = outside.read_text(encoding="utf-8")

    source_root = tmp_path / "source-case"
    source_docs = source_root / "docs"
    source_docs.mkdir(parents=True)
    secret = tmp_path / "secret.md"
    secret.write_text("# Secret\nSECRET-DOC\n", encoding="utf-8")
    (source_docs / "note.md").symlink_to(secret)
    source_err = run(source_root)
    written = source_docs / "ingestion_ready.jsonl"
    source_body = written.read_text(encoding="utf-8") if written.exists() else ""

    dir_root = tmp_path / "dir-case"
    dir_root.mkdir()
    outside_dir = tmp_path / "outside-docs"
    outside_dir.mkdir()
    (outside_dir / "secret.md").write_text("# Secret\nSECRET-DIR\n", encoding="utf-8")
    (outside_dir / "keep.txt").write_text("keep", encoding="utf-8")
    (dir_root / "docs").symlink_to(outside_dir)
    dir_err = run(dir_root)
    dir_written = outside_dir / "ingestion_ready.jsonl"
    dir_body = dir_written.read_text(encoding="utf-8") if dir_written.exists() else ""
    names = sorted(path.name for path in outside_dir.iterdir())

    assert (
        output_err,
        "SECRET-OUTPUT" in output_body,
        "hello" in output_body,
        source_err,
        "SECRET-DOC" in source_body,
        "SECRET-DOC" in secret.read_text(encoding="utf-8"),
        dir_err,
        "SECRET-DIR" in dir_body,
        names,
    ) == (
        "refusing to follow a symlink",
        True,
        False,
        "refusing to follow a symlink",
        False,
        True,
        "refusing to follow a symlink",
        False,
        ["keep.txt", "secret.md"],
    )


def test_main_writes_a_local_chunk(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "note.md").write_text("# Title\nhello\n", encoding="utf-8")
    ingest_docs.main()
    lines = (docs / "ingestion_ready.jsonl").read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[0])
    assert record["source"] == "docs/note.md"
    assert "hello" in record["content"]
    assert len(lines) == 1


def test_windows_source_separator_is_normalized():
    assert ingest_docs.source_label("docs\\note.md") == "docs/note.md"
    assert ingest_docs.source_label("docs/note.md") == "docs/note.md"
