import json
import os
import time
import uuid
from pathlib import Path

import psutil

SLOT_STATES = {"READY", "IDLE", "WORKING", "CHECKING", "WAITING", "BLOCKED", "DONE", "CRASHED"}


class StateCorruptionError(RuntimeError):
    pass


class SlotLock:
    """An exclusive per-slot lock; it never deletes an existing lock."""

    def __init__(self, path):
        self.path = Path(path)
        self.fd = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
        except FileExistsError as exc:
            raise RuntimeError(f"slot lock already held: {self.path}") from exc
        os.write(self.fd, f"{os.getpid()} {time.time()}".encode("utf-8"))
        return self

    def __exit__(self, *_):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
            self.path.unlink(missing_ok=True)


def atomic_write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def read_json(path):
    try:
        with Path(path).open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise StateCorruptionError(f"unreadable state: {path}") from exc


def default_slot(slot_id, workdir):
    return {
        "slot_id": slot_id,
        "state": "READY",
        "workdir": str(workdir),
        "process": None,
        "updated_at": time.time(),
        "owner_token": uuid.uuid4().hex,
    }


def process_matches(process):
    if not process:
        return False
    try:
        candidate = psutil.Process(int(process["pid"]))
        return abs(candidate.create_time() - float(process["create_time"])) < 1.0
    except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError, TypeError, ValueError):
        return False
