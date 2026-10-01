import errno

from scripts.run_longrun_watchdog import _idle_backoff, _is_resource_pressure


def test_idle_backoff_doubles_and_caps():
    assert _idle_backoff(300, 1800, 1) == 300
    assert _idle_backoff(300, 1800, 2) == 600
    assert _idle_backoff(300, 1800, 3) == 1200
    assert _idle_backoff(300, 1800, 4) == 1800
    assert _idle_backoff(300, 1800, 8) == 1800


def test_resource_pressure_detects_errno_and_text():
    assert _is_resource_pressure(OSError(errno.EMFILE, "Too many open files"))
    assert _is_resource_pressure(OSError(errno.ENFILE, "File table overflow"))
    assert _is_resource_pressure(RuntimeError("EMFILE while opening checkpoint"))
    assert not _is_resource_pressure(RuntimeError("ordinary test failure"))
