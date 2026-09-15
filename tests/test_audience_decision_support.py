import pytest
import json
from pathlib import Path
from scripts.audience_decision_support import (
    extract_observable_facts,
    compute_preview_decision_hash,
    generate_audience_decision_card
)

def test_extract_observable_facts():
    f = extract_observable_facts("golden_trophy_short", {})
    assert "Erdbeere (Strawberry)" in f.characters_depicted
    
    f2 = extract_observable_facts("other", {"tags": ["a"]})
    assert "a" in f2.characters_depicted

def test_compute_preview_decision_hash():
    h1 = compute_preview_decision_hash(content_id="A", media_sha256="b", publication_fingerprint="c", decision="MADE_FOR_KIDS")
    h2 = compute_preview_decision_hash(content_id="A", media_sha256="b", publication_fingerprint="c", decision="MADE_FOR_KIDS")
    assert h1 == h2

def test_generate_audience_decision_card_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        generate_audience_decision_card(tmp_path / "missing.json")

def test_generate_audience_decision_card_valid(tmp_path):
    pkg_file = tmp_path / "publish_package.json"
    pkg_file.write_text(json.dumps({
        "media_path": "a/b/c.mp4",
        "media_sha256": "def",
        "publication_dedupe_fingerprint": "ghi",
        "content_title": "title",
        "audience_decision": "DECISION_REQUIRED"
    }))
    card = generate_audience_decision_card(pkg_file)
    assert card["content_id"] == tmp_path.name
    assert card["human_readable_title"] == "title"
    assert card["decision_status"] == "PENDING_HUMAN_DECISION"
