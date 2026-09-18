from scripts import courier_github_dispatcher as dispatcher


class FinishedProcess:
    def __init__(self, returncode):
        self.returncode = returncode

    def poll(self):
        return self.returncode


def test_waiting_adapter_is_reentered_without_second_claim(monkeypatch):
    replacement = FinishedProcess(None)
    launched = []
    monkeypatch.setattr(
        dispatcher,
        "launch_adapter",
        lambda task_file: launched.append(task_file) or replacement,
    )
    active = {
        "task-1": {
            "process": FinishedProcess(dispatcher.WAITING_EXIT_CODE),
            "task_file": "/tmp/task-1.json",
        }
    }

    dispatcher.reap_adapters(active)

    assert launched == ["/tmp/task-1.json"]
    assert active["task-1"]["process"] is replacement


def test_terminal_adapter_is_reaped_without_restart(monkeypatch):
    monkeypatch.setattr(
        dispatcher,
        "launch_adapter",
        lambda _: (_ for _ in ()).throw(AssertionError("must not restart terminal adapter")),
    )
    active = {
        "task-1": {
            "process": FinishedProcess(0),
            "task_file": "/tmp/task-1.json",
        }
    }

    dispatcher.reap_adapters(active)

    assert active == {}


def test_failed_adapter_is_reaped_fail_closed_without_retry_storm(monkeypatch):
    monkeypatch.setattr(
        dispatcher,
        "launch_adapter",
        lambda _: (_ for _ in ()).throw(AssertionError("must not retry fatal adapter")),
    )
    active = {
        "task-1": {
            "process": FinishedProcess(1),
            "task_file": "/tmp/task-1.json",
        }
    }

    dispatcher.reap_adapters(active)

    assert active == {}
