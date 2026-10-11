#!/usr/bin/env python3
"""Idea Foundry Phase 2 (Issue #3): Sort / Link / Synthesize -> Red Team -> Portfolio.

Covers the regressions found in the first #171/#172/#174 drafts:
* unrelated ideas were merged purely because they shared ``kind`` (Frankenstein),
* contradiction detection was order-dependent,
* the kill engine substring-matched raw thoughts ("Founder Concierge" -> KILLED),
* missing metrics produced an invented negative score,
* Phase 2 output leaked into the Chief memory proposal.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from foundry_kill_engine import run_kill_engine  # noqa: E402
from foundry_portfolio_scoring import run_portfolio_scoring  # noqa: E402
from foundry_synthesizer import detect_contradictions, run_foundry  # noqa: E402
from run_thought_memory_mesh import canonical_hash, run_mesh  # noqa: E402
from test_thought_memory_mesh import MEMORY  # noqa: E402

FULL_METRICS = {"problem_strength": 8, "wtp_evidence": 6, "buyer_access": 5, "build_effort": 3, "compliance_risk": 1, "evidence_confidence": 0.6}


def thought(mid, summary, kind="IDEA", **facets):
    return {"message_id": mid, "source": "CHAT_EXPORT", "kind": kind, "summary": summary, "status_label": "IDEA", "payload_hash": mid, "facets": facets}


def envelope(mid, ts, kind, summary, facets=None):
    payload = {"kind": kind, "summary": summary, "status_label": "IDEA"}
    if facets:
        payload["facets"] = facets
    return {"schema_version": "thought-message-1.0", "message_id": mid, "timestamp": ts, "source": "CHAT_EXPORT", "payload": payload, "payload_hash": canonical_hash(payload)}


class SynthesisTests(unittest.TestCase):
    def test_keyword_overlap_alone_never_synthesizes(self):
        result = run_foundry([
            thought("a", "Desktop overlay robot shows agent status"),
            thought("b", "Desktop overlay robot shows billing status"),
        ])
        self.assertEqual(result["synthesized_candidates"], [])
        self.assertEqual(result["weak_links_not_synthesized"], 1)
        self.assertEqual(result["relationship_graph"][0]["type"], "RELATED_TEXT")

    def test_same_kind_unrelated_ideas_not_merged(self):
        result = run_foundry([thought("a", "Add Stripe billing for agencies."), thought("b", "Dark mode for the desktop overlay.")])
        self.assertEqual(result["synthesized_candidates"], [])

    def test_shared_problem_synthesizes_traceable_candidate(self):
        result = run_foundry([
            thought("a", "Founders lose track of approvals", problem="approval tracking", customer="solo founder"),
            thought("b", "A weekly digest of pending approvals", problem="Approval  tracking", customer="solo founder"),
            thought("c", "Unrelated: faster installer"),
        ])
        [cand] = result["synthesized_candidates"]
        self.assertEqual(cand["source_thought_ids"], ["a", "b"])
        self.assertEqual(cand["problem_hypothesis"], "approval tracking")
        self.assertEqual(cand["target_user_hypothesis"], "solo founder")
        self.assertEqual(cand["expected_outcome"], "UNKNOWN")
        self.assertEqual(cand["confidence"], "UNKNOWN")

    def test_dedup_links_without_destroying_originals(self):
        inputs = [
            thought("a", "Weekly approval digest for founders", problem="approval tracking"),
            thought("a2", "weekly approval digests for founders!", problem="approval tracking"),
            thought("b", "Slack reminder for stale approvals", problem="approval tracking"),
        ]
        before = copy.deepcopy(inputs)
        result = run_foundry(inputs)
        self.assertEqual(inputs, before)
        self.assertEqual(result["duplicate_links"], {"a2": "a"})
        [cand] = result["synthesized_candidates"]
        self.assertEqual(cand["source_thought_ids"], ["a", "a2", "b"])

    def test_contradiction_is_symmetric(self):
        x = thought("x", "Cache provider responses locally")
        y = thought("y", "Never cache provider responses")
        self.assertEqual(detect_contradictions([x, y]), detect_contradictions([y, x]))
        self.assertEqual(len(detect_contradictions([x, y])), 1)

    def test_tasks_and_decisions_are_not_foundry_input(self):
        result = run_foundry([thought("t", "Ship installer", kind="TASK"), thought("d", "Keep legal disclaimer", kind="DECISION")])
        self.assertEqual(result["thoughts_considered"], 0)

    def test_idempotent(self):
        inputs = [thought("a", "x one", problem="p"), thought("b", "y two", problem="p")]
        self.assertEqual(run_foundry(inputs), run_foundry(list(reversed(inputs))))


class RedTeamAndScoringTests(unittest.TestCase):
    def base(self, **over):
        cand = {"candidate_id": "c", "source_thought_ids": ["a", "b"], "problem_hypothesis": "p", "target_user_hypothesis": "u", "contradictions": [], "risk_flags": {}, "metrics": {}}
        cand.update(over)
        return cand

    def test_no_substring_kill_of_product_vocabulary(self):
        result = run_kill_engine([self.base(problem_hypothesis="founder concierge legal export for everyone")])
        self.assertEqual(result["killed"], [])
        self.assertEqual(len(result["experiment_ready"]), 1)

    def test_explicit_flag_kills_with_evidence(self):
        result = run_kill_engine([self.base(risk_flags={"regulatory_burden": True})])
        [killed] = result["killed"]
        self.assertEqual(killed["status"], "KILLED")
        self.assertEqual(killed["red_team_reasons"][0]["evidence"], "risk_flags.regulatory_burden=true")

    def test_unknown_buyer_or_contradiction_parks(self):
        result = run_kill_engine([self.base(candidate_id="u", target_user_hypothesis="UNKNOWN"),
                                  self.base(candidate_id="k", contradictions=[{"source_a": "a", "source_b": "b"}])])
        self.assertEqual(sorted(c["candidate_id"] for c in result["parked"]), ["k", "u"])
        self.assertEqual(result["weak_work_dropped"], 2)

    def test_missing_metrics_score_unknown_not_invented(self):
        result = run_portfolio_scoring([self.base(metrics={"problem_strength": 9})])
        score = result["sorted_portfolio"][0]["portfolio_score"]
        self.assertEqual(score["score"], "UNKNOWN")
        self.assertIn("evidence_confidence", score["missing_metrics"])

    def test_scored_before_unknown_and_ordered(self):
        weak = dict(FULL_METRICS, wtp_evidence=0)
        result = run_portfolio_scoring([self.base(candidate_id="unk"), self.base(candidate_id="weak", metrics=weak), self.base(candidate_id="strong", metrics=FULL_METRICS)])
        self.assertEqual([c["candidate_id"] for c in result["sorted_portfolio"]], ["strong", "weak", "unk"])


class MeshIntegrationTests(unittest.TestCase):
    """Issue #3 DoD slice: 10+ messy thoughts through the real mesh product path."""

    def messages(self):
        appr = {"problem": "approval tracking", "customer": "solo founder", "outcome": "no missed approvals", "metrics": FULL_METRICS}
        return [
            envelope("m01", "2026-09-01T09:00:00Z", "IDEA", "Founders lose track of approvals across chats", appr),
            envelope("m02", "2026-09-01T09:05:00Z", "IDEA", "Weekly digest of pending approvals", appr),
            envelope("m03", "2026-09-01T09:06:00Z", "IDEA", "weekly digest of pending approvals!!", appr),
            envelope("m04", "2026-09-01T10:00:00Z", "IDEA", "Auto-file receipts for accountants", {"problem": "receipt filing", "risk_flags": {"regulatory_burden": True}}),
            envelope("m05", "2026-09-01T10:01:00Z", "IDEA", "OCR receipts from email", {"problem": "receipt filing"}),
            envelope("m06", "2026-09-02T08:00:00Z", "IDEA", "Overlay robot waves when idle", {"problem": "idle visibility"}),
            envelope("m07", "2026-09-02T08:01:00Z", "IDEA", "Overlay robot should never animate", {"problem": "idle visibility"}),
            envelope("m08", "2026-09-02T09:00:00Z", "IDEA", "Dark mode for desktop hub"),
            envelope("m09", "2026-09-02T09:30:00Z", "TASK", "Founder Concierge dossier export verified"),
            envelope("m10", "2026-09-02T10:00:00Z", "DECISION", "Keep the legal disclaimer in the installer"),
            envelope("m11", "2026-09-03T11:00:00Z", "OPEN_QUESTION", "Do agencies pay for approval digests?", {"problem": "approval tracking", "customer": "solo founder", "outcome": "no missed approvals"}),
        ]

    def test_full_mesh_slice(self):
        msgs = self.messages()
        originals = copy.deepcopy(msgs)
        baseline = run_mesh([m for m in msgs], {}, MEMORY)  # same input, used for proposal comparison
        result = run_mesh(msgs, {}, MEMORY)
        self.assertEqual(msgs, originals)
        self.assertEqual(result["coverage_ledger"]["message_counts"]["rejected"], 0)
        foundry = result["foundry"]
        self.assertEqual(foundry["thoughts_considered"], 9)
        self.assertEqual(foundry["duplicate_links"], {"m03": "m02"})
        by_problem = {c["problem_hypothesis"]: c for c in foundry["synthesized_candidates"]}
        self.assertEqual(set(by_problem), {"approval tracking", "receipt filing", "idle visibility"})
        self.assertEqual(by_problem["approval tracking"]["source_thought_ids"], ["m01", "m02", "m03", "m11"])
        red = foundry["red_team"]
        self.assertEqual([c["problem_hypothesis"] for c in red["killed"]], ["receipt filing"])
        self.assertEqual(sorted(c["problem_hypothesis"] for c in red["parked"]), ["idle visibility"])
        [ready] = foundry["portfolio"]["sorted_portfolio"]
        self.assertEqual(ready["problem_hypothesis"], "approval tracking")
        self.assertNotEqual(ready["portfolio_score"]["score"], "UNKNOWN")
        # Phase 2 is advisory: memory proposal references only raw messages, never foundry ids.
        refs = result["memory_update_proposal"]["source_references"]
        self.assertEqual(refs, baseline["memory_update_proposal"]["source_references"])
        self.assertFalse(any(r.startswith("fcand-") for r in refs))


if __name__ == "__main__":
    unittest.main()
