"""Capability registry, host selection and host-qualified evidence.

A workkey declares what it needs; Symphony picks an eligible, healthy host.
Evidence carries the device that produced it and is accepted for a
requirement only if that device actually has the required capability, so
Linux evidence can never satisfy a Windows-native requirement.
"""
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

# Host health states as per Issue 76
HEALTHY = "HEALTHY"
PRESSURED = "PRESSURED"
DEGRADED = "DEGRADED"
RESOURCE_PAUSE = "RESOURCE_PAUSE"
EMERGENCY = "EMERGENCY"

SELECTABLE = {HEALTHY, PRESSURED, DEGRADED} # RESOURCE_PAUSE/EMERGENCY exclude new general work

@dataclass(frozen=True)
class HostProfile:
    name: str
    max_total_slots: int
    max_heavy_slots: int
    allow_spawn: bool = True

PROFILES = {
    "low-resource laptop": HostProfile("low-resource laptop", 4, 1),
    "normal laptop": HostProfile("normal laptop", 16, 4),
    "workstation": HostProfile("workstation", 64, 16),
    "CI/hosted runner": HostProfile("CI/hosted runner", 32, 8),
    "dedicated worker": HostProfile("dedicated worker", 128, 32)
}

@dataclass(frozen=True)
class Host:
    device_id: str
    capabilities: frozenset       # e.g. {"python", "linux"}, {"windows_native", "python"}
    profile: HostProfile = PROFILES["normal laptop"]
    health: str = HEALTHY
    cost_per_hour_eur: float = 0.0
    privacy: str = "own"          # "own" (user's device) or "hosted"
    active_leases: int = 0
    active_heavy_leases: int = 0

@dataclass(frozen=True)
class Requirement:
    capabilities: frozenset
    privacy: str | None = None    # "own" forces the user's own devices
    is_heavy: bool = False

class NoEligibleHost(Exception):
    pass

def can_admit(requirement: Requirement, host: Host) -> bool:
    """Evaluate host capacity policy."""
    if not requirement.capabilities.issubset(host.capabilities):
        return False
    if requirement.privacy is not None and host.privacy != requirement.privacy:
        return False
    if host.health in {RESOURCE_PAUSE, EMERGENCY}:
        return False
    
    # Check absolute capacity
    if host.active_leases >= host.profile.max_total_slots:
        return False
        
    if host.health == HEALTHY:
        # Full admission
        if requirement.is_heavy and host.active_heavy_leases >= host.profile.max_heavy_slots:
            return False
        return True
    elif host.health == PRESSURED:
        # no new heavy work
        if requirement.is_heavy:
            return False
        return True
    elif host.health == DEGRADED:
        # reduce concurrency, prefer remote, pause local
        if host.privacy == "own":
            return False
        # Treat max slots as halved
        if host.active_leases >= max(1, host.profile.max_total_slots // 2):
            return False
        return True
        
    return False

def eligible(requirement, hosts):
    return [h for h in hosts if can_admit(requirement, h)]

def select(requirement, hosts):
    """Cheapest eligible host, stable by device id. Never an incapable host."""
    candidates = eligible(requirement, hosts)
    if not candidates:
        raise NoEligibleHost(f"no healthy host offers {sorted(requirement.capabilities)} for heavy={requirement.is_heavy}")
    return sorted(candidates, key=lambda h: (h.cost_per_hour_eur, h.device_id))[0]

@dataclass(frozen=True)
class Evidence:
    workkey: str
    capability: str
    device_id: str
    artifact_sha256: str
    passed: bool

def accept_evidence(evidence, required_capability, hosts):
    """Return (accepted, reason). Evidence counts only from a device that has the capability."""
    by_id = {h.device_id: h for h in hosts}
    host = by_id.get(evidence.device_id)
    if host is None:
        return False, f"unknown device {evidence.device_id}"
    if evidence.capability != required_capability or required_capability not in host.capabilities:
        return False, f"{evidence.device_id} cannot evidence {required_capability}"
    if not evidence.passed:
        return False, "evidence did not pass"
    return True, "accepted"
