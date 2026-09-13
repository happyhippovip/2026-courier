import unittest
import os
import time
import subprocess
import sqlite3
import sys
import tempfile
from pathlib import Path

class TestIntegratedCustomsEscape(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name)
        self.state_dir = self.repo_root / ".courier_state"
        self.state_dir.mkdir()
        self.env = os.environ.copy()
        self.env["COURIER_REPO_ROOT"] = str(self.repo_root)
        
        sys.path.insert(0, str(Path("build/courier_ecosystem_v1/motor").resolve()))
        import supervisor_standalone
        # Force reload environment for supervisor_standalone
        supervisor_standalone.WORKSPACE = self.repo_root
        supervisor_standalone.STATE_DIR = self.state_dir
        supervisor_standalone.DB_PATH = self.state_dir / "motor.db"
        supervisor_standalone.ATTEMPTS_DIR = self.state_dir / "attempts"
        self.conn = supervisor_standalone.init_env()

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def test_path_escape_rejected(self):
        outside = self.repo_root.parent / "scratch"
        outside.mkdir(exist_ok=True)
        outside_file = outside / "outside.txt"
        outside_file.write_text("SecretData")
        
        import json
        exp_eff = json.dumps(["REGEX", "../scratch/outside.txt", "Secret"])
        
        self.conn.execute("INSERT INTO tasks (task_id, instruction, expected_effects, status, priority) VALUES ('ESCAPE-1', 'exit 0', ?, 'PENDING', 10)", (exp_eff,))
        self.conn.commit()
        
        sup = subprocess.Popen(["python3", "build/courier_ecosystem_v1/motor/supervisor_standalone.py", "run"], env=self.env)
        time.sleep(2)
        sup.terminate()
        sup.wait()
        
        c = self.conn.cursor()
        c.execute("SELECT status FROM tasks WHERE task_id='ESCAPE-1'")
        status = c.fetchone()[0]
        self.assertEqual(status, "FAILED", "Supervisor must FAIL tasks that attempt path escape")

if __name__ == "__main__":
    unittest.main()
