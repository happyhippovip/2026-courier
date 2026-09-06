"""Unit tests for Native AGY Runner using injected process doubles and real CLI validation."""
import json
import subprocess
import unittest
import os
from unittest.mock import MagicMock, patch
from pathlib import Path

from scripts.native_agy_runner import (
    AGY_CLI_PATH,
    DEFAULT_VERIFIED_MODEL,
    execute_native_agy_prompt,
    get_agy_version,
    is_agy_installed,
)


class TestNativeAgyRunner(unittest.TestCase):


    def setUp(self):
        self.patcher = patch('os.access', return_value=True)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_is_agy_installed(self) -> None:
        """Verify installed agy CLI is detected."""
        self.assertTrue(is_agy_installed())
        self.assertFalse(is_agy_installed(Path("/nonexistent/bin/agy")))

    @patch('subprocess.run')
    def test_get_agy_version(self, mock_run) -> None:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = '1.0.0'

        """Verify agy --version returns expected version."""
        version = get_agy_version()
        self.assertNotEqual(version, "NOT_INSTALLED")
        self.assertNotEqual(version, "UNKNOWN")
        self.assertEqual(get_agy_version(Path("/nonexistent/bin/agy")), "NOT_INSTALLED")

    @patch("subprocess.run")
    def test_timeout_fails_closed(self, mock_run: MagicMock) -> None:
        """Verify timeout fails closed with error_type TIMEOUT."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["agy"], timeout=60.0)
        success, res = execute_native_agy_prompt("Test prompt", timeout_seconds=60.0)
        self.assertFalse(success)
        self.assertEqual(res["error_type"], "TIMEOUT")
        self.assertEqual(res["verdict"], "FAILED")

    @patch("subprocess.run")
    def test_nonzero_exit_fails_closed(self, mock_run: MagicMock) -> None:
        """Verify nonzero returncode fails closed with error_type NONZERO_EXIT."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Internal error")
        success, res = execute_native_agy_prompt("Test prompt")
        self.assertFalse(success)
        self.assertEqual(res["error_type"], "NONZERO_EXIT")
        self.assertEqual(res["verdict"], "FAILED")

    @patch("subprocess.run")
    def test_auth_required_triggers_human_gate(self, mock_run: MagicMock) -> None:
        """Verify authentication / login prompts fail closed with HUMAN_GATE."""
        mock_run.return_value = MagicMock(returncode=1, stdout="Please login required to continue", stderr="")
        success, res = execute_native_agy_prompt("Test prompt")
        self.assertFalse(success)
        self.assertEqual(res["error_type"], "AUTHENTICATION_REQUIRED")
        self.assertEqual(res["verdict"], "HUMAN_GATE")

    @patch("subprocess.run")
    def test_invalid_outer_json_fails_closed(self, mock_run: MagicMock) -> None:
        """Verify malformed outer output fails closed."""
        mock_run.return_value = MagicMock(returncode=0, stdout="Not a JSON string", stderr="")
        success, res = execute_native_agy_prompt("Test prompt")
        self.assertFalse(success)
        self.assertEqual(res["error_type"], "INVALID_OUTER_JSON")
        self.assertEqual(res["verdict"], "FAILED")

    @patch("subprocess.run")
    def test_non_success_status_fails_closed(self, mock_run: MagicMock) -> None:
        """Verify non-success status in outer envelope fails closed."""
        outer = {"status": "ERROR", "error": "rate limit"}
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(outer), stderr="")
        success, res = execute_native_agy_prompt("Test prompt")
        self.assertFalse(success)
        self.assertEqual(res["error_type"], "AGY_EXECUTION_FAILED")
        self.assertEqual(res["verdict"], "FAILED")

    @patch("subprocess.run")
    def test_malformed_model_payload_fails_closed(self, mock_run: MagicMock) -> None:
        """Verify model response that is not valid JSON fails closed."""
        outer = {"status": "SUCCESS", "response": "I cannot return JSON"}
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(outer), stderr="")
        success, res = execute_native_agy_prompt("Test prompt")
        self.assertFalse(success)
        self.assertEqual(res["error_type"], "INVALID_MODEL_PAYLOAD_JSON")
        self.assertEqual(res["verdict"], "FAILED")

    @patch("subprocess.run")
    def test_missing_or_invalid_verdict_fails_closed(self, mock_run: MagicMock) -> None:
        """Verify missing verdict in model payload fails closed without default PASS."""
        outer = {"status": "SUCCESS", "response": json.dumps({"summary": "Done without verdict"})}
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(outer), stderr="")
        success, res = execute_native_agy_prompt("Test prompt")
        self.assertFalse(success)
        self.assertEqual(res["error_type"], "INVALID_OR_MISSING_VERDICT")
        self.assertEqual(res["verdict"], "FAILED")

    @patch("subprocess.run")
    def test_missing_summary_fails_closed(self, mock_run: MagicMock) -> None:
        """Verify missing summary in model payload fails closed."""
        outer = {"status": "SUCCESS", "response": json.dumps({"verdict": "PASS"})}
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(outer), stderr="")
        success, res = execute_native_agy_prompt("Test prompt")
        self.assertFalse(success)
        self.assertEqual(res["error_type"], "INVALID_OR_MISSING_SUMMARY")
        self.assertEqual(res["verdict"], "FAILED")

    @patch("subprocess.run")
    def test_identity_mismatch_fails_closed(self, mock_run: MagicMock) -> None:
        """Verify mismatched identity in model response fails closed."""
        model_inner = {
            "correlation_id": "wrong-corr",
            "task_id": "wrong-task",
            "task_hash": "wrong-hash",
            "target_agent": "GEMINI",
            "verdict": "PASS",
            "summary": "Mismatched identity",
        }
        outer = {
            "status": "SUCCESS",
            "conversation_id": "conv-12345",
            "response": json.dumps(model_inner),
        }
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(outer), stderr="")
        expected_ident = {
            "correlation_id": "expected-corr",
            "task_id": "expected-task",
            "task_hash": "expected-hash",
            "target_agent": "GEMINI",
        }
        success, res = execute_native_agy_prompt("Test prompt", expected_identity=expected_ident)
        self.assertFalse(success)
        self.assertEqual(res["error_type"], "IDENTITY_MISMATCH")
        self.assertEqual(res["verdict"], "FAILED")

    @patch("subprocess.run")
    def test_successful_model_execution_parsing(self, mock_run: MagicMock) -> None:
        """Verify successful structured response parsing."""
        model_inner = {
            "correlation_id": "corr-123",
            "task_id": "task-456",
            "task_hash": "hash-789",
            "target_agent": "GEMINI",
            "verdict": "PASS",
            "summary": "All tests pass cleanly",
        }
        outer = {
            "status": "SUCCESS",
            "model": "gemini-3.7-flash-medium",
            "conversation_id": "conv-12345",
            "duration_seconds": 1.25,
            "response": json.dumps(model_inner),
            "usage": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
        }
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(outer), stderr="")
        expected_ident = {
            "correlation_id": "corr-123",
            "task_id": "task-456",
            "task_hash": "hash-789",
            "target_agent": "GEMINI",
        }
        success, res = execute_native_agy_prompt("Test prompt", expected_identity=expected_ident)
        self.assertTrue(success)
        self.assertEqual(res["verdict"], "PASS")
        self.assertEqual(res["summary"], "All tests pass cleanly")
        self.assertEqual(res["conversation_id"], "conv-12345")
        self.assertEqual(res["requested_model"], DEFAULT_VERIFIED_MODEL)
    @patch("subprocess.run")
    def test_a1_hash_2fa_false_positive(self, mock_run: MagicMock) -> None:
        """A1: successful structured worker result whose task_hash contains '2fa' does NOT trigger HUMAN_GATE."""
        model_inner = {
            "task_hash": "hash-with-2fa-inside",
            "verdict": "PASS",
            "summary": "Completed",
        }
        outer = {"status": "SUCCESS", "response": json.dumps(model_inner)}
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(outer), stderr="")
        success, res = execute_native_agy_prompt("Test prompt")
        self.assertTrue(success)
        self.assertEqual(res["verdict"], "PASS")

    @patch("subprocess.run")
    def test_a2_correlation_oauth_false_positive(self, mock_run: MagicMock) -> None:
        """A2: correlation_id containing 'oauth' does NOT trigger HUMAN_GATE."""
        model_inner = {
            "correlation_id": "oauth-1234",
            "verdict": "PASS",
            "summary": "Completed",
        }
        outer = {"status": "SUCCESS", "response": json.dumps(model_inner)}
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(outer), stderr="")
        success, res = execute_native_agy_prompt("Test prompt")
        self.assertTrue(success)
        self.assertEqual(res["verdict"], "PASS")

    @patch("subprocess.run")
    def test_a3_mission_captcha_false_positive(self, mock_run: MagicMock) -> None:
        """A3: mission_id/result data containing 'captcha' does NOT trigger HUMAN_GATE."""
        model_inner = {
            "mission_id": "captcha-abc",
            "verdict": "PASS",
            "summary": "Completed",
        }
        outer = {"status": "SUCCESS", "response": json.dumps(model_inner)}
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(outer), stderr="")
        success, res = execute_native_agy_prompt("Test prompt")
        self.assertTrue(success)
        self.assertEqual(res["verdict"], "PASS")

    @patch("subprocess.run")
    def test_a4_summary_2fa_false_positive(self, mock_run: MagicMock) -> None:
        """A4: ordinary worker summary mentioning '2FA' does not itself cause an authentication gate when execution status is successful."""
        model_inner = {
            "verdict": "PASS",
            "summary": "User needs to set up 2FA.",
        }
        outer = {"status": "SUCCESS", "response": json.dumps(model_inner)}
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(outer), stderr="")
        success, res = execute_native_agy_prompt("Test prompt")
        self.assertTrue(success)
        self.assertEqual(res["verdict"], "PASS")

    @patch("subprocess.run")
    def test_a5_real_login_gate(self, mock_run: MagicMock) -> None:
        """A5: genuine AGY login-required response DOES trigger HUMAN_GATE."""
        outer = {"status": "ERROR", "error": "Login required to access Gemini"}
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(outer), stderr="")
        success, res = execute_native_agy_prompt("Test prompt")
        self.assertFalse(success)
        self.assertEqual(res["error_type"], "AUTHENTICATION_REQUIRED")
        self.assertEqual(res["verdict"], "HUMAN_GATE")

    @patch("subprocess.run")
    def test_a6_real_oauth_gate(self, mock_run: MagicMock) -> None:
        """A6: genuine OAuth-required response DOES trigger HUMAN_GATE."""
        outer = {"status": "ERROR", "error": "Invalid oauth token"}
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(outer), stderr="")
        success, res = execute_native_agy_prompt("Test prompt")
        self.assertFalse(success)
        self.assertEqual(res["error_type"], "AUTHENTICATION_REQUIRED")
        self.assertEqual(res["verdict"], "HUMAN_GATE")

    @patch("subprocess.run")
    def test_a7_real_reauth_gate(self, mock_run: MagicMock) -> None:
        """A7: genuine re-authentication requirement DOES trigger HUMAN_GATE."""
        outer = {"status": "ERROR", "error_type": "AUTHENTICATION_REQUIRED", "error": "Please re-authenticate"}
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(outer), stderr="")
        success, res = execute_native_agy_prompt("Test prompt")
        self.assertFalse(success)
        self.assertEqual(res["error_type"], "AUTHENTICATION_REQUIRED")
        self.assertEqual(res["verdict"], "HUMAN_GATE")

    @patch("subprocess.run")
    def test_a8_real_2fa_gate(self, mock_run: MagicMock) -> None:
        """A8: genuine 2FA requirement from appropriate auth/error context DOES trigger HUMAN_GATE."""
        outer = {"status": "ERROR", "error": "2fa challenge failed"}
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(outer), stderr="")
        success, res = execute_native_agy_prompt("Test prompt")
        self.assertFalse(success)
        self.assertEqual(res["error_type"], "AUTHENTICATION_REQUIRED")
        self.assertEqual(res["verdict"], "HUMAN_GATE")

    @patch("subprocess.run")
    def test_a9_ambiguous_fail_closed(self, mock_run: MagicMock) -> None:
        """A9: malformed/ambiguous auth failure remains fail-closed where appropriate."""
        mock_run.return_value = MagicMock(returncode=1, stdout="Some random login required text", stderr="")
        success, res = execute_native_agy_prompt("Test prompt")
        self.assertFalse(success)
        self.assertEqual(res["error_type"], "AUTHENTICATION_REQUIRED")
        self.assertEqual(res["verdict"], "HUMAN_GATE")

    @patch("subprocess.run")
    def test_a10_identity_preserved(self, mock_run: MagicMock) -> None:
        """A10: canonical worker JSON remains parseable and identity-bound."""
        model_inner = {
            "correlation_id": "corr-auth-123",
            "task_id": "task-456",
            "task_hash": "hash-2fa-789",
            "target_agent": "GEMINI",
            "verdict": "PASS",
            "summary": "All tests pass cleanly oauth",
        }
        outer = {
            "status": "SUCCESS",
            "model": "gemini-3.7-flash-medium",
            "response": json.dumps(model_inner),
        }
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(outer), stderr="")
        expected_ident = {
            "correlation_id": "corr-auth-123",
            "task_id": "task-456",
            "task_hash": "hash-2fa-789",
            "target_agent": "GEMINI",
        }
        success, res = execute_native_agy_prompt("Test prompt", expected_identity=expected_ident)
        self.assertTrue(success)
        self.assertEqual(res["verdict"], "PASS")
        self.assertTrue(res["model_identity_truthful"])


if __name__ == "__main__":
    unittest.main()


