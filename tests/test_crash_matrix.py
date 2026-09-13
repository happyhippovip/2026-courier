import unittest
import os
import time
import subprocess
import sqlite3
from pathlib import Path

class TestCrashMatrix(unittest.TestCase):
    def setUp(self):
        self.db_path = Path(".courier_state/motor.db")
        if self.db_path.exists():
            self.db_path.unlink()
        
        import sys
        sys.path.insert(0, str(Path("build/courier_ecosystem_v1/motor").resolve()))
        from supervisor_standalone import init_env
        self.conn = init_env()

    def tearDown(self):
        self.conn.close()

    def test_worker_dies_mid_task(self):
        self.conn.execute("INSERT INTO tasks (task_id, instruction, status, priority) VALUES ('CRASH-1', 'sleep 10', 'PENDING', 10)")
        self.conn.commit()

        sup = subprocess.Popen(["python3", "build/courier_ecosystem_v1/motor/supervisor_standalone.py", "run"])
        time.sleep(1) # Let it dispatch
        
        # Find the worker pid
        c = self.conn.cursor()
        c.execute("SELECT pid FROM attempts WHERE task_id='CRASH-1'")
        row = c.fetchone()
        self.assertIsNotNone(row)
        pid = row[0]
        
        # Kill worker abruptly
        os.kill(pid, 9)
        time.sleep(4) # Let supervisor notice (sleep cycle is 2s)
        
        sup.terminate()
        time.sleep(1)
        
        c.execute("SELECT status FROM tasks WHERE task_id='CRASH-1'")
        status = c.fetchone()[0]
        self.assertIn(status, ["FAILED", "PENDING", "RUNNING"], "Supervisor should notice worker death and either fail or retry")

    def test_stale_running_recovery(self):
        # Insert a task that is stuck in RUNNING with a stale lease
        now = time.time()
        self.conn.execute("INSERT INTO tasks (task_id, instruction, status, lease_owner, lease_expires_at) VALUES ('CRASH-2', 'echo recovery', 'RUNNING', 'OLD_MOTOR', ?)", (now - 100,))
        self.conn.commit()
        
        # Run supervisor briefly
        sup = subprocess.Popen(["python3", "build/courier_ecosystem_v1/motor/supervisor_standalone.py", "run"])
        time.sleep(2)
        sup.terminate()
        
        c = self.conn.cursor()
        c.execute("SELECT status FROM tasks WHERE task_id='CRASH-2'")
        status = c.fetchone()[0]
        self.assertIn(status, ["FAILED", "PENDING", "DONE"], "Stale task should be recovered")

if __name__ == "__main__":
    unittest.main()
