import os
import sys
import subprocess
import time
from pathlib import Path

import pytest

@pytest.mark.skipif(sys.platform != "win32", reason="Launcher tests are Windows only")
def test_launcher_log_rotation(tmp_path):
    repo_root = Path(__file__).parent.parent.parent
    launcher_cs = repo_root / "scripts" / "windows_worker" / "launcher" / "CourierLauncher.cs"
    
    csc_paths = [
        r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
        r"C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"
    ]
    csc_exe = next((p for p in csc_paths if os.path.exists(p)), None)
    if not csc_exe:
        pytest.skip("csc.exe not found on this Windows machine")
        
    out_exe = tmp_path / "CourierTest.exe"
    build = subprocess.run([csc_exe, "/target:winexe", f"/out:{out_exe}", str(launcher_cs)], capture_output=True, text=True)
    assert build.returncode == 0, f"Failed to compile CourierLauncher.cs: {build.stdout}\n{build.stderr}"
    
    # We set up a mock %LOCALAPPDATA%\Courier
    mock_appdata = tmp_path / "AppData" / "Local"
    courier_data = mock_appdata / "Courier"
    courier_data.mkdir(parents=True)
    
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(mock_appdata)
    env["PROGRAMDATA"] = str(tmp_path / "ProgramData")
    
    # Create fake python module courier_core.serve
    fake_python_lib = tmp_path / "fake_lib"
    fake_python_lib.mkdir()
    core_dir = fake_python_lib / "courier_core"
    core_dir.mkdir()
    (core_dir / "__init__.py").touch()
    
    # Serve will output slightly more than 5MB
    serve_py = core_dir / "serve.py"
    serve_py.write_text("""import sys
import time

chunk = "X" * 1024 * 1024  # 1MB
for i in range(6):
    print(chunk)
    sys.stdout.flush()
    time.sleep(0.1)

time.sleep(10)
""")
    env["PYTHONPATH"] = str(fake_python_lib) + os.pathsep + env.get("PYTHONPATH", "")
    
    # Put Courier.exe inside a mocked python env baseDir so it finds python.exe
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    
    py_dir = base_dir / "python"
    py_dir.mkdir()
    import shutil
    
    # We can just copy the current python executable so it works natively
    
    import glob
    py_dir_orig = Path(sys.executable).parent
    for f in glob.glob(str(py_dir_orig / "python*.dll")):
        shutil.copy(f, py_dir)
    shutil.copy(sys.executable, py_dir / "python.exe")

    
    exe_copy = base_dir / "CourierTest.exe"
    shutil.copy(out_exe, exe_copy)
    
    # Start the launcher
    p1 = subprocess.Popen([str(exe_copy)], env=env)
    
    try:
        # Wait until it outputs the logs and rolls over
        # It takes ~1 second for the python script to run
        for _ in range(30):
            time.sleep(0.5)
            # Check if rotation happened
            log_dir = courier_data / "logs"
            backup_log = log_dir / "controller.log.1"
            if backup_log.exists():
                break
        
        log_dir = courier_data / "logs"
        backup_log = log_dir / "controller.log.1"
        current_log = log_dir / "controller.log"
        
        assert backup_log.exists(), "Backup log controller.log.1 was not created"
        assert backup_log.stat().st_size >= 5 * 1024 * 1024, "Backup log is too small"
        
        # Current log might be small, but it should exist
        assert current_log.exists(), "Current log controller.log was not recreated"
        
    finally:
        # Cleanup
        p1.kill()
        p1.wait()

