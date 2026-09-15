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


if __name__ == "__main__":
    unittest.main()
