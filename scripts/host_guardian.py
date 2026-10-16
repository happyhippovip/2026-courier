import enum
import os
import platform
import socket
import psutil
from dataclasses import dataclass

AUTHORIZED_WINDOWS_HOSTNAMES = {"DESKTOP-JDPRUGR"}

class HostIdentityError(RuntimeError):
    """Raised when host identity verification fails closed."""
    pass

def verify_windows_hostname(
    expected_hostname: str | set[str] | list[str] | None = None,
    require_windows: bool = True
) -> tuple[bool, str]:
    """
    Verbindliche Prüfung des Windows-Hostnamens gemäß FRZ-01.
    Prüft socket.gethostname() und os.environ.get('COMPUTERNAME').
    Case-insensitiver Vergleich auf Windows.
    Gibt (True, actual_hostname) zurück wenn autorisiert,
    sonst (False, reason).
    """
    current_os = platform.system()
    if require_windows and current_os != "Windows":
        return False, f"OS_MISMATCH: expected Windows, running on {current_os}"

    socket_host = socket.gethostname()
    env_host = os.environ.get("COMPUTERNAME")

    if not socket_host or not socket_host.strip():
        return False, "HOSTNAME_EMPTY: socket.gethostname() returned empty or whitespace"

    actual_hostname = socket_host.strip()

    if current_os == "Windows" and env_host:
        if socket_host.lower() != env_host.strip().lower():
            return False, f"HOSTNAME_INCONSISTENT: socket '{socket_host}' != COMPUTERNAME '{env_host}'"

    if expected_hostname is None:
        expected_set = {h.lower() for h in AUTHORIZED_WINDOWS_HOSTNAMES}
    elif isinstance(expected_hostname, (set, list, tuple)):
        expected_set = {h.lower() for h in expected_hostname}
    else:
        expected_set = {expected_hostname.lower()}

    if actual_hostname.lower() not in expected_set:
        return False, f"HOSTNAME_MISMATCH: actual '{actual_hostname}' not in authorized {sorted(expected_set)}"

    return True, actual_hostname


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
        try:
            self._last_swap_used = psutil.swap_memory().used
        except Exception:
            self._last_swap_used = 0
        self._calm_streak = 0
        self.required_calm_streak = 3

    def verify_host_identity(
        self,
        expected_hostname: str | set[str] | list[str] | None = None,
        require_windows: bool = True
    ) -> tuple[bool, str]:
        """Verify host identity, failing closed to STABILIZING on mismatch."""
        valid, msg = verify_windows_hostname(
            expected_hostname=expected_hostname,
            require_windows=require_windows
        )
        if not valid:
            self.state = HostState.STABILIZING
        return valid, msg

    def diagnose_capacity(self) -> str:
        """Classify capacity state into canonical states."""
        if os.environ.get("RESOURCE_PAUSE"):
            return "RESOURCE_PAUSED"
        try:
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            memory_pressure = mem.percent / 100.0
            disk_floor_gb = disk.free / (1024 ** 3)
        except Exception:
            return "UNKNOWN_CAPACITY"

        if memory_pressure > 0.80:
            return "LOW_MEMORY"
        if disk_floor_gb < 2.0:
            return "LOW_DISK"
        if self.admitted_heavy >= self.max_heavy_local_jobs:
            return "HEAVY_JOB_ALREADY_ACTIVE"
        return "HEALTHY"

    def evaluate_admission(self) -> AdmissionState:
        if os.environ.get("RESOURCE_PAUSE"):
            self.state = HostState.STABILIZING
            return AdmissionState.CLOSED

        try:
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            disk = psutil.disk_usage('/')
            
            memory_pressure = mem.percent / 100.0
            swap_increasing = swap.used > self._last_swap_used
            self._last_swap_used = swap.used
            disk_floor_gb = disk.free / (1024 ** 3)
        except Exception:
            self._calm_streak = 0
            self.state = HostState.STABILIZING
            return AdmissionState.CLOSED
        
        is_high_pressure = memory_pressure > 0.80 or swap_increasing or disk_floor_gb < 2.0
        is_medium_pressure = memory_pressure > 0.70 or self.cleanup_unknown
        
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

    def request_heavy_lease(self) -> bool:
        if self.diagnose_capacity() != "HEALTHY":
            return False
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
        else:
            self.cleanup_unknown = False
            
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
