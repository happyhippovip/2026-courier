import platform
import enum
from dataclasses import dataclass, field
from typing import List, Optional

class AdmissionResult(enum.Enum):
    ELIGIBLE = "ELIGIBLE"
    BLOCKED = "BLOCKED"
    HUMAN_REQUIRED = "HUMAN_REQUIRED"

@dataclass
class TaskPacket:
    goal_id: str
    task_id: str
    attempt_id: int
    dependencies: List[str]
    required_platform: str
    required_capability: str
    logical_scope: str
    writer_required: bool
    budget: float
    result_contract: str
    human_gate_class: str
    authoritative_context_refs: List[str] = field(default_factory=list)

@dataclass
class HostState:
    platform: str
    capabilities: List[str]
    active_scopes: List[str]
    available_budget: float
    unresolved_dependencies: List[str]

class PreDispatchAdmission:
    def __init__(self, host_state: HostState):
        self.host_state = host_state
        
    def evaluate(self, packet: TaskPacket) -> AdmissionResult:
        if packet.human_gate_class and packet.human_gate_class.upper() != "NONE":
            return AdmissionResult.HUMAN_REQUIRED
            
        for dep in packet.dependencies:
            if dep in self.host_state.unresolved_dependencies:
                return AdmissionResult.BLOCKED
                
        # Normalize platforms (e.g. 'mac' -> 'darwin', 'windows' -> 'win32')
        req_plat = packet.required_platform.lower()
        if req_plat == "mac":
            req_plat = "darwin"
        elif req_plat == "windows":
            req_plat = "win32"
            
        if req_plat != "any" and req_plat != self.host_state.platform.lower():
            return AdmissionResult.BLOCKED
            
        if packet.required_capability != "any" and packet.required_capability not in self.host_state.capabilities:
            return AdmissionResult.BLOCKED
            
        if packet.writer_required and packet.logical_scope in self.host_state.active_scopes:
            return AdmissionResult.BLOCKED
            
        if packet.budget > self.host_state.available_budget:
            return AdmissionResult.BLOCKED
            
        return AdmissionResult.ELIGIBLE
