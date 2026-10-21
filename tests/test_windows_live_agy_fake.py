"""Live Windows run: install -AgyPath -> launcher -> worker -> fake agy -> verifier.

install.ps1 writes the absolute agy path into config.json, the launcher hands
it to the worker only, and a provider_exec agy task reaches COMPLETE through
the real controller, worker, adapter runner and verifier. The "agy" is a .cmd
wrapper around a local fake that prints the success envelope: no model, no
network, no cost. Runs only with COURIER_LIVE_INSTALL_TEST=1 (windows-build job).
"""
import json
import os
import shutil
import subprocess
import sys
import textwrap
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "scripts" / "windows_worker"
CONTROLLER_PORT = 8830
HUB_PORT = 8831

pytestmark = pytest.mark.skipif(
    sys.platform != "win32" or os.environ.get("COURIER_LIVE_INSTALL_TEST") != "1",
    reason="live agy fake test: Windows and COURIER_LIVE_INSTALL_TEST=1 only",
)


def _api(token, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(f"http://127.0.0.1:{CONTROLLER_PORT}{path}", data=data, method=method,
                                     headers={"X-Courier-Token": token, "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read() or b"{}")


def test_install_agy_path_reaches_the_worker_and_completes_a_fake_run(tmp_path):
    fake_dir = tmp_path / "agy"
    fake_dir.mkdir()
    marker = fake_dir / "launched.txt"
    (fake_dir / "fake_agy.py").write_text(textwrap.dedent(f"""\
        import json, pathlib, sys
        pathlib.Path({str(marker)!r}).write_text(" ".join(sys.argv[1:]))
        print(json.dumps({{"status": "SUCCESS", "response": "noop"}}))
        """), encoding="utf-8")
    agy_cmd = fake_dir / "agy.cmd"
    agy_cmd.write_text(f'@"{sys.executable}" "{fake_dir / "fake_agy.py"}" %*\r\n', encoding="ascii")

    package = tmp_path / "package"
    package.mkdir()
    for name in ("install.ps1", "uninstall.ps1", "stop.ps1", "stop.bat"):
        shutil.copy2(WORKER / name, package / name)
    (package / "launcher").mkdir()
    shutil.copy2(WORKER / "launcher" / "CourierLauncher.cs", package / "launcher" / "CourierLauncher.cs")
    install_dir = tmp_path / "Programs" / "Courier"
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.json").write_text(json.dumps({
        "COURIER_CONTROLLER_PORT": CONTROLLER_PORT, "COURIER_HUB_PORT": HUB_PORT,
    }), encoding="utf-8")
    task_name = "CourierAgyTest-" + uuid.uuid4().hex[:8]
    env = {k: v for k, v in os.environ.items() if k != "COURIER_PROVIDER_AGY_BIN"}
    env.update(COURIER_HOME=str(home), PYTHONPATH=str(ROOT))

    installed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(package / "install.ps1"),
         "-InstallDir", str(install_dir), "-CourierHome", str(home), "-TaskName", task_name,
         "-NoLaunch", "-NoAutoStart", "-AgyPath", str(agy_cmd)],
        capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL, timeout=120)
    assert installed.returncode == 0, installed.stdout + installed.stderr
    config = json.loads((home / "config.json").read_text(encoding="utf-8-sig"))
    assert Path(config["COURIER_PROVIDER_AGY_BIN"]) == agy_cmd

    launcher = subprocess.Popen([str(install_dir / "Courier.exe")], cwd=str(install_dir), env=env)
    try:
        token_path = home / "run" / "controller.token"
        deadline = time.monotonic() + 60
        token = None
        while time.monotonic() < deadline and token is None:
            assert launcher.poll() is None
            if token_path.exists():
                try:
                    _api(token_path.read_text().strip(), "GET", "/v1/health")
                    token = token_path.read_text().strip()
                except Exception:
                    pass
            time.sleep(0.5)
        assert token, "controller never became healthy"
        task_id = _api(token, "POST", "/v1/tasks", {
            "adapter": "provider_exec", "params": {"provider": "agy", "prompt": "noop"},
            "effect_class": "idempotent", "max_attempts": 1, "lease_ttl_s": 60,
        })["task_id"]
        deadline = time.monotonic() + 90
        view = {}
        while time.monotonic() < deadline:
            view = _api(token, "GET", f"/v1/tasks/{task_id}")
            if view.get("status") in ("COMPLETE", "FAILED", "BLOCKED", "CANCELLED"):
                break
            time.sleep(0.5)
        logs = "\n".join(p.read_text(errors="replace")[-1500:] for p in (home / "logs").glob("*.log"))
        assert view.get("status") == "COMPLETE", f"{view}\n{logs}"
        assert view.get("accepted_result_id")
        launched = marker.read_text()
        assert "--dangerously-skip-permissions" not in launched and "--yolo" not in launched
    finally:
        subprocess.run(["cmd.exe", "/c", str(install_dir / "stop.bat")], env=env, timeout=60, check=False)
        if launcher.poll() is None:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(launcher.pid)], check=False)
