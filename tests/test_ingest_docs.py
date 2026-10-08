import json
import pytest
from pathlib import Path

from scripts.ingest_docs import chunk_markdown, main


def test_chunk_markdown_headers(tmp_path):
    doc = tmp_path / "sample.md"
    content = """# Title
Intro paragraph.

## Section 1
Details in section 1.

### Subsection 1.1
More nested details.

## Section 2
Final summary.
"""
    doc.write_text(content, encoding="utf-8")

    chunks = chunk_markdown(str(doc))
    assert len(chunks) == 4
    assert chunks[0].startswith("# Title")
    assert "Intro paragraph." in chunks[0]
    assert chunks[1].startswith("## Section 1")
    assert chunks[2].startswith("### Subsection 1.1")
    assert chunks[3].startswith("## Section 2")


def test_chunk_markdown_no_headers(tmp_path):
    doc = tmp_path / "plain.md"
    content = "Just plain text\nacross two lines."
    doc.write_text(content, encoding="utf-8")

    chunks = chunk_markdown(str(doc))
    assert len(chunks) == 1
    assert chunks[0] == content


def test_chunk_markdown_empty_file(tmp_path):
    doc = tmp_path / "empty.md"
    doc.write_text("", encoding="utf-8")

    chunks = chunk_markdown(str(doc))
    assert len(chunks) == 0 or (len(chunks) == 1 and chunks[0] == "")


def test_main_ingestion_pipeline(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    doc1 = docs_dir / "doc1.md"
    doc1.write_text("# Doc 1\nContent 1\n## Part B\nContent B", encoding="utf-8")

    doc2 = docs_dir / "doc2.md"
    doc2.write_text("# Doc 2\nSingle chunk", encoding="utf-8")

    main()

    out, err = capsys.readouterr()
    assert "Ingested 2 files" in out
    assert "docs/ingestion_ready.jsonl" in out

    out_file = docs_dir / "ingestion_ready.jsonl"
    assert out_file.exists()

    records = [json.loads(line) for line in out_file.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 3

    ids = [r["id"] for r in records]
    assert any("doc1.md_chunk_0" in i for i in ids)
    assert any("doc1.md_chunk_1" in i for i in ids)
    assert any("doc2.md_chunk_0" in i for i in ids)
    assert all("content" in r and "source" in r for r in records)
