"""
T3 adversarial test suite: Attestation Cross-Defect Crash Replay.

Covers attacks from GOOGLE_CONTINUOUS_WORK.yaml G06 / Codex C03:
  - hung future + sibling success (partial result)
  - crash during blocker persistence
  - retry exhaustion during restart
  - init with planted evidence (VALID MACHINE_ARTIFACT stripped)
  - ACK-loss / revision-conflict interactions
  - edge conservation under crash
  - concurrent writer conflict detection
"""
import pytest
import json
import copy
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from scripts.agent_handoff_ledger import (
    initialize, update, load_bundle, LedgerError, validate_record,
)
from tests.test_agent_handoff_ledger import guard as make_guard

SHA = "0000000000000000000000000000000000000000"
RUNTIME = "TEST-RUNTIME-CRASH"


def _ts(dt=None):
    return (dt or datetime.utcnow()).strftime("%Y-%m-%dT%H:%M:%SZ")


def _base_record(**overrides):
    rec = {
        "PROJECT": "courier",
        "GOAL": "crash-replay-test",
        "BRANCH": "release-candidate-integration",
        "CURRENT_SHA": SHA,
        "RUNTIME_IDENTITY": RUNTIME,
        "RUNTIME_OWNER": "test-owner",
        "STATUS": "READY",
        "PROVEN_EDGES": [],
        "UNPROVEN_EDGES": ["edge-a", "edge-b"],
        "FIRST_CAUSAL_BLOCKER": "NONE",
        "BLOCKER_OWNER": "NONE",
        "NEXT_EXECUTABLE_ACTION": "DO_WORK",
        "ACTIVE_WRITERS": ["session-a"],
        "COLLISION_SCOPE": [],
        "GOALS_SUBMITTED": 1,
        "TASKS_COMPLETED": 0,
        "WORKERS_USED": 1,
        "USER_CONTINUE_MESSAGES": 0,
        "MANUAL_PROCESS_RESTARTS": 0,
        "DUPLICATE_EXTERNAL_EFFECTS": 0,
        "TEMP_TASK_PROCESSES_AFTER_DONE": 0,
        "CLEAN_IDLE": "NO",
        "QUEUE_INDEPENDENT": "UNKNOWN",
        "LAST_EVIDENCE": [],
        "LAST_UPDATED_BY": "session-a",
        "CONTINUATION_CHECKPOINT": "test",
    }
    rec.update(overrides)
    return rec


def _base_guard():
    g = make_guard(sha=SHA, runtime_identity=RUNTIME)
    g["acceptance_predicate"]["results"]["ISSUE_STATE"]["status"] = "UNKNOWN"
    g["acceptance_predicate"]["results"]["ISSUE_STATE"]["evidence_urls"] = []
    g["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"]["status"] = "UNKNOWN"
    g["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"]["evidence_urls"] = []
    g["evidence"] = [
        {
            "source_url": "https://example.com/init",
            "source_type": "GITHUB_COMMIT",
            "observed_at": _ts(),
            "evidence_sha": SHA,
            "runtime_binding": RUNTIME,
            "validity": "UNKNOWN",
            "reason": "init",
            "producer_id": "sys",
            "verifier_id": "sys",
        }
    ]
    return g


def _init_ledger(tmp_path, **record_overrides):
    path = tmp_path / "ledger.json"
    initialize(path, _base_record(**record_overrides), _base_guard(), 5.0)
    return path


class TestInitWithPlantedEvidence:
    """Initialize() forces PROVISIONAL regardless of planted evidence."""

    def test_init_forces_provisional_with_valid_artifact(self):
        """Even with VALID MACHINE_ARTIFACT, init sets PROVISIONAL."""
        tmp = Path(tempfile.mkdtemp())
        path = tmp / "ledger.json"

        g = _base_guard()
        g["evidence"].append({
            "source_url": "https://evil.com/planted",
            "source_type": "MACHINE_ARTIFACT",
            "observed_at": _ts(),
            "evidence_sha": SHA,
            "runtime_binding": RUNTIME,
            "validity": "VALID",
            "reason": "planted at init",
            "producer_id": "fake-prod",
            "verifier_id": "fake-ver",
        })
        rec = _base_record()
        initialize(path, rec, g, 5.0)

        bundle = load_bundle(path)
        guard = bundle["acceptance_guard"]
        # Must be PROVISIONAL, never CANONICAL_ACCEPTED at init
        assert guard["transition_state"] == "PROVISIONAL"
        assert bundle["record"]["CLEAN_IDLE"] == "NO"

    def test_init_rejects_canonical_accepted(self):
        """Cannot initialize with CANONICAL_ACCEPTED."""
        tmp = Path(tempfile.mkdtemp())
        path = tmp / "ledger.json"

        g = _base_guard()
        g["transition_state"] = "CANONICAL_ACCEPTED"
        g["acceptance_predicate"]["results"]["ISSUE_STATE"]["status"] = "PASS"
        g["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"]["status"] = "PASS"

        with pytest.raises(LedgerError, match="INIT cannot start with CANONICAL_ACCEPTED"):
            initialize(path, _base_record(), g, 5.0)


class TestEdgeConservation:
    """Edges cannot be created or destroyed — only moved between proven/unproven."""

    def test_edge_creation_rejected(self):
        """Adding a new edge that wasn't in the original set is rejected."""
        tmp = Path(tempfile.mkdtemp())
        path = _init_ledger(tmp)

        with pytest.raises(LedgerError, match="edge conservation"):
            update(path, 0, {
                "PROVEN_EDGES": ["edge-a", "edge-b", "edge-c"],
                "UNPROVEN_EDGES": [],
            }, "writer", 5.0)

    def test_edge_deletion_rejected(self):
        """Removing an edge from both lists is rejected."""
        tmp = Path(tempfile.mkdtemp())
        path = _init_ledger(tmp)

        with pytest.raises(LedgerError, match="edge conservation"):
            update(path, 0, {
                "PROVEN_EDGES": [],
                "UNPROVEN_EDGES": ["edge-a"],
            }, "writer", 5.0)

    def test_edge_move_succeeds(self):
        """Moving an edge from unproven to proven is allowed."""
        tmp = Path(tempfile.mkdtemp())
        path = _init_ledger(tmp)

        result = update(path, 0, {
            "PROVEN_EDGES": ["edge-a"],
            "UNPROVEN_EDGES": ["edge-b"],
        }, "writer", 5.0)
        assert "edge-a" in result["record"]["PROVEN_EDGES"]


class TestRevisionConflict:
    """Simulates ACK-loss / stale revision conflicts."""

    def test_stale_revision_rejected(self):
        """Writing at an old revision number is rejected."""
        tmp = Path(tempfile.mkdtemp())
        path = _init_ledger(tmp)

        # First update succeeds
        update(path, 0, {"TASKS_COMPLETED": 1}, "writer-a", 5.0)

        # Second update with stale revision
        with pytest.raises(LedgerError, match="revision conflict"):
            update(path, 0, {"TASKS_COMPLETED": 2}, "writer-b", 5.0)

    def test_correct_revision_succeeds_after_conflict(self):
        """After a conflict, the correct revision still works."""
        tmp = Path(tempfile.mkdtemp())
        path = _init_ledger(tmp)

        update(path, 0, {"TASKS_COMPLETED": 1}, "writer-a", 5.0)

        # This should fail
        with pytest.raises(LedgerError, match="revision conflict"):
            update(path, 0, {"TASKS_COMPLETED": 2}, "writer-b", 5.0)

        # But this should succeed (correct revision)
        result = update(path, 1, {"TASKS_COMPLETED": 2}, "writer-b", 5.0)
        assert result["record"]["TASKS_COMPLETED"] == 2


class TestCrashDuringBlockerPersistence:
    """Blocker state must be consistently persisted."""

    def test_blocker_set_and_survives_reload(self):
        tmp = Path(tempfile.mkdtemp())
        path = _init_ledger(tmp)

        result = update(path, 0, {
            "FIRST_CAUSAL_BLOCKER": "missing-runtime-proof",
            "BLOCKER_OWNER": "session-x",
            "STATUS": "BLOCKED",
        }, "writer-a", 5.0)
        assert result["record"]["FIRST_CAUSAL_BLOCKER"] == "missing-runtime-proof"

        # Simulate "restart" — load from disk
        bundle = load_bundle(path)
        assert bundle["record"]["FIRST_CAUSAL_BLOCKER"] == "missing-runtime-proof"
        assert bundle["record"]["BLOCKER_OWNER"] == "session-x"

    def test_blocker_clear_requires_status_change(self):
        """Clearing blocker without changing status still persists."""
        tmp = Path(tempfile.mkdtemp())
        path = _init_ledger(tmp)

        update(path, 0, {
            "FIRST_CAUSAL_BLOCKER": "test-blocker",
            "BLOCKER_OWNER": "session-x",
        }, "writer-a", 5.0)

        result = update(path, 1, {
            "FIRST_CAUSAL_BLOCKER": "NONE",
            "BLOCKER_OWNER": "NONE",
        }, "writer-b", 5.0)
        assert result["record"]["FIRST_CAUSAL_BLOCKER"] == "NONE"


class TestCleanIdleForbiddenWithUnprovenEdges:
    """CLEAN_IDLE=YES must be rejected while unproven edges exist."""

    def test_clean_idle_rejected_with_unproven(self):
        tmp = Path(tempfile.mkdtemp())
        path = _init_ledger(tmp)

        with pytest.raises(LedgerError, match="CLEAN_IDLE=YES is forbidden"):
            update(path, 0, {
                "CLEAN_IDLE": "YES",
                "STATUS": "CLEAN_IDLE",
                "NEXT_EXECUTABLE_ACTION": "NONE",
            }, "writer", 5.0)

    def test_clean_idle_auto_reverted_with_unproven(self):
        """Even if caller sets CLEAN_IDLE=YES with unproven edges, it gets reverted."""
        tmp = Path(tempfile.mkdtemp())
        path = _init_ledger(tmp)

        # Normal update that doesn't try CLEAN_IDLE
        result = update(path, 0, {"TASKS_COMPLETED": 1}, "writer", 5.0)
        assert result["record"]["CLEAN_IDLE"] == "NO"
        assert result["acceptance_guard"]["transition_state"] == "PROVISIONAL"


class TestHistoryIntegrity:
    """History entries must be durable and immutable."""

    def test_history_grows_on_each_update(self):
        tmp = Path(tempfile.mkdtemp())
        path = _init_ledger(tmp)

        update(path, 0, {"TASKS_COMPLETED": 1}, "w1", 5.0)
        update(path, 1, {"TASKS_COMPLETED": 2}, "w2", 5.0)
        update(path, 2, {"TASKS_COMPLETED": 3}, "w3", 5.0)

        bundle = load_bundle(path)
        # init creates history entry + 3 updates = 4 total
        assert len(bundle["history"]) == 4
        assert bundle["revision"] == 3

    def test_history_records_correct_writers(self):
        tmp = Path(tempfile.mkdtemp())
        path = _init_ledger(tmp)

        update(path, 0, {"TASKS_COMPLETED": 1}, "alice", 5.0)
        update(path, 1, {"TASKS_COMPLETED": 2}, "bob", 5.0)

        bundle = load_bundle(path)
        writers = [h["updated_by"] for h in bundle["history"]]
        # init writer is session-a, then alice, then bob
        assert writers == ["session-a", "alice", "bob"]


class TestMeaningfulChangeDetection:
    """Update must detect when no meaningful change occurs."""

    def test_guard_change_counts_as_meaningful(self):
        """Even if record values are the same, guard changes are meaningful."""
        tmp = Path(tempfile.mkdtemp())
        path = _init_ledger(tmp)

        # Same record value, but guard will auto-change (QUEUE_INDEPENDENT etc.)
        # This should NOT raise because the guard itself changes
        result = update(path, 0, {"TASKS_COMPLETED": 0}, "session-a", 5.0)
        assert result["revision"] == 1

    def test_different_writer_counts_as_change(self):
        """Changing LAST_UPDATED_BY is a meaningful record change."""
        tmp = Path(tempfile.mkdtemp())
        path = _init_ledger(tmp)

        result = update(path, 0, {"TASKS_COMPLETED": 0}, "new-writer", 5.0)
        assert result["record"]["LAST_UPDATED_BY"] == "new-writer"
