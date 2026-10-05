"""Provider circuit breaker and availability tracking."""
from enum import Enum
from dataclasses import dataclass, field
import time
from typing import Dict, Optional, List

class ProviderAvailability(Enum):
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    RECOVERY_PROBE_DUE = "RECOVERY_PROBE_DUE"

class WorkClassification(Enum):
    LOCAL_READY = "LOCAL_READY"
    PROVIDER_READY = "PROVIDER_READY"
    WAITING_PROVIDER = "WAITING_PROVIDER"
    WAITING_AUTHORITY = "WAITING_AUTHORITY"
    RESOURCE_PAUSED = "RESOURCE_PAUSED"
    COMPLETE = "COMPLETE"

@dataclass
class ProviderState:
    connection_id: str
    capability_class: str
    availability: ProviderAvailability = ProviderAvailability.AVAILABLE
    reset_time: Optional[float] = None
    retry_after: Optional[float] = None
    open_circuit: bool = False
    
    def update_from_error(self, error_code: int, retry_metadata: dict):
        if error_code == 429:
            self.availability = ProviderAvailability.QUOTA_EXHAUSTED
            self.open_circuit = True
            if "retry_after" in retry_metadata:
                self.retry_after = time.time() + float(retry_metadata["retry_after"])
            if "reset_time" in retry_metadata:
                self.reset_time = float(retry_metadata["reset_time"])
        elif error_code in (401, 403):
            self.availability = ProviderAvailability.AUTH_REQUIRED
            self.open_circuit = True
        elif error_code >= 500:
            self.availability = ProviderAvailability.PROVIDER_UNAVAILABLE
            self.open_circuit = True
        
    def check_recovery(self) -> bool:
        if not self.open_circuit:
            return True
            
        now = time.time()
        if self.retry_after and now >= self.retry_after:
            self.availability = ProviderAvailability.RECOVERY_PROBE_DUE
            return True
            
        if self.reset_time and now >= self.reset_time:
            self.availability = ProviderAvailability.RECOVERY_PROBE_DUE
            return True
            
        return False

class CircuitBreaker:
    def __init__(self):
        self.providers: Dict[str, ProviderState] = {}
        
    def get_state(self, connection_id: str, capability_class: str) -> ProviderState:
        key = f"{connection_id}|{capability_class}"
        if key not in self.providers:
            self.providers[key] = ProviderState(connection_id=connection_id, capability_class=capability_class)
        return self.providers[key]
        
    def record_error(self, connection_id: str, capability_class: str, error_code: int, metadata: dict):
        state = self.get_state(connection_id, capability_class)
        state.update_from_error(error_code, metadata)
        
    def record_success(self, connection_id: str, capability_class: str):
        state = self.get_state(connection_id, capability_class)
        state.availability = ProviderAvailability.AVAILABLE
        state.open_circuit = False
        state.reset_time = None
        state.retry_after = None

class AuthorizedFallbackRouter:
    def __init__(self, circuit_breaker: CircuitBreaker):
        self.circuit_breaker = circuit_breaker
        self.authorized_connections: List[dict] = []
        
    def register_connection(self, connection_id: str, capabilities: List[str], authority_constraints: dict):
        self.authorized_connections.append({
            "id": connection_id,
            "capabilities": capabilities,
            "constraints": authority_constraints
        })
        
    def find_fallback(self, required_capability: str, project_constraints: dict) -> Optional[str]:
        # Filter by capability, authority constraints, and circuit state
        for conn in self.authorized_connections:
            if required_capability in conn["capabilities"]:
                # Check constraints (simplified for demo)
                if self._check_constraints(conn["constraints"], project_constraints):
                    state = self.circuit_breaker.get_state(conn["id"], required_capability)
                    if not state.open_circuit or state.check_recovery():
                        return conn["id"]
        return None
        
    def _check_constraints(self, connection_constraints: dict, project_constraints: dict) -> bool:
        for k, v in project_constraints.items():
            if k in connection_constraints and connection_constraints[k] != v:
                return False
        return True
