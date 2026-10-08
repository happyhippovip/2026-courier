import os
import time


def classify(metrics):
    """Return NORMAL, PRESSURED, CRITICAL, or UNKNOWN.

    ``metrics is None``, and a sample whose memory readings are both
    missing, are UNKNOWN. ``load_per_core is None`` is allowed and is
    not itself a failure (Windows has no getloadavg).
    """
    if metrics is None:
        return "UNKNOWN"
    load = metrics.get("load_per_core")
    avail = metrics.get("avail_mem_pct")
    swap = metrics.get("swap_used_pct")
    if avail is None and swap is None:
        return "UNKNOWN"
    if avail is not None and avail < 10:
        return "CRITICAL"
    if (
        swap is not None
        and avail is not None
        and swap >= 80
        and avail < 25
    ):
        return "CRITICAL"
    if load is not None and load > 2.0:
        return "CRITICAL"
    if avail is not None and avail < 25:
        return "PRESSURED"
    if swap is not None and swap >= 50:
        return "PRESSURED"
    if load is not None and load > 1.5:
        return "PRESSURED"
    return "NORMAL"


def read_metrics():
    """Sample load, available memory, and swap without spawning a process.

    A raised ``getloadavg`` is a failed probe and returns None. A missing
    ``getloadavg`` leaves ``load_per_core`` None and is not a failure.
    Any failure reading psutil, including ImportError, leaves both memory
    readings unknown.
    """
    load_per_core = None
    if hasattr(os, "getloadavg"):
        try:
            load1, _load5, _load15 = os.getloadavg()
            cores = os.cpu_count() or 4
            load_per_core = load1 / cores
        except Exception:
            return None

    avail_mem_pct = None
    swap_used_pct = None
    try:
        import psutil

        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        total = memory.total
        if not total:
            raise ValueError("memory total is zero")
        avail_mem_pct = (memory.available / total) * 100.0
        swap_used_pct = float(swap.percent)
    except Exception:
        avail_mem_pct = None
        swap_used_pct = None

    return {
        "load_per_core": load_per_core,
        "avail_mem_pct": avail_mem_pct,
        "swap_used_pct": swap_used_pct,
    }


class HostPressureController:
    """
    Manages host resources by enforcing a finite state machine:
    GREEN -> YELLOW -> ORANGE -> RED -> RECOVERY

    A failed probe is UNKNOWN. HEAVY and MEDIUM work is refused, LIGHT
    work is still admitted, and the host is not quiesced.
    """
    MAX_HEAVY_JOBS = 1
    POLL_INTERVAL_BASE = 5
    RECOVERY_WINDOW = 300  # 5 minutes mandatory cooldown after hitting RED

    def __init__(self):
        self.state = "GREEN"
        self.active_jobs = {"HEAVY": 0, "MEDIUM": 0, "LIGHT": 0}
        self.recovery_end_time = 0

    def measure_pressure(self):
        """Legacy ladder over classify(read_metrics()).

        UNKNOWN stays UNKNOWN. CRITICAL is RED. PRESSURED is ORANGE.
        NORMAL is YELLOW when load_per_core > 1.0, otherwise GREEN.
        """
        metrics = read_metrics()
        level = classify(metrics)
        if level == "UNKNOWN":
            return "UNKNOWN"
        if level == "CRITICAL":
            return "RED"
        if level == "PRESSURED":
            return "ORANGE"
        load = metrics.get("load_per_core") if metrics else None
        if load is not None and load > 1.0:
            return "YELLOW"
        return "GREEN"

    def admit_job(self, budget_class):
        """Determines if a job can start, triggering backoff if not."""
        if time.time() < self.recovery_end_time:
            self.state = "RECOVERY"
            return False

        current_pressure = self.measure_pressure()

        if current_pressure == "RED":
            self.trigger_quiesce()
            return False

        if current_pressure == "UNKNOWN":
            # Fail closed for heavy work only. Do not quiesce the host.
            self.state = "UNKNOWN"
            if budget_class in ("HEAVY", "MEDIUM"):
                return False
            return True

        if current_pressure == "ORANGE" and budget_class in ("HEAVY", "MEDIUM"):
            self.state = "ORANGE"
            return False  # FAST_RAMP_DOWN

        if budget_class == "HEAVY" and self.active_jobs["HEAVY"] >= self.MAX_HEAVY_JOBS:
            return False

        # SLOW_RAMP_UP
        self.state = current_pressure
        return True

    def trigger_quiesce(self):
        """Forces the system into a recovery window and stops polling."""
        self.state = "RECOVERY"
        self.recovery_end_time = time.time() + self.RECOVERY_WINDOW

    def get_poll_interval(self):
        """BOUNDED_BACKOFF for queue polling."""
        if self.state == "GREEN": return self.POLL_INTERVAL_BASE
        if self.state == "YELLOW": return self.POLL_INTERVAL_BASE * 2
        if self.state == "ORANGE" or self.state == "UNKNOWN":
            return self.POLL_INTERVAL_BASE * 4
        if self.state == "RECOVERY": return min(30, self.RECOVERY_WINDOW)
        return self.POLL_INTERVAL_BASE

    def post_run_resource_snapshot(self):
        """Capture metrics after a run finishes to track cleanup."""
        return {
            "load": os.getloadavg() if hasattr(os, "getloadavg") else None,
            "state": self.state,
            "timestamp": time.time()
        }

# Global singleton
governor = HostPressureController()
