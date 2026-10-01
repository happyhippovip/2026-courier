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
        self.assertEqual(mock_run.call_count, 5)
        
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
        
        # mock analyze to do nothing (clean)
        res = rvsb.worker(task, self.td_path)
        
        self.assertEqual(res["task_id"], "t1")
        self.assertEqual(res["worker_status"], "PASS")
        self.assertTrue((self.td_path / "report.json").exists())
        self.assertTrue((self.td_path / "report.md").exists())
        self.assertIn("No safety violations detected", (self.td_path / "report.md").read_text(encoding="utf-8"))

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

    @patch("revenue_v1_safety_baseline.worker")
    def test_verify_success(self, mock_worker):
        task = {"test": 1}
        candidate = {
            "report_json_sha256": "h1",
            "report_md_sha256": "h2",
            "other": "val"
        }
        mock_worker.return_value = {
            "report_json_sha256": "h1",
            "report_md_sha256": "h2"
        }
        
        verified = rvsb.verify(task, candidate, self.td_path)
        self.assertEqual(verified["verifier_id"], rvsb.VERIFIER_ID)
        self.assertEqual(verified["verifier_status"], "PASS")

    @patch("revenue_v1_safety_baseline.worker")
    def test_verify_fail_hash_mismatch(self, mock_worker):
        task = {"test": 1}
        candidate = {
            "report_json_sha256": "h1",
            "report_md_sha256": "h2",
        }
        mock_worker.return_value = {
            "report_json_sha256": "h3",
            "report_md_sha256": "h2"
        }
        
        with self.assertRaises(SystemExit) as cm:
            rvsb.verify(task, candidate, self.td_path)
        self.assertIn("hashes do not match", str(cm.exception))

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
