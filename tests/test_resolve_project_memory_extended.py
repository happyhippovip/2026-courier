import pytest
from pathlib import Path

from scripts.resolve_project_memory import (
    ALLOWED_MEMORY_FILES,
    ALWAYS_CONSULTED_FILES,
    STATUS_LABEL_PATTERN,
    classify_and_select_files,
    extract_status_labels,
)

def test_allowed_memory_files_set():
    assert "PROJECT_STATE.md" in ALLOWED_MEMORY_FILES
    assert "AGENTS.md" in ALLOWED_MEMORY_FILES
    assert "PRODUCT_VISION.md" in ALLOWED_MEMORY_FILES
    assert "DECISIONS.md" in ALLOWED_MEMORY_FILES
    for item in ALWAYS_CONSULTED_FILES:
        assert item in ALLOWED_MEMORY_FILES

def test_status_label_matching_all_variants():
    text = (
        "Status: VERIFIED_CURRENT, then EXTERNAL_STATUS and HISTORICAL_DECISION. "
        "Also PLANNED, IDEA, CONFLICT, UNKNOWN, STATUS_BOUNDARY, PAUSED, "
        "PAUSED_EXTERNAL_GATE, DEFERRED, NOT VERIFIED, IN PROGRESS"
    )
    labels = extract_status_labels(text)
    assert "VERIFIED_CURRENT" in labels
    assert "EXTERNAL_STATUS" in labels
    assert "HISTORICAL_DECISION" in labels
    assert "PLANNED" in labels
    assert "IDEA" in labels
    assert "CONFLICT" in labels
    assert "UNKNOWN" in labels
    assert "STATUS_BOUNDARY" in labels
    assert "PAUSED" in labels
    assert "PAUSED_EXTERNAL_GATE" in labels
    assert "DEFERRED" in labels
    assert "NOT VERIFIED" in labels
    assert "IN PROGRESS" in labels

def test_classify_and_select_files_all_rules():
    assert "DECISIONS.md" in classify_and_select_files("we need to review the d-00 policy")
    assert "PRODUCT_VISION.md" in classify_and_select_files("what is our monetization revenue strategy")
    assert "OPEN_QUESTIONS.md" in classify_and_select_files("any clarification on ambiguity")
    assert "LESSONS_LEARNED.md" in classify_and_select_files("what mistakes should we avoid")
    assert "SOURCE_INDEX.md" in classify_and_select_files("check the audit trail provenance")
    assert "IDEA_ARCHIVE.md" in classify_and_select_files("let's brainstorm future ideas")
