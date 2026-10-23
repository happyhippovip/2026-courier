import json
import os
import unittest
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.evaluate_memory_proposal_for_auto_approval import (
    evaluate_proposal,
    process_proposal_for_chief_decision,
    get_memory_commit,
    check_secret_guard,
    fail,
    main,
    CANONICAL_MEMORY_ALLOWLIST,
    CANONICAL_STATUS_ALLOWLIST
)

class TestEvaluateMemoryProposal(unittest.TestCase):
    def setUp(self):
        self.td = TemporaryDirectory()
        self.td_path = Path(self.td.name)
        
        self.git_dir = self.td_path / ".git"
        self.git_dir.mkdir()
        self.head_file = self.git_dir / "HEAD"
        self.head_file.write_text("1234567890abcdef1234567890abcdef12345678\n", encoding="utf-8")
        
        self.valid_proposal = {
            "schema_version": "2.0",
            "proposal_id": "prop-1",
            "source_result_message_id": "msg-1",
            "task_id": "task-1",
            "correlation_id": "corr-1",
            "memory_base_commit": "1234567890abcdef1234567890abcdef12345678",
            "target_files": ["TECHNICAL_CONTEXT.md"],
            "proposed_changes": [{
                "file": "TECHNICAL_CONTEXT.md",
                "action": "APPEND",
                "section": "Current verified local technical state",
                "proposed_text": "- VERIFIED_CURRENT: something",
                "status_label": "VERIFIED_CURRENT"
            }],
            "reason": "Test reason",
            "status_labels": ["VERIFIED_CURRENT"],
            "source_references": ["artifact.json"],
            "requires_chief_approval": True,
            "created_at": "2026-09-30T10:00:00Z"
        }

    def tearDown(self):
        self.td.cleanup()

    def test_get_memory_commit(self):
        self.assertEqual(get_memory_commit(self.td_path), "1234567890abcdef1234567890abcdef12345678")
        
        # no .git
        empty_dir = self.td_path / "empty"
        empty_dir.mkdir()
        self.assertEqual(get_memory_commit(empty_dir), "0000000000000000000000000000000000000000")
        
        # head missing
        (self.git_dir / "HEAD").unlink()
        self.assertEqual(get_memory_commit(self.td_path), "0000000000000000000000000000000000000000")

    def test_get_memory_commit_with_refs(self):
        self.head_file.write_text("ref: refs/heads/main\n", encoding="utf-8")
        ref_file = self.git_dir / "refs" / "heads" / "main"
        ref_file.parent.mkdir(parents=True)
        ref_file.write_text("deadbeef1234567890deadbeef1234567890dead\n", encoding="utf-8")
        self.assertEqual(get_memory_commit(self.td_path), "deadbeef1234567890deadbeef1234567890dead")
        
    def test_get_memory_commit_with_packed_refs(self):
        self.head_file.write_text("ref: refs/heads/packed\n", encoding="utf-8")
        packed_refs = self.git_dir / "packed-refs"
        packed_refs.write_text("cafebabe1234567890cafebabe1234567890cafe refs/heads/packed\n", encoding="utf-8")
        self.assertEqual(get_memory_commit(self.td_path), "cafebabe1234567890cafebabe1234567890cafe")
        
        # no matching line
        packed_refs.write_text("cafebabe1234567890cafebabe1234567890cafe refs/heads/other\n", encoding="utf-8")
        self.assertEqual(get_memory_commit(self.td_path), "0000000000000000000000000000000000000000")

    def test_check_secret_guard(self):
        self.assertFalse(check_secret_guard("Normal text"))
        self.assertTrue(check_secret_guard("password='password123'"))
        self.assertTrue(check_secret_guard("ghp_123456789012345678901234567890"))
        self.assertTrue(check_secret_guard("sk-123456789012345678901234567890"))
        self.assertTrue(check_secret_guard("AIza12345678901234567890123456789012345"))
        self.assertTrue(check_secret_guard("-----BEGIN RSA PRIVATE KEY-----"))

    def test_evaluate_proposal_auto_approve(self):
        decision, reasons, labels = evaluate_proposal(self.valid_proposal, memory_repo_path=self.td_path)
        self.assertEqual(decision, "AUTO_APPROVE")
        self.assertIn("SAFE_VERIFIED_TECHNICAL_FACT", reasons)
        self.assertEqual(labels, ["VERIFIED_CURRENT"])

    def test_evaluate_proposal_human_review_unverified(self):
        prop = self.valid_proposal.copy()
        prop["proposed_changes"] = [{
            "file": "TECHNICAL_CONTEXT.md",
            "action": "APPEND",
            "section": "s",
            "proposed_text": "t",
            "status_label": "NOT VERIFIED"
        }]
        decision, reasons, labels = evaluate_proposal(prop, memory_repo_path=self.td_path)
        self.assertEqual(decision, "HUMAN_REVIEW")
        self.assertIn("NON_AUTO_APPROVABLE_STATUS", reasons)
        self.assertIn("UNVERIFIED_STATUS_PRESENT", reasons)

    def test_evaluate_proposal_human_review_strategic(self):
        prop = self.valid_proposal.copy()
        prop["proposed_changes"] = [{
            "file": "IDEA_ARCHIVE.md",
            "action": "APPEND",
            "section": "s",
            "proposed_text": "t",
            "status_label": "IDEA"
        }]
        decision, reasons, labels = evaluate_proposal(prop, memory_repo_path=self.td_path)
        self.assertEqual(decision, "HUMAN_REVIEW")
        self.assertIn("NON_AUTO_APPROVABLE_STATUS", reasons)
        self.assertIn("STRATEGIC_CHANGE", reasons)

    def test_evaluate_proposal_blocked_cases(self):
        # NOT DICT
        decision, reasons, labels = evaluate_proposal("string", memory_repo_path=self.td_path)
        self.assertEqual(decision, "BLOCKED")
        self.assertIn("INVALID_PROPOSAL", reasons)

        # MISSING FIELDS
        decision, reasons, labels = evaluate_proposal({}, memory_repo_path=self.td_path)
        self.assertEqual(decision, "BLOCKED")
        self.assertIn("INVALID_PROPOSAL", reasons)

        # WRONG SCHEMA VERSION
        prop = self.valid_proposal.copy()
        prop["schema_version"] = "1.0"
        decision, reasons, labels = evaluate_proposal(prop, memory_repo_path=self.td_path)
        self.assertEqual(decision, "BLOCKED")
        self.assertIn("INVALID_PROPOSAL", reasons)

        # NO CHIEF APPROVAL REQ
        prop = self.valid_proposal.copy()
        prop["requires_chief_approval"] = False
        decision, reasons, labels = evaluate_proposal(prop, memory_repo_path=self.td_path)
        self.assertEqual(decision, "BLOCKED")
        self.assertIn("APPROVAL_GATE_REQUIRED", reasons)

        # WRONG BASE COMMIT
        prop = self.valid_proposal.copy()
        prop["memory_base_commit"] = "bad"
        decision, reasons, labels = evaluate_proposal(prop, memory_repo_path=self.td_path)
        self.assertEqual(decision, "BLOCKED")
        self.assertIn("MEMORY_HEAD_CONFLICT", reasons)

        # EMPTY TARGETS
        prop = self.valid_proposal.copy()
        prop["target_files"] = []
        decision, reasons, labels = evaluate_proposal(prop, memory_repo_path=self.td_path)
        self.assertEqual(decision, "BLOCKED")
        self.assertIn("TARGET_NOT_ALLOWED", reasons)
        
        # INVALID TARGET
        prop = self.valid_proposal.copy()
        prop["target_files"] = ["INVALID.md"]
        decision, reasons, labels = evaluate_proposal(prop, memory_repo_path=self.td_path)
        self.assertEqual(decision, "BLOCKED")
        self.assertIn("TARGET_NOT_ALLOWED", reasons)

        # NO SOURCES
        prop = self.valid_proposal.copy()
        prop["source_references"] = []
        decision, reasons, labels = evaluate_proposal(prop, memory_repo_path=self.td_path)
        self.assertEqual(decision, "BLOCKED")
        self.assertIn("SOURCE_MISSING", reasons)

        # EMPTY PROPOSED CHANGES
        prop = self.valid_proposal.copy()
        prop["proposed_changes"] = []
        decision, reasons, labels = evaluate_proposal(prop, memory_repo_path=self.td_path)
        self.assertEqual(decision, "BLOCKED")
        self.assertIn("INVALID_PROPOSAL", reasons)

        # PROPOSED CHANGE NOT A DICT
        prop = self.valid_proposal.copy()
        prop["proposed_changes"] = ["string"]
        decision, reasons, labels = evaluate_proposal(prop, memory_repo_path=self.td_path)
        self.assertEqual(decision, "BLOCKED")
        self.assertIn("INVALID_PROPOSAL", reasons)

        # CHANGE FILE INVALID
        prop = self.valid_proposal.copy()
        prop["proposed_changes"] = [{"file": "INVALID.md"}]
        decision, reasons, labels = evaluate_proposal(prop, memory_repo_path=self.td_path)
        self.assertEqual(decision, "BLOCKED")
        self.assertIn("TARGET_NOT_ALLOWED", reasons)

        # CHANGE ACTION DELETE
        prop = self.valid_proposal.copy()
        prop["proposed_changes"] = [{"file": "TECHNICAL_CONTEXT.md", "action": "DELETE"}]
        decision, reasons, labels = evaluate_proposal(prop, memory_repo_path=self.td_path)
        self.assertEqual(decision, "BLOCKED")
        self.assertIn("DELETE_ACTION_FORBIDDEN", reasons)

        # SECRETS
        prop = self.valid_proposal.copy()
        prop["proposed_changes"] = [{"file": "TECHNICAL_CONTEXT.md", "action": "APPEND", "proposed_text": "token='123456789'"}]
        decision, reasons, labels = evaluate_proposal(prop, memory_repo_path=self.td_path)
        self.assertEqual(decision, "BLOCKED")
        self.assertIn("SECRET_DETECTED", reasons)

        # BAD STATUS
        prop = self.valid_proposal.copy()
        prop["proposed_changes"] = [{"file": "TECHNICAL_CONTEXT.md", "action": "APPEND", "status_label": "HACK"}]
        decision, reasons, labels = evaluate_proposal(prop, memory_repo_path=self.td_path)
        self.assertEqual(decision, "BLOCKED")
        self.assertIn("NON_AUTO_APPROVABLE_STATUS", reasons)

    def test_process_proposal_for_chief_decision(self):
        prop_file = self.td_path / "proposal.json"
        prop_file.write_text(json.dumps(self.valid_proposal))

        decisions_dir = self.td_path / "decisions"
        approvals_dir = self.td_path / "approvals"

        decision_record = process_proposal_for_chief_decision(
            proposal_file=prop_file,
            memory_repo_path=self.td_path,
            output_decisions_dir=decisions_dir,
            output_approvals_dir=approvals_dir
        )

        self.assertEqual(decision_record["decision"], "AUTO_APPROVE")
        
        # Check files were written
        decisions = list(decisions_dir.glob("*.json"))
        self.assertEqual(len(decisions), 1)
        
        approvals = list(approvals_dir.glob("*.json"))
        self.assertEqual(len(approvals), 1)
        
        appr_data = json.loads(approvals[0].read_text())
        self.assertEqual(appr_data["approved_by"], "AUTONOMOUS_CHIEF_POLICY")
        self.assertEqual(appr_data["approval_status"], "APPROVED")

    def test_output_dirs_do_not_follow_a_symlink(self):
        prop_file = self.td_path / "proposal.json"
        prop_file.write_text(json.dumps(self.valid_proposal), encoding="utf-8")
        outside_dec = self.td_path / "outside-dec"
        outside_appr = self.td_path / "outside-appr"
        outside_dec.mkdir()
        outside_appr.mkdir()
        (outside_dec / "keep.txt").write_text("keep", encoding="utf-8")
        (outside_appr / "keep.txt").write_text("keep", encoding="utf-8")
        linked_dec = self.td_path / "linked-dec"
        linked_appr = self.td_path / "linked-appr"
        linked_dec.symlink_to(outside_dec)
        linked_appr.symlink_to(outside_appr)
        try:
            process_proposal_for_chief_decision(
                proposal_file=prop_file,
                memory_repo_path=self.td_path,
                output_decisions_dir=linked_dec,
                output_approvals_dir=linked_appr,
            )
        except SystemExit as exc:
            outcome = str(exc)
        else:
            outcome = "wrote"
        leaked_dec = sorted(p.name for p in outside_dec.iterdir())
        leaked_appr = sorted(p.name for p in outside_appr.iterdir())
        self.assertEqual(
            (outcome, leaked_dec, leaked_appr, linked_dec.is_symlink(), linked_appr.is_symlink()),
            ("CHIEF_POLICY_ERROR: refusing to follow a symlink", ["keep.txt"], ["keep.txt"], True, True),
        )

    def test_process_proposal_missing_file(self):
        with self.assertRaises(SystemExit):
            process_proposal_for_chief_decision(self.td_path / "missing.json")
            
    def test_process_proposal_bad_json(self):
        prop_file = self.td_path / "bad.json"
        prop_file.write_text("{bad")
        
        decision_record = process_proposal_for_chief_decision(
            proposal_file=prop_file,
            memory_repo_path=self.td_path,
            output_decisions_dir=self.td_path / "dec",
            output_approvals_dir=self.td_path / "app"
        )
        # Should gracefully block
        self.assertEqual(decision_record["decision"], "BLOCKED")
        self.assertIn("INVALID_PROPOSAL", decision_record["reason_codes"])
        
    def test_fail(self):
        with self.assertRaises(SystemExit):
            fail("Some message")

    def test_cli_does_not_follow_proposal_or_memory_symlink(self):
        outside_prop = self.td_path / "outside-prop.json"
        secret_prop = dict(self.valid_proposal)
        secret_prop["task_id"] = "task-secret"
        secret_prop["source_references"] = ["SECRET-PROPOSAL-BODY"]
        outside_prop.write_text(json.dumps(secret_prop), encoding="utf-8")
        linked_prop = self.td_path / "linked-prop.json"
        linked_prop.symlink_to(outside_prop)

        outside_repo = self.td_path / "outside-repo"
        outside_repo.mkdir()
        (outside_repo / ".git").mkdir()
        (outside_repo / ".git" / "HEAD").write_text(
            "abcdefabcdefabcdefabcdefabcdefabcdefabcd\n", encoding="utf-8",
        )
        linked_repo = self.td_path / "linked-repo"
        linked_repo.symlink_to(outside_repo)
        repo_prop = dict(self.valid_proposal)
        repo_prop["memory_base_commit"] = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"
        repo_prop["task_id"] = "task-repo"
        repo_file = self.td_path / "repo-prop.json"
        repo_file.write_text(json.dumps(repo_prop), encoding="utf-8")

        def run(prop, repo, tag):
            dec = self.td_path / f"dec-{tag}"
            appr = self.td_path / f"appr-{tag}"
            original = sys.argv
            sys.argv = [
                "prog",
                "--proposal", str(prop),
                "--memory-repo", str(repo),
                "--output-decisions", str(dec),
                "--output-approvals", str(appr),
            ]
            try:
                main()
                err = None
            except SystemExit as exc:
                err = str(exc)
            finally:
                sys.argv = original
            names = sorted(p.name for p in dec.iterdir()) if dec.exists() else []
            body = (dec / names[0]).read_text(encoding="utf-8") if names else ""
            return err, names, body

        err_prop, names_prop, body_prop = run(linked_prop, self.td_path, "prop")
        err_repo, names_repo, body_repo = run(repo_file, linked_repo, "repo")

        dec_lib = self.td_path / "dec-lib"
        appr_lib = self.td_path / "appr-lib"
        try:
            process_proposal_for_chief_decision(
                proposal_file=linked_prop,
                memory_repo_path=self.td_path,
                output_decisions_dir=dec_lib,
                output_approvals_dir=appr_lib,
            )
            err_lib = None
        except SystemExit as exc:
            err_lib = str(exc)
        names_lib = sorted(p.name for p in dec_lib.iterdir()) if dec_lib.exists() else []
        body_lib = (dec_lib / names_lib[0]).read_text(encoding="utf-8") if names_lib else ""

        refused = "CHIEF_POLICY_ERROR: refusing to follow a symlink"
        self.assertEqual(
            (
                err_prop, names_prop, "SECRET-PROPOSAL-BODY" in body_prop,
                err_repo, names_repo, "abcdefabcdefabcdefabcdefabcdefabcdefabcd" in body_repo,
                err_lib, names_lib, "SECRET-PROPOSAL-BODY" in body_lib,
                linked_prop.is_symlink(), linked_repo.is_symlink(),
            ),
            (refused, [], False, refused, [], False, refused, [], False, True, True),
        )

    def test_main(self):
        prop_file = self.td_path / "proposal.json"
        prop_file.write_text(json.dumps(self.valid_proposal))
        
        decisions_dir = self.td_path / "decisions"
        approvals_dir = self.td_path / "approvals"

        original_argv = sys.argv
        sys.argv = [
            "evaluate_memory_proposal_for_auto_approval.py",
            "--proposal", str(prop_file),
            "--memory-repo", str(self.td_path),
            "--output-decisions", str(decisions_dir),
            "--output-approvals", str(approvals_dir)
        ]
        
        try:
            main()
        finally:
            sys.argv = original_argv

if __name__ == "__main__":
    unittest.main()
