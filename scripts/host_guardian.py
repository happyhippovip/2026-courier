import enum
import psutil
import os
from dataclasses import dataclass

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

class HostGuardian:
    def __init__(self, max_heavy_local_jobs: int = 1):
        self.max_heavy_local_jobs = max_heavy_local_jobs
        self.state = HostState.NORMAL
        self.admitted_heavy = 0
        self.admitted_light = 0
        self.cleanup_unknown = False
        self._last_swap_used = psutil.swap_memory().used

    def evaluate_admission(self) -> AdmissionState:
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        disk = psutil.disk_usage('/')
        
        memory_pressure = mem.percent / 100.0
        swap_increasing = swap.used > self._last_swap_used
        self._last_swap_used = swap.used
        disk_floor_gb = disk.free / (1024 ** 3)
        
        if memory_pressure > 0.80 or swap_increasing or disk_floor_gb < 2.0:
            if self.state not in [HostState.STABILIZING, HostState.RESTART_RECOMMENDED, HostState.RECOVERING]:
                self.state = HostState.STABILIZING
        elif memory_pressure > 0.70 or self.cleanup_unknown:
            self.state = HostState.LIGHT_ONLY
        else:
            self.state = HostState.NORMAL

        if self.state in [HostState.STABILIZING, HostState.RESTART_RECOMMENDED, HostState.RECOVERING]:
            return AdmissionState.CLOSED
        elif self.state == HostState.LIGHT_ONLY:
            return AdmissionState.LIGHT_ONLY
        else:
            return AdmissionState.OPEN

    def stabilize(self, resources) -> HostState:
        if self.state != HostState.STABILIZING:
            return self.state
            
        for res in resources:
            if not getattr(res, "is_alive", lambda: False)():
                if hasattr(res, "terminate"):
                    res.terminate()
            elif getattr(res, "is_idle", lambda: False)():
                if hasattr(res, "terminate"):
                    res.terminate()
                
        self.evaluate_admission()
        
        if self.state == HostState.STABILIZING:
            self.state = HostState.RESTART_RECOMMENDED
            
        return self.state

    def request_heavy_lease(self) -> bool:
        admission = self.evaluate_admission()
        if admission != AdmissionState.OPEN:
            return False
            
        if self.admitted_heavy < self.max_heavy_local_jobs:
            self.admitted_heavy += 1
            return True
        return False

    def release_heavy_lease(self, cleanup_proven: bool = True):
        if self.admitted_heavy > 0:
            self.admitted_heavy -= 1
        
        if not cleanup_proven:
            self.cleanup_unknown = True
            
    def get_metrics(self) -> HostMetrics:
        return HostMetrics(
            desired_agent_slots=64,
            admitted_local_light=self.admitted_light,
            admitted_local_heavy=self.admitted_heavy,
            waiting=0,
            handle_pressure=0.0,
            memory_pressure=psutil.virtual_memory().percent / 100.0,
            swap_pressure=psutil.swap_memory().percent / 100.0,
            disk_floor_gb=psutil.disk_usage('/').free / (1024 ** 3),
            process_count=len(psutil.pids()),
            owned_descendants=0,
            heavy_job_lease=self.max_heavy_local_jobs,
            host_health=self.state.value,
            cleanup_unknown=self.cleanup_unknown
        )
