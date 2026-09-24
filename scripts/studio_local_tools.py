"""Read-only local process telemetry. No command arguments, prompts or paths leave this module."""

from __future__ import annotations

import datetime
import json
import os
import platform
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_DIR = Path(__file__).resolve().parent.parent


def cpu_seconds(value: str) -> float:
    parts = value.split(":")
    return sum(float(p) * 60**i for i, p in enumerate(reversed(parts)))


def classify(command: str) -> str | None:
    if not command:
        return None
    cmd_norm = command.replace("\\", "/").lower()
    if "antigravity" in cmd_norm:
        return "antigravity"
    if "chatgpt" in cmd_norm or "codex" in cmd_norm:
        return "chatgpt"
    if "muse" in cmd_norm:
        return "muse"
    return None


class LocalToolObserver:
    def __init__(self, repo_dir: Path | None = None):
        self.repo_dir = repo_dir or REPO_DIR
        self.previous: dict[str, tuple[str, float]] = {}
        self.last_sample: float | None = None
        self.cached: dict[str, Any] | None = None
        self.active_until: dict[str, float] = {}
        self.remote_sampled_at = 0.0
        self.remote_hosts: dict[str, Any] = {}

    def observe_windows(self, now: float) -> dict[str, Any]:
        """Read-only, bounded observation of the Windows Courier host."""
        if self.remote_hosts and now - self.remote_sampled_at < 30:
            return self.remote_hosts

        is_local_windows = platform.system() == "Windows"
        observed: dict[str, Any] = {
            "hostname": platform.node(),
            "status": "ONLINE" if is_local_windows else "UNKNOWN",
            "courier_health": "UNKNOWN",
            "runtime_sha": None,
            "task_known": False,
        }

        # Check local/remote HTTP health
        health_urls = ["http://127.0.0.1:8080/health"]
        if not is_local_windows:
            health_urls.append("http://192.168.178.87:8080/health")

        for url in health_urls:
            try:
                with urllib.request.urlopen(url, timeout=1) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    if response.status == 200 and payload.get("status") == "healthy":
                        observed.update(status="ONLINE", courier_health="HEALTHY")
                        break
            except (OSError, ValueError, urllib.error.URLError):
                pass

        if observed["courier_health"] == "UNKNOWN":
            observed["courier_health"] = "UNREACHABLE"

        # Resolve HEAD SHA
        if is_local_windows:
            try:
                res = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    cwd=str(self.repo_dir),
                )
                if res.returncode == 0 and res.stdout.strip():
                    observed["runtime_sha"] = res.stdout.strip()
            except Exception:
                pass
        else:
            if observed["status"] == "ONLINE":
                try:
                    command = (
                        "Set-Location C:\\Users\\lol\\2026-workspace\\2026-courier; "
                        "Write-Output $env:COMPUTERNAME; git rev-parse HEAD"
                    )
                    result = subprocess.run(
                        [
                            "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=2",
                            "windows-ai", "powershell", "-NoProfile", "-Command", command,
                        ],
                        capture_output=True,
                        text=True,
                        timeout=4,
                        check=True,
                    )
                    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
                    if len(lines) >= 2:
                        observed["hostname"] = lines[-2]
                        observed["runtime_sha"] = lines[-1]
                except (OSError, subprocess.SubprocessError):
                    pass

        observed["observed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.remote_sampled_at = now
        self.remote_hosts = {"windows": observed}
        return self.remote_hosts

    def _sample_processes(self) -> dict[str, tuple[str, float]]:
        current: dict[str, tuple[str, float]] = {}
        try:
            import psutil
            for p in psutil.process_iter(["pid", "name", "cmdline", "cpu_times"]):
                try:
                    name = p.info.get("name") or ""
                    cmdline = " ".join(p.info.get("cmdline") or [])
                    full_cmd = f"{name} {cmdline}"
                    tool = classify(full_cmd)
                    if tool:
                        cpu_t = p.info.get("cpu_times")
                        total_cpu = (cpu_t.user + cpu_t.system) if cpu_t else 0.0
                        current[str(p.info["pid"])] = (tool, float(total_cpu))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return current
        except ImportError:
            pass

        # Fallback to ps on POSIX
        if os.name != "nt":
            try:
                output = subprocess.run(
                    ["ps", "-axo", "pid=,time=,comm="],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=True,
                ).stdout
                for line in output.splitlines():
                    fields = line.strip().split(None, 2)
                    if len(fields) != 3:
                        continue
                    pid, used, command = fields
                    tool = classify(command)
                    if tool:
                        current[pid] = (tool, cpu_seconds(used))
            except Exception:
                pass

        return current

    def snapshot(self) -> dict[str, Any]:
        now = time.monotonic()
        if self.cached and self.last_sample is not None and now - self.last_sample < 4:
            return self.cached

        try:
            current = self._sample_processes()
            elapsed = now - self.last_sample if self.last_sample is not None else None
            tools: dict[str, Any] = {}

            for key in ("chatgpt", "muse", "antigravity"):
                matching = {pid: record for pid, record in current.items() if record[0] == key}
                measured = elapsed is not None and any(pid in self.previous for pid in matching)
                delta = sum(
                    max(0.0, record[1] - self.previous[pid][1])
                    for pid, record in matching.items()
                    if pid in self.previous and self.previous[pid][0] == key
                )
                cpu = round(delta / elapsed * 100, 1) if (measured and elapsed and elapsed > 0) else None
                if cpu is not None and cpu >= 2:
                    self.active_until[key] = now + 8
                status = (
                    "OFFLINE"
                    if not matching
                    else ("COMPUTING" if self.active_until.get(key, 0) > now else "OPEN")
                )
                tools[key] = {
                    "status": status,
                    "process_count": len(matching),
                    "cpu_percent": cpu,
                    "activity_source": "PROCESS_CPU_DELTA",
                    "task_known": False,
                }

            self.previous = current
            self.last_sample = now

            local_host = "windows" if platform.system() == "Windows" else "mac"
            self.cached = {
                "observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "source": "LOCAL_PROCESS_OBSERVER",
                "hosts": {
                    local_host: {
                        "hostname": platform.node(),
                        "status": "ONLINE",
                        "task_known": False,
                    },
                    **self.observe_windows(now),
                },
                "tools": tools,
            }
            return self.cached
        except Exception as exc:
            return {
                "source": "LOCAL_PROCESS_OBSERVER",
                "error": f"OBSERVATION_UNAVAILABLE: {exc}",
                "tools": {},
            }


observer = LocalToolObserver()

if __name__ == "__main__":
    snap = observer.snapshot()
    print(json.dumps(snap, indent=2))
