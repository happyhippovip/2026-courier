import re

with open("tests/test_courier_complete_lifecycle.py", "r") as f:
    content = f.read()

gemini_mock_old = """    def _gemini(self, task: dict) -> dict:
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

content = re.sub(r'    def _gemini\(self, task: dict\) -> dict:.*?return _response\(task, status="COMPLETED", payload=payload\)', gemini_mock_old, content, flags=re.DOTALL)

# Update assertions back
content = content.replace('["GEMINI", "GEMINI", "GEMINI"]', '["CLI1", "GEMINI", "CLI1"]')
content = content.replace('# self.assertEqual(ledger["file_hashes"]["worker_id"], "GEMINI")', 'self.assertEqual(ledger["file_hashes"]["worker_id"], "GEMINI")')

# Update test_underdetermined...
content = content.replace("['VERIFIED']", '[]') # Wait, I replaced '["VERIFIED"]' with '[]', so I need to replace '[]' back.
# Let's just do it manually with regex or replace.
content = content.replace("self.assertEqual([m[\"status\"] for m in runtime.queue.read_all()], [])", "self.assertEqual([m[\"status\"] for m in runtime.queue.read_all()], [\"VERIFIED\"])")
content = content.replace('self.assertEqual(goal["status"], "ACTIVE")', 'self.assertEqual(goal["status"], "BLOCKED")')

with open("tests/test_courier_complete_lifecycle.py", "w") as f:
    f.write(content)
