"""Capability registry, host selection and host-qualified evidence.

A workkey declares what it needs; Symphony picks an eligible, healthy host.
Evidence carries the device that produced it and is accepted for a
requirement only if that device actually has the required capability, so
Linux evidence can never satisfy a Windows-native requirement.
"""
from dataclasses import dataclass
from typing import Optional

HEALTHY, BUSY, IDLE, DEGRADED, OFFLINE, RECOVERING = "HEALTHY", "BUSY", "IDLE", "DEGRADED", "OFFLINE", "RECOVERING"
SELECTABLE = {HEALTHY, IDLE, BUSY}


@dataclass(frozen=True)
class Host:
    device_id: str
    capabilities: frozenset       # e.g. {"python", "linux"}, {"windows_native", "python"}
    health: str = HEALTHY
    cost_per_hour_eur: float = 0.0
    privacy: str = "own"          # "own" (user's device) or "hosted"
    active_leases: int = 0
    max_leases: int = 1


@dataclass(frozen=True)
class Requirement:
    capabilities: frozenset
    privacy: Optional[str] = None    # "own" forces the user's own devices


class NoEligibleHost(Exception):
    pass


def eligible(requirement, hosts):
    return [h for h in hosts
            if requirement.capabilities <= h.capabilities and h.health in SELECTABLE
            and h.active_leases < h.max_leases
            and (requirement.privacy is None or h.privacy == requirement.privacy)]


def select(requirement, hosts):
    """Cheapest eligible host, idle before busy, then stable by device id. Never an incapable host."""
    candidates = eligible(requirement, hosts)
    if not candidates:
        raise NoEligibleHost(f"no healthy host offers {sorted(requirement.capabilities)}")
    return sorted(candidates, key=lambda h: (h.cost_per_hour_eur, h.health == BUSY, h.device_id))[0]


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
