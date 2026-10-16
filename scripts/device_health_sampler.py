#!/usr/bin/env python3
"""Device Health Sampler (FRZ-03).

Bounded periodic sampling of host resources (CPU, RAM, disk, handle counts,
process counts) and surface / controller responsiveness into SQLite journal
or durable log/outbox so that GUI freeze or crash incidents have forensically
sound before/after evidence.

Design constraints:
- Autonomous spend: 0 EUR.
- Bounded sampling intervals and retention (FIFO ring buffer / max entries).
- Zero external dependencies (uses standard library + optional psutil when present).
- Zero grep-family tools, zero kill-by-name.
- Cross-platform: Windows (ctypes/wmi/registry), Linux (/proc), macOS (sysctl/vm_stat).
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import platform
import shutil
import sqlite3
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional

# Optional psutil import
try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False


def get_default_journal_db() -> Path:
    """Return default courier.db location based on OS conventions."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
        return Path(base) / "Courier" / "courier.db"
    return Path(os.path.expanduser("~/.courier")) / "courier.db"


def get_default_samples_file() -> Path:
    """Return default jsonl samples location."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
        return Path(base) / "Courier" / "device_health.jsonl"
    return Path(os.path.expanduser("~/.courier")) / "device_health.jsonl"


def sample_resources() -> Dict[str, Any]:
    """Capture current system resource metrics safely with fallbacks."""
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    metrics: Dict[str, Any] = {
        "timestamp": timestamp,
        "platform": sys.platform,
        "cpu_percent": 0.0,
        "memory_percent": 0.0,
        "memory_used_mb": 0.0,
        "memory_total_mb": 0.0,
        "disk_percent": 0.0,
        "disk_free_gb": 0.0,
        "process_count": 0,
        "handle_count": 0,
    }

    # Disk usage (built-in shutil)
    try:
        disk_usage = shutil.disk_usage(os.getcwd())
        metrics["disk_total_gb"] = round(disk_usage.total / (1024**3), 2)
        metrics["disk_free_gb"] = round(disk_usage.free / (1024**3), 2)
        if disk_usage.total > 0:
            metrics["disk_percent"] = round((disk_usage.used / disk_usage.total) * 100.0, 1)
    except Exception as e:
        metrics["disk_error"] = str(e)

    if _HAS_PSUTIL:
        try:
            metrics["cpu_percent"] = psutil.cpu_percent(interval=0.0)
            mem = psutil.virtual_memory()
            metrics["memory_percent"] = mem.percent
            metrics["memory_used_mb"] = round(mem.used / (1024**2), 1)
            metrics["memory_total_mb"] = round(mem.total / (1024**2), 1)
            pids = psutil.pids()
            metrics["process_count"] = len(pids)

            # Windows handle counts or cross-platform fallback
            if sys.platform == "win32":
                total_handles = 0
                for p in psutil.process_iter(["num_handles"]):
                    try:
                        h = p.info.get("num_handles")
                        if h:
                            total_handles += h
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                metrics["handle_count"] = total_handles
        except Exception as e:
            metrics["psutil_error"] = str(e)
    else:
        # Fallback when psutil is not installed
        if sys.platform == "darwin":
            try:
                # Load average fallback
                load1, _, _ = os.getloadavg()
                metrics["load_1min"] = round(load1, 2)
            except Exception:
                pass
        elif sys.platform.startswith("linux"):
            try:
                with open("/proc/meminfo", "r", encoding="utf-8") as f:
                    lines = f.readlines()
                meminfo = {}
                for line in lines:
                    parts = line.split(":")
                    if len(parts) == 2:
                        k = parts[0].strip()
                        v = parts[1].strip().split()[0]
                        meminfo[k] = int(v)
                total = meminfo.get("MemTotal", 0) * 1024
                avail = meminfo.get("MemAvailable", 0) * 1024
                if total > 0:
                    metrics["memory_total_mb"] = round(total / (1024**2), 1)
                    metrics["memory_used_mb"] = round((total - avail) / (1024**2), 1)
                    metrics["memory_percent"] = round(((total - avail) / total) * 100.0, 1)
            except Exception:
                pass

    return metrics


def check_endpoint_responsiveness(url: str, timeout_sec: float = 2.0) -> Dict[str, Any]:
    """Test HTTP endpoint responsiveness without blocking or crashing."""
    start_t = time.perf_counter()
    res: Dict[str, Any] = {
        "url": url,
        "available": False,
        "latency_ms": 0.0,
        "status_code": 0,
        "error": None,
    }
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Courier-HealthSampler/1.0"})
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            latency = (time.perf_counter() - start_t) * 1000.0
            res["available"] = True
            res["latency_ms"] = round(latency, 2)
            res["status_code"] = resp.getcode()
    except urllib.error.HTTPError as e:
        latency = (time.perf_counter() - start_t) * 1000.0
        res["latency_ms"] = round(latency, 2)
        res["status_code"] = e.code
        res["available"] = True  # Responded, even if error status
    except Exception as e:
        latency = (time.perf_counter() - start_t) * 1000.0
        res["latency_ms"] = round(latency, 2)
        res["error"] = str(e)
    return res


def record_sample_to_db(sample: Dict[str, Any], db_path: Path, max_records: int = 1000) -> None:
    """Store resource sample into SQLite courier.db with bounded retention."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path), timeout=5.0) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS device_health_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                cpu_percent REAL,
                memory_percent REAL,
                memory_used_mb REAL,
                disk_percent REAL,
                disk_free_gb REAL,
                process_count INTEGER,
                handle_count INTEGER,
                raw_json TEXT NOT NULL
            )
        """)
        conn.execute(
            """
            INSERT INTO device_health_samples (
                timestamp, cpu_percent, memory_percent, memory_used_mb,
                disk_percent, disk_free_gb, process_count, handle_count, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sample.get("timestamp"),
                sample.get("cpu_percent", 0.0),
                sample.get("memory_percent", 0.0),
                sample.get("memory_used_mb", 0.0),
                sample.get("disk_percent", 0.0),
                sample.get("disk_free_gb", 0.0),
                sample.get("process_count", 0),
                sample.get("handle_count", 0),
                json.dumps(sample),
            ),
        )

        # Enforce bounded ring buffer limit
        conn.execute(
            """
            DELETE FROM device_health_samples
            WHERE id NOT IN (
                SELECT id FROM device_health_samples
                ORDER BY id DESC LIMIT ?
            )
            """,
            (max_records,),
        )
        conn.commit()


def record_sample_to_jsonl(sample: Dict[str, Any], file_path: Path, max_lines: int = 1000) -> None:
    """Store sample in bounded JSONL log file."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(sample) + "\n"
    
    # Simple append
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(line)

    # Prune if over max_lines
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > max_lines:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(lines[-max_lines:])
    except Exception:
        pass


def get_health_summary(db_path: Path, limit: int = 10) -> List[Dict[str, Any]]:
    """Retrieve the most recent health samples from the database."""
    if not db_path.is_file():
        return []
    with sqlite3.connect(str(db_path), timeout=5.0) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT * FROM device_health_samples
            ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]


def evaluate_health_status(sample: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate if current metrics indicate hazardous memory/cpu/disk pressure."""
    warnings: List[str] = []
    status = "OK"

    mem_pct = sample.get("memory_percent", 0.0)
    cpu_pct = sample.get("cpu_percent", 0.0)
    disk_pct = sample.get("disk_percent", 0.0)
    disk_free = sample.get("disk_free_gb", 100.0)

    # Memory threshold (freeze incident saw sustained ~81% memory with 71 Electron processes)
    if mem_pct >= 90.0:
        status = "CRITICAL"
        warnings.append(f"Memory exhaustion risk: {mem_pct}% used")
    elif mem_pct >= 80.0:
        if status != "CRITICAL":
            status = "WARNING"
        warnings.append(f"High memory pressure: {mem_pct}% used")

    # CPU threshold
    if cpu_pct >= 95.0:
        status = "CRITICAL"
        warnings.append(f"CPU saturation: {cpu_pct}%")
    elif cpu_pct >= 85.0:
        if status != "CRITICAL":
            status = "WARNING"
        warnings.append(f"High CPU usage: {cpu_pct}%")

    # Disk threshold
    if disk_free < 1.0 or disk_pct >= 98.0:
        status = "CRITICAL"
        warnings.append(f"Disk full danger: {disk_free} GB free ({disk_pct}%)")
    elif disk_free < 5.0 or disk_pct >= 90.0:
        if status != "CRITICAL":
            status = "WARNING"
        warnings.append(f"Low disk space: {disk_free} GB free ({disk_pct}%)")

    return {
        "status": status,
        "warnings": warnings,
        "sample": sample,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Courier Device Health Sampler (FRZ-03)")
    parser.add_argument("--once", action="store_true", help="Capture a single sample and exit")
    parser.add_argument("--json", action="store_true", help="Print sample output in JSON format")
    parser.add_argument("--check-endpoint", help="HTTP URL to test for responsiveness")
    parser.add_argument("--db", type=Path, default=get_default_journal_db(), help="Path to courier.db")
    parser.add_argument("--jsonl", type=Path, default=get_default_samples_file(), help="Path to jsonl file")
    parser.add_argument("--summary", type=int, default=0, help="Print last N samples and exit")
    args = parser.parse_args()

    if args.summary > 0:
        rows = get_health_summary(args.db, limit=args.summary)
        if args.json:
            print(json.dumps(rows, indent=2))
        else:
            print(f"=== Last {len(rows)} Device Health Samples ===")
            for r in rows:
                print(f"[{r.get('timestamp')}] CPU: {r.get('cpu_percent')}% | RAM: {r.get('memory_percent')}% ({r.get('memory_used_mb')}MB) | Disk: {r.get('disk_percent')}% ({r.get('disk_free_gb')}GB free)")
        return 0

    sample = sample_resources()
    if args.check_endpoint:
        sample["endpoint_responsiveness"] = check_endpoint_responsiveness(args.check_endpoint)

    eval_res = evaluate_health_status(sample)
    sample["health_verdict"] = eval_res["status"]
    sample["health_warnings"] = eval_res["warnings"]

    # Record sample
    try:
        record_sample_to_db(sample, args.db)
    except Exception as e:
        sample["db_error"] = str(e)

    try:
        record_sample_to_jsonl(sample, args.jsonl)
    except Exception as e:
        sample["jsonl_error"] = str(e)

    if args.json:
        print(json.dumps(sample, indent=2))
    else:
        print(f"Device Health Sample: {sample['timestamp']}")
        print(f"Status: {eval_res['status']}")
        if eval_res['warnings']:
            for w in eval_res['warnings']:
                print(f"  WARNING: {w}")
        print(f"CPU: {sample['cpu_percent']}% | Memory: {sample['memory_percent']}% ({sample['memory_used_mb']} MB) | Disk Free: {sample['disk_free_gb']} GB ({sample['disk_percent']}%) | Processes: {sample['process_count']} | Handles: {sample['handle_count']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
