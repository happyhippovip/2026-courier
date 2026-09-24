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

from __future__ import annotations

import argparse
import http.server
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any
import urllib.parse

HERE = Path(__file__).resolve()
REPO = HERE.parent.parent
STUDIO_DIR = REPO / "studio"
GALLERY_FILE = STUDIO_DIR / "muse-gallery.json"

DEFAULT_WORK_DIR = Path(
    os.environ.get("MUSE_WORKHORSE_DIR", str(Path(tempfile.gettempdir()) / "muse_workhorse"))
)

QUEUE_CONTRACT = (
    "Gallery -> Workspace -> queue.jsonl -> runner(lease/claim) -> "
    "results/<task_id>.json -> workspace updates. Concurrency policy: "
    "runner claims at most one task at a time (concurrency=1 default)."
)

VALID_STATES = ("QUEUED", "RUNNING", "COMPLETED", "BLOCKED", "FAILED")


def ensure_dirs(work_dir: Path | None = None) -> Path:
    w_dir = Path(work_dir) if work_dir else DEFAULT_WORK_DIR
    w_dir.mkdir(parents=True, exist_ok=True)
    (w_dir / "results").mkdir(parents=True, exist_ok=True)
    (w_dir / "lease").mkdir(parents=True, exist_ok=True)
    cp = w_dir / "checkpoint.json"
    if not cp.exists():
        cp.write_text(json.dumps({"concurrency": 1}) + "\n", encoding="utf-8")
    return w_dir


def read_queue(work_dir: Path | None = None) -> list[dict[str, Any]]:
    w_dir = Path(work_dir) if work_dir else DEFAULT_WORK_DIR
    q_file = w_dir / "queue.jsonl"
    tasks: list[dict[str, Any]] = []
    if q_file.exists():
        for line in q_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    tasks.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return tasks


def append_task(envelope: dict[str, Any], work_dir: Path | None = None) -> dict[str, Any]:
    w_dir = ensure_dirs(work_dir)
    task_id = envelope.get("task_id") or ("muse-%d" % int(time.time() * 1000))
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
    q_file = w_dir / "queue.jsonl"
    with open(q_file, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    return record


def claim_task(runner_id: str, work_dir: Path | None = None) -> dict[str, Any] | None:
    w_dir = ensure_dirs(work_dir)
    lock_path = w_dir / "lease" / "runner.lock"
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return None

    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"runner_id": runner_id, "at": time.time()}))

    tasks = read_queue(w_dir)
    for task in tasks:
        if task.get("state") == "QUEUED":
            return task

    try:
        lock_path.unlink(missing_ok=True)
    except OSError:
        pass
    return None


def release_lease(work_dir: Path | None = None) -> bool:
    w_dir = Path(work_dir) if work_dir else DEFAULT_WORK_DIR
    lock_path = w_dir / "lease" / "runner.lock"
    if lock_path.exists():
        try:
            lock_path.unlink(missing_ok=True)
            return True
        except OSError:
            pass
    return False


def create_handler_class(work_dir: Path | None = None, studio_dir: Path | None = None):
    active_work_dir = Path(work_dir) if work_dir else DEFAULT_WORK_DIR
    active_studio_dir = Path(studio_dir) if studio_dir else STUDIO_DIR

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(active_studio_dir), **kwargs)

        def _json(self, code: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or 0)
            if not length:
                return {}
            try:
                return json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return {}

        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/api/muse/gallery":
                gal_file = active_studio_dir / "muse-gallery.json"
                if gal_file.exists():
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(gal_file.read_bytes())
                else:
                    self._json(404, {"error": "gallery missing"})
            elif parsed.path == "/api/muse/state":
                ensure_dirs(active_work_dir)
                results_dir = active_work_dir / "results"
                results = sorted(p.name for p in results_dir.glob("*.json"))
                self._json(
                    200,
                    {
                        "queue": read_queue(active_work_dir),
                        "results": results,
                        "contract": QUEUE_CONTRACT,
                    },
                )
            else:
                super().do_GET()

        def do_POST(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/api/muse/queue":
                record = append_task(self._read_json(), work_dir=active_work_dir)
                self._json(200, {"ok": True, "task": record})
            elif parsed.path == "/api/muse/claim":
                data = self._read_json()
                task = claim_task(data.get("runner_id", "unknown"), work_dir=active_work_dir)
                if task is None:
                    self._json(409, {"ok": False, "reason": "busy-or-empty"})
                else:
                    self._json(200, {"ok": True, "task": task})
            else:
                self.send_error(404, "Endpoint not found")

    return Handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Muse Workbench Companion Server")
    parser.add_argument("--port", type=int, default=8091, help="Server port (default: 8091)")
    parser.add_argument("--work-dir", type=Path, help="Work directory for queue and results")
    parser.add_argument("--studio-dir", type=Path, help="Studio directory for static files")
    parser.add_argument("--status", action="store_true", help="Print queue status and exit")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = parser.parse_args(argv)

    w_dir = ensure_dirs(args.work_dir)

    if args.status:
        tasks = read_queue(w_dir)
        info = {
            "work_dir": str(w_dir),
            "queue_len": len(tasks),
            "queued": sum(1 for t in tasks if t.get("state") == "QUEUED"),
            "contract": QUEUE_CONTRACT,
        }
        if args.json:
            print(json.dumps(info, indent=2))
        else:
            print(f"MUSE_STATUS: {info}")
        return 0

    handler_cls = create_handler_class(work_dir=args.work_dir, studio_dir=args.studio_dir)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler_cls)
    print(f"muse-bench on http://127.0.0.1:{args.port}/muse-bench.html", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
