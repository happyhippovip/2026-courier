"""Process ownership: Courier may only stop a process it can prove it started.

A process is identified by (pid, create_time). A PID alone is not identity:
PIDs are reused, so a recorded PID whose create time differs is a different
process and is never touched. Records live in a small JSON registry written
atomically by the supervisor that spawned the process.

    python -m courier_runtime.ownership record --registry R --pid P --workkey W --owner O
    python -m courier_runtime.ownership stop   --registry R --workkey W
"""
import argparse
import json
import os
import sys
import tempfile
import time
from dataclasses import asdict, dataclass

import psutil

CREATE_TIME_TOLERANCE_S = 0.05


@dataclass(frozen=True)
class OwnedProcess:
    pid: int
    create_time: float
    workkey: str
    owner: str
    recorded_at: float

    @classmethod
    def capture(cls, pid, workkey, owner):
        """Record a process this caller just started. Raises if it is already gone."""
        proc = psutil.Process(pid)
        return cls(pid=pid, create_time=proc.create_time(), workkey=workkey, owner=owner,
                   recorded_at=time.time())


def is_same_process(record):
    """True only if the PID is alive and still the process that was recorded."""
    try:
        proc = psutil.Process(record.pid)
        if proc.status() == psutil.STATUS_ZOMBIE:
            return False
        return abs(proc.create_time() - record.create_time) <= CREATE_TIME_TOLERANCE_S
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def terminate_owned(record, timeout=5.0):
    """Stop the recorded process and its descendants; never anything else.

    Returns a receipt dict. A record that no longer matches a live process is
    reported as NOT_RUNNING and nothing is signalled.
    """
    receipt = {"pid": record.pid, "workkey": record.workkey, "owner": record.owner,
               "action": "NONE", "terminated": [], "still_alive": [], "result": "NOT_RUNNING"}
    if not is_same_process(record):
        return receipt
    root = psutil.Process(record.pid)
    try:
        tree = root.children(recursive=True) + [root]
    except psutil.NoSuchProcess:
        return receipt
    for proc in tree:
        try:
            proc.terminate()
        except psutil.NoSuchProcess:
            pass
    gone, alive = psutil.wait_procs(tree, timeout=timeout)
    for proc in alive:
        try:
            proc.kill()
        except psutil.NoSuchProcess:
            pass
    gone2, alive2 = psutil.wait_procs(alive, timeout=timeout)
    receipt.update(action="TERMINATE_OWNED_TREE",
                   terminated=sorted(p.pid for p in gone + gone2),
                   still_alive=sorted(p.pid for p in alive2),
                   result="STOPPED" if not alive2 else "ORPHANS_REMAIN")
    return receipt


class Registry:
    """JSON list of OwnedProcess records, replaced atomically on every write."""

    def __init__(self, path):
        self.path = path

    def load(self):
        try:
            with open(self.path, encoding="utf-8") as handle:
                return [OwnedProcess(**item) for item in json.load(handle)]
        except FileNotFoundError:
            return []

    def _save(self, records):
        directory = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".owned-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump([asdict(r) for r in records], handle, indent=1)
        os.replace(tmp, self.path)

    def add(self, record):
        records = [r for r in self.load() if (r.pid, r.create_time) != (record.pid, record.create_time)]
        records.append(record)
        self._save(records)

    def owned(self, workkey=None):
        return [r for r in self.load() if workkey is None or r.workkey == workkey]

    def stop(self, workkey=None, timeout=5.0):
        """Stop every owned record (optionally one workkey) and drop it from the registry."""
        receipts, keep = [], []
        for record in self.load():
            if workkey is None or record.workkey == workkey:
                receipts.append(terminate_owned(record, timeout=timeout))
            else:
                keep.append(record)
        self._save(keep)
        return receipts


def main(argv=None):
    parser = argparse.ArgumentParser(description="Record or stop processes Courier owns.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    rec = sub.add_parser("record")
    rec.add_argument("--registry", required=True)
    rec.add_argument("--pid", type=int, required=True)
    rec.add_argument("--workkey", required=True)
    rec.add_argument("--owner", default="local")
    stop = sub.add_parser("stop")
    stop.add_argument("--registry", required=True)
    stop.add_argument("--workkey")
    stop.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args(argv)

    registry = Registry(args.registry)
    if args.cmd == "record":
        try:
            registry.add(OwnedProcess.capture(args.pid, args.workkey, args.owner))
        except psutil.NoSuchProcess:
            print(f"pid {args.pid} is not running; nothing recorded", file=sys.stderr)
            return 1
        return 0
    receipts = registry.stop(args.workkey, timeout=args.timeout)
    print(json.dumps(receipts))
    return 1 if any(r["result"] == "ORPHANS_REMAIN" for r in receipts) else 0


if __name__ == "__main__":
    sys.exit(main())
