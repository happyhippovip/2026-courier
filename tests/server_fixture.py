"""
server_fixture.py - Autonomous Ephemeral Test Server Fixture for Courier
Provides zero-configuration, fail-safe HTTP test environments:
- Checks if a live studio server is already responding on port 8088.
- If not running, spawns an isolated ephemeral server.js instance on an OS-assigned port.
- Tears down the instance cleanly after test execution.
- Completely prevents ConnectionRefusedError across all test runners.
"""

import os
import sys
import time
import shutil
import tempfile
import subprocess
import urllib.request
import urllib.error
import unittest

WORKSPACE_ROOT = r"C:\Users\lol\2026-workspace"
PROJECT_MEMORY_DIR = os.path.join(WORKSPACE_ROOT, "project-memory")
CUA_NODE_EXE = r"C:\Users\lol\AppData\Local\OpenAI\Codex\runtimes\cua_node\b58ca2eaa616c2da\bin\node.exe"
NODE_CMD = CUA_NODE_EXE if os.path.exists(CUA_NODE_EXE) else (shutil.which("node") or "node")

def is_server_responding(url: str, timeout: float = 0.5) -> bool:
    """Checks if an HTTP server is responding to ping."""
    try:
        req = urllib.request.Request(f"{url}/api/courier/ping", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False

def launch_ephemeral_server():
    """Spawns an ephemeral instance of studio/server.js on an OS-assigned free port."""
    server_js_path = os.path.join(PROJECT_MEMORY_DIR, "studio", "server.js").replace("\\", "/")
    runner_content = f"""
const {{ server }} = require('{server_js_path}');
server.listen(0, '127.0.0.1', () => {{
  const port = server.address().port;
  console.log('SERVER_READY:' + port);
}});
"""
    fd, runner_file = tempfile.mkstemp(prefix="courier_test_server_", suffix=".js")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(runner_content)

    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        [NODE_CMD, runner_file],
        cwd=PROJECT_MEMORY_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags
    )

    port = None
    start_time = time.time()
    while time.time() - start_time < 15:
        line = proc.stdout.readline()
        if "SERVER_READY:" in line:
            port = int(line.strip().split("SERVER_READY:")[1])
            break
        time.sleep(0.05)

    if not port:
        proc.kill()
        if os.path.exists(runner_file):
            os.remove(runner_file)
        raise RuntimeError("Failed to start ephemeral studio/server.js test instance")

    base_url = f"http://127.0.0.1:{port}"
    return base_url, proc, runner_file

def get_or_launch_test_server(preferred_port: int = 8088):
    """Returns base_url and cleanup tuple (proc, runner_file). If live server exists, proc is None."""
    default_url = f"http://127.0.0.1:{preferred_port}"
    if is_server_responding(default_url):
        return default_url, None, None
    return launch_ephemeral_server()

class CourierServerTestCase(unittest.TestCase):
    """Base TestCase providing an ephemeral or existing studio server instance."""
    base_url = None
    _server_proc = None
    _runner_file = None

    @classmethod
    def setUpClass(cls):
        cls.base_url, cls._server_proc, cls._runner_file = get_or_launch_test_server()

    @classmethod
    def tearDownClass(cls):
        if cls._server_proc:
            try:
                if sys.platform == "win32":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(cls._server_proc.pid)],
                        capture_output=True,
                        check=False
                    )
                else:
                    cls._server_proc.terminate()
            except Exception:
                pass
            try:
                cls._server_proc.wait(timeout=2)
            except Exception:
                pass
        if cls._runner_file and os.path.exists(cls._runner_file):
            try:
                os.remove(cls._runner_file)
            except Exception:
                pass
