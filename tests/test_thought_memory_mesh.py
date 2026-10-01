#!/usr/bin/env python3
"""Zero-cost synthetic tests for the Thought Coverage Mesh."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_thought_memory_mesh import canonical_hash, run_mesh, main, load_json, read_messages, parse_timestamp, contains_sensitive_value



def memory_repo() -> Path:
    """Real memory checkout if present (COURIER_MEMORY_REPO or the operator default),
    else a throwaway git repo so the read-only invariant is still exercised."""
    import os
    configured = Path(os.environ.get("COURIER_MEMORY_REPO", "/Users/user/Downloads/2026-project-memory"))
    if (configured / ".git").exists():
        return configured
    scratch = Path(tempfile.mkdtemp(prefix="courier-memory-fixture-"))
    git = ["git", "-C", str(scratch), "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid"]
    subprocess.run(["git", "init", "-q", str(scratch)], check=True)
    subprocess.run(git + ["commit", "-q", "--allow-empty", "-m", "fixture"], check=True)
    return scratch


MEMORY = memory_repo()


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

    def test_edge_cases_and_cli(self):
        # Line 48-50: load_json non-existent path
        import json
        with tempfile.TemporaryDirectory() as td:
            missing_path = Path(td) / "missing.json"
            self.assertEqual(load_json(missing_path, {"default": 1}), {"default": 1})
            
            # Line 78-81: read_messages must be list
            bad_json = Path(td) / "bad.json"
            bad_json.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_messages(bad_json)
                
            # Line 314-325: test main() CLI
            messages_path = Path(td) / "input.json"
            messages_path.write_text(json.dumps([message("cli-1", "2026-08-25T10:00:00Z", "CHAT_EXPORT", "TASK", "CLI test", "UNKNOWN")]), encoding="utf-8")
            ledger_path = Path(td) / "ledger.json"
            output_path = Path(td) / "output.json"
            
            original_argv = sys.argv
            sys.argv = ["run_thought_memory_mesh.py", "--messages", str(messages_path), "--ledger", str(ledger_path), "--output", str(output_path), "--memory-repo", str(MEMORY)]
            try:
                main()
            finally:
                sys.argv = original_argv
                
            self.assertTrue(output_path.exists())
            self.assertTrue(ledger_path.exists())

        # Validation errors (92-93, 97, 100, 103, 105)
        invalid_types = [
            [], # not a dict (92-93)
            {"message_id": 123, "timestamp": "2026-08-25T09:00:00Z", "source": "CHAT_EXPORT", "payload": {}}, # wrong identity type (97)
            {"message_id": "ok", "timestamp": "1999-01-01T00:00:00Z", "source": "CHAT_EXPORT", "payload": {}, "payload_hash": canonical_hash({})}, # before anchor (100)
            {"message_id": "ok2", "timestamp": "2026-08-25T09:00:00Z", "source": "CHAT_EXPORT", "payload": {}, "payload_hash": "badhash"}, # payload hash mismatch (103)
            {"message_id": "ok3", "timestamp": "2026-08-25T09:00:00Z", "source": "CHAT_EXPORT", "payload": {}, "payload_hash": canonical_hash({}), "schema_version": "bad-version"} # bad schema version (105)
        ]
        res = run_mesh(invalid_types, {}, MEMORY)
        self.assertEqual(res["coverage_ledger"]["message_counts"]["rejected"], 5)

        # 198: empty summary in thought_manager
        msg = message("empty-summary", "2026-08-25T10:00:00Z", "CHAT_EXPORT", "TASK", "   ", "UNKNOWN")
        res = run_mesh([msg], {}, MEMORY)
        self.assertEqual(len(res["thought_manager"]), 0)
        
        # 222: "new message alone cannot establish VERIFIED_CURRENT"
        msg = message("v-curr", "2026-08-25T10:00:00Z", "CHAT_EXPORT", "TASK", "Summary", "VERIFIED_CURRENT")
        res = run_mesh([msg], {}, MEMORY)
        self.assertEqual(res["thought_boss_b"]["findings"][0]["reason"], "new message alone cannot establish VERIFIED_CURRENT")

        # 235: fallback to UNKNOWN proposed status
        msg = message("weird-status", "2026-08-25T10:00:00Z", "CHAT_EXPORT", "TASK", "Summary", "MAGIC_STATUS")
        res = run_mesh([msg], {}, MEMORY)
        self.assertEqual(res["memory_update_proposal"]["proposed_changes"][0]["status_label"], "UNKNOWN")

        # Line 55, 67, 73: exception branches parsing timestamp and checking values
        with self.assertRaises(ValueError):
            parse_timestamp(123)
        self.assertTrue(contains_sensitive_value(["something", {"secret": "secret: password"}]))
        self.assertTrue(contains_sensitive_value({"nested": {"API_KEY": "AIza1234567890123456789012345678901234567"}}))


if __name__ == "__main__":
    unittest.main()
