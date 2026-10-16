import enum
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    psutil = None
    _HAS_PSUTIL = False

class HostState(enum.Enum):
    NORMAL = "NORMAL"
    STABILIZING = "STABILIZING"
    LIGHT_ONLY = "LIGHT_ONLY"
    RESTART_RECOMMENDED = "RESTART_RECOMMENDED"
    RECOVERING = "RECOVERING"

class AdmissionState(enum.Enum):
    OPEN = "OPEN"
    LIGHT_ONLY = "LIGHT_ONLY"
    CLOSED = "CLOSED"

class CapacityState(str, enum.Enum):
    HEALTHY = "HEALTHY"
    LOW_MEMORY = "LOW_MEMORY"
    LOW_DISK = "LOW_DISK"
    RESOURCE_PAUSED = "RESOURCE_PAUSED"
    HEAVY_JOB_ALREADY_ACTIVE = "HEAVY_JOB_ALREADY_ACTIVE"
    UNKNOWN_CAPACITY = "UNKNOWN_CAPACITY"

@dataclass(frozen=True)
class HeavyAdmissionDecision:
    admitted: bool
    state: CapacityState
    reason: str

    def __iter__(self):
        return iter((self.admitted, self.state, self.reason))

@dataclass
class HostMetrics:
    desired_agent_slots: int
    admitted_local_light: int
    admitted_local_heavy: int
    waiting: int
    handle_pressure: float
    memory_pressure: float
    swap_pressure: float
    disk_floor_gb: float
    process_count: int
    owned_descendants: int
    heavy_job_lease: int
    host_health: str
    cleanup_unknown: bool


def is_resource_paused(pause_file: Optional[str] = None) -> bool:
    """Check if host-wide or local RESOURCE_PAUSE is active."""
    if pause_file and os.path.exists(pause_file):
        return True
    pause_env = os.environ.get("COURIER_RESOURCE_PAUSE_FILE")
    if pause_env and os.path.exists(pause_env):
        return True
    local_pause = os.path.join(os.getcwd(), "RESOURCE_PAUSE")
    if os.path.exists(local_pause):
        return True
    repo_pause = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "RESOURCE_PAUSE")
    if os.path.exists(repo_pause):
        return True
    if os.environ.get("COURIER_ADMISSION_STATE") in ("CLOSED", "BLOCKED", "RESOURCE_PAUSE"):
        return True
    return False


class HostGuardian:
    def __init__(self, max_heavy_local_jobs: int = 1):
        self.max_heavy_local_jobs = max_heavy_local_jobs
        self.state = HostState.NORMAL
        self.admitted_heavy = 0
        self.admitted_light = 0
        self.cleanup_unknown = False
        try:
            self._last_swap_used = psutil.swap_memory().used if _HAS_PSUTIL and psutil else 0
        except Exception:
            self._last_swap_used = 0
        self._calm_streak = 0
        self.required_calm_streak = 3

    def evaluate_admission(self, telemetry: Optional[Any] = None) -> AdmissionState:
        if is_resource_paused():
            self._calm_streak = 0
            self.state = HostState.STABILIZING
            return AdmissionState.CLOSED

        try:
            if isinstance(telemetry, dict):
                if telemetry.get("unknown") or telemetry.get("status") == "UNKNOWN":
                    self._calm_streak = 0
                    self.state = HostState.STABILIZING
                    return AdmissionState.CLOSED
                mem_p = telemetry.get("memory_percent")
                if mem_p is None and "memory_pressure" in telemetry:
                    mem_p = telemetry["memory_pressure"] * 100.0
                disk_gb = telemetry.get("disk_free_gb")
                swap_used = telemetry.get("swap_used", self._last_swap_used)
                if mem_p is None or disk_gb is None:
                    self._calm_streak = 0
                    self.state = HostState.STABILIZING
                    return AdmissionState.CLOSED
                memory_pressure = float(mem_p) / 100.0
                disk_floor_gb = float(disk_gb)
                swap_increasing = swap_used > self._last_swap_used
                self._last_swap_used = swap_used
            else:
                if not _HAS_PSUTIL or psutil is None:
                    self._calm_streak = 0
                    self.state = HostState.STABILIZING
                    return AdmissionState.CLOSED

                mem = psutil.virtual_memory()
                swap = psutil.swap_memory()
                try:
                    disk = psutil.disk_usage(os.getcwd())
                except Exception:
                    disk = psutil.disk_usage('/')
                
                memory_pressure = mem.percent / 100.0
                swap_increasing = swap.used > self._last_swap_used
                self._last_swap_used = swap.used
                disk_floor_gb = disk.free / (1024 ** 3)
            
            is_high_pressure = memory_pressure > 0.80 or swap_increasing or disk_floor_gb < 2.0
            is_medium_pressure = memory_pressure > 0.70 or self.cleanup_unknown
        except Exception:
            self._calm_streak = 0
            self.state = HostState.STABILIZING
            return AdmissionState.CLOSED
        
        if is_high_pressure:
            self._calm_streak = 0
            if self.state not in [HostState.STABILIZING, HostState.RESTART_RECOMMENDED, HostState.RECOVERING]:
                self.state = HostState.STABILIZING
        elif is_medium_pressure:
            self._calm_streak = 0
            self.state = HostState.LIGHT_ONLY
        else:
            if self.state in [HostState.STABILIZING, HostState.RESTART_RECOMMENDED, HostState.RECOVERING, HostState.LIGHT_ONLY]:
                self._calm_streak += 1
                self.state = HostState.RECOVERING
                if self._calm_streak >= self.required_calm_streak:
                    self.state = HostState.NORMAL
            else:
                self._calm_streak += 1
                self.state = HostState.NORMAL

        if self.state in [HostState.STABILIZING, HostState.RESTART_RECOMMENDED, HostState.RECOVERING]:
            return AdmissionState.CLOSED
        elif self.state == HostState.LIGHT_ONLY:
            return AdmissionState.LIGHT_ONLY
        else:
            return AdmissionState.OPEN

    def evaluate_heavy_job_admission(
        self,
        telemetry: Optional[Any] = None,
        pause_file: Optional[str] = None,
    ) -> HeavyAdmissionDecision:
        """Evaluates admission for heavy job execution, distinguishing all 6 canonical states:
        - HEALTHY
        - LOW_MEMORY
        - LOW_DISK
        - RESOURCE_PAUSED
        - HEAVY_JOB_ALREADY_ACTIVE
        - UNKNOWN_CAPACITY
        """
        # 1. Check RESOURCE_PAUSED
        if is_resource_paused(pause_file):
            return HeavyAdmissionDecision(
                admitted=False,
                state=CapacityState.RESOURCE_PAUSED,
                reason="RESOURCE_PAUSED: active resource pause file or environment flag",
            )

        # 2. Extract metrics / check UNKNOWN_CAPACITY
        try:
            if isinstance(telemetry, dict):
                if telemetry.get("unknown") or telemetry.get("status") == "UNKNOWN":
                    return HeavyAdmissionDecision(
                        admitted=False,
                        state=CapacityState.UNKNOWN_CAPACITY,
                        reason="UNKNOWN_CAPACITY: host telemetry explicitly marked unknown",
                    )
                mem_val = telemetry.get("memory_percent")
                if mem_val is None and "memory_pressure" in telemetry:
                    mem_val = telemetry["memory_pressure"] * 100.0
                disk_val = telemetry.get("disk_free_gb")
                if disk_val is None and "disk_free_bytes" in telemetry:
                    disk_val = telemetry["disk_free_bytes"] / (1024 ** 3)
                if (
                    mem_val is None
                    or disk_val is None
                    or not isinstance(mem_val, (int, float))
                    or not isinstance(disk_val, (int, float))
                    or mem_val < 0
                    or disk_val < 0
                ):
                    return HeavyAdmissionDecision(
                        admitted=False,
                        state=CapacityState.UNKNOWN_CAPACITY,
                        reason="UNKNOWN_CAPACITY: host telemetry metrics missing, invalid or corrupt",
                    )
                mem_percent = float(mem_val)
                disk_floor_gb = float(disk_val)
            elif telemetry is not None:
                if getattr(telemetry, "unknown", False):
                    return HeavyAdmissionDecision(
                        admitted=False,
                        state=CapacityState.UNKNOWN_CAPACITY,
                        reason="UNKNOWN_CAPACITY: telemetry object marked unknown",
                    )
                mem_val = getattr(telemetry, "percent", getattr(telemetry, "memory_percent", None))
                if mem_val is None:
                    mp = getattr(telemetry, "memory_pressure", None)
                    if mp is not None:
                        mem_val = mp * 100.0
                disk_val = getattr(telemetry, "disk_free_gb", None)
                if disk_val is None and hasattr(telemetry, "free"):
                    disk_val = getattr(telemetry, "free") / (1024 ** 3)
                if mem_val is None or disk_val is None:
                    return HeavyAdmissionDecision(
                        admitted=False,
                        state=CapacityState.UNKNOWN_CAPACITY,
                        reason="UNKNOWN_CAPACITY: telemetry object missing required metrics",
                    )
                mem_percent = float(mem_val)
                disk_floor_gb = float(disk_val)
            else:
                if not _HAS_PSUTIL or psutil is None:
                    return HeavyAdmissionDecision(
                        admitted=False,
                        state=CapacityState.UNKNOWN_CAPACITY,
                        reason="UNKNOWN_CAPACITY: psutil not available to sample host metrics",
                    )
                mem = psutil.virtual_memory()
                mem_percent = float(mem.percent)
                try:
                    disk = psutil.disk_usage(os.getcwd())
                except Exception:
                    disk = psutil.disk_usage('/')
                disk_floor_gb = float(disk.free) / (1024 ** 3)
        except Exception as e:
            return HeavyAdmissionDecision(
                admitted=False,
                state=CapacityState.UNKNOWN_CAPACITY,
                reason=f"UNKNOWN_CAPACITY: unhandled error reading host telemetry: {e}",
            )

        # 3. Check LOW_MEMORY
        if mem_percent > 80.0:
            return HeavyAdmissionDecision(
                admitted=False,
                state=CapacityState.LOW_MEMORY,
                reason=f"LOW_MEMORY: memory utilization {mem_percent:.1f}% exceeds 80.0% threshold",
            )

        # 4. Check LOW_DISK
        if disk_floor_gb < 2.0:
            return HeavyAdmissionDecision(
                admitted=False,
                state=CapacityState.LOW_DISK,
                reason=f"LOW_DISK: free disk space {disk_floor_gb:.2f} GB below 2.0 GB safety floor",
            )

        # 5. Check Host State / Previous cleanup
        adm_state = self.evaluate_admission(telemetry=telemetry)
        if adm_state != AdmissionState.OPEN:
            return HeavyAdmissionDecision(
                admitted=False,
                state=CapacityState.LOW_MEMORY,
                reason=f"HOST_NOT_OPEN: guardian admission state is {adm_state.value}",
            )

        # 6. Check HEAVY_JOB_ALREADY_ACTIVE
        if self.admitted_heavy >= self.max_heavy_local_jobs:
            return HeavyAdmissionDecision(
                admitted=False,
                state=CapacityState.HEAVY_JOB_ALREADY_ACTIVE,
                reason=f"HEAVY_JOB_ALREADY_ACTIVE: active heavy jobs {self.admitted_heavy} >= limit {self.max_heavy_local_jobs}",
            )

        # 7. HEALTHY
        return HeavyAdmissionDecision(
            admitted=True,
            state=CapacityState.HEALTHY,
            reason="HEALTHY: host capacity nominal, zero active heavy jobs, admitted",
        )

    def stabilize(self, resources) -> HostState:
        if self.state not in (HostState.STABILIZING, HostState.RESTART_RECOMMENDED):
            return self.state
            
        for res in resources:
            try:
                is_alive = getattr(res, "is_alive", lambda: False)()
                safe_to_retire = getattr(res, "safe_to_retire", lambda: False)()
                
                if not is_alive or safe_to_retire:
                    if hasattr(res, "terminate"):
                        res.terminate()
            except Exception:
                self.cleanup_unknown = True
                
        self.evaluate_admission()
        
        if self.state == HostState.STABILIZING:
            self.state = HostState.RESTART_RECOMMENDED
            
        return self.state

    def request_heavy_lease(self, telemetry: Optional[Any] = None, pause_file: Optional[str] = None) -> bool:
        decision = self.evaluate_heavy_job_admission(telemetry=telemetry, pause_file=pause_file)
        if decision.admitted:
            self.admitted_heavy += 1
            return True
        return False

    def release_heavy_lease(self, cleanup_proven: bool = True):
        if self.admitted_heavy > 0:
            self.admitted_heavy -= 1
        
        if not cleanup_proven:
            self.cleanup_unknown = True
        else:
            self.cleanup_unknown = False
            
    def get_metrics(self) -> HostMetrics:
        try:
            mem_p = psutil.virtual_memory().percent / 100.0 if _HAS_PSUTIL and psutil else 0.0
        except Exception:
            mem_p = 0.0
        try:
            swap_p = psutil.swap_memory().percent / 100.0 if _HAS_PSUTIL and psutil else 0.0
        except Exception:
            swap_p = 0.0
        try:
            disk_gb = (psutil.disk_usage(os.getcwd()).free / (1024 ** 3)) if _HAS_PSUTIL and psutil else 0.0
        except Exception:
            disk_gb = 0.0
        try:
            pids_cnt = len(psutil.pids()) if _HAS_PSUTIL and psutil else 0
        except Exception:
            pids_cnt = 0

        return HostMetrics(
            desired_agent_slots=64,
            admitted_local_light=self.admitted_light,
            admitted_local_heavy=self.admitted_heavy,
            waiting=0,
            handle_pressure=0.0,
            memory_pressure=mem_p,
            swap_pressure=swap_p,
            disk_floor_gb=disk_gb,
            process_count=pids_cnt,
            owned_descendants=0,
            heavy_job_lease=self.max_heavy_local_jobs,
            host_health=self.state.value,
            cleanup_unknown=self.cleanup_unknown
        )

