"""P9 hardening for courier_worker.service.main signal handling (tests only).

Pins the shutdown-signal wiring of the worker entry point without starting
any loop, thread, or network call: which signals get a handler, that the
handler flips the exact stop event handed to WorkerLoop.run, and that a
refused handler install never blocks startup. No behavior change.
"""

import signal
import threading

import pytest

from courier_worker import service

CANDIDATE_SIGNALS = ("SIGTERM", "SIGINT", "SIGBREAK")


def _present_signals():
    return [getattr(signal, name) for name in CANDIDATE_SIGNALS
            if getattr(signal, name, None) is not None]


def _run_main(monkeypatch, tmp_path, argv_extra=None, signal_side_effect=None):
    """Run service.main with a recorded signal installer and a stubbed loop."""
    installed = {}

    def _record(signum, handler):
        if signal_side_effect is not None:
            signal_side_effect(signum, handler)
        installed[signum] = handler
        return handler

    monkeypatch.setattr(signal, "signal", _record)
    captured = {}

    def _fake_run(self, stop=None):
        captured["stop"] = stop
        return 0

    monkeypatch.setattr(service.WorkerLoop, "run", _fake_run)
    argv = ["--controller", "http://127.0.0.1:9", "--home", str(tmp_path),
            "--worker-id", "w1"]
    argv.extend(argv_extra or [])
    result = service.main(argv)
    assert result == 0
    assert isinstance(captured.get("stop"), threading.Event)
    return installed, captured["stop"]


def test_main_installs_one_handler_per_available_signal(monkeypatch, tmp_path):
    present = _present_signals()
    assert present, "expected at least one shutdown signal on this platform"
    installed, stop = _run_main(monkeypatch, tmp_path)
    assert sorted(installed) == sorted(present)
    handlers = set(installed.values())
    assert len(handlers) == 1
    assert callable(next(iter(handlers)))
    assert stop.is_set() is False


def test_installed_handler_sets_the_loop_stop_event(monkeypatch, tmp_path):
    present = _present_signals()
    assert present, "expected at least one shutdown signal on this platform"
    installed, stop = _run_main(monkeypatch, tmp_path)
    signum = present[0]
    installed[signum](signum, None)
    assert stop.is_set() is True


@pytest.mark.parametrize("failure", [OSError("denied"), ValueError("bad handler")])
def test_refused_handler_install_never_blocks_startup(monkeypatch, tmp_path, failure):
    def _refuse(signum, handler):
        raise failure

    installed, stop = _run_main(monkeypatch, tmp_path, signal_side_effect=_refuse)
    assert installed == {}
    assert stop.is_set() is False


def test_partial_install_failure_still_starts_loop(monkeypatch, tmp_path):
    present = _present_signals()
    assert present, "expected at least one shutdown signal on this platform"

    def _refuse_first(signum, handler):
        if signum == present[0]:
            raise OSError("denied")

    installed, stop = _run_main(monkeypatch, tmp_path, signal_side_effect=_refuse_first)
    assert sorted(installed) == sorted(present[1:])
    assert stop.is_set() is False
