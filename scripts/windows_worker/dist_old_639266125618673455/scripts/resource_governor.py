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
        """Mock reading system metrics. Avoids third-party dependencies."""
        try:
            if hasattr(os, "getloadavg"):
                load1, load5, load15 = os.getloadavg()
                cores = os.cpu_count() or 4
                norm_load = load1 / cores
                
                if norm_load > 2.0: return "RED"
                if norm_load > 1.5: return "ORANGE"
                if norm_load > 1.0: return "YELLOW"
            return "GREEN"
        except Exception:
            return "UNKNOWN"

    def admit_job(self, budget_class):
        """Determines if a job can start, triggering backoff if not."""
        if time.time() < self.recovery_end_time:
            self.state = "RECOVERY"
            return False

        current_pressure = self.measure_pressure()
        
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
        return {
            "load": os.getloadavg() if hasattr(os, "getloadavg") else None,
            "state": self.state,
            "timestamp": time.time()
        }

# Global singleton
governor = HostPressureController()
