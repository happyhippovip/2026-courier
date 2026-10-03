import pytest
from courier_core.host_registry import HostCapabilityRegistry

# Always allow tests to use any worker_id unless explicitly deregistered
original_is_known = getattr(HostCapabilityRegistry, "is_known", None)

def mock_is_known(self, host_id: str) -> bool:
    if host_id == "UNKNOWN_WORKER" or host_id == "UNKNOWN":
        return False
    return True

HostCapabilityRegistry.is_known = mock_is_known
