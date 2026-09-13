import unittest
import json
import os
import shutil
from pathlib import Path
import datetime as dt
import hashlib
from unittest.mock import patch

from scripts.run_thought_ingestion import run_ingestion
from scripts.run_thought_curator import ThoughtCurator
from scripts.run_thought_memory_mesh import canonical_hash as h

def make_msg(ingestion_id, source_message_id, content_dict):
    msg = {
        "ingestion_id": ingestion_id,
        "source_type": "CHAT_EXPORT",
        "source_message_id": source_message_id,
        "source_timestamp": "2026-09-01T12:00:00+00:00",
        "received_at": "2026-09-01T12:00:00+00:00",
        "content_hash": h(content_dict),
        "content": content_dict,
        "metadata": {},
        "correlation_id": "corr1",
        "privacy_class": "PUBLIC"
    }
    return msg

class TestP0DataHardening(unittest.TestCase):
    def setUp(self):
        self.base_dir = Path("scratch/test_hardening")
        self.inbox = self.base_dir / "inbox"
        self.processed = self.base_dir / "processed"
        self.rejected = self.base_dir / "rejected"
        self.memory = self.base_dir / "memory"
        
        for d in [self.inbox, self.processed, self.rejected, self.memory]:
            if d.exists():
                shutil.rmtree(d)
            d.mkdir(parents=True)
            
    def tearDown(self):
        if self.base_dir.exists():
            shutil.rmtree(self.base_dir)

    def write_inbox(self, name, data):
        if isinstance(data, bytes):
            (self.inbox / name).write_bytes(data)
        else:
            (self.inbox / name).write_text(json.dumps(data))

    def run_ingest(self):
        return run_ingestion(self.inbox, self.processed, self.rejected, self.memory)

    def test_same_thought_twice(self):
        msg = make_msg("ingest1", "msg1", {"summary": "Hello world this is a long enough summary for the normalized version to accept it."})
        self.write_inbox("1.json", msg)
        res = self.run_ingest()
        self.assertEqual(res["new_ingestions"], 1)

        self.write_inbox("2.json", msg)
        res2 = self.run_ingest()
        self.assertEqual(res2["skipped"], 2)

    def test_same_source_different_content(self):
        msg1 = make_msg("ingest1", "msg1", {"summary": "Hello world this is a long enough summary for the normalized version to accept it."})
        msg2 = make_msg("ingest2", "msg1", {"summary": "Hacked! Hello world this is a long enough summary for the normalized version to accept it."})
        self.write_inbox("1.json", msg1)
        res1 = self.run_ingest()
        self.assertEqual(res1["new_ingestions"], 1)
        
        self.write_inbox("2.json", msg2)
        res2 = self.run_ingest()
        self.assertEqual(res2["conflicts"], 1)

    def test_changed_outside_summary(self):
        # Even if content changes slightly (outside summary), it is a new content_hash, but same source_message_id -> conflict
        msg1 = make_msg("ingest1", "msg1", {"summary": "Hello world this is a long enough summary for the normalized version to accept it.", "metadata_noise": "A"})
        msg2 = make_msg("ingest2", "msg1", {"summary": "Hello world this is a long enough summary for the normalized version to accept it.", "metadata_noise": "B"})
        
        self.write_inbox("1.json", msg1)
        res1 = self.run_ingest()
        self.assertEqual(res1["new_ingestions"], 1)
        
        self.write_inbox("2.json", msg2)
        res2 = self.run_ingest()
        self.assertEqual(res2["conflicts"], 1)

    def test_non_utf8(self):
        self.write_inbox("1.json", b'\xff\xfeH\x00e\x00l\x00l\x00o\x00')
        res = self.run_ingest()
        self.assertEqual(res["rejected"], 1)

    def test_curator_secret(self):
        curator = ThoughtCurator(repo_dir=self.base_dir, memory_dir=self.memory)
        with self.assertRaises(ValueError) as cm:
            curator.curate_idea("Here is my secret: ghp_123456789012345678901234567890123456", provenance_guard="cli")
        self.assertIn("SECURITY VIOLATION", str(cm.exception))

    def test_curator_unbound(self):
        curator = ThoughtCurator(repo_dir=self.base_dir, memory_dir=self.memory)
        res = curator.curate_idea("Normal idea with lots of text to test unbound input classification", provenance_guard="cli")
        self.assertEqual(res["classification"], "UNBOUND_UNTRUSTED_INPUT")
        self.assertEqual(res["provenance"]["provenance_state"], "UNBOUND_UNTRUSTED")
        state = json.loads((self.base_dir / "events" / "agent-states" / "agent-thought-curator.json").read_text(encoding="utf-8"))
        self.assertEqual(state["state"], "BLOCKED")
        self.assertEqual(state["human_gate"], "REQUIRE_EXPLICIT_HUMAN_APPROVAL")

    def test_curator_rejects_malformed_claimed_provenance(self):
        curator = ThoughtCurator(repo_dir=self.base_dir, memory_dir=self.memory)
        with self.assertRaisesRegex(ValueError, "accepted_thought_reference"):
            curator.curate_idea("A normal idea.", accepted_thought_reference={"forged": "object"})

    def test_curator_does_not_dispatch_when_canonical_memory_is_unavailable(self):
        curator = ThoughtCurator(repo_dir=self.base_dir, memory_dir=self.memory)
        result = curator.curate_idea(
            "A sourced thought must not bypass a missing memory comparison.",
            accepted_thought_reference="ingestion-run-memory-missing",
        )
        self.assertEqual(result["memory_comparison_state"], "UNAVAILABLE")
        state = json.loads((self.base_dir / "events" / "agent-states" / "agent-thought-curator.json").read_text(encoding="utf-8"))
        self.assertEqual(state["state"], "BLOCKED")
        self.assertIn("reconcile canonical Project Memory", state["next_action"])

    def test_curator_overwrite(self):
        curator = ThoughtCurator(repo_dir=self.base_dir, memory_dir=self.memory)
        
        try:
            import hashlib
            orig_hash = hashlib.sha256
            def mock_hash(b):
                class MockDigest:
                    def hexdigest(self): return "idea_static"
                return MockDigest()
            hashlib.sha256 = mock_hash
            
            curator.curate_idea("First time good idea", provenance_guard="cli")
            with self.assertRaises(ValueError) as cm:
                curator.curate_idea("Second time bad idea", provenance_guard="cli")
            self.assertIn("Silent overwrite", str(cm.exception))
        finally:
            hashlib.sha256 = orig_hash

    def test_curator_keeps_thoughts_and_visual_state_in_its_own_workspace(self):
        curator = ThoughtCurator(repo_dir=self.base_dir, memory_dir=self.memory)
        result = curator.curate_idea(
            "A scoped, traceable idea that is long enough for the test.",
            accepted_thought_reference="ingestion-run-001",
        )
        thought_file = self.base_dir / "events" / "thoughts" / f"{result['idea_id']}.json"
        state_file = self.base_dir / "events" / "agent-states" / "agent-thought-curator.json"
        self.assertTrue(thought_file.exists())
        self.assertTrue(state_file.exists())
        self.assertEqual(result["provenance"], {
            "source_reference": "ingestion-run-001",
            "provenance_state": "CALLER_DECLARED_UNVERIFIED",
        })

    def test_derived_record_write_is_atomic_and_never_replaces_existing_record(self):
        target = self.base_dir / "events" / "thoughts" / "idea-race.json"
        ThoughtCurator._write_derived_record_once(target, {"winner": "first"})
        before = target.read_bytes()
        with self.assertRaises(ValueError) as raised:
            ThoughtCurator._write_derived_record_once(target, {"winner": "second"})
        self.assertIn("Silent overwrite", str(raised.exception))
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(list(target.parent.glob(".idea-race.json.tmp-*")), [])

    def test_two_workspaces_keep_identical_idea_records_separate(self):
        other_workspace = self.base_dir.parent / "test_hardening_other"
        other_memory = other_workspace / "memory"
        other_workspace.mkdir(parents=True, exist_ok=True)
        other_memory.mkdir(parents=True, exist_ok=True)
        try:
            first = ThoughtCurator(repo_dir=self.base_dir, memory_dir=self.memory)
            second = ThoughtCurator(repo_dir=other_workspace, memory_dir=other_memory)
            idea = "The same idea is evaluated independently in two isolated workspaces."
            first_result = first.curate_idea(idea, accepted_thought_reference="source-a")
            second_result = second.curate_idea(idea, accepted_thought_reference="source-b")
            self.assertEqual(first_result["idea_id"], second_result["idea_id"])
            self.assertTrue((self.base_dir / "events" / "thoughts" / f"{first_result['idea_id']}.json").exists())
            self.assertTrue((other_workspace / "events" / "thoughts" / f"{second_result['idea_id']}.json").exists())
        finally:
            if other_workspace.exists():
                shutil.rmtree(other_workspace)

    def test_persistence_failure_never_emits_sent_to_chief(self):
        curator = ThoughtCurator(repo_dir=self.base_dir, memory_dir=self.memory)
        with patch.object(ThoughtCurator, "_write_derived_record_once", side_effect=OSError("disk unavailable")):
            with self.assertRaises(OSError):
                curator.curate_idea(
                    "A durable record must exist before this is presented as delivered.",
                    accepted_thought_reference="source-failure",
                )
        state_file = self.base_dir / "events" / "agent-states" / "agent-thought-curator.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        self.assertEqual(state["state"], "BLOCKED")
        self.assertEqual(state["result"], "PERSISTENCE_FAILED")

if __name__ == "__main__":
    unittest.main()
