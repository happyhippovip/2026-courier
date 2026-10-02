from courier_core.state_machine import TaskStatus

def test_r01_automation_lifecycle():
    assert TaskStatus.QUEUED.value == "QUEUED"
