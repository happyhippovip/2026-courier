import enum
import psutil
import os
from dataclasses import dataclass

class HostState(enum.Enum):
    NOMINAL = "NOMINAL"
    WATCH = "WATCH"
    PRESSURED = "PRESSURED"
    DEGRADED = "DEGRADED"
    RESOURCE_PAUSE = "RESOURCE_PAUSE"
    EMERGENCY = "EMERGENCY"
    RECOVERING = "RECOVERING"

@dataclass
class HostMetrics:
    desired_agent_slots: int
    admitted_local_light: int
    admitted_local_heavy: int
    waiting: int
    handle_pressure: float
    memory_pressure: float
    process_count: int
    owned_descendants: int
    heavy_job_lease: int
    host_health: str

class HostGuardian:
    def __init__(self, max_heavy_local_jobs: int = 1):
        self.max_heavy_local_jobs = max_heavy_local_jobs
        self.state = HostState.NOMINAL
        self.admitted_heavy = 0
        self.admitted_light = 0

    def evaluate_pressure(self) -> HostState:
        # In a real environment, read psutil memory and handle counts.
        # For Courier #76, we focus on safe capacity admission.
        mem = psutil.virtual_memory()
        memory_pressure = mem.percent / 100.0

        if memory_pressure > 0.90:
            self.state = HostState.EMERGENCY
        elif memory_pressure > 0.80:
            self.state = HostState.RESOURCE_PAUSE
        elif memory_pressure > 0.70:
            self.state = HostState.PRESSURED
        else:
            self.state = HostState.NOMINAL
            
        return self.state

    def request_heavy_lease(self) -> bool:
        self.evaluate_pressure()
        if self.state in [HostState.EMERGENCY, HostState.RESOURCE_PAUSE]:
            return False
            
        if self.admitted_heavy < self.max_heavy_local_jobs:
            self.admitted_heavy += 1
            return True
        return False

    def release_heavy_lease(self):
        if self.admitted_heavy > 0:
            self.admitted_heavy -= 1
            
    def get_metrics(self) -> HostMetrics:
        return HostMetrics(
            desired_agent_slots=64,
            admitted_local_light=self.admitted_light,
            admitted_local_heavy=self.admitted_heavy,
            waiting=0,
            handle_pressure=0.0,
            memory_pressure=psutil.virtual_memory().percent / 100.0,
            process_count=len(psutil.pids()),
            owned_descendants=0,
            heavy_job_lease=self.max_heavy_local_jobs,
            host_health=self.state.value
        )
