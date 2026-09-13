#!/usr/bin/env python3
"""Zero-cost file/event ingestion tests; all runtime data stays temporary."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_thought_ingestion import atomic_json_write, canonical_hash, run_ingestion

# Tests must not inspect or depend on the user's real Project-Memory checkout.
MEMORY = ROOT / "tests" / "_isolated_missing_memory_repo"


def envelope(ingestion_id, source_message_id, timestamp, content, *, source_type="CHAT_EXPORT", metadata=None, privacy_class="INTERNAL"):
    return {"ingestion_id": ingestion_id, "source_type": source_type, "source_message_id": source_message_id, "source_timestamp": timestamp, "received_at": timestamp, "content_hash": canonical_hash(content), "content": content, "metadata": metadata or {"kind": "OPEN_QUESTION", "status_label": "UNKNOWN"}, "correlation_id": f"corr-{ingestion_id}", "privacy_class": privacy_class}


def write_json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


class ThoughtIngestionTests(unittest.TestCase):
    def test_real_file_ingestion_dedupe_conflict_secret_and_delta(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            inbox, processed, rejected = base / "inbox", base / "processed", base / "rejected"
            inbox.mkdir()
            normal = envelope("ing-001", "source-001", "2026-08-25T09:00:00Z", "A normal user message.", metadata={"kind": "INTENT", "status_label": "USER_INTENT"})
            idea = envelope("ing-002", "source-002", "2026-08-25T10:00:00Z", "A new idea.", metadata={"kind": "IDEA", "status_label": "IDEA"})
            decision = envelope("ing-003", "source-003", "2026-08-26T10:00:00Z", "A historical decision.", metadata={"kind": "DECISION", "status_label": "HISTORICAL_DECISION"})
            technical = envelope("ing-004", "source-004", "2026-08-27T10:00:00Z", "A technical result.", source_type="WORK_RESULT", metadata={"kind": "TASK", "status_label": "PLANNED"})
            duplicate = dict(normal)
            changed = envelope("ing-001", "source-001", "2026-08-28T10:00:00Z", "Changed source content.")
            sensitive = envelope("ing-006", "source-006", "2026-08-28T11:00:00Z", {"summary": "Synthetic", "api_key": "synthetic-value"})
            for index, data in enumerate([normal, idea, decision, technical, duplicate, changed, sensitive]):
                write_json(inbox / f"{index:03d}.json", data)
            (inbox / "invalid.json").write_text("{not valid json", encoding="utf-8")
            source_bytes_before = {path.name: path.read_bytes() for path in inbox.iterdir()}
            first = run_ingestion(inbox, processed, rejected, MEMORY)
            self.assertEqual(first["new_ingestions"], 4)
            self.assertEqual(first["skipped"], 1)
            self.assertEqual(first["conflicts"], 1)
            self.assertEqual(first["rejected"], 2)
            self.assertTrue(first["proposal_created"])
            self.assertTrue(first["scene_audit"]["coverage_complete"])
            self.assertEqual(first["chief_delivery"]["delivery_status"], "PREPARED_NOT_DELIVERED")
            self.assertEqual(source_bytes_before, {path.name: path.read_bytes() for path in inbox.iterdir()})
            replay = run_ingestion(inbox, processed, rejected, MEMORY)
            self.assertEqual(replay["new_ingestions"], 0)
            self.assertFalse(replay["proposal_created"])
            changed_source = envelope("ing-008", "source-001", "2026-08-29T09:00:00Z", "Changed source id with a new ingestion id.")
            write_json(inbox / "998.json", changed_source)
            day_two = envelope("ing-007", "source-007", "2026-08-29T10:00:00Z", "A next-day delta.", source_type="GOOGLE_ANTIGRAVITY_RESULT", metadata={"kind": "TASK", "status_label": "PLANNED"})
            write_json(inbox / "999.json", day_two)
            delta = run_ingestion(inbox, processed, rejected, MEMORY)
            self.assertEqual(delta["new_ingestions"], 1)
            self.assertGreaterEqual(delta["conflicts"], 1)
            self.assertTrue(delta["proposal_created"])
            self.assertTrue(delta["scene_audit"]["coverage_complete"])
            self.assertTrue(any(rejected.glob("*-rejected.json")))

    def test_pre_anchor_privacy_hash_and_lock_boundaries(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            inbox, processed, rejected = base / "inbox", base / "processed", base / "rejected"
            inbox.mkdir()
            pre_anchor = envelope("before", "before", "2026-08-24T23:59:59Z", "Historical boundary test.")
            bank_data = envelope("bank", "bank", "2026-08-25T09:00:00Z", {"summary": "Private", "iban": "synthetic"})
            mismatch = envelope("mismatch", "mismatch", "2026-08-25T10:00:00Z", "Integrity test.")
            mismatch["content_hash"] = "0" * 64
            for index, data in enumerate([pre_anchor, bank_data, mismatch]):
                write_json(inbox / f"boundary-{index}.json", data)
            result = run_ingestion(inbox, processed, rejected, MEMORY)
            self.assertEqual(result["new_ingestions"], 0)
            self.assertEqual(result["rejected"], 3)
            lock = processed / ".ingestion.lock"
            lock.mkdir(parents=True)
            locked = run_ingestion(inbox, processed, rejected, MEMORY)
            self.assertEqual(locked["status"], "LOCKED")
            lock.rmdir()

    def test_same_source_and_content_with_new_ingestion_id_is_not_reprocessed(self):
        """A transport retry may mint a new envelope id, never a new thought."""
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            inbox, processed, rejected = base / "inbox", base / "processed", base / "rejected"
            inbox.mkdir()
            original = envelope("ing-001", "source-immutable-001", "2026-08-30T09:00:00Z", "One immutable source thought.")
            retry = envelope("ing-002", "source-immutable-001", "2026-08-30T09:00:00Z", "One immutable source thought.")
            write_json(inbox / "original.json", original)
            self.assertEqual(run_ingestion(inbox, processed, rejected, MEMORY)["new_ingestions"], 1)

            write_json(inbox / "transport-retry.json", retry)
            replay = run_ingestion(inbox, processed, rejected, MEMORY)
            self.assertEqual(replay["new_ingestions"], 0)
            self.assertGreaterEqual(replay["skipped"], 2)
            self.assertEqual(replay["conflicts"], 0)
            records = list(processed.glob("run-*.json"))
            self.assertEqual(len(records), 1)

    def test_corrupt_recovery_state_fails_closed_without_replacing_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            inbox, processed, rejected = base / "inbox", base / "processed", base / "rejected"
            inbox.mkdir()
            write_json(inbox / "original.json", envelope("ing-001", "source-001", "2026-08-30T09:00:00Z", "A thought with durable evidence."))
            self.assertEqual(run_ingestion(inbox, processed, rejected, MEMORY)["new_ingestions"], 1)
            state_file = processed / "ingestion-state.json"
            state_file.write_text("{broken", encoding="utf-8")
            before = state_file.read_bytes()

            result = run_ingestion(inbox, processed, rejected, MEMORY)

            self.assertEqual(result["status"], "RECOVERY_STATE_CORRUPT")
            self.assertEqual(result["new_ingestions"], 0)
            self.assertTrue(result["retry_safe"])
            self.assertEqual(state_file.read_bytes(), before)
            self.assertFalse((processed / ".ingestion.lock").exists())

    def test_conflicting_recovery_journal_identity_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            inbox, processed, rejected = base / "inbox", base / "processed", base / "rejected"
            inbox.mkdir()
            write_json(inbox / "original.json", envelope("ing-001", "source-001", "2026-08-30T09:00:00Z", "Original content."))
            first = run_ingestion(inbox, processed, rejected, MEMORY)
            run_record = Path(first["run_record"])
            record = json.loads(run_record.read_text(encoding="utf-8"))
            record["completed_ingestions"][0]["content_hash"] = "f" * 64
            run_record.write_text(json.dumps(record), encoding="utf-8")

            result = run_ingestion(inbox, processed, rejected, MEMORY)

            self.assertEqual(result["status"], "RECOVERY_STATE_CORRUPT")
            self.assertIn("conflicting", result["reason"])

    def test_atomic_write_does_not_damage_previous_record_or_leak_temp_on_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "state.json"
            atomic_json_write(target, {"status": "previous"})
            before = target.read_bytes()

            with self.assertRaises(TypeError):
                atomic_json_write(target, {"not_json": {"a", "set"}})

            self.assertEqual(target.read_bytes(), before)
            self.assertEqual(list(target.parent.glob(".state.json.tmp-*")), [])

    def test_thousand_record_ingestion_is_linear_shape(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            inbox, processed, rejected = base / "inbox", base / "processed", base / "rejected"
            inbox.mkdir()
            for number in range(1000):
                timestamp = f"2026-08-30T{number // 60:02d}:{number % 60:02d}:00Z"
                write_json(inbox / f"bulk-{number:04d}.json", envelope(f"bulk-{number}", f"source-bulk-{number}", timestamp, f"Bulk record {number}.", source_type="COURIER_EVENT", metadata={"kind": "TASK", "status_label": "PLANNED"}))
            result = run_ingestion(inbox, processed, rejected, MEMORY)
            self.assertEqual(result["new_ingestions"], 1000)
            record = json.loads(Path(result["run_record"]).read_text(encoding="utf-8"))
            self.assertEqual(record["coverage_ledger"]["message_counts"]["valid_unique"], 1000)
            self.assertNotIn("message_ids", record["coverage_ledger"]["scanner_ranges"]["THOUGHT_FORWARD_SCANNER"])

    def test_four_concurrent_cli_runs_create_one_durable_semantic_effect(self):
        """The real CLI must converge under process races, not merely in-process calls."""
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            inbox, processed, rejected = base / "inbox", base / "processed", base / "rejected"
            inbox.mkdir()
            for number in range(40):
                write_json(
                    inbox / f"concurrent-{number:03d}.json",
                    envelope(
                        f"concurrent-ingestion-{number}",
                        f"concurrent-source-{number}",
                        f"2026-08-30T{number // 60:02d}:{number % 60:02d}:00Z",
                        f"Concurrent record {number}.",
                        source_type="COURIER_EVENT",
                        metadata={"kind": "TASK", "status_label": "PLANNED"},
                    ),
                )
            command = [
                sys.executable, str(ROOT / "scripts" / "run_thought_ingestion.py"),
                "--inbox", str(inbox), "--processed", str(processed),
                "--rejected", str(rejected), "--memory-repo", str(MEMORY),
            ]
            processes = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(4)]
            outcomes = []
            for process in processes:
                stdout, stderr = process.communicate(timeout=15)
                self.assertEqual(process.returncode, 0, stderr)
                outcomes.append(json.loads(stdout))

            self.assertEqual(sum(outcome.get("new_ingestions", 0) for outcome in outcomes), 40)
            self.assertEqual(len(list(processed.glob("run-*.json"))), 1)
            state = json.loads((processed / "ingestion-state.json").read_text(encoding="utf-8"))
            self.assertEqual(len(state["ingestions"]), 40)
            self.assertEqual(len(state["source_messages"]), 40)
            self.assertFalse((processed / ".ingestion.lock").exists())


if __name__ == "__main__":
    unittest.main()
