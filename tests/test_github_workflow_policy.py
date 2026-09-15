import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import validate_github_workflow_policy as workflow_policy


class GitHubWorkflowPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = json.loads((ROOT / ".github/github-actions-policy.json").read_text(encoding="utf-8"))

    def validate(self, workflow: str) -> list[str]:
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "courier-codex.yml"
            path.write_text(workflow, encoding="utf-8")
            return workflow_policy.validate_workflow(path, self.policy)

    def approved_workflow(self) -> str:
        return (ROOT / "tests/fixtures/github_actions_policy/approved-courier-codex.yml").read_text(encoding="utf-8")

    def test_repository_workflows_pass_policy(self) -> None:
        self.assertEqual(
            [],
            [
                error
                for path in sorted((ROOT / ".github/workflows").glob("*.yml"))
                for error in workflow_policy.validate_workflow(path, self.policy)
            ],
        )

    def test_approved_fixture_passes(self) -> None:
        self.assertEqual([], self.validate(self.approved_workflow()))

    def test_missing_timeout_is_rejected(self) -> None:
        self.assertIn("missing timeout-minutes", "\n".join(self.validate(self.approved_workflow().replace("    timeout-minutes: 10\n", "", 1))))

    def test_self_hosted_runner_is_rejected(self) -> None:
        self.assertIn("self-hosted runners are forbidden", "\n".join(self.validate(self.approved_workflow().replace("ubuntu-latest", "self-hosted", 1))))

    def test_direct_main_push_is_rejected(self) -> None:
        self.assertIn("direct main push is forbidden", "\n".join(self.validate(self.approved_workflow().replace('HEAD:$PROPOSAL_BRANCH', "HEAD:main"))))

    def test_worker_contents_write_is_rejected(self) -> None:
        unsafe = self.approved_workflow().replace(
            "  codex-worker:\n    timeout-minutes: 10\n    runs-on: ubuntu-latest\n    permissions:\n      contents: read",
            "  codex-worker:\n    timeout-minutes: 10\n    runs-on: ubuntu-latest\n    permissions:\n      contents: write",
        )
        self.assertIn("worker must have contents: read only", "\n".join(self.validate(unsafe)))

    def test_worker_verifier_role_conflation_is_rejected(self) -> None:
        conflated = self.approved_workflow().replace("  verify-result:", "  codex-worker-verify-result:")
        self.assertIn("jobs must exactly match the explicit role allowlist", "\n".join(self.validate(conflated)))


if __name__ == "__main__":
    unittest.main()
