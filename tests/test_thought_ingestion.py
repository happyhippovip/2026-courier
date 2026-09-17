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
from run_thought_ingestion import canonical_hash, run_ingestion

MEMORY = Path("/Users/user/Downloads/2026-project-memory")


def envelope(ingestion_id, source_message_id, timestamp, content, *, source_type="CHAT_EXPORT", metadata=None, privacy_class="INTERNAL"):
    return {"ingestion_id": ingestion_id, "source_type": source_type, "source_message_id": source_message_id, "source_timestamp": timestamp, "received_at": timestamp, "content_hash": canonical_hash(content), "content": content, "metadata": metadata or {"kind": "OPEN_QUESTION", "status_label": "UNKNOWN"}, "correlation_id": f"corr-{ingestion_id}", "privacy_class": privacy_class}


def write_json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


class ThoughtIngestionTests(unittest.TestCase):
    def test_real_file_ingestion_dedupe_conflict_secret_and_delta(self):
        memory_before = subprocess.run(["git", "-C", str(MEMORY, timeout=60), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
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
        memory_after = subprocess.run(["git", "-C", str(MEMORY, timeout=60), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
        self.assertEqual(memory_before, memory_after)

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


if __name__ == "__main__":
    unittest.main()
