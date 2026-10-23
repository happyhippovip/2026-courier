"""A failed mission-chip step must not be labeled PASS."""

from courier_hub.mission_chip import run_mission_chip


class _ClosedController:
    def __init__(self, home, verifier=None):
        self.db_path = type("PathName", (), {"name": "courier.db"})()

    def boot(self):
        return self

    def create_task(self, body):
        return 409, {"task_id": "task-closed", "duplicate": False}

    def claim(self, body):
        return {"dispatch_id": "dsp-closed"}

    def start(self, body):
        return None

    def result(self, body):
        return 409, {}

    def drain(self):
        return None

    def task_view(self, task_id):
        return {
            "status": "FAILED",
            "resolution": "rejected",
            "accepted_result_id": None,
        }

    def stop(self):
        return None

    class journal:
        @staticmethod
        def events():
            return []


def test_chip_status_is_not_pass_when_the_step_failed(tmp_path, monkeypatch):
    monkeypatch.setattr("courier_hub.mission_chip.Controller", _ClosedController)
    result = run_mission_chip(tmp_path)
    step_1 = result["checks"][0]
    step_2 = result["checks"][1]
    assert (
        step_1["status"],
        step_1["passed"],
        step_2["status"],
        step_2["passed"],
        result["overall_status"],
    ) == ("FAIL", False, "FAIL", False, "FAILED")
