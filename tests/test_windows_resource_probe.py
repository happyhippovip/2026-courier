"""A failed Windows CPU probe pauses claims. It is not treated as idle."""
import ctypes

import pytest

from tests.test_windows_worker_contract import StopLoop, load_daemon


def test_host_without_windows_api_is_not_a_failed_probe(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    if hasattr(ctypes, "windll"):
        pytest.skip("this host has the Windows API")
    assert daemon.read_cpu_load_percent() == 0.0
    assert daemon.is_resource_pressure_high() is False


def test_probe_failure_is_unknown(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)

    class Kernel:
        @staticmethod
        def GetSystemTimes(*_args):
            raise OSError("probe failed")

    class Windll:
        kernel32 = Kernel()

    monkeypatch.setattr(ctypes, "windll", Windll(), raising=False)
    assert daemon.read_cpu_load_percent() is None
    assert daemon.is_resource_pressure_high() is None


def test_high_load_pauses_and_a_quiet_sample_does_not(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    samples = iter((
        (100, 50, 50),    # baseline
        (100, 100, 100),  # 100% busy
        (200, 150, 150),  # idle rose with the clock
    ))

    def GetSystemTimes(idle_p, kernel_p, user_p):
        idle, kernel, user = next(samples)
        idle_p._obj.dwLowDateTime = idle
        kernel_p._obj.dwLowDateTime = kernel
        user_p._obj.dwLowDateTime = user
        idle_p._obj.dwHighDateTime = 0
        kernel_p._obj.dwHighDateTime = 0
        user_p._obj.dwHighDateTime = 0

    class Kernel:
        pass

    Kernel.GetSystemTimes = staticmethod(GetSystemTimes)

    class Windll:
        kernel32 = Kernel()

    monkeypatch.setattr(ctypes, "windll", Windll(), raising=False)
    assert daemon.read_cpu_load_percent() is None
    assert daemon.is_resource_pressure_high() is True
    assert daemon.is_resource_pressure_high() is False


def _windows_times(samples):
    sequence = iter(samples)

    def GetSystemTimes(idle_p, kernel_p, user_p):
        idle, kernel, user = next(sequence)
        idle_p._obj.dwLowDateTime = idle
        kernel_p._obj.dwLowDateTime = kernel
        user_p._obj.dwLowDateTime = user
        idle_p._obj.dwHighDateTime = 0
        kernel_p._obj.dwHighDateTime = 0
        user_p._obj.dwHighDateTime = 0

    class Kernel:
        pass

    Kernel.GetSystemTimes = staticmethod(GetSystemTimes)

    class Windll:
        kernel32 = Kernel()

    return Windll()


def test_first_windows_sample_does_not_claim(tmp_path, monkeypatch):
    """One unread sample is not proof the host is idle."""
    daemon = load_daemon(tmp_path, monkeypatch)
    daemon._last_sys_times = None
    monkeypatch.setattr(ctypes, "windll", _windows_times(((100, 50, 50),)), raising=False)
    calls = []

    def urlopen(req, data=None, timeout=None):
        calls.append(req.full_url)
        return object()

    messages = []

    def stop(_seconds):
        raise StopLoop()

    def capture(*args, **_kwargs):
        messages.append(" ".join(str(arg) for arg in args))

    monkeypatch.setattr(daemon.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(daemon.time, "sleep", stop)
    monkeypatch.setattr("builtins.print", capture)
    with pytest.raises(StopLoop):
        daemon.loop()
    assert not any(url.endswith("/tasks/claim") for url in calls)
    assert any("Resource check failed. Pausing claims." in line for line in messages)


def test_unknown_pressure_does_not_claim(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    calls = []

    def urlopen(req, data=None, timeout=None):
        calls.append(req.full_url)
        return object()

    def stop(_seconds):
        raise StopLoop()

    messages = []

    def capture(*args, **_kwargs):
        messages.append(" ".join(str(arg) for arg in args))

    monkeypatch.setattr(daemon, "read_cpu_load_percent", lambda: None)
    monkeypatch.setattr(daemon.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(daemon.time, "sleep", stop)
    monkeypatch.setattr("builtins.print", capture)
    with pytest.raises(StopLoop):
        daemon.loop()
    assert not any(url.endswith("/tasks/claim") for url in calls)
    assert any("Resource check failed. Pausing claims." in line for line in messages)
