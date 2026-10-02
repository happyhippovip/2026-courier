import sys
import re

cs_file = "scripts/windows_worker/launcher/CourierLauncher.cs"
with open(cs_file, "r") as f:
    cs_code = f.read()

def test_single_instance_mutex():
    assert "CreateMutex" in cs_code, "RED: L6 Launcher missing Single Instance Mutex"
    assert "ERROR_ALREADY_EXISTS" in cs_code, "RED: L6 Launcher not checking mutex error"
    assert "Environment.Exit(2)" in cs_code, "RED: F1: Mutex fail must not look like success (exit 2 for duplicate)"
    assert "Environment.Exit(1)" in cs_code and "mutex == IntPtr.Zero" in cs_code, "RED: F1: Mutex fail must fail closed"

def test_safe_local_app_data():
    assert "Environment.UserName" in cs_code and "SYSTEM" in cs_code, "RED: L6 Launcher missing SYSTEM safe app data check"
    assert "ProgramData" in cs_code, "RED: L6 Launcher not using ProgramData for SYSTEM"

def test_crash_backoff():
    # Look for some restart loop or backoff
    assert "Thread.Sleep(backoff)" in cs_code, "RED: L6 Launcher missing crash backoff sleep"

def test_start_failure_survives():
    assert "catch (Exception" in cs_code, "RED: F2: Start failure not caught"
    assert "failed to start" in cs_code, "RED: F2: Start failure doesn't log explicitly"

def test_backoff_resets_after_healthy_run():
    assert "healthyUptimeThreshold" in cs_code, "RED: F3: Backoff never resets"
    assert "backoff = initialBackoff" in cs_code, "RED: F3: Backoff does not reset to initial"

def test_job_assignment_fails_closed():
    assert "try { proc.Kill(); } catch { }" in cs_code, "RED: F4: Containment failure doesn't kill child"
    assert "Failed to assign process to Job Object (Containment failure)" in cs_code, "RED: F4: Containment failure doesn't throw or log fatally"

if __name__ == "__main__":
    test_single_instance_mutex()
    test_safe_local_app_data()
    test_crash_backoff()
    test_start_failure_survives()
    test_backoff_resets_after_healthy_run()
    test_job_assignment_fails_closed()
    print("All L6 Security rules passed.")
