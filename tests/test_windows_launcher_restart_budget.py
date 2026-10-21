"""The desktop launcher must stop restarting a component that keeps dying."""
from pathlib import Path

LAUNCHER = Path(__file__).resolve().parents[1] / "scripts" / "windows_worker" / "launcher" / "CourierLauncher.cs"


def test_launcher_records_its_pid_after_it_owns_the_instance():
    text = LAUNCHER.read_text(encoding="utf-8")
    assert "launcher.pid" in text
    assert "GetCurrentProcess()" in text
    owner = text.index("GetCurrentProcess()")
    second = text.index("if (!createdNew)")
    assert second < owner


def test_fast_exits_stop_the_restart_loop():
    text = LAUNCHER.read_text(encoding="utf-8")
    loop = text.split("while (true)", 1)[1].split("catch (Exception ex)", 1)[0]
    assert "repeated fast exits" in loop
    assert "ctrlFast > 3" in loop
    assert "workerFast > 3" in loop
    assert "hubFast > 3" in loop
    assert "MessageBox" not in loop
    assert "crash.txt" in loop
    assert "Environment.Exit" not in loop


def test_unhealthy_start_is_a_failed_process():
    text = LAUNCHER.read_text(encoding="utf-8")
    health = text.split("if (!healthOk)", 1)[1].split("while (true)", 1)[0]
    assert "Environment.Exit(1)" in health
    caught = text.split("catch (Exception ex)", 1)[1]
    assert "Environment.Exit(1)" in caught
