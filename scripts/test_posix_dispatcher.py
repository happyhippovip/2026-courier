import os
from pathlib import Path
from courier_admission_control import TaskPacket
from courier_router import WorkerTarget
from courier_posix_dispatcher import PosixRalphDispatcher
from unittest.mock import patch, MagicMock

@patch("subprocess.Popen")
def test_posix_ralph_dispatcher(mock_popen, tmp_path):
    dispatcher = PosixRalphDispatcher("dummy.sh")
    
    packet = TaskPacket(
        goal_id="g1", task_id="t1", attempt_id=1, dependencies=[],
        required_platform="darwin", required_capability="gemini", logical_scope="R",
        writer_required=True, budget=5.0, result_contract="none", human_gate_class="NONE"
    )
    target = WorkerTarget("t1", "darwin", ["gemini", "bash"], 1.0, 0, 1)
    
    dispatcher.dispatch(packet, target, str(tmp_path))
    
    # Assert env file written correctly
    env_file = tmp_path / ".ralph" / ".env"
    assert env_file.exists()
    assert 'RALPH_TOOL="gemini"' in env_file.read_text()
    
    prompt_file = tmp_path / "task_t1_prompt.md"
    assert prompt_file.exists()
    assert "Task: t1" in prompt_file.read_text()
    
    # Assert Popen called correctly
    mock_popen.assert_called_once()
    args, kwargs = mock_popen.call_args
    cmd = args[0]
    assert cmd[0] == "bash"
    assert cmd[1] == "dummy.sh"
    assert cmd[2] == "3"
    assert cmd[3] == str(prompt_file.absolute())
