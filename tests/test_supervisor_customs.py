import unittest
import os
import time
import json
import tempfile
from pathlib import Path
import sqlite3

class TestSupervisorCustoms(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name)
        
        self.db_path = self.repo_root / "test_customs.db"
        
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("CREATE TABLE attempts (attempt_id TEXT PRIMARY KEY, task_id TEXT, pid INTEGER, start_time REAL, end_time REAL, exit_code INTEGER)")
        self.conn.commit()

        self.workspace = self.repo_root / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.log_file = self.workspace / "task.log"
        self.log_file.write_text("dummy log")

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def _eval_customs(self, returncode, exp_eff_val, start_time, file_mtime_override=None):
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
                
                # Patch WORKSPACE for test
                original_workspace = result_customs.WORKSPACE
                result_customs.WORKSPACE = WORKSPACE
                
                try:
                    eff_val = meta["exp_eff"]
                    try:
                        parsed_eff = json.loads(eff_val)
                    except json.JSONDecodeError:
                        parsed_eff = eff_val

                    if isinstance(parsed_eff, list) and len(parsed_eff) == 3 and parsed_eff[0] == "REGEX":
                        eff_path = Path(WORKSPACE / parsed_eff[1])
                        if file_mtime_override is not None:
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
                        if eff_path_stat and eff_path_stat.st_mtime < meta["start_time"]:
                            success = False
                            msg = f"Stale Result Rejection: {eff_path} was last modified before task started."
                finally:
                    result_customs.WORKSPACE = original_workspace
            except Exception as e:
                success = False
                msg = str(e)
                
        return success, msg

    def test_stale_artifact(self):
        target = self.workspace / "stale.txt"
        target.write_text("Content 123")
        old_mtime = time.time() - 100
        os.utime(target, (old_mtime, old_mtime))
        
        task_start = time.time() - 10
        
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
        self.assertFalse(succ)

if __name__ == "__main__":
    unittest.main()
