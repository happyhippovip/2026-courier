"""Regression: ingest_docs is CWD-independent and rooted at an explicit base."""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ingest_docs import chunk_markdown, main


@pytest.fixture
def docroot(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("# Title A\nBody A.\n## Sub\nMore.\n", encoding="utf-8")
    (docs / "b.md").write_text("No headers here.\n", encoding="utf-8")
    return tmp_path


def test_chunk_markdown_splits_on_headers(tmp_path):
    target = tmp_path / "x.md"
    target.write_text("# One\ntext\n# Two\nmore\n", encoding="utf-8")
    chunks = chunk_markdown(str(target))
    assert len(chunks) == 2
    assert chunks[0].startswith("# One")
    assert chunks[1].startswith("# Two")


def test_main_writes_records_under_given_root(docroot):
    main(root=docroot)
    out = docroot / "docs" / "ingestion_ready.jsonl"
    records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 3  # 2 chunks from a.md + 1 from b.md
    by_id = {r["id"]: r for r in records}
    assert by_id["a.md_chunk_0"]["source"] == os.path.join("docs", "a.md")
    assert by_id["a.md_chunk_0"]["content"].startswith("# Title A")
    assert by_id["b.md_chunk_0"]["content"] == "No headers here."


def test_main_ignores_caller_cwd(docroot, tmp_path, monkeypatch):
    # Regression: previously main() used CWD-relative "docs/*.md" and
    # "docs/ingestion_ready.jsonl", so running from another directory
    # crashed (or silently ingested the wrong tree).
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    main(root=docroot)
    out = docroot / "docs" / "ingestion_ready.jsonl"
    records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 3
    assert not (elsewhere / "docs").exists()
