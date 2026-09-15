import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import phase8_workforce as workforce


def task() -> dict[str, object]:
    return {
        "schema_version": "1.0", "goal_id": "goal-1", "task_id": "task-1",
        "attempt_id": "attempt-1", "idempotency_key": "idempotency-key-0001",
        "capability": workforce.CAPABILITY, "scope": workforce.SCOPE,
        "budget": {"max_files": 1, "max_bytes": 65536},
        "result_contract": workforce.RESULT_CONTRACT, "proposal_mode": "PR_ONLY",
    }


class Phase8WorkforceTests(unittest.TestCase):
    def test_valid_bounded_task_is_accepted(self) -> None:
        workforce.validate_task(task())

    def test_invalid_capability_or_scope_is_rejected_before_worker_effect(self) -> None:
        for key, value in (("capability", "shell"), ("scope", "README.md")):
            unsafe = task()
            unsafe[key] = value
            with self.assertRaises(SystemExit):
                workforce.worker(unsafe, ROOT, "1", "1")

    def test_task_attempt_or_run_mismatch_is_rejected(self) -> None:
        result = workforce.worker(task(), ROOT, "1", "1")
        result["attempt_id"] = "other"
        with TemporaryDirectory() as directory, self.assertRaises(SystemExit):
            workforce.verify(task(), result, ROOT, Path(directory), "1", "1")
        result = workforce.worker(task(), ROOT, "1", "1")
        result["github_run_id"] = "2"
        with TemporaryDirectory() as directory, self.assertRaises(SystemExit):
            workforce.verify(task(), result, ROOT, Path(directory), "1", "1")

    def test_worker_cannot_self_certify(self) -> None:
        result = workforce.worker(task(), ROOT, "1", "1")
        result["verifier_status"] = "PASS"
        with TemporaryDirectory() as directory, self.assertRaises(SystemExit):
            workforce.verify(task(), result, ROOT, Path(directory), "1", "1")

    def test_unfenced_or_mismatched_verifier_result_is_rejected(self) -> None:
        worker_result = workforce.worker(task(), ROOT, "1", "1")
        with self.assertRaises(SystemExit):
            workforce.validate_verified_result(task(), worker_result, ROOT, "1", "1")
        with TemporaryDirectory() as directory:
            verified = workforce.verify(task(), worker_result, ROOT, Path(directory), "1", "1")
        verified["verifier_id"] = "worker-says-pass"
        with self.assertRaises(SystemExit):
            workforce.validate_verified_result(task(), verified, ROOT, "1", "1")

    def test_verifier_digest_mismatch_is_rejected(self) -> None:
        result = workforce.worker(task(), ROOT, "1", "1")
        result["digest_sha256"] = "0" * 64
        with TemporaryDirectory() as directory, self.assertRaises(SystemExit):
            workforce.verify(task(), result, ROOT, Path(directory), "1", "1")

    def test_direct_main_result_is_rejected(self) -> None:
        unsafe = task()
        unsafe["proposal_mode"] = "MAIN"
        with self.assertRaises(SystemExit):
            workforce.validate_task(unsafe)

    def test_duplicate_idempotency_key_fails_closed(self) -> None:
        result = workforce.worker(task(), ROOT, "1", "1")
        with TemporaryDirectory() as directory:
            Path(directory, "prior.json").write_text(json.dumps({**result, "idempotency_key": task()["idempotency_key"]}))
            with self.assertRaises(SystemExit):
                workforce.verify(task(), result, ROOT, Path(directory), "1", "1")

    def test_reconcile_requires_the_bound_human_review_pr(self) -> None:
        worker_result = workforce.worker(task(), ROOT, "1", "1")
        with TemporaryDirectory() as directory:
            verified = workforce.verify(task(), worker_result, ROOT, Path(directory), "1", "1")
        handoff = {
            "task_id": "task-1", "attempt_id": "attempt-1",
            "result_path": "phase8/results/task-1-attempt-1-1-1.json",
            "verifier_id": workforce.VERIFIER_ID, "result_commit": "a" * 40,
            "proposal_branch": "phase8/result-proposal-1-1",
            "proposal_pr": "https://github.com/happyhippovip/2026-courier/pull/1",
            "human_merge_required": True,
        }
        reconciled = workforce.reconcile_handoff(task(), verified, handoff, ROOT, "1", "phase8/result-proposal-1-1", "main")
        self.assertEqual("HANDOFF_RECONCILED", reconciled["status"])
        handoff["proposal_pr"] = "https://github.com/happyhippovip/2026-courier/pull/2"
        with self.assertRaises(SystemExit):
            workforce.reconcile_handoff(task(), verified, handoff, ROOT, "1", "phase8/result-proposal-1-1", "main")


if __name__ == "__main__":
    unittest.main()
