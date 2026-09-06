import re
with open("tests/test_courier_complete_lifecycle.py", "r") as f:
    content = f.read()

# Delete lines 89 to the end of the file, then re-append what's needed. Wait, lines 89 to 110 are messed up.
# Let's just find the duplicate _gemini and clean it up.
gemini_mock_clean = """    def _gemini(self, task: dict) -> dict:
        self.implementation_attempts += 1
        if self.implementation_attempts == 2:
            (self.workspace / "lifecycle_effect.txt").write_text("DONE", encoding="utf-8")
        payload = {
            "action": "implementation",
            "changed_files": ["lifecycle_effect.txt"],
            "verification_strategy": "local_file_check",
            "verdict": "PASS",
        }
        return _response(task, status="COMPLETED", payload=payload)"""

content = re.sub(r'    def _gemini\(self, task: dict\) -> dict:.*?        return _response\(task, status="COMPLETED", payload=payload\)\n        elif action == "verify_improvement_tests":.*?(?=    def test_complete_lifecycle_retries_once_then_satisfies_goal)', gemini_mock_clean + '\n\n', content, flags=re.DOTALL)

with open("tests/test_courier_complete_lifecycle.py", "w") as f:
    f.write(content)
