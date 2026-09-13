import unittest
import os
import time
import json
from pathlib import Path
import sqlite3

class TestSupervisorCustoms(unittest.TestCase):
    def setUp(self):
        self.db_path = Path("test_customs.db")
        if self.db_path.exists():
            self.db_path.unlink()
        
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("CREATE TABLE attempts (attempt_id TEXT PRIMARY KEY, task_id TEXT, pid INTEGER, start_time REAL, end_time REAL, exit_code INTEGER)")
        self.conn.commit()

        # Dummy workspace
        self.workspace = Path("scratch/test_sup_workspace")
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.log_file = self.workspace / "task.log"
        self.log_file.write_text("dummy log")

    def tearDown(self):
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def _eval_customs(self, returncode, exp_eff_val, start_time, file_mtime_override=None):
        # Emulate the supervisor_standalone.py customs logic
        success = (returncode == 0)
        msg = ""
        meta = {
            "exp_eff": exp_eff_val,
            "log": str(self.log_file),
            "start_time": start_time
        }
        
        WORKSPACE = self.workspace

        if success and meta["exp_eff"]:
            try:
                import sys
                sys.path.insert(0, str(Path("build/courier_ecosystem_v1/motor").resolve()))
                import result_customs
                eff_val = meta["exp_eff"]
                try:
                    parsed_eff = json.loads(eff_val)
                except json.JSONDecodeError:
                    parsed_eff = eff_val # legacy raw string path

                if isinstance(parsed_eff, list) and len(parsed_eff) == 3 and parsed_eff[0] == "REGEX":
                    eff_path = Path(WORKSPACE / parsed_eff[1])
                    if file_mtime_override is not None:
                        # Monkeypatch stat for testing
                        class DummyStat:
                            st_mtime = file_mtime_override
                        eff_path_stat = DummyStat()
                    else:
                        eff_path_stat = eff_path.stat() if eff_path.exists() else None
                        
                    success, msg = result_customs.ResultCustoms.verify_content_regex(str(eff_path), parsed_eff[2])
                else:
                    eff_path = Path(WORKSPACE / str(parsed_eff))
                    if file_mtime_override is not None:
                        class DummyStat:
                            st_mtime = file_mtime_override
                        eff_path_stat = DummyStat()
                    else:
                        eff_path_stat = eff_path.stat() if eff_path.exists() else None
                        
                    success, msg = result_customs.ResultCustoms.verify_file_exists(str(eff_path))

                if success:
                    # Stale result rejection
                    if eff_path_stat and eff_path_stat.st_mtime < meta["start_time"]:
                        success = False
                        msg = f"Stale Result Rejection: {eff_path} was last modified before task started."
            except Exception as e:
                success = False
                msg = str(e)
                
        return success, msg

    def test_stale_artifact(self):
        # Create file BEFORE task start time
        target = self.workspace / "stale.txt"
        target.write_text("Content 123")
        old_mtime = time.time() - 100
        os.utime(target, (old_mtime, old_mtime))
        
        task_start = time.time() - 10
        
        # Test REGEX on stale file
        exp_eff = json.dumps(["REGEX", "stale.txt", "Content"])
        succ, msg = self._eval_customs(0, exp_eff, task_start, file_mtime_override=old_mtime)
        self.assertFalse(succ)
        self.assertIn("Stale Result Rejection", msg)

    def test_worker_failure_matching_artifact(self):
        target = self.workspace / "failed.txt"
        target.write_text("Fail Match")
        task_start = time.time() - 10
        exp_eff = json.dumps(["REGEX", "failed.txt", "Match"])
        
        succ, msg = self._eval_customs(1, exp_eff, task_start)
        self.assertFalse(succ) # Fails because returncode is 1

if __name__ == "__main__":
    unittest.main()
