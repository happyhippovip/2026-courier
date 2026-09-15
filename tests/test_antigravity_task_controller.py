import pytest
from scripts.antigravity_task_controller import AntigravityTaskController

def test_is_available():
    controller = AntigravityTaskController()
    assert controller.is_available() is False

def test_cancel_unavailable():
    controller = AntigravityTaskController()
    with pytest.raises(RuntimeError, match="Antigravity cancellation API is not available."):
        controller.cancel("task-123")

def test_get_state_unavailable():
    controller = AntigravityTaskController()
    with pytest.raises(RuntimeError, match="Antigravity cancellation API is not available."):
        controller.get_state("task-123")

def test_list_owned_unavailable():
    controller = AntigravityTaskController()
    with pytest.raises(RuntimeError, match="Antigravity cancellation API is not available."):
        controller.list_owned("attempt-123")
