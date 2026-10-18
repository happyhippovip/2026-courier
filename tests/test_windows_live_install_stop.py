"""Live Windows run: install without questions, start, stop by PID, uninstall.

Builds the launcher from source, installs it with install.ps1 into temporary
folders under a unique task name, starts it, and stops it with stop.bat while
a second, unrelated program called Courier.exe runs. stop.bat must end the
launcher and all of its children and leave the other program running.
uninstall.ps1 must remove the program, the task, the configuration and run\\,
and keep the database and the logs.

It registers a real logon task, so it runs only when
COURIER_LIVE_INSTALL_TEST=1 (the windows-build CI job sets it).
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "scripts" / "windows_worker"
CSC = [
    r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
    r"C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe",
]
CONTROLLER_PORT = 8820
HUB_PORT = 8821

pytestmark = pytest.mark.skipif(
    sys.platform != "win32" or os.environ.get("COURIER_LIVE_INSTALL_TEST") != "1",
    reason="live install test: Windows and COURIER_LIVE_INSTALL_TEST=1 only",
)


def _csc():
    for path in CSC:
        if os.path.exists(path):
            return path
    pytest.fail("csc.exe not found")


def _compile(source, out, *references):
    refs = [f"/reference:{name}" for name in references]
    build = subprocess.run([_csc(), "/nologo", "/target:winexe", *refs, f"/out:{out}", str(source)],
                           capture_output=True, text=True)
    assert build.returncode == 0, build.stdout + build.stderr


def _powershell(script, *args, env=None):
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *args],
        capture_output=True, text=True, env=env, timeout=120,
    )


def _task_exists(name):
    probe = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command",
         f"if (Get-ScheduledTask -TaskName '{name}' -ErrorAction SilentlyContinue) {{ "
         f"(Get-ScheduledTask -TaskName '{name}').Principal | ConvertTo-Json }} else {{ 'NONE' }}"],
        capture_output=True, text=True, timeout=60,
    )
    out = probe.stdout.strip()
    return None if out == "NONE" else json.loads(out)


def _healthy(token):
    request = urllib.request.Request(f"http://127.0.0.1:{CONTROLLER_PORT}/v1/health",
                                     headers={"X-Courier-Token": token})
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def test_install_start_stop_by_pid_and_uninstall(tmp_path):
    import psutil

    package = tmp_path / "package"
    package.mkdir()
    for name in ("install.ps1", "uninstall.ps1", "stop.ps1", "stop.bat", "start.bat"):
        shutil.copy2(WORKER / name, package / name)
    _compile(WORKER / "launcher" / "CourierLauncher.cs", package / "Courier.exe",
             "System.Windows.Forms.dll", "System.Drawing.dll")

    install_dir = tmp_path / "Programs" / "Courier"
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.json").write_text(json.dumps({
        "COURIER_CONTROLLER_PORT": CONTROLLER_PORT, "COURIER_HUB_PORT": HUB_PORT,
    }), encoding="utf-8")
    task = "CourierLiveTest-" + uuid.uuid4().hex[:8]
    env = dict(os.environ, COURIER_HOME=str(home), PYTHONPATH=str(ROOT))

    decoy = None
    launcher = None
    try:
        # 1. Install: no prompt (stdin closed), no SYSTEM, no token written.
        installed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(package / "install.ps1"),
             "-InstallDir", str(install_dir), "-CourierHome", str(home), "-TaskName", task, "-NoLaunch"],
            capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL, timeout=120,
        )
        assert installed.returncode == 0, installed.stdout + installed.stderr
        assert (install_dir / "Courier.exe").is_file()
        config = json.loads((home / "config.json").read_text(encoding="utf-8-sig"))
        assert config["COURIER_CONTROLLER_PORT"] == CONTROLLER_PORT
        assert config["COURIER_WORKER_ID"].startswith("WIN-")
        assert not (home / "run" / "controller.token").exists()
        principal = _task_exists(task)
        assert principal is not None, "logon task was not registered"
        assert principal["UserId"].upper() != "SYSTEM"
        assert principal["RunLevel"] in (0, "Limited")

        # 2. Start the installed launcher and wait until the controller answers.
        launcher = subprocess.Popen([str(install_dir / "Courier.exe")], cwd=str(install_dir), env=env)
        token_path = home / "run" / "controller.token"
        pid_path = home / "run" / "launcher.pid"
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            assert launcher.poll() is None, f"launcher exited with {launcher.returncode}"
            if token_path.exists() and pid_path.exists() and _healthy(token_path.read_text().strip()):
                break
            time.sleep(0.5)
        else:
            logs = "\n".join(p.read_text(errors="replace")[-2000:] for p in (home / "logs").glob("*.log"))
            pytest.fail("controller never became healthy\n" + logs)
        assert int(pid_path.read_text().strip()) == launcher.pid
        time.sleep(3)  # worker and hub start after the controller is healthy
        # Courier's tree: launcher, its python/console children and their
        # descendants. The browser it opens for the hub is the user's.
        root = psutil.Process(launcher.pid)
        components = [c for c in root.children() if c.name().lower() in ("python.exe", "pythonw.exe", "conhost.exe")]
        tree = [root] + components + [d for c in components for d in c.children(recursive=True)]
        owned = {p.pid: (p.create_time(), p.name(), " ".join(p.cmdline())[:160]) for p in tree}
        assert len(owned) >= 4, owned  # launcher + controller + worker + hub

        # 3. An unrelated program with the same image name.
        decoy_dir = tmp_path / "decoy"
        decoy_dir.mkdir()
        decoy_src = decoy_dir / "Decoy.cs"
        decoy_src.write_text("class P { static void Main() { System.Threading.Thread.Sleep(300000); } }",
                             encoding="utf-8")
        _compile(decoy_src, decoy_dir / "Courier.exe")
        decoy = subprocess.Popen([str(decoy_dir / "Courier.exe")])

        # 4. stop.bat ends exactly the owned tree.
        stopped = subprocess.run(["cmd.exe", "/c", str(install_dir / "stop.bat")],
                                 capture_output=True, text=True, env=env, timeout=60)
        assert stopped.returncode == 0, stopped.stdout + stopped.stderr
        launcher.wait(timeout=15)

        def still_running(pid, created):
            # Windows reuses PIDs quickly: the same PID with another start
            # time is a different process.
            try:
                return psutil.Process(pid).create_time() == created
            except psutil.NoSuchProcess:
                return False

        survivors = {pid: info for pid, info in owned.items() if still_running(pid, info[0])}
        assert survivors == {}, f"survivors={survivors}\nstop.bat output:\n{stopped.stdout}{stopped.stderr}"
        assert decoy.poll() is None, "stop.bat killed an unrelated Courier.exe"
        assert not pid_path.exists()
        assert not _healthy(token_path.read_text().strip())

        # 5. Uninstall removes program, task, config and run\, keeps data.
        removed = _powershell(install_dir / "uninstall.ps1", "-InstallDir", str(install_dir),
                              "-CourierHome", str(home), "-TaskName", task, env=env)
        assert removed.returncode == 0, removed.stdout + removed.stderr
        assert not install_dir.exists()
        assert _task_exists(task) is None
        assert not (home / "config.json").exists()
        assert not (home / "run").exists()
        assert (home / "logs").is_dir()
        assert any(home.glob("*.db")), list(home.iterdir())
        assert decoy.poll() is None
    finally:
        if launcher is not None and launcher.poll() is None:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(launcher.pid)], check=False)
        if decoy is not None and decoy.poll() is None:
            decoy.kill()
        if _task_exists(task) is not None:
            subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                            f"Unregister-ScheduledTask -TaskName '{task}' -Confirm:$false"], check=False)
