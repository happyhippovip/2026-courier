"""Distributed Worker Health Beacon and Heartbeat Transmitter.

Emits periodic telemetry pulses containing worker health, resource consumption,
and proactive lease renewal recommendations.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _format_time(dt: datetime) -> str:
    return dt.strftime(TIME_FORMAT)


def _parse_time(ts: str) -> datetime:
    return datetime.strptime(ts, TIME_FORMAT).replace(tzinfo=timezone.utc)


def _get_rss_mb() -> float:
    try:
        import psutil  # type: ignore

        proc = psutil.Process()
        return round(proc.memory_info().rss / (1024.0 * 1024.0), 2)
    except Exception:
        return 32.0


@dataclass
class BeaconPulse:
    """Telemetry pulse emitted by active worker."""

    worker_id: str
    host: str
    pid: int
    timestamp: str
    uptime_sec: float
    rss_mb: float
    current_item_id: str | None = None
    lease_expires_at: str | None = None
    renewal_recommended: bool = False
    status: str = "HEALTHY"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BeaconPulse":
        return cls(
            worker_id=data["worker_id"],
            host=data.get("host", "unknown"),
            pid=int(data.get("pid", 0)),
            timestamp=data["timestamp"],
            uptime_sec=float(data.get("uptime_sec", 0.0)),
            rss_mb=float(data.get("rss_mb", 0.0)),
            current_item_id=data.get("current_item_id"),
            lease_expires_at=data.get("lease_expires_at"),
            renewal_recommended=bool(data.get("renewal_recommended", False)),
            status=data.get("status", "HEALTHY"),
        )


class HealthBeacon:
    """Manages heartbeat emission and lease expiry detection."""

    def __init__(
        self,
        worker_id: str = "windows-titan",
        host: str | None = None,
        beacon_file: str = "run/beacon.json",
        history_file: str | None = None,
        renewal_threshold_sec: float = 300.0,
    ):
        self.worker_id = worker_id
        self.host = host or socket.gethostname()
        self.beacon_file = Path(beacon_file)
        self.history_file = Path(history_file) if history_file else None
        self.renewal_threshold_sec = renewal_threshold_sec
        self.start_time = time.time()

    def should_renew_lease(self, lease_expires_at: str, now: datetime | None = None) -> bool:
        if not lease_expires_at:
            return False
        cur_now = now or _now_utc()
        try:
            exp_dt = _parse_time(lease_expires_at)
            diff = (exp_dt - cur_now).total_seconds()
            return diff <= self.renewal_threshold_sec
        except Exception:
            return False

    def generate_pulse(
        self,
        current_item_id: str | None = None,
        lease_expires_at: str | None = None,
        now: datetime | None = None,
    ) -> BeaconPulse:
        cur_now = now or _now_utc()
        renewal_rec = False
        if lease_expires_at:
            renewal_rec = self.should_renew_lease(lease_expires_at, now=cur_now)

        uptime = round(time.time() - self.start_time, 2)
        rss = _get_rss_mb()

        return BeaconPulse(
            worker_id=self.worker_id,
            host=self.host,
            pid=os.getpid(),
            timestamp=_format_time(cur_now),
            uptime_sec=uptime,
            rss_mb=rss,
            current_item_id=current_item_id,
            lease_expires_at=lease_expires_at,
            renewal_recommended=renewal_rec,
            status="HEALTHY",
        )

    def emit_pulse(
        self,
        current_item_id: str | None = None,
        lease_expires_at: str | None = None,
        now: datetime | None = None,
    ) -> BeaconPulse:
        pulse = self.generate_pulse(
            current_item_id=current_item_id,
            lease_expires_at=lease_expires_at,
            now=now,
        )

        # Atomic write to beacon_file
        self.beacon_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.beacon_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(pulse.to_dict(), indent=2), encoding="utf-8")
        tmp.replace(self.beacon_file)

        # Append to history if configured
        if self.history_file:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(pulse.to_dict()) + "\n")

        return pulse


def emit_pulse(
    worker_id: str = "windows-titan",
    current_item_id: str | None = None,
    lease_expires_at: str | None = None,
    beacon_file: str = "run/beacon.json",
    now: datetime | None = None,
) -> BeaconPulse:
    beacon = HealthBeacon(worker_id=worker_id, beacon_file=beacon_file)
    return beacon.emit_pulse(
        current_item_id=current_item_id,
        lease_expires_at=lease_expires_at,
        now=now,
    )


def should_renew_lease(
    lease_expires_at: str,
    threshold_sec: float = 300.0,
    now: datetime | None = None,
) -> bool:
    beacon = HealthBeacon(renewal_threshold_sec=threshold_sec)
    return beacon.should_renew_lease(lease_expires_at, now=now)


def is_beacon_alive(
    beacon_path: str,
    max_age_sec: float = 60.0,
    now: datetime | None = None,
) -> bool:
    p = Path(beacon_path)
    if not p.exists():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        pulse_time = _parse_time(data["timestamp"])
        cur_now = now or _now_utc()
        age = (cur_now - pulse_time).total_seconds()
        return 0 <= age <= max_age_sec
    except Exception:
        return False


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Worker Health Beacon.")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # emit
    p_emit = subparsers.add_parser("emit")
    p_emit.add_argument("--worker-id", default="windows-titan")
    p_emit.add_argument("--item", help="Current work item ID")
    p_emit.add_argument("--lease-expiry", help="Lease expiration timestamp")
    p_emit.add_argument("--beacon-file", default="run/beacon.json")
    p_emit.add_argument("--history-file", help="Optional history jsonl")

    # check
    p_chk = subparsers.add_parser("check")
    p_chk.add_argument("--beacon-file", default="run/beacon.json")
    p_chk.add_argument("--max-age", type=float, default=60.0)

    args = parser.parse_args(argv)

    if args.subcommand == "emit":
        beacon = HealthBeacon(
            worker_id=args.worker_id,
            beacon_file=args.beacon_file,
            history_file=args.history_file,
        )
        pulse = beacon.emit_pulse(
            current_item_id=args.item,
            lease_expires_at=args.lease_expiry,
        )
        print(json.dumps({"status": "EMITTED", "pulse": pulse.to_dict()}))
        return 0

    elif args.subcommand == "check":
        alive = is_beacon_alive(args.beacon_file, max_age_sec=args.max_age)
        print(json.dumps({"status": "CHECKED", "alive": alive}))
        return 0 if alive else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
