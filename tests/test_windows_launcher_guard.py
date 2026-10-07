import os
import sys
import subprocess
import time
from pathlib import Path

import pytest

@pytest.mark.skipif(sys.platform != "win32", reason="Launcher guard tests are Windows only")
def test_launcher_single_instance_guard(tmp_path):
    repo_root = Path(__file__).parent.parent
    launcher_cs = repo_root / "scripts" / "windows_worker" / "launcher" / "CourierLauncher.cs"
    
    # Check if we have csc.exe available to compile a test copy
    # On GitHub Actions windows-latest, csc is usually in PATH, but if not we can use MSBuild or find it
    # For a simple script, trying a few standard paths:
    csc_paths = [
        r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
        r"C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"
    ]
    csc_exe = None
    for p in csc_paths:
        if os.path.exists(p):
            csc_exe = p
            break
            
    if not csc_exe:
        pytest.skip("csc.exe not found on this Windows machine")
        
    out_exe = tmp_path / "CourierTest.exe"
    build = subprocess.run([csc_exe, "/target:winexe", f"/out:{out_exe}", str(launcher_cs)], capture_output=True, text=True)
    assert build.returncode == 0, f"Failed to compile CourierLauncher.cs: {build.stdout}\n{build.stderr}"
    
    # We set up a mock %LOCALAPPDATA%\Courier so the launcher doesn't pollute the real one
    mock_appdata = tmp_path / "AppData" / "Local"
    mock_appdata.mkdir(parents=True)
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(tmp_path / "AppData" / "Local")
    env["PROGRAMDATA"] = str(tmp_path / "ProgramData")
    
    # Start the first instance
    p1 = subprocess.Popen([str(out_exe)], env=env)
    
    try:
        # Give it a moment to acquire the mutex
        time.sleep(1.0)
        
        # Start the second instance
        # Because of the Mutex, the second instance should detect the first instance is running
        # It will try to open a browser (Process.Start with URL) and then exit immediately (return).
        # We can just verify it exits quickly with 0.
        t0 = time.time()
        p2 = subprocess.run([str(out_exe)], env=env, timeout=5)
        t1 = time.time()
        
        assert p2.returncode == 0, "Second instance should exit cleanly"
        assert (t1 - t0) < 3.0, "Second instance should exit immediately without starting a new loop"
        
        # Ensure the first instance is still running
        assert p1.poll() is None, "First instance should still be running"
        
    finally:
        # Cleanup
        p1.kill()
        p1.wait()

