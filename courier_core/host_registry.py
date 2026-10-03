from dataclasses import dataclass, field
from typing import Set, List, Dict, Optional, Union

@dataclass
class HostProfile:
    host_id: str
    os_family: str
    capabilities: Set[str] = field(default_factory=set)

@dataclass
class WorkkeyRequirements:
    required_os: Optional[str] = None
    required_capabilities: Set[str] = field(default_factory=set)

class HostCapabilityRegistry:
    """
    Minimal device/host capability registry.
    Maps workkey requirements to ELIGIBLE HOSTS or BLOCKED_RIGHT_HOST.
    """
    def __init__(self):
        self._hosts: Dict[str, HostProfile] = {}

    def register_host(self, host_id: str, os_family: str, capabilities: Set[str]) -> None:
        """Advertises a host's OS and capabilities to the registry."""
        self._hosts[host_id] = HostProfile(host_id, os_family, set(capabilities))

    def deregister_host(self, host_id: str) -> None:
        self._hosts.pop(host_id, None)

    def is_known(self, host_id: str) -> bool:
        return host_id in self._hosts


    def find_eligible_hosts(self, req: WorkkeyRequirements) -> Union[List[str], str]:
        """
        Returns deterministically sorted ELIGIBLE HOSTS or 'BLOCKED_RIGHT_HOST'.
        """
        eligible = []
        for host in self._hosts.values():
            if req.required_os and host.os_family != req.required_os:
                continue
            if not req.required_capabilities.issubset(host.capabilities):
                continue
            eligible.append(host.host_id)

        if not eligible:
            return "BLOCKED_RIGHT_HOST"
            
        # Guarantee deterministic selection order (lexicographical)
        return sorted(eligible)

