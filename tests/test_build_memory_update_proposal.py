import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
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

    def test_git_metadata_does_not_follow_a_symlink(self):
        outside_git = self.td_path / "outside-git"
        outside_git.mkdir()
        (outside_git / "HEAD").write_text(
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n", encoding="utf-8",
        )
        linked_repo = self.td_path / "linked-repo"
        linked_repo.mkdir()
        (linked_repo / ".git").symlink_to(outside_git, target_is_directory=True)

        head_repo = self.td_path / "head-repo"
        (head_repo / ".git").mkdir(parents=True)
        outside_head = self.td_path / "outside-HEAD"
        outside_head.write_text(
            "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n", encoding="utf-8",
        )
        (head_repo / ".git" / "HEAD").symlink_to(outside_head)

        packed_repo = self.td_path / "packed-repo"
        (packed_repo / ".git").mkdir(parents=True)
        (packed_repo / ".git" / "HEAD").write_text(
            "ref: refs/heads/main\n", encoding="utf-8",
        )
        outside_packed = self.td_path / "outside-packed-refs"
        outside_packed.write_text(
            "cccccccccccccccccccccccccccccccccccccccc refs/heads/main\n",
            encoding="utf-8",
        )
        (packed_repo / ".git" / "packed-refs").symlink_to(outside_packed)

        plain_repo = self.td_path / "plain-repo"
        (plain_repo / ".git").mkdir(parents=True)
        (plain_repo / ".git" / "HEAD").write_text(
            "1234567890abcdef1234567890abcdef12345678", encoding="utf-8",
        )

        def run(repo):
            try:
                return ("ok", get_memory_commit(repo))
            except SystemExit as exc:
                return ("err", str(exc))

        refused = "MEMORY_PROPOSAL_ERROR: refusing to follow a symlink"
        self.assertEqual(
            (run(linked_repo), run(head_repo), run(packed_repo), run(plain_repo)),
            (
                ("err", refused),
                ("err", refused),
                ("err", refused),
                ("ok", "1234567890abcdef1234567890abcdef12345678"),
            ),
        )

    def test_git_ref_does_not_escape_the_git_dir(self):
        outside = self.td_path / "outside-ref"
        outside.write_text(
            "dddddddddddddddddddddddddddddddddddddddd\n", encoding="utf-8",
        )
        repo = self.td_path / "escape-repo"
        git_dir = repo / ".git"
        git_dir.mkdir(parents=True)
        (git_dir / "HEAD").write_text("ref: ../../outside-ref\n", encoding="utf-8")

        plain = self.td_path / "plain-ref-repo"
        plain_git = plain / ".git"
        (plain_git / "refs" / "heads").mkdir(parents=True)
        (plain_git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        (plain_git / "refs" / "heads" / "main").write_text(
            "abcdef1234567890abcdef1234567890abcdef12\n", encoding="utf-8",
        )

        def run(path):
            try:
                return ("ok", get_memory_commit(path))
            except SystemExit as exc:
                return ("err", str(exc))

        self.assertEqual(
            (run(repo), outside.read_text(encoding="utf-8"), run(plain)),
            (
                ("err", "MEMORY_PROPOSAL_ERROR: refusing a git ref outside .git"),
                "dddddddddddddddddddddddddddddddddddddddd\n",
                ("ok", "abcdef1234567890abcdef1234567890abcdef12"),
            ),
        )

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

    def test_output_dir_symlink_is_not_written(self):
        result_file = self.td_path / "result-link.json"
        result_file.write_text(json.dumps({
            "task_id": "task-link",
            "message_id": "msg-link",
            "correlation_id": "corr-link",
            "payload": {"summary": "Completed testing", "verified_facts": ["fact"]},
        }), encoding="utf-8")
        outside = self.td_path / "outside"
        outside.mkdir()
        (outside / "keep.txt").write_text("keep", encoding="utf-8")
        linked = self.td_path / "linked-out"
        linked.symlink_to(outside)
        via = self.td_path / "via"
        via.symlink_to(self.td_path)
        nested = via / "proposals"
        errors = []
        for dest in (linked, nested):
            try:
                build_proposal_from_result(
                    result_file=result_file,
                    memory_repo_path=self.td_path,
                    output_dir=dest,
                )
            except SystemExit as exc:
                errors.append(str(exc))
            else:
                errors.append("wrote")
        leaked = sorted(p.name for p in outside.iterdir())
        self.assertEqual(
            (errors, leaked, linked.is_symlink()),
            ([
                "MEMORY_PROPOSAL_ERROR: refusing to follow a symlink",
                "MEMORY_PROPOSAL_ERROR: refusing to follow a symlink",
            ], ["keep.txt"], True),
        )

    def test_memory_repo_does_not_follow_a_symlink(self):
        result_file = self.td_path / "result-repo.json"
        result_file.write_text(json.dumps({
            "task_id": "task-repo",
            "message_id": "msg-repo",
            "correlation_id": "corr-repo",
            "payload": {"summary": "plain", "verified_facts": ["fact"]},
        }), encoding="utf-8")
        outside = self.td_path / "outside-repo"
        outside.mkdir()
        (outside / ".git").mkdir()
        secret = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"
        (outside / ".git" / "HEAD").write_text(secret + "\n", encoding="utf-8")
        linked = self.td_path / "linked-repo"
        linked.symlink_to(outside)
        parent_real = self.td_path / "parent-real"
        nested = parent_real / "repo"
        nested.mkdir(parents=True)
        (nested / ".git").mkdir()
        parent_secret = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        (nested / ".git" / "HEAD").write_text(parent_secret + "\n", encoding="utf-8")
        parent_link = self.td_path / "parent-link"
        parent_link.symlink_to(parent_real)
        plain = self.td_path / "plain-repo"
        plain.mkdir()
        (plain / ".git").mkdir()
        plain_commit = "1234567890abcdef1234567890abcdef12345678"
        (plain / ".git" / "HEAD").write_text(plain_commit + "\n", encoding="utf-8")

        def run_main(mem, tag):
            out = self.td_path / f"out-{tag}"
            original = sys.argv
            sys.argv = [
                "prog", "--result", str(result_file),
                "--output-dir", str(out), "--memory-repo", str(mem),
            ]
            try:
                try:
                    main()
                    err = None
                except SystemExit as exc:
                    err = str(exc)
            finally:
                sys.argv = original
            names = sorted(p.name for p in out.iterdir()) if out.exists() else []
            body = (out / names[0]).read_text(encoding="utf-8") if names else ""
            return err, names, body

        err_link, names_link, body_link = run_main(linked, "link")
        err_parent, names_parent, body_parent = run_main(parent_link / "repo", "parent")
        out_lib = self.td_path / "out-lib"
        try:
            build_proposal_from_result(
                result_file=result_file, memory_repo_path=linked, output_dir=out_lib,
            )
            err_lib = None
        except SystemExit as exc:
            err_lib = str(exc)
        names_lib = sorted(p.name for p in out_lib.iterdir()) if out_lib.exists() else []
        body_lib = (out_lib / names_lib[0]).read_text(encoding="utf-8") if names_lib else ""
        err_plain, names_plain, body_plain = run_main(plain, "plain")
        refused = "MEMORY_PROPOSAL_ERROR: refusing to follow a symlink"
        self.assertEqual(
            (
                err_link, secret in body_link, names_link,
                err_parent, parent_secret in body_parent, names_parent,
                err_lib, secret in body_lib, names_lib,
                err_plain, plain_commit in body_plain, names_plain,
                linked.is_symlink(), parent_link.is_symlink(),
            ),
            (
                refused, False, [],
                refused, False, [],
                refused, False, [],
                None, True, ["task-repo-memory-proposal.json"],
                True, True,
            ),
        )

    def test_result_file_does_not_follow_a_symlink(self):
        outside = self.td_path / "outside-result.json"
        outside.write_text(json.dumps({
            "task_id": "task-secret",
            "message_id": "msg-secret",
            "correlation_id": "corr-secret",
            "payload": {"summary": "x", "verified_facts": ["SECRET-RESULT-BODY"]},
        }), encoding="utf-8")
        linked = self.td_path / "linked-result.json"
        linked.symlink_to(outside)
        parent_real = self.td_path / "parent-real"
        parent_real.mkdir()
        nested = parent_real / "nested-result.json"
        nested.write_text(json.dumps({
            "task_id": "task-parent",
            "message_id": "msg-parent",
            "correlation_id": "corr-parent",
            "payload": {"summary": "x", "verified_facts": ["SECRET-PARENT-BODY"]},
        }), encoding="utf-8")
        parent_link = self.td_path / "parent-link"
        parent_link.symlink_to(parent_real)
        plain = self.td_path / "plain-result.json"
        plain.write_text(json.dumps({
            "task_id": "task-plain",
            "message_id": "msg-plain",
            "correlation_id": "corr-plain",
            "payload": {"summary": "x", "verified_facts": ["PLAIN-RESULT-BODY"]},
        }), encoding="utf-8")

        def run_main(result, tag):
            out = self.td_path / f"out-{tag}"
            original = sys.argv
            sys.argv = [
                "prog", "--result", str(result),
                "--output-dir", str(out), "--memory-repo", str(self.td_path),
            ]
            try:
                try:
                    main()
                    err = None
                except SystemExit as exc:
                    err = str(exc)
            finally:
                sys.argv = original
            names = sorted(p.name for p in out.iterdir()) if out.exists() else []
            body = (out / names[0]).read_text(encoding="utf-8") if names else ""
            return err, names, body

        err_link, names_link, body_link = run_main(linked, "link")
        err_parent, names_parent, body_parent = run_main(parent_link / "nested-result.json", "parent")
        out_lib = self.td_path / "out-lib"
        try:
            build_proposal_from_result(
                result_file=linked, memory_repo_path=self.td_path, output_dir=out_lib,
            )
            err_lib = None
        except SystemExit as exc:
            err_lib = str(exc)
        names_lib = sorted(p.name for p in out_lib.iterdir()) if out_lib.exists() else []
        body_lib = (out_lib / names_lib[0]).read_text(encoding="utf-8") if names_lib else ""
        err_plain, names_plain, body_plain = run_main(plain, "plain")
        refused = "MEMORY_PROPOSAL_ERROR: refusing to follow a symlink"
        self.assertEqual(
            (
                err_link, "SECRET-RESULT-BODY" in body_link, names_link,
                err_parent, "SECRET-PARENT-BODY" in body_parent, names_parent,
                err_lib, "SECRET-RESULT-BODY" in body_lib, names_lib,
                err_plain, "PLAIN-RESULT-BODY" in body_plain, names_plain,
                linked.is_symlink(), parent_link.is_symlink(),
            ),
            (
                refused, False, [],
                refused, False, [],
                refused, False, [],
                None, True, ["task-plain-memory-proposal.json"],
                True, True,
            ),
        )

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

    def test_validate_proposal_does_not_follow_a_symlink(self):
        valid_proposal = {
            "schema_version": "2.0",
            "proposal_id": "prop-mem-secret-12345678",
            "source_result_message_id": "msg-secret",
            "task_id": "task-secret",
            "correlation_id": "corr-secret",
            "memory_base_commit": "1234567890abcdef1234567890abcdef12345678",
            "target_files": ["TECHNICAL_CONTEXT.md"],
            "proposed_changes": [{
                "file": "TECHNICAL_CONTEXT.md",
                "action": "APPEND",
                "section": "Current verified local technical state",
                "proposed_text": "- **VERIFIED_CURRENT** | SECRET-PROPOSAL-BODY",
                "status_label": "VERIFIED_CURRENT"
            }],
            "reason": "SECRET-PROPOSAL-BODY",
            "status_labels": ["VERIFIED_CURRENT"],
            "source_references": ["file1.json"],
            "requires_chief_approval": True,
            "created_at": "2026-09-30T10:00:00Z"
        }
        outside = self.td_path / "outside-proposal.json"
        outside.write_text(json.dumps(valid_proposal), encoding="utf-8")
        link = self.td_path / "linked-proposal.json"
        link.symlink_to(outside)

        parent_outside = self.td_path / "parent-outside"
        parent_outside.mkdir()
        parent_file = parent_outside / "parent-proposal.json"
        parent_file.write_text(json.dumps(valid_proposal), encoding="utf-8")
        linked_parent = self.td_path / "linked-parent"
        linked_parent.symlink_to(parent_outside, target_is_directory=True)

        plain = self.td_path / "plain-proposal.json"
        plain.write_text(json.dumps(valid_proposal), encoding="utf-8")

        def run(path):
            buf = io.StringIO()
            original_argv = sys.argv
            sys.argv = [
                "build_memory_update_proposal.py",
                "--validate-proposal",
                str(path),
            ]
            try:
                with redirect_stdout(buf):
                    main()
            except SystemExit as exc:
                return ("err", str(exc), buf.getvalue())
            finally:
                sys.argv = original_argv
            return ("ok", buf.getvalue())

        linked = run(link)
        parent = run(linked_parent / "parent-proposal.json")
        real = run(plain)
        self.assertEqual(
            (linked, parent, real[0], "SECRET-PROPOSAL-BODY" in real[1], "MEMORY_UPDATE_PROPOSAL_SCHEMA_VALID" in real[1]),
            (
                ("err", "MEMORY_PROPOSAL_ERROR: refusing to follow a symlink", ""),
                ("err", "MEMORY_PROPOSAL_ERROR: refusing to follow a symlink", ""),
                "ok",
                False,
                True,
            ),
        )

    def test_schema_does_not_follow_a_symlink(self):
        self.maxDiff = None
        outside = self.td_path / "outside-schema.json"
        outside.write_text(json.dumps({"required": ["SECRET-SCHEMA-FIELD"]}), encoding="utf-8")
        link = self.td_path / "linked-schema.json"
        link.symlink_to(outside)

        parent_outside = self.td_path / "schema-parent-outside"
        parent_outside.mkdir()
        (parent_outside / "schema.json").write_text(
            json.dumps({"required": ["SECRET-PARENT-FIELD"]}),
            encoding="utf-8",
        )
        linked_parent = self.td_path / "schema-linked-parent"
        linked_parent.symlink_to(parent_outside, target_is_directory=True)

        proposal = self.td_path / "empty-proposal.json"
        proposal.write_text("{}", encoding="utf-8")

        def run_cli(schema):
            buf = io.StringIO()
            original_argv = sys.argv
            argv = [
                "build_memory_update_proposal.py",
                "--validate-proposal",
                str(proposal),
            ]
            if schema is not None:
                argv.extend(["--schema", str(schema)])
            sys.argv = argv
            try:
                with redirect_stdout(buf):
                    main()
            except SystemExit as exc:
                return ("err", str(exc), buf.getvalue())
            finally:
                sys.argv = original_argv
            return ("ok", buf.getvalue())

        lib_link = validate_proposal_against_schema({}, link)
        lib_parent = validate_proposal_against_schema({}, linked_parent / "schema.json")
        cli_link = run_cli(link)
        cli_parent = run_cli(linked_parent / "schema.json")
        cli_real = run_cli(None)
        self.assertEqual(
            (
                lib_link,
                lib_parent,
                cli_link,
                cli_parent,
                "SECRET-SCHEMA-FIELD" in cli_real[1],
                "SECRET-PARENT-FIELD" in cli_real[1],
            ),
            (
                (False, "refusing to follow a symlink"),
                (False, "refusing to follow a symlink"),
                ("err", "MEMORY_PROPOSAL_ERROR: refusing to follow a symlink", ""),
                ("err", "MEMORY_PROPOSAL_ERROR: refusing to follow a symlink", ""),
                False,
                False,
            ),
        )

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
