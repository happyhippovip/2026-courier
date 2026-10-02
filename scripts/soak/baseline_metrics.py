"""Best-effort host baseline sampler for the endurance soak harness.

Observed-only: process counts, FD/handles, RSS, swap, load, log/temp sizes,
plus native Mac (vm_stat/sysctl) and Windows (process handle count) evidence
where the platform exposes it. Anything the platform hides is reported as
``"n/a"`` with a reason -- never inferred from the other platform.

Simulated counters (queue size, schedulers, provider sessions, admitted
slots) are owned by the harness, not by this module.
"""

from __future__ import annotations

import os
import platform
import subprocess
import time


def _psutil():
    try:
        import psutil
        return psutil
    except Exception:
        return None


def _mac_native() -> dict:
    if platform.system() != "Darwin":
        return {"status": "n/a", "reason": "not-macos"}
    out: dict = {"status": "observed"}
    try:
        vm = subprocess.run(["vm_stat"], capture_output=True, text=True,
                            timeout=10)
        if vm.returncode == 0:
            lines = [ln.strip() for ln in vm.stdout.splitlines() if "Pages free" in ln
                     or "Pages occupied by compressor" in ln]
            out["vm_stat"] = lines
    except Exception as exc:
        out["vm_stat_error"] = str(exc)[:200]
    try:
        sw = subprocess.run(["sysctl", "vm.swapusage"], capture_output=True,
                            text=True, timeout=10)
        if sw.returncode == 0:
            out["swapusage"] = sw.stdout.strip()
    except Exception as exc:
        out["swapusage_error"] = str(exc)[:200]
    return out


def _windows_native(psutil_mod) -> dict:
    if os.name != "nt":
        return {"status": "n/a", "reason": "not-windows"}
    out: dict = {"status": "observed"}
    try:
        if psutil_mod is not None:
            out["num_handles"] = int(psutil_mod.Process().num_handles())
    except Exception as exc:
        out["num_handles_error"] = str(exc)[:200]
    out["note"] = ("Job-Object membership is owned by courier_worker.host "
                   "ContainedRun; this sampler reports handle counts only.")
    return out


def _dir_bytes(paths) -> dict:
    total = 0
    files = 0
    for root in paths:
        if not root or not os.path.isdir(root):
            continue
        for dirpath, _, filenames in os.walk(root):
            for name in filenames:
                full = os.path.join(dirpath, name)
                try:
                    total += os.path.getsize(full)
                    files += 1
                except OSError:
                    continue
    return {"bytes": total, "files": files}


def collect_sample(log_dirs=()) -> dict:
    """One observed baseline sample. Never raises on missing platform APIs."""
    psutil_mod = _psutil()
    sample: dict = {"timestamp": time.time(), "platform": platform.platform()}
    if psutil_mod is not None:
        try:
            proc = psutil_mod.Process()
            sample["owned_process_count"] = 1
            sample["owned_descendant_count"] = len(proc.children(recursive=True))
            try:
                sample["fd_count"] = int(proc.num_fds())
                sample["fd_method"] = "num_fds"
            except AttributeError:
                try:
                    sample["fd_count"] = int(proc.num_handles())
                    sample["fd_method"] = "num_handles"
                except Exception as exc:
                    sample["fd_count"] = "n/a"
                    sample["fd_method"] = f"unavailable: {exc}"[:200]
            sample["rss_kb"] = int(proc.memory_info().rss // 1024)
            sm = psutil_mod.swap_memory()
            sample["swap"] = {"total": sm.total, "used": sm.used,
                              "percent": sm.percent}
        except Exception as exc:
            sample["psutil_error"] = str(exc)[:200]
    else:
        sample["psutil"] = "n/a: psutil not installed"
    try:
        if hasattr(os, "getloadavg"):
            sample["load"] = list(os.getloadavg())
        sample["cores"] = os.cpu_count()
    except Exception:
        pass
    sample["log_temp"] = _dir_bytes(list(log_dirs or ()))
    sample["mac_native"] = _mac_native()
    sample["windows_native"] = _windows_native(psutil_mod)
    try:
        import resource
        ru = resource.getrusage(resource.RUSAGE_SELF)
        sample["maxrss_kb"] = int(ru.ru_maxrss)
    except Exception:
        pass
    return sample


def slope(xs, ys) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
