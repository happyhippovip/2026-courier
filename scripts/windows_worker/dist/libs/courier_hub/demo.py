"""Run the Desktop Hub against a real local Courier: `python -m courier_hub.demo`.

Starts the real controller (courier_core.serve) and worker host
(courier_worker.host) on a fresh home, gives them three synthetic tasks and
lets the runtime produce real states — nothing is faked:

1. a normal task that finishes and is checked by Courier      -> Done, Checked by Courier
2. a non-idempotent task whose worker is killed mid-action     -> Needs you (BLOCKED)
3. a task that keeps running                                   -> Working

Then it starts the hub and prints its URL. Ctrl+C stops everything.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _spawn(args, home, log_name, new_group=False):
    env = dict(os.environ, COURIER_HOME=str(home),
               PYTHONPATH=os.pathsep.join([str(REPO), os.environ.get("PYTHONPATH", "")]))
    kwargs = {}
    if new_group:
        kwargs = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt"
                  else {"start_new_session": True})
    log = open(Path(home) / log_name, "ab")
    return subprocess.Popen([sys.executable, "-m", *args], cwd=str(REPO), env=env, stdout=subprocess.PIPE,
                            stderr=log, stdin=subprocess.DEVNULL, **kwargs)


def _api(base, token, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"X-Courier-Token": token, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read() or b"{}")


def _wait(what, check, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(0.3)
    raise SystemExit(f"demo: timed out waiting for {what}")


def _kill_tree(proc):
    if proc.poll() is not None:
        return
    if os.name == "nt":
        proc.kill()
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    proc.wait(10)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m courier_hub.demo")
    parser.add_argument("--home", help="empty directory to use (default: a new temp dir)")
    parser.add_argument("--hub-port", type=int, default=8780)
    args = parser.parse_args(argv)
    home = Path(args.home or tempfile.mkdtemp(prefix="courier-demo-"))
    home.mkdir(parents=True, exist_ok=True)
    procs = []
    try:
        controller = _spawn(["courier_core.serve", "--home", str(home), "--port", "0", "--print-port"],
                            home, "controller.log")
        procs.append(controller)
        port = int(controller.stdout.readline().strip())
        base = f"http://127.0.0.1:{port}"
        token = _wait("controller token", lambda: (home / "run" / "controller.token").exists()
                      and (home / "run" / "controller.token").read_text().strip(), 20)
        status = lambda tid: _api(base, token, "GET", f"/v1/tasks/{tid}")["status"]  # noqa: E731

        worker = _spawn(["courier_worker.host", "--home", str(home), "--controller", base, "--max-tasks", "1",
                         "--heartbeat", "2"], home, "worker-1.log", new_group=True)
        procs.append(worker)
        print("demo: 1/3 a normal task, checked by Courier ...", flush=True)
        done_id = _api(base, token, "POST", "/v1/tasks", {
            "adapter": "synthetic", "params": {"sleep_s": 1, "write": "out.txt", "content": "courier-demo"},
            "effect_class": "idempotent", "max_attempts": 3, "lease_ttl_s": 6})["task_id"]
        _wait("the first task to finish", lambda: status(done_id) == "COMPLETE", 60)

        print("demo: 2/3 a non-idempotent task whose worker dies mid-action ...", flush=True)
        blocked_id = _api(base, token, "POST", "/v1/tasks", {
            "adapter": "synthetic", "params": {"write": "sent.txt", "content": "message", "hang": True},
            "effect_class": "non_idempotent", "max_attempts": 3, "lease_ttl_s": 6})["task_id"]
        _wait("the action to start", lambda: status(blocked_id) == "RUNNING", 30)
        _kill_tree(worker)
        _wait("Courier to stop and ask", lambda: status(blocked_id) == "BLOCKED", 30)

        print("demo: 3/3 a long-running task ...", flush=True)
        worker = _spawn(["courier_worker.host", "--home", str(home), "--controller", base, "--max-tasks", "1",
                         "--heartbeat", "2"], home, "worker-2.log", new_group=True)
        procs.append(worker)
        working_id = _api(base, token, "POST", "/v1/tasks", {
            "adapter": "synthetic", "params": {"sleep_s": 600, "write": "report.txt", "content": "long"},
            "effect_class": "idempotent", "max_attempts": 3, "lease_ttl_s": 6, "timeout_s": 900})["task_id"]
        _wait("the long task to start", lambda: status(working_id) == "RUNNING", 30)

        hub = _spawn(["courier_hub", "--home", str(home), "--controller", base, "--port", str(args.hub_port),
                      "--print-url"], home, "hub.log")
        procs.append(hub)
        url = hub.stdout.readline().decode().strip()
        print(f"\nCourier Desktop Hub: {url}\nhome: {home}\nCtrl+C to stop.\n", flush=True)
        while all(p.poll() is None for p in (controller, hub)):
            time.sleep(1)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        for proc in reversed(procs):
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(10)
                except subprocess.TimeoutExpired:
                    _kill_tree(proc)


if __name__ == "__main__":
    sys.exit(main())
