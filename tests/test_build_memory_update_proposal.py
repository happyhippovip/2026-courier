import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_memory_update_proposal import (
    build_proposal_from_result,
    fail,
    get_memory_commit,
    main,
    validate_proposal_against_schema,
)


class TestBuildMemoryUpdateProposal(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.td_path = Path(self.td.name)

    def tearDown(self):
        self.td.cleanup()

    def test_get_memory_commit_no_git(self):
        commit = get_memory_commit(self.td_path)
        self.assertEqual(commit, "0000000000000000000000000000000000000000")

    def test_get_memory_commit_with_head_hash(self):
        git_dir = self.td_path / ".git"
        git_dir.mkdir()
        head_file = git_dir / "HEAD"
        head_file.write_text("1234567890abcdef1234567890abcdef12345678", encoding="utf-8")
        commit = get_memory_commit(self.td_path)
        self.assertEqual(commit, "1234567890abcdef1234567890abcdef12345678")

    def test_get_memory_commit_with_ref(self):
        git_dir = self.td_path / ".git"
        git_dir.mkdir()
        head_file = git_dir / "HEAD"
        head_file.write_text("ref: refs/heads/main\n", encoding="utf-8")
        ref_file = git_dir / "refs" / "heads" / "main"
        ref_file.parent.mkdir(parents=True)
        ref_file.write_text("abcdef1234567890abcdef1234567890abcdef12\n", encoding="utf-8")
        commit = get_memory_commit(self.td_path)
        self.assertEqual(commit, "abcdef1234567890abcdef1234567890abcdef12")
        
    def test_get_memory_commit_with_packed_refs(self):
        git_dir = self.td_path / ".git"
        if not git_dir.exists():
            git_dir.mkdir()
        head_file = git_dir / "HEAD"
        head_file.write_text("ref: refs/heads/packed_branch\n", encoding="utf-8")
        packed_refs_file = git_dir / "packed-refs"
        packed_refs_file.write_text("deadbeef1234567890deadbeef1234567890dead refs/heads/packed_branch\n", encoding="utf-8")
        commit = get_memory_commit(self.td_path)
        self.assertEqual(commit, "deadbeef1234567890deadbeef1234567890dead")
        
    def test_get_memory_commit_head_missing(self):
        git_dir = self.td_path / ".git"
        if not git_dir.exists():
            git_dir.mkdir()
        # No HEAD file
        commit = get_memory_commit(self.td_path)
        self.assertEqual(commit, "0000000000000000000000000000000000000000")

    def test_get_memory_commit_packed_no_match(self):
        git_dir = self.td_path / ".git"
        if not git_dir.exists():
            git_dir.mkdir()
        head_file = git_dir / "HEAD"
        head_file.write_text("ref: refs/heads/unknown_branch\n", encoding="utf-8")
        packed_refs_file = git_dir / "packed-refs"
        packed_refs_file.write_text("deadbeef1234567890deadbeef1234567890dead refs/heads/other_branch\n", encoding="utf-8")
        commit = get_memory_commit(self.td_path)
        self.assertEqual(commit, "0000000000000000000000000000000000000000")

    def test_validate_proposal_against_schema(self):
        valid_proposal = {
            "schema_version": "2.0",
            "proposal_id": "prop-mem-task1-12345678",
            "source_result_message_id": "msg-1",
            "task_id": "task1",
            "correlation_id": "corr-1",
            "memory_base_commit": "1234567890abcdef1234567890abcdef12345678",
            "target_files": ["TECHNICAL_CONTEXT.md"],
            "proposed_changes": [{
                "file": "TECHNICAL_CONTEXT.md",
                "action": "APPEND",
                "section": "Current verified local technical state",
                "proposed_text": "- **VERIFIED_CURRENT** | Something",
                "status_label": "VERIFIED_CURRENT"
            }],
            "reason": "Test",
            "status_labels": ["VERIFIED_CURRENT"],
            "source_references": ["file1.json"],
            "requires_chief_approval": True,
            "created_at": "2026-09-30T10:00:00Z"
        }
        valid, err = validate_proposal_against_schema(valid_proposal)
        self.assertTrue(valid, err)

        # Missing fields
        invalid_proposal = valid_proposal.copy()
        del invalid_proposal["reason"]
        valid, err = validate_proposal_against_schema(invalid_proposal)
        self.assertFalse(valid)
        
        # Bad schema version
        invalid2 = valid_proposal.copy()
        invalid2["schema_version"] = "1.0"
        valid, err = validate_proposal_against_schema(invalid2)
        self.assertFalse(valid)
        self.assertIn("Invalid schema_version", err)

        # Target files not list
        invalid3 = valid_proposal.copy()
        invalid3["target_files"] = "string"
        valid, err = validate_proposal_against_schema(invalid3)
        self.assertFalse(valid)
        self.assertIn("target_files must be a non-empty list", err)

        # Other specific field validations
        bad = [
            (None, "Proposal data must be a JSON object"),
            ({**valid_proposal, "proposal_id": "bad id!"}, "Invalid proposal_id"),
            ({**valid_proposal, "source_result_message_id": "msg 1"}, "Invalid source_result_message_id"),
            ({**valid_proposal, "memory_base_commit": "short"}, "Invalid memory_base_commit"),
            ({**valid_proposal, "requires_chief_approval": False}, "requires_chief_approval must be strictly boolean True"),
            ({**valid_proposal, "proposed_changes": []}, "proposed_changes must be a non-empty list"),
            ({**valid_proposal, "proposed_changes": ["not a dict"]}, "Change #0 must be an object"),
            ({**valid_proposal, "proposed_changes": [{"file": "f", "action": "BAD", "section": "s", "proposed_text": "t", "status_label": "IDEA"}]}, "Change #0 invalid action"),
            ({**valid_proposal, "proposed_changes": [{"file": "f", "action": "APPEND", "section": "s", "proposed_text": "t", "status_label": "BAD_STATUS"}]}, "Change #0 invalid status_label"),
            ({**valid_proposal, "proposed_changes": [{"file": "f", "action": "APPEND", "section": "s", "proposed_text": "", "status_label": "IDEA"}]}, "Change #0 proposed_text must be a non-empty string"),
            ({**valid_proposal, "proposed_changes": [{"file": "f", "action": "APPEND", "section": "s"}]}, "Change #0 fields mismatch")
        ]
        
        for data, expected_err in bad:
            valid, err = validate_proposal_against_schema(data)
            self.assertFalse(valid)
            self.assertIn(expected_err, err)

        # Bad schema file JSON loading
        schema_path = self.td_path / "bad_schema.json"
        schema_path.write_text("{bad json", encoding="utf-8")
        valid, err = validate_proposal_against_schema(valid_proposal, schema_path=schema_path)
        self.assertFalse(valid)
        self.assertIn("Failed to load schema file", err)

    def test_build_proposal_from_result(self):
        result_file = self.td_path / "result.json"
        result_file.write_text(json.dumps({
            "task_id": "task-test-1",
            "message_id": "msg-test-1",
            "correlation_id": "corr-test-1",
            "payload": {
                "summary": "Completed testing",
                "verified_facts": ["This is a test fact", "EXTERNAL_STATUS fact"]
            }
        }), encoding="utf-8")
        
        output_dir = self.td_path / "out"
        
        proposal = build_proposal_from_result(
            result_file=result_file,
            memory_repo_path=self.td_path,
            output_dir=output_dir
        )
        
        self.assertEqual(proposal["task_id"], "task-test-1")
        self.assertEqual(len(proposal["proposed_changes"]), 2)
        self.assertEqual(proposal["proposed_changes"][0]["status_label"], "VERIFIED_CURRENT")
        self.assertEqual(proposal["proposed_changes"][1]["status_label"], "EXTERNAL_STATUS")
        self.assertTrue((output_dir / "task-test-1-memory-proposal.json").exists())

    def test_build_proposal_from_result_no_facts(self):
        result_file = self.td_path / "result2.json"
        result_file.write_text(json.dumps({
            "task_id": "task-test-2",
            "message_id": "msg-test-2",
            "correlation_id": "corr-test-2",
            "payload": {
                "summary": "Completed testing with no facts"
            }
        }), encoding="utf-8")
        
        proposal = build_proposal_from_result(
            result_file=result_file,
            memory_repo_path=self.td_path,
            output_dir=self.td_path
        )
        
        self.assertEqual(len(proposal["proposed_changes"]), 1)
        self.assertEqual(proposal["proposed_changes"][0]["status_label"], "VERIFIED_CURRENT")
        
    def test_build_proposal_from_result_status_fact_variants(self):
        result_file = self.td_path / "result3.json"
        result_file.write_text(json.dumps({
            "task_id": "task-test-3",
            "message_id": "msg-test-3",
            "correlation_id": "corr-test-3",
            "payload": {
                "summary": "Completed",
                "verified_facts": ["This is a mismatch!", "Something is missing.", "This is paused."]
            }
        }), encoding="utf-8")
        
        proposal = build_proposal_from_result(
            result_file=result_file,
            memory_repo_path=self.td_path,
            output_dir=self.td_path
        )
        
        labels = {ch["status_label"] for ch in proposal["proposed_changes"]}
        self.assertIn("CONFLICT", labels) # from mismatch
        self.assertIn("UNKNOWN", labels) # from missing
        self.assertIn("PAUSED_EXTERNAL_GATE", labels) # from paused

    def test_build_proposal_fails(self):
        # Missing file
        with self.assertRaises(SystemExit) as cm:
            build_proposal_from_result(self.td_path / "nope.json")
        self.assertIn("Result file not found", str(cm.exception))

        # Bad json
        bad_json = self.td_path / "bad.json"
        bad_json.write_text("{bad", encoding="utf-8")
        with self.assertRaises(SystemExit) as cm:
            build_proposal_from_result(bad_json)
        self.assertIn("Invalid JSON", str(cm.exception))

        # Missing fields
        missing_fields = self.td_path / "missing.json"
        missing_fields.write_text(json.dumps({"task_id": "t"}), encoding="utf-8")
        with self.assertRaises(SystemExit) as cm:
            build_proposal_from_result(missing_fields)
        self.assertIn("missing task_id", str(cm.exception))

    def test_build_proposal_validation_fail(self):
        result_file = self.td_path / "result_fail.json"
        # task_id pattern failure by having spaces
        result_file.write_text(json.dumps({
            "task_id": "task fail",
            "message_id": "msg-fail",
            "correlation_id": "corr-fail",
            "payload": {"summary": "Completed testing with no facts"}
        }), encoding="utf-8")
        with self.assertRaises(SystemExit) as cm:
            build_proposal_from_result(result_file, output_dir=self.td_path)
        self.assertIn("schema validation", str(cm.exception))

    def test_main_cli_build(self):
        result_file = self.td_path / "result_cli.json"
        result_file.write_text(json.dumps({
            "task_id": "task-cli",
            "message_id": "msg-cli",
            "correlation_id": "corr-cli",
            "payload": {"summary": "CLI test"}
        }), encoding="utf-8")
        
        output_dir = self.td_path / "out_cli"
        
        original_argv = sys.argv
        sys.argv = ["build_memory_update_proposal.py", "--result", str(result_file), "--output-dir", str(output_dir), "--memory-repo", str(self.td_path)]
        try:
            main()
        finally:
            sys.argv = original_argv
            
        self.assertTrue((output_dir / "task-cli-memory-proposal.json").exists())

    def test_main_cli_validate(self):
        # build a valid one first
        valid_proposal = {
            "schema_version": "2.0",
            "proposal_id": "prop-mem-task2-12345678",
            "source_result_message_id": "msg-2",
            "task_id": "task2",
            "correlation_id": "corr-2",
            "memory_base_commit": "1234567890abcdef1234567890abcdef12345678",
            "target_files": ["TECHNICAL_CONTEXT.md"],
            "proposed_changes": [{
                "file": "TECHNICAL_CONTEXT.md",
                "action": "APPEND",
                "section": "Current verified local technical state",
                "proposed_text": "- **VERIFIED_CURRENT** | Something",
                "status_label": "VERIFIED_CURRENT"
            }],
            "reason": "Test",
            "status_labels": ["VERIFIED_CURRENT"],
            "source_references": ["file1.json"],
            "requires_chief_approval": True,
            "created_at": "2026-09-30T10:00:00Z"
        }
        prop_file = self.td_path / "prop.json"
        prop_file.write_text(json.dumps(valid_proposal), encoding="utf-8")
        
        original_argv = sys.argv
        sys.argv = ["build_memory_update_proposal.py", "--validate-proposal", str(prop_file)]
        try:
            main()
        finally:
            sys.argv = original_argv

    def test_main_cli_errors(self):
        original_argv = sys.argv

        # No arguments
        sys.argv = ["build_memory_update_proposal.py"]
        with self.assertRaises(SystemExit):
            main()

        # Validate missing file
        sys.argv = ["build_memory_update_proposal.py", "--validate-proposal", str(self.td_path / "nope.json")]
        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertIn("Proposal file not found", str(cm.exception))

        # Validate bad json
        bad = self.td_path / "bad_val.json"
        bad.write_text("{bad", encoding="utf-8")
        sys.argv = ["build_memory_update_proposal.py", "--validate-proposal", str(bad)]
        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertIn("Invalid JSON in proposal file", str(cm.exception))

        # Validate invalid proposal
        bad2 = self.td_path / "bad_val2.json"
        bad2.write_text("{}", encoding="utf-8")
        sys.argv = ["build_memory_update_proposal.py", "--validate-proposal", str(bad2)]
        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertIn("Proposal validation failed", str(cm.exception))

        sys.argv = original_argv
        
    def test_fail(self):
        with self.assertRaises(SystemExit):
            fail("Some error")

if __name__ == "__main__":
    unittest.main()
