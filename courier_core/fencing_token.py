"""Distributed Lease Fence Token and Split-Brain Prevention Guard.

Provides monotonically increasing fencing token allocation,
stale token write rejection (zombie worker split-brain defense),
and atomic resource lease tracking.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Optional


class FencingError(Exception):
    """Base exception for fencing token and lease errors."""


class StaleFencingTokenError(FencingError):
    """Raised when an operation presents a fencing token that is older than the highest committed generation."""


class LeaseConflictError(FencingError):
    """Raised when attempting to acquire a lease already held by another active worker."""


@dataclass
class FencingTokenRecord:
    """Lease and fencing token state for a specific resource."""

    resource_id: str
    holder: str
    generation: int
    acquired_at: float
    expires_at: float
    highest_committed: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FencingTokenRecord:
        return cls(
            resource_id=str(data["resource_id"]),
            holder=str(data["holder"]),
            generation=int(data["generation"]),
            acquired_at=float(data["acquired_at"]),
            expires_at=float(data["expires_at"]),
            highest_committed=int(data.get("highest_committed", 0)),
        )


class FencingTokenManager:
    """Manages atomic resource leasing and monotonic fencing tokens."""

    def __init__(self, state_path: str | Path) -> None:
        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._resources: dict[str, FencingTokenRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._resources = {
                k: FencingTokenRecord.from_dict(v) for k, v in data.get("resources", {}).items()
            }
        except Exception:
            self._resources = {}

    def _save(self) -> None:
        payload = {
            "resources": {k: v.to_dict() for k, v in self._resources.items()},
            "updated_at": time.time(),
        }
        tmp_file = self.state_path.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        tmp_file.replace(self.state_path)

    def acquire(
        self,
        resource_id: str,
        holder: str,
        ttl_seconds: float = 30.0,
        now: Optional[float] = None,
    ) -> FencingTokenRecord:
        """Acquire or renew lease for resource and allocate next monotonic fencing token."""
        if not isinstance(resource_id, str) or not resource_id.strip() or "\x00" in resource_id:
            raise FencingError("resource_id must be a non-empty string without NUL")
        if not isinstance(holder, str) or not holder.strip() or "\x00" in holder:
            raise FencingError("holder must be a non-empty string without NUL")

        curr_time = now if now is not None else time.time()
        existing = self._resources.get(resource_id)

        # Check for active lease held by different worker
        if existing and existing.expires_at > curr_time and existing.holder != holder:
            raise LeaseConflictError(
                f"Resource is currently leased to {existing.holder} until {existing.expires_at}"
            )

        next_generation = (existing.generation + 1) if existing else 1
        highest_committed = existing.highest_committed if existing else 0

        record = FencingTokenRecord(
            resource_id=resource_id,
            holder=holder,
            generation=next_generation,
            acquired_at=curr_time,
            expires_at=curr_time + ttl_seconds,
            highest_committed=highest_committed,
        )

        self._resources[resource_id] = record
        self._save()
        return record

    def validate_and_commit(
        self,
        resource_id: str,
        generation: int,
        holder: Optional[str] = None,
        now: Optional[float] = None,
    ) -> bool:
        """Validate that token generation is active and not stale, and commit it as highest seen."""
        existing = self._resources.get(resource_id)
        if existing and holder is not None and existing.holder != holder:
            raise StaleFencingTokenError(
                f"Stale fencing token {generation} rejected: holder mismatch (held by {existing.holder}, presented by {holder})"
            )
        if existing is None:
            raise StaleFencingTokenError(
                f"Stale fencing token {generation} rejected: no active lease for {resource_id}"
            )

        highest = existing.highest_committed
        if generation < highest or generation != existing.generation:
            raise StaleFencingTokenError(
                f"Stale fencing token {generation} rejected: current committed generation is {highest}"
            )

        curr_time = now if now is not None else time.time()
        if existing.expires_at <= curr_time:
            raise StaleFencingTokenError(
                f"Stale fencing token {generation} rejected: lease expired at {existing.expires_at}"
            )

        existing.highest_committed = max(highest, generation)
        self._save()
        return True

    def release(self, resource_id: str, holder: str, generation: Optional[int] = None) -> bool:
        """Release an active lease with optional generation guarding."""
        existing = self._resources.get(resource_id)
        if existing and existing.holder == holder:
            if generation is not None and existing.generation != generation:
                return False
            existing.expires_at = 0.0
            self._save()
            return True
        return False

    def inspect(self, resource_id: str) -> Optional[dict[str, Any]]:
        """Inspect lease and fencing status for a resource."""
        record = self._resources.get(resource_id)
        return record.to_dict() if record else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Distributed Lease Fence Token Manager")
    subparsers = parser.add_subparsers(dest="action", required=True)

    # acquire
    acq_p = subparsers.add_parser("acquire", help="Acquire lease and get fencing token")
    acq_p.add_argument("--file", required=True, help="State file path")
    acq_p.add_argument("--resource", required=True, help="Resource ID")
    acq_p.add_argument("--holder", required=True, help="Holder identifier")
    acq_p.add_argument("--ttl", type=float, default=30.0, help="Lease TTL in seconds")

    # validate
    val_p = subparsers.add_parser("validate", help="Validate and commit fencing token")
    val_p.add_argument("--file", required=True, help="State file path")
    val_p.add_argument("--resource", required=True, help="Resource ID")
    val_p.add_argument("--generation", type=int, required=True, help="Fencing token generation number")

    # release
    rel_p = subparsers.add_parser("release", help="Release resource lease")
    rel_p.add_argument("--file", required=True, help="State file path")
    rel_p.add_argument("--resource", required=True, help="Resource ID")
    rel_p.add_argument("--holder", required=True, help="Holder identifier")

    # inspect
    ins_p = subparsers.add_parser("inspect", help="Inspect resource fence status")
    ins_p.add_argument("--file", required=True, help="State file path")
    ins_p.add_argument("--resource", required=True, help="Resource ID")

    args = parser.parse_args()
    mgr = FencingTokenManager(state_path=args.file)

    if args.action == "acquire":
        rec = mgr.acquire(resource_id=args.resource, holder=args.holder, ttl_seconds=args.ttl)
        print(f"Acquired lease for {rec.resource_id} (holder={rec.holder}, generation={rec.generation})")

    elif args.action == "validate":
        try:
            valid = mgr.validate_and_commit(resource_id=args.resource, generation=args.generation)
            if valid:
                print("TOKEN_COMMITTED_OK")
        except FencingError as e:
            print(f"VALIDATION_FAILED: {e}")
            sys.exit(1)

    elif args.action == "release":
        released = mgr.release(resource_id=args.resource, holder=args.holder)
        print(f"Released {args.resource}: {released}")

    elif args.action == "inspect":
        info = mgr.inspect(resource_id=args.resource)
        print(json.dumps(info or {}, indent=2))


if __name__ == "__main__":
    main()
