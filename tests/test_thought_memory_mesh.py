#!/usr/bin/env python3
"""Zero-cost synthetic tests for the Thought Coverage Mesh."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_thought_memory_mesh import canonical_hash, run_mesh

MEMORY = Path("/Users/user/Downloads/2026-project-memory")


def message(message_id, timestamp, source, kind, summary, status_label, requested_status=None):
    payload = {"kind": kind, "summary": summary, "status_label": status_label}
    if requested_status:
        payload["requested_status"] = requested_status
    return {"schema_version": "thought-message-1.0", "message_id": message_id, "timestamp": timestamp, "source": source, "payload": payload, "payload_hash": canonical_hash(payload)}


class ThoughtMeshTests(unittest.TestCase):
    def test_coverage_audit_dedupe_delta_and_proposal(self):
        memory_head_before = subprocess.run(
            ["git", "-C", str(MEMORY), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        ).stdout.strip()
        initial = [
            message("m-20260825", "2026-08-25T09:00:00Z", "CHAT_EXPORT", "INTENT", "Keep historical statements classified.", "USER_INTENT"),
            message("m-20260827", "2026-08-27T09:00:00Z", "COURIER_EVENT", "OPEN_QUESTION", "Verify external status before promotion.", "UNKNOWN", "VERIFIED_CURRENT"),
        ]
        initial.append(dict(initial[0]))  # deliberate identical duplicate
        first = run_mesh(initial, {}, MEMORY)
        audit = first["scene_audit"]
        self.assertTrue(audit["coverage_complete"])
        expected_ids = {"m-20260825", "m-20260827"}
        self.assertEqual(first["coverage_ledger"]["message_counts"]["valid_unique"], len(expected_ids))
        self.assertTrue(first["coverage_ledger"]["scanner_ranges"]["THOUGHT_FORWARD_SCANNER"]["message_count"])
        self.assertTrue(first["coverage_ledger"]["scanner_ranges"]["THOUGHT_REVERSE_SCANNER"]["message_count"])
        self.assertTrue(first["coverage_ledger"]["scanner_ranges"]["THOUGHT_MIDPOINT_BACK_SCANNER"]["message_count"])
        self.assertTrue(first["coverage_ledger"]["scanner_ranges"]["THOUGHT_MIDPOINT_FORWARD_SCANNER"]["message_count"])
        self.assertIn("2026-08-26", audit["gaps"])
        self.assertEqual(audit["duplicate_findings"][0]["kind"], "DUPLICATE")
        self.assertEqual(audit["illegal_status_promotions_blocked"], ["m-20260827"])
        self.assertEqual(first["coverage_ledger"]["message_counts"]["delta_processed"], 2)
        self.assertEqual(len(first["memory_update_proposal"]["proposed_changes"]), 1)
        self.assertTrue(first["memory_update_proposal"]["requires_chief_approval"])
        self.assertEqual(first["chief_delivery_adapter"]["delivery_status"], "PREPARED_NOT_DELIVERED")
        second_input = initial + [message("m-20260828", "2026-08-28T09:00:00Z", "WORK_RESULT", "TASK", "Process only the next-day delta.", "PLANNED")]
        second = run_mesh(second_input, first["coverage_ledger"], MEMORY)
        self.assertEqual(second["coverage_ledger"]["message_counts"]["delta_processed"], 1)
        self.assertEqual(second["thought_manager"][0]["message_id"], "m-20260828")
        replay = run_mesh(second_input, second["coverage_ledger"], MEMORY)
        self.assertEqual(replay["coverage_ledger"]["message_counts"]["delta_processed"], 0)
        self.assertIsNone(replay["memory_update_proposal"])
        memory_head_after = subprocess.run(
            ["git", "-C", str(MEMORY), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        ).stdout.strip()
        self.assertEqual(memory_head_before, memory_head_after)

    def test_invalid_empty_changed_hash_and_volume_behavior(self):
        empty = run_mesh([], {}, MEMORY)
        self.assertEqual(empty["coverage_ledger"]["message_counts"]["valid_unique"], 0)
        self.assertIsNone(empty["memory_update_proposal"])
        invalid = {"schema_version": "thought-message-1.0", "message_id": "missing-time", "source": "CHAT_EXPORT", "payload": {}, "payload_hash": canonical_hash({})}
        naive = message("naive", "2026-08-25T09:00:00", "CHAT_EXPORT", "TASK", "Naive timestamp.", "UNKNOWN")
        rejected = run_mesh([invalid, naive], {}, MEMORY)
        self.assertEqual(rejected["coverage_ledger"]["message_counts"]["rejected"], 2)
        sensitive_payload = {"kind": "TASK", "summary": "Do not retain credential material.", "status_label": "UNKNOWN", "api_key": "placeholder-value"}
        sensitive = {"schema_version": "thought-message-1.0", "message_id": "sensitive", "timestamp": "2026-08-25T10:00:00Z", "source": "CHAT_EXPORT", "payload": sensitive_payload, "payload_hash": canonical_hash(sensitive_payload)}
        sensitive_result = run_mesh([sensitive], {}, MEMORY)
        self.assertEqual(sensitive_result["coverage_ledger"]["message_counts"]["rejected"], 1)
        self.assertIsNone(sensitive_result["memory_update_proposal"])
        original = message("stable-id", "2026-08-25T09:00:00Z", "CHAT_EXPORT", "IDEA", "First payload.", "IDEA")
        first = run_mesh([original], {}, MEMORY)
        changed = message("stable-id", "2026-08-26T09:00:00Z", "CHAT_EXPORT", "IDEA", "Changed payload.", "IDEA")
        conflict = run_mesh([changed], first["coverage_ledger"], MEMORY)
        self.assertEqual(conflict["coverage_ledger"]["message_counts"]["delta_processed"], 0)
        self.assertEqual(conflict["scene_audit"]["prior_identity_hash_conflicts"][0]["message_id"], "stable-id")
        volume = [message(f"bulk-{n}", f"2026-08-30T{n // 60:02d}:{n % 60:02d}:00Z", "COURIER_EVENT", "TASK", f"Bulk {n}", "PLANNED") for n in range(1000)]
        bulk = run_mesh(volume, {}, MEMORY)
        self.assertEqual(bulk["coverage_ledger"]["message_counts"]["valid_unique"], 1000)
        self.assertNotIn("message_ids", bulk["coverage_ledger"]["scanner_ranges"]["THOUGHT_FORWARD_SCANNER"])


if __name__ == "__main__":
    unittest.main()
