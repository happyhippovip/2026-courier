import os
import time

class HostPressureController:
    """
    Manages host resources by enforcing a finite state machine:
    GREEN -> YELLOW -> ORANGE -> RED -> RECOVERY
    """
    MAX_HEAVY_JOBS = 1
    POLL_INTERVAL_BASE = 5
    RECOVERY_WINDOW = 300  # 5 minutes mandatory cooldown after hitting RED

    def __init__(self):
        self.state = "GREEN"
        self.active_jobs = {"HEAVY": 0, "MEDIUM": 0, "LIGHT": 0}
        self.recovery_end_time = 0

    def measure_pressure(self):
        """Read system metrics across POSIX and Windows hosts."""
        try:
            if hasattr(os, "getloadavg"):
                load1, load5, load15 = os.getloadavg()
                cores = os.cpu_count() or 4
                norm_load = load1 / cores
                
                if norm_load > 2.0: return "RED"
                if norm_load > 1.5: return "ORANGE"
                if norm_load > 1.0: return "YELLOW"
                return "GREEN"

            # Windows / cross-platform fallback using psutil metrics
            try:
                import psutil
                cpu = psutil.cpu_percent(interval=None)
                mem = psutil.virtual_memory().percent
                if cpu > 90.0 or mem > 90.0:
                    return "RED"
                if cpu > 75.0 or mem > 80.0:
                    return "ORANGE"
                if cpu > 60.0 or mem > 70.0:
                    return "YELLOW"
                return "GREEN"
            except Exception:
                # Blind on this host (psutil missing or unreadable):
                # report UNKNOWN, never a healthy GREEN.
                return "UNKNOWN"
        except Exception:
            return "UNKNOWN"

    def admit_job(self, budget_class):
        """Determines if a job can start, triggering backoff if not."""
        if time.time() < self.recovery_end_time:
            self.state = "RECOVERY"
            return False

        current_pressure = self.measure_pressure()
        budget_class = str(budget_class or "LIGHT").upper()
        
        if current_pressure == "RED":
            self.trigger_quiesce()
            return False
            
        if current_pressure == "ORANGE" and budget_class in ("HEAVY", "MEDIUM"):
            return False  # FAST_RAMP_DOWN

        if budget_class == "HEAVY" and self.active_jobs["HEAVY"] >= self.MAX_HEAVY_JOBS:
            return False

        # SLOW_RAMP_UP
        self.state = current_pressure
        return True

    def start_job(self, budget_class: str) -> bool:
        """Admit and increment active job count if admitted."""
        budget_class = str(budget_class or "LIGHT").upper()
        if self.admit_job(budget_class):
            if budget_class in self.active_jobs:
                self.active_jobs[budget_class] += 1
            return True
        return False

    def finish_job(self, budget_class: str) -> None:
        """Decrement active job count on completion."""
        budget_class = str(budget_class or "LIGHT").upper()
        if budget_class in self.active_jobs and self.active_jobs[budget_class] > 0:
            self.active_jobs[budget_class] -= 1

    def trigger_quiesce(self):
        """Forces the system into a recovery window and stops polling."""
        self.state = "RECOVERY"
        self.recovery_end_time = time.time() + self.RECOVERY_WINDOW
        
    def get_poll_interval(self):
        """BOUNDED_BACKOFF for queue polling."""
        if self.state == "GREEN": return self.POLL_INTERVAL_BASE
        if self.state == "YELLOW": return self.POLL_INTERVAL_BASE * 2
        if self.state == "ORANGE": return self.POLL_INTERVAL_BASE * 4
        if self.state == "RECOVERY": return min(30, self.RECOVERY_WINDOW)
        return self.POLL_INTERVAL_BASE
        
    def post_run_resource_snapshot(self):
        """Capture metrics after a run finishes to track cleanup."""
        load = os.getloadavg() if hasattr(os, "getloadavg") else None
        snapshot = {
            "load": load,
            "state": self.state,
            "timestamp": time.time()
        }
        if load is None:
            try:
                import psutil
                snapshot["cpu_percent"] = psutil.cpu_percent(interval=None)
                snapshot["memory_percent"] = psutil.virtual_memory().percent
            except Exception:
                pass
        return snapshot

# Global singleton
governor = HostPressureController()
