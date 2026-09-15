import pytest
from unittest.mock import patch, MagicMock
from courier_admission_control import TaskPacket
from courier_router import WorkerTarget
from courier_github_dispatcher import GitHubExternalDispatcher

@patch("subprocess.run")
def test_github_dispatch_success(mock_run):
    # Setup mock
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_run.return_value = mock_result
    
    packet = TaskPacket(
        goal_id="g1", task_id="t1", attempt_id=1, dependencies=["dep1"],
        required_platform="linux", required_capability="github", logical_scope="A",
        writer_required=True, budget=5.0, result_contract="none", human_gate_class="NONE"
    )
    target = WorkerTarget("github_runner", "linux", ["github"], 0.5, 0, 10)
    
    dispatcher = GitHubExternalDispatcher()
    dispatch_id = dispatcher.dispatch(packet, target, "test-branch")
    
    assert dispatch_id == "github-actions-dispatch-t1-1"
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "gh" in args
    assert "workflow" in args
    assert "run" in args
    assert "--ref" in args
    assert "test-branch" in args
