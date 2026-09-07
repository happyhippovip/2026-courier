import unittest
import json
from unittest.mock import patch, MagicMock
from scripts.native_agy_runner import execute_native_agy_prompt

class TestJsonExtractor(unittest.TestCase):
    def run_extractor(self, response_text):
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            agy_output = {
                "conversation_id": "conv-1",
                "status": "SUCCESS",
                "response": response_text
            }
            mock_result.stdout = json.dumps(agy_output)
            mock_run.return_value = mock_result
            return execute_native_agy_prompt(prompt="t", expected_identity={"id": 1}, timeout_seconds=1)

    def test_1_raw_valid_json(self):
        txt = '{"id": 1, "verdict": "PASS", "summary": "done", "changed_files": []}'
        success, payload = self.run_extractor(txt)
        self.assertTrue(success)
        self.assertEqual(payload["verdict"], "PASS")

    def test_2_markdown_json_fenced(self):
        txt = 'Here is it:\n```json\n{"id": 1, "verdict": "PASS", "summary": "done", "changed_files": []}\n```'
        success, payload = self.run_extractor(txt)
        self.assertTrue(success)
        self.assertEqual(payload["verdict"], "PASS")

    def test_3_generic_fenced_valid_json(self):
        txt = 'Here is it:\n```\n{"id": 1, "verdict": "PASS", "summary": "done", "changed_files": []}\n```'
        success, payload = self.run_extractor(txt)
        self.assertTrue(success)
        self.assertEqual(payload["verdict"], "PASS")

    def test_4_rejects_malformed_truncated(self):
        txt = 'Here is it:\n```json\n{"id": 1, "verdict": "PASS"'
        success, payload = self.run_extractor(txt)
        self.assertFalse(success)
        self.assertEqual(payload["error_type"], "INVALID_MODEL_PAYLOAD_JSON")

    def test_5_rejects_schema_invalid(self):
        txt = '```json\n[1, 2, 3]\n```'
        success, payload = self.run_extractor(txt)
        self.assertFalse(success)
        self.assertEqual(payload["error_type"], "INVALID_MODEL_PAYLOAD_JSON")

    def test_6_rejects_two_competing_valid(self):
        txt = 'Option 1:\n```json\n{"id": 1, "verdict": "PASS", "summary": "done", "changed_files": []}\n```\nOption 2:\n```json\n{"id": 1, "verdict": "FAIL", "summary": "done", "changed_files": []}\n```'
        success, payload = self.run_extractor(txt)
        self.assertFalse(success)
        self.assertIn("Multiple valid JSON", payload["error"])

    def test_7_rejects_unrelated_json_prose_ambiguity(self):
        txt = '{"id": 1, "verdict": "PASS", "summary": "done", "changed_files": []} and then I added another JSON like {"some": "thing"}'
        success, payload = self.run_extractor(txt)
        self.assertFalse(success)
        self.assertEqual(payload["error_type"], "INVALID_MODEL_PAYLOAD_JSON")

if __name__ == '__main__':
    unittest.main()
