import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock

# Add scripts directory to path to allow import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import revenue_v1_safety_baseline as rvsb

class TestRevenueSafetyBaseline(unittest.TestCase):
    def setUp(self):
        self.td = TemporaryDirectory()
        self.td_path = Path(self.td.name)
        
    def tearDown(self):
        self.td.cleanup()

    def test_fail(self):
        with self.assertRaises(SystemExit) as cm:
            rvsb.fail("test error")
        self.assertIn("revenue workforce rejected: test error", str(cm.exception))

    def test_hash_file(self):
        p = self.td_path / "test.txt"
        p.write_bytes(b"hello")
        import hashlib
        expected = hashlib.sha256(b"hello").hexdigest()
        self.assertEqual(rvsb.hash_file(p), expected)

    @patch("revenue_v1_safety_baseline.subprocess.run")
    def test_clone_and_extract(self, mock_run):
        dest = self.td_path / "repo"
        
        def run_side_effect(*args, **kwargs):
            if "init" in args[0]:
                (dest / ".git" / "info").mkdir(parents=True, exist_ok=True)
                
        mock_run.side_effect = run_side_effect
        rvsb.clone_and_extract("owner", "repo", "123456", dest)
        self.assertTrue(dest.exists())
        self.assertTrue((dest / ".git" / "info" / "sparse-checkout").exists())
        self.assertEqual(mock_run.call_count, 6)
        self.assertIn(["git", "-C", str(dest), "config", "core.autocrlf", "false"],
                      [c.args[0] for c in mock_run.call_args_list])
        
    @patch("revenue_v1_safety_baseline.subprocess.run")
    def test_clone_and_extract_exists(self, mock_run):
        dest = self.td_path / "repo2"
        dest.mkdir()
        
        def run_side_effect(*args, **kwargs):
            if "init" in args[0]:
                (dest / ".git" / "info").mkdir(parents=True, exist_ok=True)
                
        mock_run.side_effect = run_side_effect
        rvsb.clone_and_extract("owner", "repo", "123456", dest)
        self.assertTrue(dest.exists())

    def test_analyze_workflows_empty(self):
        res = rvsb.analyze_workflows(self.td_path)
        self.assertEqual(res["findings"], [])
        self.assertEqual(res["inspected_files"], {})

    def test_analyze_workflows_with_issues(self):
        wf_dir = self.td_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        
        # 1. safe workflow
        safe_wf = wf_dir / "safe.yml"
        safe_wf.write_text("timeout-minutes: 10\npermissions:\nconcurrency:", encoding="utf-8")
        
        # 2. unsafe workflow
        unsafe_wf = wf_dir / "unsafe.yml"
        unsafe_wf.write_text("runs-on: self-hosted\npermissions: write-all\ngit push", encoding="utf-8")
        
        res = rvsb.analyze_workflows(self.td_path)
        issues = {f["issue"] for f in res["findings"]}
        
        self.assertIn("Self-hosted runner detected.", issues)
        self.assertIn("Missing timeout-minutes configuration.", issues)
        self.assertIn("Permissive write-all detected.", issues)
        self.assertIn("Missing concurrency block.", issues)
        self.assertIn("git push detected in workflow.", issues)
        self.assertEqual(len(res["inspected_files"]), 2)

    @patch("revenue_v1_safety_baseline.clone_and_extract")
    def test_worker_clean(self, mock_clone):
        task = {
            "target_owner": "a",
            "target_repo": "b",
            "target_sha": "c",
            "task_id": "t1",
            "attempt_id": "a1",
            "idempotency_key": "k1",
            "customer_reference": "cr1"
        }
        os.environ["GITHUB_RUN_ID"] = "r1"
        os.environ["GITHUB_RUN_ATTEMPT"] = "1"
        
        # mock clone creates no workflows: 0 files inspected must not be PASS
        res = rvsb.worker(task, self.td_path)
        
        self.assertEqual(res["task_id"], "t1")
        self.assertEqual(res["worker_status"], "WARN")
        self.assertEqual(res["warning"], "NO_FILES_INSPECTED")
        self.assertTrue((self.td_path / "report.json").exists())
        self.assertTrue((self.td_path / "report.md").exists())
        report_md = (self.td_path / "report.md").read_text(encoding="utf-8")
        self.assertIn("NO_FILES_INSPECTED", report_md)
        self.assertNotIn("No safety violations detected", report_md)

    @patch("revenue_v1_safety_baseline.clone_and_extract")
    def test_worker_does_not_follow_a_symlink(self, mock_clone):
        task = {
            "target_owner": "a",
            "target_repo": "b",
            "target_sha": "c",
            "task_id": "t1",
            "attempt_id": "a1",
            "idempotency_key": "k1",
            "customer_reference": "cr1",
        }
        outside = self.td_path / "outside"
        outside.mkdir()
        (outside / "keep.txt").write_text("keep", encoding="utf-8")
        linked = self.td_path / "linked-work"
        linked.symlink_to(outside)
        parent_real = self.td_path / "parent-real"
        nested_real = parent_real / "job"
        nested_real.mkdir(parents=True)
        (nested_real / "keep.txt").write_text("keep", encoding="utf-8")
        parent_link = self.td_path / "parent-link"
        parent_link.symlink_to(parent_real)
        plain = self.td_path / "plain-work"
        plain.mkdir()

        def run(dest):
            try:
                rvsb.worker(task, dest)
                return None
            except SystemExit as exc:
                return str(exc)

        err_link = run(linked)
        err_parent = run(parent_link / "job")
        err_plain = run(plain)
        leaked = sorted(p.name for p in outside.iterdir())
        leaked_parent = sorted(p.name for p in nested_real.iterdir())
        plain_names = sorted(p.name for p in plain.iterdir())
        refused = "revenue workforce rejected: refusing to follow a symlink"
        self.assertEqual(
            (err_link, leaked, err_parent, leaked_parent, err_plain, "report.json" in plain_names, linked.is_symlink(), parent_link.is_symlink(), mock_clone.called),
            (refused, ["keep.txt"], refused, ["keep.txt"], None, True, True, True, True),
        )

    def test_analyze_workflows_reads_yaml_extension(self):
        wf_dir = self.td_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "ci.yaml").write_text("runs-on: self-hosted", encoding="utf-8")
        (wf_dir / "other.yml").write_text("timeout-minutes: 5\npermissions:\nconcurrency:", encoding="utf-8")
        res = rvsb.analyze_workflows(self.td_path)
        self.assertIn("ci.yaml", res["inspected_files"])
        self.assertIn("other.yml", res["inspected_files"])
        self.assertIn("Self-hosted runner detected.", {f["issue"] for f in res["findings"] if f["file"] == "ci.yaml"})

    @patch("revenue_v1_safety_baseline.clone_and_extract")
    def test_worker_clean_with_files_is_pass(self, mock_clone):
        task = {"target_owner": "a", "target_repo": "b", "target_sha": "c", "task_id": "t1",
                "attempt_id": "a1", "idempotency_key": "k1", "customer_reference": "cr1"}

        def mock_clone_side_effect(owner, repo, sha, dest):
            wf_dir = dest / ".github" / "workflows"
            wf_dir.mkdir(parents=True)
            (wf_dir / "ok.yaml").write_text("timeout-minutes: 5\npermissions:\nconcurrency:", encoding="utf-8")

        mock_clone.side_effect = mock_clone_side_effect
        res = rvsb.worker(task, self.td_path)
        self.assertEqual(res["worker_status"], "PASS")
        self.assertNotIn("warning", res)
        self.assertIn("No safety violations detected", (self.td_path / "report.md").read_text(encoding="utf-8"))

    def test_verify_no_files_is_not_pass(self):
        with patch("revenue_v1_safety_baseline.run_independent_verifier") as m:
            m.return_value = {"verdict": "PASS", "accepted": True, "reasons": [], "verifier": {"name": "x"}}
            verified = rvsb.verify({}, {"report_json_sha256": "h1", "worker_status": "WARN"}, self.td_path)
        self.assertEqual(verified["verifier_status"], "WARN")

    @patch("revenue_v1_safety_baseline.clone_and_extract")
    def test_worker_with_findings(self, mock_clone):
        task = {
            "target_owner": "a",
            "target_repo": "b",
            "target_sha": "c",
            "task_id": "t1",
            "attempt_id": "a1",
            "idempotency_key": "k1",
            "customer_reference": "cr1"
        }
        
        def mock_clone_side_effect(owner, repo, sha, dest):
            # inject a bad workflow
            wf_dir = dest / ".github" / "workflows"
            wf_dir.mkdir(parents=True)
            (wf_dir / "bad.yml").write_text("runs-on: self-hosted", encoding="utf-8")
            
        mock_clone.side_effect = mock_clone_side_effect
        
        res = rvsb.worker(task, self.td_path)
        report_md = (self.td_path / "report.md").read_text(encoding="utf-8")
        self.assertIn("Self-hosted runner detected", report_md)

    def test_render_report_de_findings(self):
        analysis = {"inspected_files": {"ci.yaml": "abc"},
                    "findings": [{"rule": "timeout", "file": "ci.yaml", "issue": "Missing timeout-minutes configuration."}]}
        md = rvsb.render_report_de("o", "r", "s" * 40, analysis)
        self.assertIn("`ci.yaml`", md)
        self.assertIn("**Regel:** `timeout`", md)
        self.assertIn("**Schweregrad:** NIEDRIG", md)
        self.assertIn("**Erklärung:**", md)
        self.assertIn("**Fix-Hinweis:**", md)
        self.assertIn("```yaml\n", md)
        self.assertIn("timeout-minutes: 15", md)
        self.assertIn("keine Garantie", md)
        self.assertIn("menschliche Durchsicht", md)
        self.assertNotIn("NO_FILES_INSPECTED", md)

    def test_render_report_de_all_rules_have_texts(self):
        for rule in ["runner_type", "timeout", "permissions", "concurrency", "mutation_risk",
                     "pull_request_target", "unpinned_action", "script_injection"]:
            for key in ["title", "severity", "explain", "fix", "yaml"]:
                self.assertTrue(rvsb.RULES_DE[rule][key])

    def test_render_report_de_no_files_warn(self):
        md = rvsb.render_report_de("o", "r", "s", {"inspected_files": {}, "findings": []})
        self.assertIn("WARNUNG: NO_FILES_INSPECTED", md)
        self.assertIn("KEIN unbedenkliches Ergebnis", md)

    @patch("revenue_v1_safety_baseline.clone_and_extract")
    def test_worker_writes_report_de_and_keeps_existing_outputs(self, mock_clone):
        task = {"target_owner": "a", "target_repo": "b", "target_sha": "c", "task_id": "t1",
                "attempt_id": "a1", "idempotency_key": "k1", "customer_reference": "cr1"}

        def mock_clone_side_effect(owner, repo, sha, dest):
            wf_dir = dest / ".github" / "workflows"
            wf_dir.mkdir(parents=True)
            (wf_dir / "bad.yml").write_text("runs-on: self-hosted", encoding="utf-8")

        mock_clone.side_effect = mock_clone_side_effect
        res = rvsb.worker(task, self.td_path)
        for name in ["report.json", "report.md", "report_de.md"]:
            self.assertTrue((self.td_path / name).exists())
        self.assertIn("Self-hosted runner detected", (self.td_path / "report.md").read_text(encoding="utf-8"))
        self.assertIn("Schweregrad:** HOCH", (self.td_path / "report_de.md").read_text(encoding="utf-8"))
        self.assertEqual(res["report_de_md_sha256"], rvsb.hash_file(self.td_path / "report_de.md"))

    def _write_wf(self, rel, text):
        p = self.td_path / ".github" / "workflows" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def _rules(self, res, file):
        return [f["rule"] for f in res["findings"] if f["file"] == file]

    def test_rule_pull_request_target(self):
        self._write_wf("a.yml", "on:\n  pull_request_target:\n    types: [opened]\n")
        self._write_wf("b.yml", "on:\n  pull_request:\n# pull_request_target only in comment\n")
        res = rvsb.analyze_workflows(self.td_path)
        self.assertIn("pull_request_target", self._rules(res, "a.yml"))
        self.assertNotIn("pull_request_target", self._rules(res, "b.yml"))

    def test_rule_unpinned_action(self):
        sha = "a" * 40
        self._write_wf("ci.yml", (
            "jobs:\n  t:\n    steps:\n"
            "      - uses: actions/checkout@v4\n"
            f"      - uses: actions/setup-python@{sha} # v5\n"
            "      - uses: ./local-action\n"
            "      - uses: docker://alpine:3\n"
            "      - uses: 'org/x@main'\n"))
        res = rvsb.analyze_workflows(self.td_path)
        issues = [f["issue"] for f in res["findings"] if f["rule"] == "unpinned_action"]
        self.assertEqual(len(issues), 2)
        self.assertTrue(any("actions/checkout@v4" in i for i in issues))
        self.assertTrue(any("org/x@main" in i for i in issues))

    def test_rule_script_injection(self):
        self._write_wf("inj.yml", (
            "jobs:\n  t:\n    steps:\n"
            "      - run: echo ${{ github.event.issue.title }}\n"
            "      - run: |\n          echo start\n          echo \"${{github.event.pull_request.head.ref}}\"\n"
            "      - name: safe\n        env:\n          T: ${{ github.event.issue.title }}\n        run: echo \"$T\"\n"))
        res = rvsb.analyze_workflows(self.td_path)
        self.assertEqual(self._rules(res, "inj.yml").count("script_injection"), 2)

    def test_same_name_in_subfolders_not_overwritten(self):
        self._write_wf("ci.yml", "runs-on: self-hosted\n")
        self._write_wf("sub/ci.yml", "timeout-minutes: 5\npermissions:\nconcurrency:\n")
        res = rvsb.analyze_workflows(self.td_path)
        self.assertEqual(set(res["inspected_files"]), {"ci.yml", "sub/ci.yml"})
        self.assertNotEqual(res["inspected_files"]["ci.yml"], res["inspected_files"]["sub/ci.yml"])
        self.assertIn("runner_type", self._rules(res, "ci.yml"))
        self.assertEqual(self._rules(res, "sub/ci.yml"), [])

    def test_yaml_mode_structure_rules(self):
        self._write_wf("s.yml", (
            "on:\n  pull_request_target:\n    types: [opened]\n"
            "jobs:\n"
            "  a:\n    runs-on: [self-hosted, linux]\n    timeout-minutes: 5\n"
            "    steps:\n      - run: git push origin HEAD\n"
            "  b:\n    runs-on: ubuntu-latest\n    # timeout-minutes: 5 (only a comment)\n"
            "    permissions: write-all\n    steps:\n      - run: echo hi\n"
            "  call:\n    uses: org/repo/.github/workflows/x.yml@v1\n"))
        res = rvsb.analyze_workflows(self.td_path)
        self.assertEqual(res["parse_modes"]["s.yml"], "yaml")
        by_rule = {f["rule"]: f["issue"] for f in res["findings"] if f["file"] == "s.yml"}
        self.assertIn("runner_type", by_rule)               # list form runs-on
        self.assertIn("pull_request_target", by_rule)       # key `on` parsed as True by PyYAML
        self.assertIn("jobs: b", by_rule["timeout"])        # comment does not count, reusable call skipped
        self.assertNotIn("call", by_rule["timeout"])
        self.assertEqual(by_rule["permissions"], "Missing explicit permissions block.")
        self.assertIn("concurrency", by_rule)
        self.assertIn("mutation_risk", by_rule)
        self.assertIn("org/repo/.github/workflows/x.yml@v1", by_rule["unpinned_action"])

    def test_yaml_mode_clean_workflow(self):
        sha = "b" * 40
        self._write_wf("ok.yaml", (
            "on: [push]\npermissions:\n  contents: read\nconcurrency:\n  group: x\n"
            "jobs:\n  t:\n    runs-on: ubuntu-latest\n    timeout-minutes: 10\n"
            f"    steps:\n      - uses: actions/checkout@{sha}\n"
            "      - env:\n          T: ${{ github.event.issue.title }}\n        run: echo \"$T\"\n"))
        res = rvsb.analyze_workflows(self.td_path)
        self.assertEqual(res["parse_modes"]["ok.yaml"], "yaml")
        self.assertEqual(res["findings"], [])

    def test_yaml_permissions_write_all_top_level(self):
        self._write_wf("w.yml", "on: push\npermissions: write-all\nconcurrency: g\njobs:\n  t:\n    runs-on: ubuntu-latest\n    timeout-minutes: 1\n    steps: []\n")
        res = rvsb.analyze_workflows(self.td_path)
        self.assertEqual([f["issue"] for f in res["findings"]], ["Permissive write-all detected."])

    def test_broken_yaml_falls_back_to_text(self):
        self._write_wf("broken.yml", "jobs:\n  t:\n    runs-on: self-hosted\n   bad: [unclosed\n")
        res = rvsb.analyze_workflows(self.td_path)
        self.assertEqual(res["parse_modes"]["broken.yml"], "text")
        self.assertIn("runner_type", self._rules(res, "broken.yml"))
        self.assertIn("timeout", self._rules(res, "broken.yml"))

    def test_without_pyyaml_falls_back_to_text(self):
        self._write_wf("ci.yml", "on: push\njobs:\n  t:\n    runs-on: ubuntu-latest\n    timeout-minutes: 5\n")
        with patch.object(rvsb, "yaml", None):
            res = rvsb.analyze_workflows(self.td_path)
        self.assertEqual(res["parse_modes"]["ci.yml"], "text")
        self.assertNotIn("timeout", self._rules(res, "ci.yml"))

    def test_report_de_shows_parse_mode(self):
        md = rvsb.render_report_de("o", "r", "s", {"inspected_files": {"a.yml": "h"}, "parse_modes": {"a.yml": "yaml"}, "findings": []})
        self.assertIn("(Prüfmodus: yaml)", md)

    @patch("revenue_v1_safety_baseline.run_independent_verifier")
    def test_verify_success(self, mock_ind):
        ident = {"kind": "independent_verifier", "name": "n", "version": "1.0.0", "source_sha256": "s"}
        mock_ind.return_value = {"verdict": "PASS", "accepted": True, "reasons": [], "verifier": ident}
        verified = rvsb.verify({"t": 1}, {"report_json_sha256": "h1", "other": "val"}, self.td_path)
        self.assertEqual(verified["verifier_id"], rvsb.VERIFIER_ID)
        self.assertEqual(verified["verifier_status"], "PASS")
        self.assertEqual(verified["independent_verdict"], "PASS")
        self.assertEqual(verified["independent_verifier"], ident)

    @patch("revenue_v1_safety_baseline.run_independent_verifier")
    def test_verify_rejects_mismatch(self, mock_ind):
        mock_ind.return_value = {"verdict": "MISMATCH", "accepted": False, "reasons": ["findings differ"], "verifier": {}}
        with self.assertRaises(SystemExit) as cm:
            rvsb.verify({}, {"report_json_sha256": "h1"}, self.td_path)
        self.assertIn("MISMATCH", str(cm.exception))

    def test_independent_verifier_path_override(self):
        with patch.dict(os.environ, {"REVENUE_V1_INDEPENDENT_VERIFIER": "/tmp/pinned.py"}):
            self.assertEqual(rvsb.independent_verifier_path(), Path("/tmp/pinned.py"))
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("REVENUE_V1_INDEPENDENT_VERIFIER", None)
            self.assertEqual(rvsb.independent_verifier_path(), rvsb.INDEPENDENT_VERIFIER)

    @patch("revenue_v1_safety_baseline.subprocess.run")
    def test_pinned_verifier_missing_is_fail(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", returncode=2)  # e.g. pinned file not found
        with patch.dict(os.environ, {"REVENUE_V1_INDEPENDENT_VERIFIER": "/nonexistent.py"}):
            v = rvsb.run_independent_verifier({}, {}, self.td_path)
        self.assertFalse(v["accepted"])
        self.assertEqual(mock_run.call_args[0][0][1], str(Path("/nonexistent.py")))

    @patch("revenue_v1_safety_baseline.subprocess.run")
    def test_run_independent_verifier_fail_closed(self, mock_run):
        # unreadable output
        mock_run.return_value = MagicMock(stdout="not json", returncode=0)
        self.assertFalse(rvsb.run_independent_verifier({}, {}, self.td_path)["accepted"])
        # PASS text but non-zero exit code
        mock_run.return_value = MagicMock(stdout='{"verdict": "PASS", "accepted": true}', returncode=1)
        self.assertFalse(rvsb.run_independent_verifier({}, {}, self.td_path)["accepted"])

    @patch("revenue_v1_safety_baseline.verify")
    def test_validate_verified_result(self, mock_verify):
        task = {}
        result = {"a": 1}
        mock_verify.return_value = {"a": 1}
        
        # should not raise
        rvsb.validate_verified_result(task, result, self.td_path)
        
        mock_verify.return_value = {"a": 2}
        with self.assertRaises(SystemExit):
            rvsb.validate_verified_result(task, result, self.td_path)

    @patch("revenue_v1_safety_baseline.validate_verified_result")
    def test_reconcile_handoff_success(self, mock_validate):
        task = {}
        result = {
            "github_run_id": "r1",
            "github_run_attempt": "a1",
            "task_id": "t1",
            "attempt_id": "att1",
            "idempotency_key": "k1",
            "worker_result_id": "w1"
        }
        handoff = {
            "task_id": "t1",
            "attempt_id": "att1",
            "result_path": "revenue_v1/results/t1-att1-r1-a1.json",
            "verifier_id": rvsb.VERIFIER_ID,
            "result_commit": "a"*40,
            "proposal_branch": "revenue/result-proposal-1",
            "proposal_pr": "https://github.com/happyhippovip/2026-courier/pull/123",
            "human_merge_required": True,
        }
        
        res = rvsb.reconcile_handoff(task, result, handoff, self.td_path, "123", "revenue/result-proposal-1", "main")
        self.assertEqual(res["status"], "HANDOFF_RECONCILED")

    def test_reconcile_handoff_invalid_run_identity(self):
        with self.assertRaisesRegex(SystemExit, "verified result has no valid"):
            rvsb.reconcile_handoff({}, {}, {}, self.td_path, "1", "rev", "main")

    @patch("revenue_v1_safety_baseline.validate_verified_result")
    def test_reconcile_handoff_invalid_proposal(self, mock_validate):
        result = {"github_run_id": "r1", "github_run_attempt": "a1"}
        with self.assertRaisesRegex(SystemExit, "proposal identity is not a human-reviewable PR"):
            rvsb.reconcile_handoff({}, result, {}, self.td_path, "abc", "rev", "main")
            
        with self.assertRaisesRegex(SystemExit, "proposal identity is not a human-reviewable PR"):
            rvsb.reconcile_handoff({}, result, {}, self.td_path, "123", "badhead", "main")
            
        with self.assertRaisesRegex(SystemExit, "proposal identity is not a human-reviewable PR"):
            rvsb.reconcile_handoff({}, result, {}, self.td_path, "123", "revenue/result-proposal-1", "dev")

    @patch("revenue_v1_safety_baseline.validate_verified_result")
    def test_reconcile_handoff_invalid_commit(self, mock_validate):
        result = {
            "github_run_id": "r1",
            "github_run_attempt": "a1",
            "task_id": "t1",
            "attempt_id": "att1"
        }
        handoff = {
            "task_id": "t1",
            "attempt_id": "att1",
            "result_path": "revenue_v1/results/t1-att1-r1-a1.json",
            "verifier_id": rvsb.VERIFIER_ID,
            "result_commit": "short", # invalid commit
            "proposal_branch": "revenue/result-proposal-1",
            "proposal_pr": "https://github.com/happyhippovip/2026-courier/pull/123",
            "human_merge_required": True,
        }
        with self.assertRaisesRegex(SystemExit, "handoff has no valid durable result commit"):
            rvsb.reconcile_handoff({}, result, handoff, self.td_path, "123", "revenue/result-proposal-1", "main")

    @patch("revenue_v1_safety_baseline.validate_verified_result")
    def test_reconcile_handoff_mismatch(self, mock_validate):
        result = {
            "github_run_id": "r1",
            "github_run_attempt": "a1",
            "task_id": "t1",
            "attempt_id": "att1"
        }
        handoff = {
            "task_id": "t1",
            "attempt_id": "att1",
            "result_path": "revenue_v1/results/WRONG",
            "verifier_id": rvsb.VERIFIER_ID,
            "result_commit": "a"*40,
            "proposal_branch": "revenue/result-proposal-1",
            "proposal_pr": "https://github.com/happyhippovip/2026-courier/pull/123",
            "human_merge_required": True,
        }
        with self.assertRaisesRegex(SystemExit, "handoff does not bind"):
            rvsb.reconcile_handoff({}, result, handoff, self.td_path, "123", "revenue/result-proposal-1", "main")

    def test_cli_execution(self):
        script_path = Path(__file__).resolve().parent.parent / "scripts" / "revenue_v1_safety_baseline.py"
        
        task_p = self.td_path / "task.json"
        task_p.write_text(json.dumps({"target_owner": "a", "target_repo": "b", "target_sha": "c", "task_id": "t1", "attempt_id": "a1", "idempotency_key": "k1", "customer_reference": "cr1"}))
        
        res = {
            "worker_status": "PASS",
            "task_id": "t1",
            "attempt_id": "a1",
            "github_run_id": "r1",
            "github_run_attempt": "1",
            "report_json_sha256": "d4c6c97623b0ce8e46721d6d12c7d581233bdfeaac68d8b1c540928cdc2efdcb",
            "report_md_sha256": "958cf819dd0acd47b38980335964f5f671eacf5271a94183733c61f2b4f26ae0",
            "effect_classification": "SAFE_READ_ONLY",
            "worker_result_id": "worker-a1"
        }
        cand_p = self.td_path / "cand.json"
        cand_p.write_text(json.dumps(res))
        
        handoff_p = self.td_path / "handoff.json"
        handoff_p.write_text(json.dumps({
            "task_id": "t1",
            "attempt_id": "a1",
            "result_path": f"revenue_v1/results/t1-a1-r1-1.json",
            "verifier_id": rvsb.VERIFIER_ID,
            "result_commit": "a"*40,
            "proposal_branch": "revenue/result-proposal-123",
            "proposal_pr": "https://github.com/happyhippovip/2026-courier/pull/123",
            "human_merge_required": True,
        }))

        with open(script_path, "r", encoding="utf-8") as f:
            code = f.read()

        ns = rvsb.__dict__.copy()
        ns["__name__"] = "__main__"
        
        # worker
        with patch.object(sys, 'argv', ["prog", "worker", str(task_p), str(self.td_path)]):
            with patch("subprocess.run") as mock_run:
                def run_side_effect(*args, **kwargs):
                    if "init" in args[0]:
                        dest = Path(args[0][2])
                        (dest / ".git" / "info").mkdir(parents=True, exist_ok=True)
                mock_run.side_effect = run_side_effect
                try:
                    exec(code, ns)
                except SystemExit:
                    pass

        # verify
        with patch.object(sys, 'argv', ["prog", "verify", str(task_p), str(self.td_path), str(cand_p)]):
            with patch("subprocess.run") as mock_run:
                def run_side_effect(*args, **kwargs):
                    if "init" in args[0]:
                        dest = Path(args[0][2])
                        (dest / ".git" / "info").mkdir(parents=True, exist_ok=True)
                mock_run.side_effect = run_side_effect
                try:
                    exec(code, ns)
                except SystemExit:
                    pass

        # reconcile
        with patch.object(sys, 'argv', ["prog", "reconcile", str(task_p), str(self.td_path), str(cand_p), str(handoff_p), "123", "revenue/result-proposal-123", "main"]):
            with patch("subprocess.run") as mock_run:
                def run_side_effect(*args, **kwargs):
                    if "init" in args[0]:
                        dest = Path(args[0][2])
                        (dest / ".git" / "info").mkdir(parents=True, exist_ok=True)
                mock_run.side_effect = run_side_effect
                try:
                    exec(code, ns)
                except SystemExit:
                    pass

if __name__ == "__main__":
    unittest.main()
