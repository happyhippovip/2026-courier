#!/usr/bin/env python3
"""Fix-guard rails for DLQ-01/DLQ-02/DLQ-07.

These tests pin the NEGATIVE matrix: legitimate behaviors Google's fixes must
NOT break. All pass on current code; each encodes the exact boundary of the
decided invariant so an over-blocking fix fails loudly.

Scope: Muse packet-QA collateral (tests/ is a safe Muse write). No production
code touched.
"""

import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "agent_handoff_ledger.py"
SPEC = importlib.util.spec_from_file_location("agent_handoff_ledger", CLI)
assert SPEC and SPEC.loader
ledger = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ledger)

SHA = "d" * 40
RT = "guard-test-runtime"
ISSUE_URL = "https://github.com/example/project/issues/9"


def now_utc():
    return datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def record(**over):
    base = {
        "PROJECT": "happyhippovip/2026-courier",
        "GOAL": "fix-guard rails",
        "CURRENT_SHA": SHA,
        "BRANCH": "release-candidate-integration",
        "RUNTIME_IDENTITY": RT,
        "RUNTIME_OWNER": "guard-test",
        "STATUS": "WAITING_PHYSICAL_PROOF",
        "PROVEN_EDGES": ["issue state"],
        "UNPROVEN_EDGES": [],
        "FIRST_CAUSAL_BLOCKER": "NONE",
        "BLOCKER_OWNER": "guard-test",
        "NEXT_EXECUTABLE_ACTION": "await proof",
        "ACTIVE_WRITERS": ["guard-test"],
        "COLLISION_SCOPE": [],
        "GOALS_SUBMITTED": 0,
        "TASKS_COMPLETED": 0,
        "WORKERS_USED": 0,
        "USER_CONTINUE_MESSAGES": 0,
        "MANUAL_PROCESS_RESTARTS": 0,
        "DUPLICATE_EXTERNAL_EFFECTS": 0,
        "TEMP_TASK_PROCESSES_AFTER_DONE": 0,
        "CLEAN_IDLE": "NO",
        "QUEUE_INDEPENDENT": "NO",
        "LAST_EVIDENCE": [ISSUE_URL],
        "LAST_UPDATED_BY": "guard-test",
        "CONTINUATION_CHECKPOINT": "guard-test",
    }
    base.update(over)
    return base


def guard():
    return {
        "flow": list(ledger.FLOW),
        "transition_state": "PROVISIONAL",
        "binding": {"branch": "release-candidate-integration",
                    "current_sha": SHA, "runtime_identity": RT},
        "worker_state": "READY_FOR_FOREIGN_VALIDATION",
        "evidence": [{
            "source_url": ISSUE_URL,
            "source_type": "GITHUB_ISSUE_STATE",
            "observed_at": now_utc(),
            "evidence_sha": SHA,
            "runtime_binding": RT,
            "validity": "VALID",
            "reason": "issue observed",
        }],
        "acceptance_predicate": {
            "name": "courier-physical-acceptance",
            "version": "1",
            "required_results": ["ISSUE_STATE", "RUNTIME_ARTIFACT"],
            "results": {
                "ISSUE_STATE": {"status": "PASS", "observed_value": "CLOSED",
                                "evidence_urls": [ISSUE_URL]},
                "RUNTIME_ARTIFACT": {"status": "UNKNOWN",
                                     "observed_value": "NOT_BOUND",
                                     "evidence_urls": []},
            },
        },
    }


ART_URL = "https://github.com/example/project/actions/runs/guard-1"

# Offline attestation receipts for the pinned two-step flow: introduction
# (update N) lands PROVISIONAL without a receipt; promotion (update N+1,
# independent writer, pre-existing evidence) requires a strictly verified
# receipt. The production seam exists for exactly this; the resolver below
# answers only the fixture URLs so no live network is needed.
ATTESTATIONS = {
    ART_URL + "-tw": ("indep-producer", "indep-verifier"),
    ART_URL + "-fr": ("fresh-prod", "fresh-ver"),
}


def install_resolver():
    previous = ledger._attestation_resolver

    def resolve(url):
        if url not in ATTESTATIONS:
            return None
        producer, verifier = ATTESTATIONS[url]
        return {
            "verdict": "PASS",
            "producer_principal": producer,
            "verifier_principal": verifier,
            "goal_id": "fix-guard rails",
            "binding": {"sha": SHA, "runtime": RT},
        }

    ledger._attestation_resolver = resolve
    return previous


def artifact(url_suffix, producer, verifier):
    return {
        "source_url": ART_URL + url_suffix,
        "source_type": "MACHINE_ARTIFACT",
        "observed_at": now_utc(),
        "evidence_sha": SHA,
        "runtime_binding": RT,
        "validity": "VALID",
        "reason": "independent attestation",
        "producer_id": producer,
        "verifier_id": verifier,
    }


def with_pass(g, url):
    g["acceptance_predicate"]["results"]["RUNTIME_ARTIFACT"] = {
        "status": "PASS", "observed_value": "BOUND", "evidence_urls": [url]}
    return g


class FixGuardTests(unittest.TestCase):
    def test_legit_two_writer_accumulation_accepted(self):
        """DLQ-01 negative: introducer A != promoter B with independent
        producer/verifier must keep working after the writer-independence fix.
        """
        path = Path("/tmp") / "guard_two_writer.json"
        if path.exists():
            path.unlink()
        previous = install_resolver()
        try:
            ledger.initialize(path, record(), guard(), 5.0)
            g1 = with_pass(guard(), ART_URL + "-tw")
            g1["evidence"].append(artifact("-tw", "indep-producer", "indep-verifier"))
            b1 = ledger.update(path, 0, {"TASKS_COMPLETED": 1},
                               "writer-A", 5.0, g1)
            self.assertEqual(b1["acceptance_guard"]["transition_state"],
                             "PROVISIONAL")
            # Independent writer-B promotes with NO new evidence.
            b2 = ledger.update(path, 1, {"TASKS_COMPLETED": 2}, "writer-B", 5.0)
            self.assertEqual(b2["acceptance_guard"]["transition_state"],
                             "CANONICAL_ACCEPTED")
        finally:
            ledger._attestation_resolver = previous

    def test_fresh_bound_evidence_promotes(self):
        """DLQ-02 negative: fresh (now-stamped) bound VALID evidence must keep
        promoting after the recency fix."""
        path = Path("/tmp/guard_fresh.json")
        if path.exists():
            path.unlink()
        previous = install_resolver()
        try:
            ledger.initialize(path, record(), guard(), 5.0)
            g1 = with_pass(guard(), ART_URL + "-fr")
            g1["evidence"].append(artifact("-fr", "fresh-prod", "fresh-ver"))
            ledger.update(path, 0, {"TASKS_COMPLETED": 1}, "w1", 5.0, g1)
            b2 = ledger.update(path, 1, {"TASKS_COMPLETED": 2}, "w2", 5.0)
            self.assertEqual(b2["acceptance_guard"]["transition_state"],
                             "CANONICAL_ACCEPTED")
        finally:
            ledger._attestation_resolver = previous

    def test_provisional_init_round_trips(self):
        """DLQ-07 negative: PROVISIONAL INIT must keep loading clean after the
        INIT-must-be-PROVISIONAL fix."""
        path = Path("/tmp/guard_init.json")
        if path.exists():
            path.unlink()
        b = ledger.initialize(path, record(), guard(), 5.0)
        loaded = ledger.load_bundle(path)
        self.assertEqual(loaded["revision"], 0)
        self.assertEqual(
            loaded["acceptance_guard"]["transition_state"], "PROVISIONAL")
        self.assertEqual(b["acceptance_guard"]["transition_state"],
                         "PROVISIONAL")

    def test_unknown_github_evidence_never_proves(self):
        """Migration guard: production-ledger-shaped evidence (GITHUB_COMMIT /
        UNKNOWN, aged date) must never count as physical proof, so a recency
        fix scoped to VALID MACHINE_ARTIFACT cannot strand the live ledger."""
        path = Path("/tmp/guard_prodshape.json")
        if path.exists():
            path.unlink()
        rec = record()
        g = guard()
        g["evidence"] = [{
            "source_url": "https://github.com/happyhippovip/2026-courier/commit/" + "e" * 40,
            "source_type": "GITHUB_COMMIT",
            "observed_at": "2026-09-17T12:00:00Z",
            "evidence_sha": "e" * 40,
            "runtime_binding": RT,
            "validity": "UNKNOWN",
            "reason": "production shape",
        }]
        g["acceptance_predicate"]["results"]["ISSUE_STATE"] = {
            "status": "UNKNOWN", "observed_value": "UNOBSERVED",
            "evidence_urls": []}
        ledger.initialize(path, rec, g, 5.0)
        b1 = ledger.update(path, 0, {"TASKS_COMPLETED": 1}, "motor", 5.0)
        self.assertNotEqual(
            b1["acceptance_guard"]["transition_state"], "CANONICAL_ACCEPTED")


if __name__ == "__main__":
    unittest.main()
