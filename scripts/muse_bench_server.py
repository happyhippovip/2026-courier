#!/usr/bin/env python3
"""Muse workbench companion server (stdlib only, new file, no studio changes).

Serves the studio directory (reuses existing static hosting pattern) plus
three Muse-bench endpoints backed by a file queue:

  GET  /muse-bench.html            workbench page (static)
  GET  /api/muse/gallery           prompt gallery JSON
  GET  /api/muse/state             queue + results + checkpoint snapshot
  POST /api/muse/queue             append one task envelope {slot, template_id,
                                   template_version, inputs, prompt}
  POST /api/muse/claim             lease one QUEUED task (runner boundary)

States are file-backed and therefore real; nothing is simulated.
Runner/execution backend is OUT OF SCOPE (see QUEUE_CONTRACT below).
"""
import http.server
import json
import os
import time
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[1] if HERE.parents[1].name == "2026-courier" else Path.cwd()
STUDIO_DIR = REPO / "studio"
GALLERY_FILE = STUDIO_DIR / "muse-gallery.json"

WORK_DIR = Path(os.environ.get("MUSE_WORKHORSE_DIR", "/tmp/muse_workhorse"))
QUEUE_FILE = WORK_DIR / "queue.jsonl"
RESULTS_DIR = WORK_DIR / "results"
CHECKPOINT_FILE = WORK_DIR / "checkpoint.json"
LEASE_DIR = WORK_DIR / "lease"

QUEUE_CONTRACT = (
    "Gallery -> Workspace -> queue.jsonl -> runner(lease/claim) -> "
    "results/<task_id>.json -> workspace updates. Concurrency policy: "
    "runner claims at most one task at a time (concurrency=1 default)."
)

VALID_STATES = ("QUEUED", "RUNNING", "COMPLETED", "BLOCKED", "FAILED")


def ensure_dirs():
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    LEASE_DIR.mkdir(parents=True, exist_ok=True)
    if not CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.write_text(json.dumps({"concurrency": 1}) + "\n")


def read_queue():
    tasks = []
    if QUEUE_FILE.exists():
        for line in QUEUE_FILE.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    tasks.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return tasks


def append_task(envelope):
    ensure_dirs()
    task_id = envelope.get("task_id") or (
        "muse-%d" % int(time.time() * 1000)
    )
    record = {
        "task_id": task_id,
        "slot": envelope.get("slot", "CHAT 1"),
        "template_id": envelope.get("template_id", "CUSTOM"),
        "template_version": envelope.get("template_version", "1.0.0"),
        "inputs": envelope.get("inputs", {}),
        "prompt": envelope.get("prompt", ""),
        "state": "QUEUED",
        "queued_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    with open(QUEUE_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    return record


def claim_task(runner_id):
    ensure_dirs()
    lock_path = LEASE_DIR / "runner.lock"
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return None
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"runner_id": runner_id, "at": time.time()}))
    tasks = read_queue()
    for task in tasks:
        if task.get("state") == "QUEUED":
            return task
    os.unlink(lock_path)
    return None


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STUDIO_DIR), **kwargs)

    def _json(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/muse/gallery":
            if GALLERY_FILE.exists():
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(GALLERY_FILE.read_bytes())
            else:
                self._json(404, {"error": "gallery missing"})
        elif parsed.path == "/api/muse/state":
            ensure_dirs()
            results = sorted(p.name for p in RESULTS_DIR.glob("*.json"))
            self._json(200, {
                "queue": read_queue(),
                "results": results,
                "contract": QUEUE_CONTRACT,
            })
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/muse/queue":
            record = append_task(self._read_json())
            self._json(200, {"ok": True, "task": record})
        elif parsed.path == "/api/muse/claim":
            data = self._read_json()
            task = claim_task(data.get("runner_id", "unknown"))
            if task is None:
                self._json(409, {"ok": False, "reason": "busy-or-empty"})
            else:
                self._json(200, {"ok": True, "task": task})
        else:
            self.send_error(404, "Endpoint not found")


if __name__ == "__main__":
    port = int(os.environ.get("MUSE_BENCH_PORT", "8091"))
    ensure_dirs()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"muse-bench on http://127.0.0.1:{port}/muse-bench.html", flush=True)
    server.serve_forever()
