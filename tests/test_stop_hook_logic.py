import unittest
import subprocess
import json
import os
from pathlib import Path

class TestStopHookLogic(unittest.TestCase):
    def setUp(self):
        self.state_file = Path(".courier_state/mac_autonomy_state.json")
        self.history_file = Path(".courier_state/hook_history.json")
        self.state_file.parent.mkdir(exist_ok=True)
        if self.history_file.exists():
            self.history_file.unlink()
            
    def _run_hook(self):
        res = subprocess.run(["python3", "scripts/continuation_hook.py"], capture_output=True, text=True, input="{}")
        return json.loads(res.stdout)

    def test_unrelated_human_gate_allows_continue(self):
        state = {
            "NEXT_SAFE_TASK": "SOME_SAFE_TASK",
            "CONTINUATION_DECISION": "CONTINUE",
            "ACTIVE_WRITER": None,
            "HUMAN_GATES": ["stripe_payment_gate"]
        }
        self.state_file.write_text(json.dumps(state))
        decision = self._run_hook()
        self.assertEqual(decision["decision"], "continue")

    def test_active_writer_stops(self):
        state = {
            "NEXT_SAFE_TASK": "SOME_SAFE_TASK",
            "CONTINUATION_DECISION": "CONTINUE",
            "ACTIVE_WRITER": "Codex",
            "HUMAN_GATES": []
        }
        self.state_file.write_text(json.dumps(state))
        decision = self._run_hook()
        self.assertEqual(decision["decision"], "stop")

    def test_loop_protection(self):
        state = {
            "NEXT_SAFE_TASK": "SAME_TASK",
            "CONTINUATION_DECISION": "CONTINUE",
            "ACTIVE_WRITER": None,
            "HUMAN_GATES": []
        }
        self.state_file.write_text(json.dumps(state))
        self.assertEqual(self._run_hook()["decision"], "continue")
        self.assertEqual(self._run_hook()["decision"], "continue")
        self.assertEqual(self._run_hook()["decision"], "continue")
        decision = self._run_hook()
        self.assertEqual(decision["decision"], "stop")
        self.assertIn("Loop detected", decision["reason"])

if __name__ == "__main__":
    unittest.main()
