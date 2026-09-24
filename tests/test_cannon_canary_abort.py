import os
import json
import time
import subprocess
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock
from app.cannon.adapters import LiveMuseAdapter

def test_canary_aborts_on_stop_requested(tmp_path):
    results_dir = tmp_path / "results"
    results_dir.mkdir(parents=True)
    state_dir = tmp_path

    motor_json = state_dir / "motor.json"
    motor_json.write_text(json.dumps({"stop_requested": False}), encoding="utf-8")

    def flip_stop():
        time.sleep(1)
        motor_json.write_text(json.dumps({"stop_requested": True}), encoding="utf-8")

    t = threading.Thread(target=flip_stop)
    t.start()

    class MockProcess:
        def __init__(self):
            self.pid = 12345
            self.returncode = None
            self._poll_count = 0
            self._terminated = False
        def poll(self):
            if self._terminated:
                self.returncode = -15
                return self.returncode
            return None
        def terminate(self):
            self._terminated = True
        def kill(self):
            self._terminated = True
        def wait(self, timeout=None):
            return self.returncode

    mock_popen = MagicMock(return_value=MockProcess())

    with patch('shutil.which', return_value='/fake/muse'), \
         patch('subprocess.Popen', mock_popen):
        task = {'provider': 'meta', 'acceptance': 'isolated_nonce_canary_v1', 'task_id': 't1'}

        start_time = time.time()
        try:
            LiveMuseAdapter.execute_canary(task, str(results_dir), lambda x: None, timeout=3)
        except ValueError as e:
            assert 'ABORTED_BY_OPERATOR' in str(e)

        elapsed = time.time() - start_time
        assert elapsed < 3.0, f"Did not abort quickly: took {elapsed}s"

    t.join()
