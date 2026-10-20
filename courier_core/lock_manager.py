"""Distributed Single-Writer Lock Manager with Monotonic Fencing Tokens (P29)

Implements fail-closed distributed mutual exclusion with monotonic fencing
tokens to eliminate split-brain hazards and prevent stale worker writes.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Optional, TypeVar

T = TypeVar("T")
_PROCESS_LOCK = threading.RLock()


class StaleFencingTokenError(Exception):
    """Raised when an operation is attempted with an outdated or expired fencing token."""
    pass


@dataclass
class LockState:
    resource_id: str
    holder: str
    fencing_token: int
    expires_at: float
    released: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "holder": self.holder,
            "fencing_token": self.fencing_token,
            "expires_at": self.expires_at,
            "released": self.released,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LockState:
        return cls(
            resource_id=str(data.get("resource_id", "")),
            holder=str(data.get("holder", "")),
            fencing_token=int(data.get("fencing_token", 0)),
            expires_at=float(data.get("expires_at", 0.0)),
            released=bool(data.get("released", False)),
        )


class LockHandle:
    def __init__(
        self,
        resource_id: str,
        holder: str,
        fencing_token: int,
        expires_at: float,
        _manager: DistributedLockManager,
    ) -> None:
        self.resource_id = resource_id
        self.holder = holder
        self.fencing_token = fencing_token
        self.expires_at = expires_at
        self._manager = _manager
        self._released = False

    def is_active(self) -> bool:
        if self._released:
            return False
        return self._manager.validate_token(self.resource_id, self.fencing_token)

    def renew(self, ttl_seconds: float = 30.0) -> bool:
        return self._manager.renew(self, ttl_seconds=ttl_seconds)

    def release(self) -> bool:
        return self._manager.release(self)


class DistributedLockManager:
    """Provides file-backed distributed locks with strictly monotonic fencing tokens."""

    def __init__(self, storage_dir: Optional[Path | str] = None) -> None:
        if storage_dir is None:
            storage_dir = Path("run/locks")
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _lock_file(self, resource_id: str) -> Path:
        # Sanitize resource_id for safe filesystem naming; append digest when characters are replaced
        safe_id = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in resource_id)
        if safe_id != resource_id:
            digest = hashlib.sha256(resource_id.encode("utf-8")).hexdigest()[:12]
            safe_id = f"{safe_id}__{digest}"
        return self.storage_dir / f"{safe_id}.lock.json"

    @contextmanager
    def _mutex(self, resource_id: str) -> Iterator[None]:
        lock_file = self._lock_file(resource_id)
        mutex_path = self.storage_dir / f".{lock_file.stem}.mutex"
        with _PROCESS_LOCK:
            fd = os.open(str(mutex_path), os.O_RDWR | os.O_CREAT, 0o600)
            try:
                if os.name == "nt":
                    import msvcrt
                    deadline = time.monotonic() + 5.0
                    while True:
                        try:
                            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                            break
                        except OSError:
                            if time.monotonic() >= deadline:
                                raise
                            time.sleep(0.01)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_EX)
                yield
            finally:
                try:
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(fd, fcntl.LOCK_UN)
                except OSError:
                    pass
                try:
                    os.close(fd)
                except OSError:
                    pass

    def _load_state(self, resource_id: str) -> Optional[LockState]:
        path = self._lock_file(resource_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            state = LockState.from_dict(data)
            if state.resource_id != resource_id:
                return None
            return state
        except Exception:
            return None

    def _save_state(self, state: LockState) -> None:
        path = self._lock_file(state.resource_id)
        tmp_fd, tmp_path = tempfile.mkstemp(
            prefix=f"lock_{path.stem}_",
            suffix=".tmp",
            dir=str(self.storage_dir)
        )
        try:
            with open(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(state.to_dict(), f, indent=2)
            # Atomic replace
            os.replace(tmp_path, str(path))
        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            raise

    def acquire(
        self,
        resource_id: str,
        holder: str,
        ttl_seconds: float = 30.0
    ) -> Optional[LockHandle]:
        """Attempt to acquire the lock. Returns LockHandle with fencing token if successful, else None."""
        with self._mutex(resource_id):
            now = time.time()
            state = self._load_state(resource_id)

            if state is not None and not state.released and state.expires_at > now:
                if state.holder == holder:
                    # Same holder extending lease
                    state.expires_at = now + ttl_seconds
                    self._save_state(state)
                    return LockHandle(
                        resource_id=resource_id,
                        holder=holder,
                        fencing_token=state.fencing_token,
                        expires_at=state.expires_at,
                        _manager=self,
                    )
                else:
                    # Actively held by another worker
                    return None

            # Lock is either non-existent, released, or expired: acquire with monotonically higher token
            prev_token = state.fencing_token if state else 0
            new_token = prev_token + 1
            new_state = LockState(
                resource_id=resource_id,
                holder=holder,
                fencing_token=new_token,
                expires_at=now + ttl_seconds,
                released=False,
            )
            self._save_state(new_state)
            return LockHandle(
                resource_id=resource_id,
                holder=holder,
                fencing_token=new_token,
                expires_at=new_state.expires_at,
                _manager=self,
            )

    def renew(self, handle: LockHandle, ttl_seconds: float = 30.0) -> bool:
        """Extend lock validity if the handle's holder and token match current active state."""
        with self._mutex(handle.resource_id):
            now = time.time()
            state = self._load_state(handle.resource_id)
            if (
                state is not None
                and not state.released
                and state.expires_at > now
                and state.holder == handle.holder
                and state.fencing_token == handle.fencing_token
            ):
                state.expires_at = now + ttl_seconds
                self._save_state(state)
                handle.expires_at = state.expires_at
                return True
            return False

    def release(self, handle: LockHandle) -> bool:
        """Release lock if the handle's holder and token match current active state."""
        with self._mutex(handle.resource_id):
            state = self._load_state(handle.resource_id)
            if (
                state is not None
                and not state.released
                and state.holder == handle.holder
                and state.fencing_token == handle.fencing_token
            ):
                state.released = True
                self._save_state(state)
                handle._released = True
                return True
            return False

    def validate_token(self, resource_id: str, fencing_token: int) -> bool:
        """Verify that the fencing token represents the current active, unexpired lock."""
        state = self._load_state(resource_id)
        if state is None or state.released:
            return False
        if time.time() > state.expires_at:
            return False
        return state.fencing_token == fencing_token

    def guard_write(
        self,
        resource_id: str,
        fencing_token: int,
        write_action: Callable[[], T]
    ) -> T:
        """Execute write action if fencing token is strictly valid; raise StaleFencingTokenError otherwise."""
        if not self.validate_token(resource_id, fencing_token):
            raise StaleFencingTokenError(
                f"Stale fencing token: token {fencing_token} is no longer valid for resource '{resource_id}'"
            )
        return write_action()


def main(argv: Optional[list[str]] = None) -> int:
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("--storage", default="run/locks", help="Storage directory for locks")

    parser = argparse.ArgumentParser(description="Distributed Lock Manager CLI", parents=[parent_parser])
    subparsers = parser.add_subparsers(dest="command", required=True)

    acq_parser = subparsers.add_parser("acquire", help="Acquire a lock", parents=[parent_parser])
    acq_parser.add_argument("--resource", required=True)
    acq_parser.add_argument("--holder", required=True)
    acq_parser.add_argument("--ttl", type=float, default=30.0)

    val_parser = subparsers.add_parser("validate", help="Validate a fencing token", parents=[parent_parser])
    val_parser.add_argument("--resource", required=True)
    val_parser.add_argument("--token", type=int, required=True)

    rel_parser = subparsers.add_parser("release", help="Release a lock", parents=[parent_parser])
    rel_parser.add_argument("--resource", required=True)
    rel_parser.add_argument("--holder", required=True)
    rel_parser.add_argument("--token", type=int, required=True)

    args = parser.parse_args(argv)
    manager = DistributedLockManager(storage_dir=args.storage)

    if args.command == "acquire":
        handle = manager.acquire(args.resource, args.holder, ttl_seconds=args.ttl)
        if handle is not None:
            print(json.dumps({
                "status": "ACQUIRED",
                "resource": handle.resource_id,
                "holder": handle.holder,
                "fencing_token": handle.fencing_token,
                "expires_at": handle.expires_at,
            }))
            return 0
        else:
            print(json.dumps({"status": "REJECTED", "reason": "Lock already held"}))
            return 1

    elif args.command == "validate":
        valid = manager.validate_token(args.resource, args.token)
        print(json.dumps({"resource": args.resource, "token": args.token, "valid": valid}))
        return 0 if valid else 1

    elif args.command == "release":
        handle = LockHandle(
            resource_id=args.resource,
            holder=args.holder,
            fencing_token=args.token,
            expires_at=0.0,
            _manager=manager,
        )
        released = manager.release(handle)
        print(json.dumps({"resource": args.resource, "released": released}))
        return 0 if released else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
