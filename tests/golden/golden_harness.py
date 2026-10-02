"""Golden harness helpers (L1-owned): real Courier processes driven through the v1 contract.

See tests/golden/README.md. Imported by tests/golden/conftest.py and the golden tests.
"""

import contextlib
import hashlib
import importlib
import importlib.util
import os
import signal
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import psutil
import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = Path(__file__).resolve().parent
REQUIRED_MODULES = (
    "courier_core.serve",
    "courier_core.journal",
    "courier_core.projection",
    "courier_worker.host",
    "adapters.synthetic",
)
GOLDEN_CONTENT = "courier-golden"
GOLDEN_SHA256 = hashlib.sha256(GOLDEN_CONTENT.encode("utf-8")).hexdigest()


def missing_modules():
    missing = []
    for name in REQUIRED_MODULES:
        try:
            if importlib.util.find_spec(name) is None:
                missing.append(name)
        except (ImportError, ValueError):
            missing.append(name)
    return missing


def wait_until(predicate, timeout, what, interval=0.2):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval)
    print(f"\nDEBUG TIMEOUT: what={what!r}, last={last!r}")
    raise AssertionError(f"timed out after {timeout}s waiting for {what}; last={last!r}")


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def pids_alive(pids):
    alive = []
    for pid in pids:
        try:
            proc = psutil.Process(pid)
            if proc.status() != psutil.STATUS_ZOMBIE:
                alive.append(pid)
        except psutil.NoSuchProcess:
            continue
    return alive


def descendants(pid):
    try:
        return [child.pid for child in psutil.Process(pid).children(recursive=True)]
    except psutil.NoSuchProcess:
        return []


def open_handles(pid):
    proc = psutil.Process(pid)
    return proc.num_handles() if os.name == "nt" else proc.num_fds()


def synthetic_params(**overrides):
    params = {
        "sleep_s": 1,
        "write": "out.txt",
        "content": GOLDEN_CONTENT,
        "crash_after_s": None,
        "hang": False,
        "fail_transient_n": 0,
        "fault_attempts": [1],
    }
    params.update(overrides)
    return params


class Api:
    def __init__(self, base_url, token):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers["X-Courier-Token"] = token

    def get(self, path, **kwargs):
        kwargs.setdefault("timeout", 10)
        return self.session.get(self.base_url + path, **kwargs)

    def post(self, path, json_body=None, **kwargs):
        kwargs.setdefault("timeout", 10)
        return self.session.post(self.base_url + path, json=json_body, **kwargs)


class Courier:
    """One isolated Courier installation (COURIER_HOME) with real processes."""

    def __init__(self, home, logs):
        self.home = home
        self.logs = logs
        self.port = free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.controller = None
        self.workers = []
        self.tracked_pids = set()
        self._log_handles = []
        self.api = None

    # -- environment and processes ------------------------------------------
    def env(self):
        env = dict(os.environ)
        env["COURIER_HOME"] = str(self.home)
        parts = [str(REPO_ROOT)] + [p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p]
        env["PYTHONPATH"] = os.pathsep.join(parts)
        return env

    def _spawn(self, args, log_name, new_group=False):
        log = open(self.logs / log_name, "ab")
        self._log_handles.append(log)
        kwargs = {}
        if new_group:
            if os.name == "nt":
                kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                kwargs["start_new_session"] = True
        proc = subprocess.Popen(
            [sys.executable, "-m", *args],
            cwd=str(REPO_ROOT), env=self.env(),
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, **kwargs)
        self.tracked_pids.add(proc.pid)
        return proc

    def start_controller(self, timeout=30):
        self.controller = self._spawn(
            ["courier_core.serve", "--home", str(self.home), "--port", str(self.port), "--print-port"],
            "controller.log")
        token_file = self.home / "run" / "controller.token"

        def ready():
            if self.controller.poll() is not None:
                raise AssertionError(f"controller exited early: {self.controller.returncode}\n{self.log_tail('controller.log')}")
            if not token_file.exists():
                return False
            try:
                api = Api(self.base_url, token_file.read_text(encoding="utf-8").strip())
                return api if api.get("/v1/health", timeout=2).status_code == 200 else False
            except requests.RequestException:
                return False

        self.api = wait_until(ready, timeout, "controller /v1/health")
        return self.api

    def start_worker(self):
        worker = self._spawn(
            ["courier_worker.host", "--home", str(self.home), "--controller", self.base_url,
             "--max-tasks", "1", "--heartbeat", "2"],
            f"worker-{len(self.workers)}.log", new_group=True)
        self.workers.append(worker)
        return worker

    @property
    def worker(self):
        return self.workers[-1]

    def stop_controller_graceful(self, timeout=10):
        with contextlib.suppress(requests.RequestException):
            self.api.post("/v1/shutdown", timeout=5)
        self.controller.wait(timeout=timeout)

    def kill_controller(self):
        self.controller.kill()
        self.controller.wait(timeout=10)

    def stop_worker_graceful(self, worker=None, timeout=10):
        worker = worker or self.worker
        if os.name == "nt":
            os.kill(worker.pid, signal.CTRL_BREAK_EVENT)
        else:
            worker.send_signal(signal.SIGTERM)
        worker.wait(timeout=timeout)

    def kill_worker(self, worker=None):
        worker = worker or self.worker
        self.tracked_pids.update(descendants(worker.pid))
        worker.kill()
        worker.wait(timeout=10)

    def settled_descendants(self, worker=None, settle_s=1.0, timeout=10):
        """Descendants that exist before any task runs, once the set stops changing.

        A Windows venv python.exe is a launcher with one child interpreter; a
        POSIX python has no child at all. Both are valid baselines, so an empty
        set is returned as-is instead of being waited for.
        """
        worker = worker or self.worker
        deadline = time.monotonic() + timeout
        last, since = None, time.monotonic()
        while time.monotonic() < deadline:
            current = set(self.worker_descendants(worker))
            if current != last:
                last, since = current, time.monotonic()
            elif time.monotonic() - since >= settle_s:
                break
            time.sleep(0.2)
        return last or set()

    def worker_descendants(self, worker=None):
        worker = worker or self.worker
        pids = descendants(worker.pid)
        self.tracked_pids.update(pids)
        return pids

    # -- journal (read-only; the controller is the only writer) -------------
    @property
    def db_path(self):
        return self.home / "courier.db"

    def _ro(self, path=None):
        uri = Path(path or self.db_path).resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    def all_events(self):
        if not self.db_path.exists():
            return []
        with contextlib.closing(self._ro()) as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM events ORDER BY seq")]

    def task_events(self, task_id):
        return [event for event in self.all_events() if event["task_id"] == task_id]

    def task_types(self, task_id):
        return [event["type"] for event in self.task_events(task_id) if event["type"] != "TASK_PROGRESS"]

    def wait_event(self, task_id, event_type, timeout=60, count=1):
        return wait_until(
            lambda: [e for e in self.task_events(task_id) if e["type"] == event_type][count - 1:] or None,
            timeout, f"{event_type} x{count} for {task_id}")[0]

    def head_seq(self):
        events = self.all_events()
        return events[-1]["seq"] if events else 0

    def copy_db(self, dest):
        with contextlib.closing(self._ro()) as src, contextlib.closing(sqlite3.connect(str(dest))) as dst:
            src.backup(dst)
        return dest

    def projection_hash(self, path=None):
        projection = importlib.import_module("courier_core.projection")
        with contextlib.closing(self._ro(path)) as conn:
            return projection.projection_hash(conn)

    def verify_and_rebuild(self, workdir):
        """Verify the hash chain and rebuild projections on a COPY of the journal."""
        journal_mod = importlib.import_module("courier_core.journal")
        projection = importlib.import_module("courier_core.projection")
        copy = self.copy_db(workdir / "copy.db")
        rebuilt = workdir / "rebuilt.db"
        journal = journal_mod.Journal(copy)
        journal.open()
        try:
            report = journal.verify_chain()
            projection.rebuild(journal, rebuilt)
        finally:
            close = getattr(journal, "close", None)
            if close is not None:
                close()
        return report, self.projection_hash(copy), self.projection_hash(rebuilt)

    def read_sse_seqs(self, until_seq, timeout=20):
        seqs = []
        deadline = time.monotonic() + timeout
        with self.api.session.get(self.base_url + "/v1/events", headers={"Last-Event-ID": "0"},
                                  stream=True, timeout=(5, 5)) as response:
            assert response.status_code == 200, response.text
            try:
                for raw in response.iter_lines(decode_unicode=True):
                    if raw and raw.startswith("id:"):
                        seqs.append(int(raw.split(":", 1)[1].strip()))
                        if seqs[-1] >= until_seq:
                            break
                    if time.monotonic() > deadline:
                        break
            except requests.exceptions.ConnectionError:
                pass
        return seqs

    def outbox_files(self):
        root = self.home / "outbox"
        return sorted(str(p) for p in root.rglob("*") if p.is_file()) if root.exists() else []

    def make_task(self, effect_class="idempotent", max_attempts=3, lease_ttl_s=6, timeout_s=None, **params):
        body = {
            "adapter": "synthetic",
            "params": synthetic_params(**params),
            "effect_class": effect_class,
            "max_attempts": max_attempts,
            "lease_ttl_s": lease_ttl_s,
        }
        if timeout_s is not None:
            body["timeout_s"] = timeout_s
        response = self.api.post("/v1/tasks", body)
        assert response.status_code in (200, 201), response.text
        return response.json()["task_id"]

    def log_tail(self, name, lines=60):
        path = self.logs / name
        if not path.exists():
            return f"<no {name}>"
        return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])

    # -- teardown ------------------------------------------------------------
    def close(self):
        procs = [p for p in [self.controller, *self.workers] if p is not None]
        for proc in procs:
            if proc.poll() is None:
                self.tracked_pids.update(descendants(proc.pid))
        for proc in procs:
            if proc.poll() is None:
                proc.kill()
                with contextlib.suppress(subprocess.TimeoutExpired):
                    proc.wait(timeout=10)
        for pid in pids_alive(self.tracked_pids):
            with contextlib.suppress(psutil.Error):
                psutil.Process(pid).kill()
        for handle in self._log_handles:
            handle.close()
