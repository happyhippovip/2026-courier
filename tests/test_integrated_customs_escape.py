import unittest
import os
import time
import subprocess
import sqlite3
import sys
from pathlib import Path

class TestIntegratedCustomsEscape(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(".courier_state/motor.db")
        if self.db_path.exists():
            self.db_path.unlink()
            
        sys.path.insert(0, str(Path("build/courier_ecosystem_v1/motor").resolve()))
        from supervisor_standalone import init_env
        self.conn = init_env()

    def tearDown(self):
        self.conn.close()

    def test_path_escape_rejected(self):
        # Create a file outside workspace
        outside = Path("scratch/outside.txt")
        outside.write_text("SecretData")
        
        # Inject task that "produces" this file but as a path escape
        import json
        exp_eff = json.dumps(["REGEX", "../outside.txt", "Secret"])
        
        self.conn.execute("INSERT INTO tasks (task_id, instruction, expected_effects, status, priority) VALUES ('ESCAPE-1', 'exit 0', ?, 'PENDING', 10)", (exp_eff,))
        self.conn.commit()
        
        # Run supervisor briefly
        sup = subprocess.Popen(["python3", "build/courier_ecosystem_v1/motor/supervisor_standalone.py", "run"])
        time.sleep(2)
        sup.terminate()
        
        # Verify task is failed
        c = self.conn.cursor()
        c.execute("SELECT status FROM tasks WHERE task_id='ESCAPE-1'")
        status = c.fetchone()[0]
        self.assertEqual(status, "FAILED", "Supervisor must FAIL tasks that attempt path escape")

if __name__ == "__main__":
    unittest.main()
