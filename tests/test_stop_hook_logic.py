import unittest
import subprocess
import json
import os
import tempfile
import sqlite3
from pathlib import Path

class TestStopHookLogic(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name)
        self.state_dir = self.repo_root / ".courier_state"
        self.state_dir.mkdir()
        self.db_path = self.state_dir / "motor.db"
        self.history_file = self.state_dir / "hook_history.json"
        
        self.conn = sqlite3.connect(self.db_path)
        c = self.conn.cursor()
        c.execute('''CREATE TABLE tasks (task_id TEXT PRIMARY KEY, status TEXT, gate_id TEXT, priority INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE approved_gates (gate_id TEXT PRIMARY KEY)''')
        self.conn.commit()
        
        self.env = os.environ.copy()
        self.env["COURIER_REPO_ROOT"] = str(self.repo_root)

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def _run_hook(self):
        res = subprocess.run(["python3", "scripts/continuation_hook.py"], capture_output=True, text=True, input="{}", env=self.env)
        try:
            return json.loads(res.stdout)
        except json.JSONDecodeError:
            return {"decision": "error", "reason": res.stdout}

    def test_unrelated_human_gate_allows_continue(self):
        c = self.conn.cursor()
        c.execute("INSERT INTO tasks (task_id, status) VALUES ('SOME_SAFE_TASK', 'PENDING')")
        self.conn.commit()
        
        decision = self._run_hook()
        self.assertEqual(decision["decision"], "continue")

    def test_active_writer_stops(self):
        c = self.conn.cursor()
        c.execute("INSERT INTO tasks (task_id, status) VALUES ('SOME_SAFE_TASK', 'PENDING')")
        self.conn.commit()
        
        # Create lock file
        (self.state_dir / ".courier_writer.lock").touch()
        
        decision = self._run_hook()
        self.assertEqual(decision["decision"], "stop")

    def test_loop_protection(self):
        c = self.conn.cursor()
        c.execute("INSERT INTO tasks (task_id, status) VALUES ('SAME_TASK', 'PENDING')")
        self.conn.commit()
        
        self.assertEqual(self._run_hook()["decision"], "continue")
        self.assertEqual(self._run_hook()["decision"], "continue")
        self.assertEqual(self._run_hook()["decision"], "continue")
        decision = self._run_hook()
        self.assertEqual(decision["decision"], "stop")
        self.assertIn("Loop detected", decision["reason"])

if __name__ == "__main__":
    unittest.main()
