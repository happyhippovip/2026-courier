with open("tests/test_stop_daemon_safety.py", "a") as f:
    import textwrap
    f.write(textwrap.dedent("""
def test_stop_daemon_kills_watchdog(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    (ROOT / "logs").mkdir(exist_ok=True)
    pid_file = ROOT / "logs" / "courier_watchdog.pid"
    
    # Start a dummy process with "courier_watchdog.py" in its arguments
    import sys
    dummy = subprocess.Popen([sys.executable, "-c", "import time, sys; sys.argv[0]='courier_watchdog.py'; time.sleep(10)"])
    try:
        pid_file.write_text(str(dummy.pid))
        out = subprocess.check_output(["bash", "scripts/stop_daemon.sh"], text=True)
        assert "Courier Watchdog stopped" in out
        assert not pid_file.exists()
        
        # Ensure it was actually terminated
        assert dummy.wait(timeout=2) != 0
    finally:
        if dummy.poll() is None:
            dummy.kill()
            dummy.wait()
        if pid_file.exists():
            pid_file.unlink()
"""))
