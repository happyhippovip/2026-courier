"""Multi-Worker Lease Heartbeat Keepalive Synchronizer (P38)

Maintains active work item leases during long-running tasks, performing
proactive renewals prior to expiry, syncing heartbeat pulses, and detecting
lease loss to prevent split-brain writes.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class KeepaliveStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    LOST = "LOST"


@dataclass
class LeaseState:
    item_id: str
    holder: str
    expires_at: float
    ttl_seconds: float = 30.0
    renewal_count: int = 0
    consecutive_failures: int = 0
    status: KeepaliveStatus = KeepaliveStatus.HEALTHY
    last_renewed: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "holder": self.holder,
            "expires_at": self.expires_at,
            "ttl_seconds": self.ttl_seconds,
            "renewal_count": self.renewal_count,
            "consecutive_failures": self.consecutive_failures,
            "status": self.status.value,
            "last_renewed": self.last_renewed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LeaseState:
        return cls(
            item_id=str(data.get("item_id", "")),
            holder=str(data.get("holder", "")),
            expires_at=float(data.get("expires_at", 0.0)),
            ttl_seconds=float(data.get("ttl_seconds", 30.0)),
            renewal_count=int(data.get("renewal_count", 0)),
            consecutive_failures=int(data.get("consecutive_failures", 0)),
            status=KeepaliveStatus(data.get("status", "HEALTHY")),
            last_renewed=float(data.get("last_renewed", 0.0)),
        )


class LeaseSynchronizer:
    """Manages proactive keepalive renewals and heartbeat pulse synchronization."""

    def __init__(
        self,
        renew_fn: Optional[Callable[[str, float], bool]] = None,
        renewal_threshold_seconds: float = 10.0,
        max_consecutive_failures: int = 3,
        beacon: Any = None,
    ) -> None:
        self.renew_fn = renew_fn or (lambda item_id, ttl: True)
        self.renewal_threshold_seconds = renewal_threshold_seconds
        self.max_consecutive_failures = max_consecutive_failures
        self.beacon = beacon
        self._leases: Dict[str, LeaseState] = {}
        self._lock = threading.Lock()

    def track_lease(
        self,
        item_id: str,
        holder: str,
        expires_at: float,
        ttl_seconds: float = 30.0,
    ) -> LeaseState:
        with self._lock:
            lease = LeaseState(
                item_id=item_id,
                holder=holder,
                expires_at=expires_at,
                ttl_seconds=ttl_seconds,
                last_renewed=time.time(),
            )
            self._leases[item_id] = lease
            return lease

    def stop_lease(self, item_id: str) -> bool:
        with self._lock:
            if item_id in self._leases:
                del self._leases[item_id]
                return True
            return False

    def get_lease(self, item_id: str) -> Optional[LeaseState]:
        with self._lock:
            return self._leases.get(item_id)

    def is_lease_valid(self, item_id: str) -> bool:
        with self._lock:
            lease = self._leases.get(item_id)
            if not lease:
                return False
            if lease.status == KeepaliveStatus.LOST:
                return False
            return time.time() < lease.expires_at

    def step(self) -> Dict[str, int]:
        """Perform a single keepalive evaluation and renewal cycle."""
        with self._lock:
            now = time.time()
            renewed = 0
            failed = 0
            lost = 0

            for lease in self._leases.values():
                if lease.status == KeepaliveStatus.LOST:
                    continue

                time_to_expiry = lease.expires_at - now
                if time_to_expiry <= 0:
                    lease.status = KeepaliveStatus.LOST
                    lost += 1
                    continue
                if time_to_expiry <= self.renewal_threshold_seconds:
                    try:
                        success = self.renew_fn(lease.item_id, lease.ttl_seconds)
                    except Exception:
                        success = False

                    if success:
                        lease.expires_at = now + lease.ttl_seconds
                        lease.renewal_count += 1
                        lease.consecutive_failures = 0
                        lease.status = KeepaliveStatus.HEALTHY
                        lease.last_renewed = now
                        renewed += 1

                        if self.beacon and hasattr(self.beacon, "emit_pulse"):
                            try:
                                self.beacon.emit_pulse()
                            except Exception:
                                pass
                    else:
                        lease.consecutive_failures += 1
                        failed += 1
                        if lease.consecutive_failures >= self.max_consecutive_failures:
                            lease.status = KeepaliveStatus.LOST
                            lost += 1
                        else:
                            lease.status = KeepaliveStatus.DEGRADED

            return {
                "renewed": renewed,
                "failed": failed,
                "lost": lost,
                "tracked": len(self._leases),
            }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Lease Synchronizer CLI")
    subparsers = parser.add_subparsers(dest="action", required=True)

    tick_parser = subparsers.add_parser("tick", help="Evaluate and renew tracking leases once")
    tick_parser.add_argument("--leases", required=True, help="Path to leases JSON file")

    args = parser.parse_args(argv)

    if args.action == "tick":
        data = json.loads(Path(args.leases).read_text(encoding="utf-8"))
        syncer = LeaseSynchronizer()

        for l_data in data.get("leases", []):
            syncer.track_lease(
                item_id=l_data["item_id"],
                holder=l_data.get("holder", "cli-holder"),
                expires_at=float(l_data["expires_at"]),
                ttl_seconds=float(l_data.get("ttl_seconds", 30.0)),
            )

        res = syncer.step()
        print(json.dumps({
            "status": "SUCCESS",
            "renewed": res["renewed"],
            "failed": res["failed"],
            "lost": res["lost"],
            "tracked": res["tracked"],
        }, indent=2))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
