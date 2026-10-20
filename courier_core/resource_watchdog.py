"""Fail-closed resource watchdog and hysteresis cooldown policy for RESOURCE_PAUSE.

Lane L3. Inspects runtime resource metrics (memory RSS, open file descriptors / handles)
against declared thresholds. Implements hysteresis cooldown to prevent thermal/pressure
thrashing, returning structured states: NORMAL, COOLDOWN, or PRESSURED.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class ResourcePolicy:
    max_rss_mb: float = 4096.0
    max_open_fds: int = 1024
    cooldown_seconds: float = 60.0


@dataclass
class ResourceHealthReport:
    state: str  # "NORMAL", "COOLDOWN", "PRESSURED"
    rss_mb: float
    open_fds: int
    pressure_reasons: list[str] = field(default_factory=list)
    cooldown_remaining_s: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _get_process_rss_mb() -> float:
    try:
        import psutil  # type: ignore

        proc = psutil.Process()
        return proc.memory_info().rss / (1024.0 * 1024.0)
    except Exception:
        # Fallback for Windows without psutil or basic inspection
        try:
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            pmc = PROCESS_MEMORY_COUNTERS()
            pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
                return float(pmc.WorkingSetSize) / (1024.0 * 1024.0)
        except Exception:
            pass
        return 32.0  # safe baseline fallback


def _get_open_fds_count() -> int:
    try:
        import psutil  # type: ignore

        proc = psutil.Process()
        if hasattr(proc, "num_handles"):
            return proc.num_handles()
        return len(proc.open_files())
    except Exception:
        # On POSIX:
        if hasattr(os, "listdir") and os.path.exists("/proc/self/fd"):
            try:
                return len(os.listdir("/proc/self/fd"))
            except Exception:
                pass
        return 16  # safe nominal count


def evaluate_resource_health(
    home_path: str | Path,
    policy: Optional[ResourcePolicy] = None,
    cooldown_until: Optional[float] = None,
    now: Optional[float] = None,
) -> ResourceHealthReport:
    p = policy or ResourcePolicy()
    current_time = now if now is not None else time.time()
    rss_mb = _get_process_rss_mb()
    open_fds = _get_open_fds_count()

    pressure_reasons: list[str] = []
    if rss_mb > p.max_rss_mb:
        pressure_reasons.append("memory-pressure")
    if open_fds > p.max_open_fds:
        pressure_reasons.append("fd-exhaustion")

    if pressure_reasons:
        return ResourceHealthReport(
            state="PRESSURED",
            rss_mb=round(rss_mb, 2),
            open_fds=open_fds,
            pressure_reasons=pressure_reasons,
            cooldown_remaining_s=0.0,
        )

    cooldown_remaining = 0.0
    if cooldown_until is not None and cooldown_until > current_time:
        cooldown_remaining = round(cooldown_until - current_time, 2)
        return ResourceHealthReport(
            state="COOLDOWN",
            rss_mb=round(rss_mb, 2),
            open_fds=open_fds,
            pressure_reasons=[],
            cooldown_remaining_s=cooldown_remaining,
        )

    return ResourceHealthReport(
        state="NORMAL",
        rss_mb=round(rss_mb, 2),
        open_fds=open_fds,
        pressure_reasons=[],
        cooldown_remaining_s=0.0,
    )


def should_pause(report: ResourceHealthReport) -> tuple[bool, Optional[str]]:
    if report.state == "PRESSURED":
        reason = report.pressure_reasons[0] if report.pressure_reasons else "pressure"
        return True, reason
    return False, None


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="courier_core.resource_watchdog",
        description="Fail-closed resource watchdog and hysteresis cooldown policy.",
    )
    parser.add_argument("home_path", help="Path to home directory")
    parser.add_argument("--max-rss-mb", type=float, default=4096.0, help="Maximum allowed process RSS in MB")
    parser.add_argument("--max-open-fds", type=int, default=1024, help="Maximum allowed open handles/descriptors")
    parser.add_argument("--cooldown-seconds", type=float, default=60.0, help="Hysteresis cooldown in seconds")
    args = parser.parse_args(argv)

    policy = ResourcePolicy(
        max_rss_mb=args.max_rss_mb,
        max_open_fds=args.max_open_fds,
        cooldown_seconds=args.cooldown_seconds,
    )
    report = evaluate_resource_health(args.home_path, policy=policy)
    print(json.dumps(report.to_dict(), indent=2))
    return 1 if report.state == "PRESSURED" else 0


if __name__ == "__main__":
    sys.exit(main())
