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

def admission_limit(requirement: Requirement, host: Host) -> str | None:
    """None when the host can take the work, else the limitation that blocks it."""
    missing = sorted(requirement.capabilities - host.capabilities)
    if missing:
        return f"missing capabilities {missing}"
    if requirement.privacy is not None and host.privacy != requirement.privacy:
        return f"privacy {host.privacy} is not {requirement.privacy}"
    if host.health in {RESOURCE_PAUSE, EMERGENCY}:
        return f"health {host.health}"
    if host.active_leases >= host.profile.max_total_slots:
        return "total slots full"
    if host.health == HEALTHY:
        if requirement.is_heavy and host.active_heavy_leases >= host.profile.max_heavy_slots:
            return "heavy slots full"
        return None
    if host.health == PRESSURED:
        if requirement.is_heavy:
            return "health PRESSURED blocks heavy work"
        return None
    if host.health == DEGRADED:
        if host.privacy == "own":
            return "health DEGRADED pauses own devices"
        if host.active_leases >= max(1, host.profile.max_total_slots // 2):
            return "health DEGRADED slot limit"
        return None
    return f"health {host.health}"


def can_admit(requirement: Requirement, host: Host) -> bool:
    """Evaluate host capacity policy."""
    return admission_limit(requirement, host) is None

def eligible(requirement, hosts):
    return [h for h in hosts if can_admit(requirement, h)]

def select(requirement, hosts):
    """Cheapest eligible host, stable by device id. Never an incapable host."""
    candidates = eligible(requirement, hosts)
    if not candidates:
        limits = [f"{host.device_id}: {admission_limit(requirement, host)}" for host in hosts]
        detail = "; ".join(limits) if limits else "no hosts"
        raise NoEligibleHost(
            f"no host can take {sorted(requirement.capabilities)} for heavy={requirement.is_heavy}: {detail}"
        )
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
