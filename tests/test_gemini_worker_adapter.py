import json
import os
import tempfile
import pytest

from scripts.gemini_worker_adapter import run_worker, consume


class MockProcess:
    def __init__(self, stdout_text, stderr_text="", pid=12345):
        self.stdout_text = stdout_text
        self.stderr_text = stderr_text
        self.pid = pid

    def communicate(self, timeout=None):
        return self.stdout_text, self.stderr_text

    def kill(self):
        pass


def test_gemini_worker_adapter_success(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp_dir:
        task_file = os.path.join(tmp_dir, "task.json")
        state_file = os.path.join(tmp_dir, "central_state.json")
        with open(task_file, "w", encoding="utf-8") as f:
            json.dump({"task_id": "T-GEM-01", "instruction": "Do work"}, f)

        observed_cmd = []

        def mock_popen(cmd, **kwargs):
            observed_cmd.extend(cmd)
            return MockProcess('{"status": "SUCCESS", "data": "all good"}')

        monkeypatch.setattr("subprocess.Popen", mock_popen)

        pid, dispatch_ref, result_ref = run_worker(task_file, output_dir=tmp_dir, state_file=state_file)

        assert "--dangerously-skip-permissions" in observed_cmd
        assert os.path.exists(result_ref)

        with open(result_ref, "r", encoding="utf-8") as f:
            res = json.load(f)
        assert res["status"] == "SUCCESS"

        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
        assert state["tasks"]["T-GEM-01"]["reconciled_status"] == "SUCCESS"


def test_gemini_worker_adapter_markdown_codeblock(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp_dir:
        task_file = os.path.join(tmp_dir, "task.json")
        state_file = os.path.join(tmp_dir, "central_state.json")
        with open(task_file, "w", encoding="utf-8") as f:
            json.dump({"task_id": "T-GEM-02", "instruction": "Do work"}, f)

        mock_out = "Here is the result:\n```json\n{\"status\": \"SUCCESS\", \"key\": 42}\n```"
        monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: MockProcess(mock_out))

        pid, dispatch_ref, result_ref = run_worker(task_file, output_dir=tmp_dir, state_file=state_file)

        with open(result_ref, "r", encoding="utf-8") as f:
            res = json.load(f)
        assert res["status"] == "SUCCESS"
        assert res["key"] == 42


def test_gemini_worker_adapter_fail_closed_on_garbage(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp_dir:
        task_file = os.path.join(tmp_dir, "task.json")
        state_file = os.path.join(tmp_dir, "central_state.json")
        with open(task_file, "w", encoding="utf-8") as f:
            json.dump({"task_id": "T-GEM-03", "instruction": "Do work"}, f)

        mock_out = "I cannot process this instruction and this is not json."
        monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: MockProcess(mock_out))

        pid, dispatch_ref, result_ref = run_worker(task_file, negative_test=True, output_dir=tmp_dir, state_file=state_file)

        with open(result_ref, "r", encoding="utf-8") as f:
            res = json.load(f)
        assert res["status"] == "FAILED"
        assert res["reason"] == "INVALID_RESULT"

        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
        assert state["tasks"]["T-GEM-03"]["reconciled_status"] == "FAILED"
