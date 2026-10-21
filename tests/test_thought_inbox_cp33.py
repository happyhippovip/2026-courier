"""Tests for CP-33 / CQ-33 / GB-THOUGHT-DEDUP-01: Thought Inbox Engine & Project Dedup Guard.

Verifies:
1. Zero model jobs spawned when saving thoughts ("Speichern erzeugt keinen Modelljob").
2. Exact deduplication within the same project.
3. Uncertain/fuzzy similarity is flagged as candidate suggestion and NEVER silently merged.
4. Strict cross-project isolation ("Kein fremdes Projekt betroffen").
5. Immutable preservation of raw text and provenance metadata.
6. Evidence generated with ['thought-schema', 'project-identity', 'dedup-cases'].
"""

import pytest

from courier_core.thought_inbox_engine import (
    DedupMatchStatus,
    ThoughtInboxEngine,
    ThoughtProvenance,
)


def test_saving_thought_spawns_zero_model_jobs():
    """Ingesting and saving thoughts is purely deterministic and costs zero model tokens."""
    engine = ThoughtInboxEngine()
    prov = ThoughtProvenance(
        created_at_iso="2026-10-21T11:30:00Z",
        source_channel="slack_quick_note",
        author="dennis",
    )

    record = engine.ingest_thought(
        thought_id="th-001",
        project_id="courier",
        raw_text="Verify that lease timeout is 6 seconds.",
        provenance=prov,
    )

    assert record.model_jobs_spawned == 0
    assert engine.total_model_jobs == 0
    assert record.dedup_status == DedupMatchStatus.UNIQUE


def test_exact_deduplication_detected_within_same_project():
    """Exact duplicates (normalized for whitespace and casing) are marked without deleting raw data."""
    engine = ThoughtInboxEngine()
    prov = ThoughtProvenance(
        created_at_iso="2026-10-21T11:30:00Z",
        source_channel="web_ui",
        author="dennis",
    )

    r1 = engine.ingest_thought(
        thought_id="th-101",
        project_id="courier",
        raw_text="Add Windows exe build test",
        provenance=prov,
    )
    assert r1.dedup_status == DedupMatchStatus.UNIQUE

    # Identical with mixed case and extra spaces
    r2 = engine.ingest_thought(
        thought_id="th-102",
        project_id="courier",
        raw_text="  add   WINDOWS  exe  BUILD  test   ",
        provenance=prov,
    )
    assert r2.dedup_status == DedupMatchStatus.EXACT_DUPLICATE
    assert r2.candidate_duplicate_of == "th-101"
    # Raw text preserved
    assert r2.raw_text == "  add   WINDOWS  exe  BUILD  test   "


def test_uncertain_similarity_suggested_never_silently_merged():
    """Similar wording is surfaced as UNCERTAIN_SUGGESTION and never silently merged."""
    engine = ThoughtInboxEngine()
    prov = ThoughtProvenance(
        created_at_iso="2026-10-21T11:30:00Z",
        source_channel="mobile",
        author="dennis",
    )

    r1 = engine.ingest_thought(
        thought_id="th-201",
        project_id="courier",
        raw_text="Optimize SQLite write transaction boundaries for speed",
        provenance=prov,
    )

    # Similar but distinct thought
    r2 = engine.ingest_thought(
        thought_id="th-202",
        project_id="courier",
        raw_text="Optimize SQLite write transaction boundaries and flush intervals",
        provenance=prov,
    )

    assert r2.dedup_status == DedupMatchStatus.UNCERTAIN_SUGGESTION
    assert r2.candidate_duplicate_of == "th-201"
    # Both records remain independently stored; no silent merge
    assert len(engine.inbox_by_project["courier"]) == 2


def test_cross_project_isolation_no_foreign_project_matching():
    """Identical thoughts in distinct projects never match or deduplicate across projects."""
    engine = ThoughtInboxEngine()
    prov = ThoughtProvenance(
        created_at_iso="2026-10-21T11:30:00Z",
        source_channel="chat",
        author="dennis",
    )

    r_courier = engine.ingest_thought(
        thought_id="th-proj-a",
        project_id="courier_project",
        raw_text="Refactor authentication handshake",
        provenance=prov,
    )

    r_other = engine.ingest_thought(
        thought_id="th-proj-b",
        project_id="marketing_project",
        raw_text="Refactor authentication handshake",
        provenance=prov,
    )

    assert r_courier.dedup_status == DedupMatchStatus.UNIQUE
    # Project B must be UNIQUE, not marked as duplicate of Project A
    assert r_other.dedup_status == DedupMatchStatus.UNIQUE
    assert r_other.candidate_duplicate_of is None


def test_raw_text_and_provenance_immutably_preserved():
    """User raw text, timestamps, and channels are preserved without truncation."""
    engine = ThoughtInboxEngine()
    prov = ThoughtProvenance(
        created_at_iso="2026-10-21T11:35:00Z",
        source_channel="terminal",
        author="tester",
    )

    raw = "Crucial thought: Verify $SPEND == 0.00 EUR always!"
    r = engine.ingest_thought(
        thought_id="th-raw-check",
        project_id="courier",
        raw_text=raw,
        provenance=prov,
    )

    assert r.raw_text == raw
    assert r.provenance.source_channel == "terminal"
    assert r.provenance.created_at_iso == "2026-10-21T11:35:00Z"


def test_evidence_generation():
    """Emits required evidence with thought-schema, project-identity, and dedup-cases."""
    engine = ThoughtInboxEngine()
    prov = ThoughtProvenance(
        created_at_iso="2026-10-21T11:30:00Z",
        source_channel="ui",
        author="dennis",
    )
    engine.ingest_thought("th-evid-1", "project-x", "Initial note", prov)
    engine.ingest_thought("th-evid-2", "project-x", "Initial note", prov)

    evidence = engine.generate_thought_inbox_evidence()
    required_keys = ["thought-schema", "project-identity", "dedup-cases"]
    for k in required_keys:
        assert k in evidence

    assert evidence["thought-schema"]["zero_model_job_invariant"] is True
    assert "project-x" in evidence["project-identity"]["isolated_project_partitions"]
    assert evidence["dedup-cases"]["exact_duplicate_count"] == 1
    assert evidence["dedup-cases"]["silent_merges_performed"] == 0
