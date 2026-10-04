import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from courier_runtime.garbage_collection import sweep_unowned_artifacts_and_temps
from courier_runtime.task_lifecycle import TaskLifecycleManager, TaskRecord, ActivityClass

class TestOrphanStateGarbageCollection(unittest.TestCase):
    def setUp(self):
        self.home_dir = tempfile.mkdtemp()
        self.artifacts_dir = Path(self.home_dir) / "artifacts"
        self.run_dir = Path(self.home_dir) / "run"
        self.artifacts_dir.mkdir()
        self.run_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.home_dir)

    def test_sweep_unowned_artifacts_and_temps(self):
        # Create an old unowned artifact dir
        old_task_dir = self.artifacts_dir / "task_old_1"
        old_task_dir.mkdir()
        (old_task_dir / "data.txt").write_text("old data")

        # Create an old unowned tmp file
        old_tmp_out = self.run_dir / "task-task_old_1.out"
        old_tmp_out.write_text("old logs")

        # Create a new active artifact dir
        active_task_dir = self.artifacts_dir / "task_active_1"
        active_task_dir.mkdir()
        (active_task_dir / "data.txt").write_text("active data")

        # Create a new active tmp file
        active_tmp_out = self.run_dir / "task-task_active_1.out"
        active_tmp_out.write_text("active logs")

        # Artificially age the old ones
        past = time.time() - 90000
        os.utime(old_task_dir, (past, past))
        os.utime(old_tmp_out, (past, past))

        manager = TaskLifecycleManager(home_dir=self.home_dir)
        manager.active_tasks["task_active_1"] = TaskRecord(
            task_id="task_active_1", workkey="wk", owner_session="s", owner_host="h",
            pid_or_execution_id="1", process_start_identity="1", started_at=time.time(),
            expected_activity_class=ActivityClass.COMPUTE
        )

        reclaimed = manager.run_garbage_collection(max_age_seconds=86400)

        # Assert old are gone
        self.assertFalse(old_task_dir.exists())
        self.assertFalse(old_tmp_out.exists())

        # Assert new are intact
        self.assertTrue(active_task_dir.exists())
        self.assertTrue(active_tmp_out.exists())

        # At least some bytes reclaimed
        self.assertGreater(reclaimed, 0)

if __name__ == "__main__":
    unittest.main()
