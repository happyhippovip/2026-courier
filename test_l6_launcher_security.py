import sys

cs_file = "scripts/windows_worker/launcher/CourierLauncher.cs"
with open(cs_file, "r") as f:
    cs_code = f.read()

def test_single_instance_mutex():
    assert "CreateMutex" in cs_code, "RED: L6 Launcher missing Single Instance Mutex"
    assert "ERROR_ALREADY_EXISTS" in cs_code, "RED: L6 Launcher not checking mutex error"

def test_safe_local_app_data():
    assert "Environment.UserName" in cs_code and "SYSTEM" in cs_code, "RED: L6 Launcher missing SYSTEM safe app data check"
    assert "ProgramData" in cs_code, "RED: L6 Launcher not using ProgramData for SYSTEM"

def test_crash_backoff():
    # Look for some restart loop or backoff
    assert "Thread.Sleep" in cs_code and ("backoff" in cs_code.lower() or "Math.Min" in cs_code), "RED: L6 Launcher missing crash backoff"
