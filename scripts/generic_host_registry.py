#!/usr/bin/env python3
"""Generic Multi-Host Cluster Registry (Mission Infinite Life Level-5).

Tracks all known host nodes (Primary, Hot Standby, Warm Standby, Sentinel)
with monotonic cluster epochs, deterministic health state tracking,
and single-active-primary authority enforcement.

Invariants:
- Exactly ONE host may hold PRIMARY write authority in any cluster generation.
- Stale host generations are strictly fenced off.
- 0 EUR autonomous spend limit.
"""

from __future__ import annotations

import argparse
import datetime as dt
import enum
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

COURIER_DIR = Path(__file__).resolve().parent.parent
EVENTS_DIR = COURIER_DIR / "events"
HOST_SURVIVAL_DIR = EVENTS_DIR / "host-survival"
HOST_REGISTRY_FILE = HOST_SURVIVAL_DIR / "generic_host_registry.json"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class HostRole(str, enum.Enum):
    PRIMARY = "PRIMARY"
    STANDBY_HOT = "STANDBY_HOT"
    STANDBY_WARM = "STANDBY_WARM"
    SENTINEL = "SENTINEL"
    OBSERVER = "OBSERVER"


class HostHealthState(str, enum.Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNREACHABLE = "UNREACHABLE"
    OFFLINE = "OFFLINE"
    FENCED_OFF = "FENCED_OFF"
    UNKNOWN = "UNKNOWN"


@dataclass
class HostNodeRecord:
    host_id: str
    role: str  # PRIMARY | STANDBY_HOT | STANDBY_WARM | SENTINEL | OBSERVER
    hardware_profile: str  # e.g. "APPLE_SILICON_M_SERIES", "LINUX_X86_64", "RPI_ARM64"
    health_state: str  # HEALTHY | DEGRADED | UNREACHABLE | OFFLINE | FENCED_OFF | UNKNOWN
    current_generation: int
    cluster_epoch: str
    last_heartbeat_at: str
    capabilities: List[str]  # e.g. ["HEAVY_RENDER", "CODE_BUILD", "SENTINEL_PROBE", "LIGHT_OPS"]
    is_fenced: bool = False
    fenced_reason: str = ""
    registered_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GenericHostRegistry:
    """Manages dynamic cluster host topology with strict authority guarantees."""

    def __init__(self, repo_dir: Optional[Path] = None):
        self.repo_dir = repo_dir or COURIER_DIR
        self.registry_dir = self.repo_dir / "events" / "host-survival"
        self.registry_file = self.registry_dir / "generic_host_registry.json"

        self.cluster_epoch = "EPOCH_2026"
        self.active_generation = 1
        self.hosts: Dict[str, HostNodeRecord] = {}

        self._ensure_dir()
        self.load_registry()

    def _ensure_dir(self) -> None:
        self.registry_dir.mkdir(parents=True, exist_ok=True)

    def register_host(
        self,
        host_id: str,
        role: HostRole,
        hardware_profile: str,
        capabilities: List[str],
    ) -> HostNodeRecord:
        """Registers or updates a host node in the cluster."""
        now = utc_now()
        is_primary = (role == HostRole.PRIMARY)

        # If claiming primary, ensure no other un-fenced host holds primary at same generation
        if is_primary:
            for hid, h in self.hosts.items():
                if h.role == HostRole.PRIMARY.value and hid != host_id and not h.is_fenced:
                    h.role = HostRole.STANDBY_HOT.value

        record = HostNodeRecord(
            host_id=host_id,
            role=role.value,
            hardware_profile=hardware_profile,
            health_state=HostHealthState.HEALTHY.value,
            current_generation=self.active_generation if is_primary else 0,
            cluster_epoch=self.cluster_epoch,
            last_heartbeat_at=now,
            capabilities=capabilities,
            is_fenced=False,
            registered_at=now,
        )
        self.hosts[host_id] = record
        self.save_registry()
        return record

    def update_host_heartbeat(
        self,
        host_id: str,
        health_state: HostHealthState = HostHealthState.HEALTHY,
        generation: Optional[int] = None,
    ) -> bool:
        """Records host heartbeat and checks fencing status."""
        if host_id not in self.hosts:
            return False

        h = self.hosts[host_id]
        if h.is_fenced:
            # Fenced hosts cannot heartbeat as healthy primary
            h.health_state = HostHealthState.FENCED_OFF.value
            self.save_registry()
            return False

        h.last_heartbeat_at = utc_now()
        h.health_state = health_state.value
        if generation is not None:
            h.current_generation = generation
        self.save_registry()
        return True

    def get_active_primary(self) -> Optional[HostNodeRecord]:
        """Returns the single active primary host."""
        for h in self.hosts.values():
            if h.role == HostRole.PRIMARY.value and not h.is_fenced and h.health_state == HostHealthState.HEALTHY.value:
                return h
        return None

    def get_standby_candidates(self) -> List[HostNodeRecord]:
        """Returns ordered list of available standby hosts eligible for promotion."""
        standbys = [
            h for h in self.hosts.values()
            if h.role in (HostRole.STANDBY_HOT.value, HostRole.STANDBY_WARM.value)
            and not h.is_fenced
            and h.health_state in (HostHealthState.HEALTHY.value, HostHealthState.UNKNOWN.value)
        ]
        # Sort hot standbys first
        standbys.sort(key=lambda h: (0 if h.role == HostRole.STANDBY_HOT.value else 1, h.host_id))
        return standbys

    def fence_host(self, host_id: str, reason: str = "SUPERSEDED_BY_FAILOVER") -> bool:
        """Fences off a superseded or malfunctioning host."""
        if host_id in self.hosts:
            h = self.hosts[host_id]
            h.is_fenced = True
            h.fenced_reason = reason
            h.health_state = HostHealthState.FENCED_OFF.value
            if h.role == HostRole.PRIMARY.value:
                h.role = HostRole.OBSERVER.value
            self.save_registry()
            return True
        return False

    def promote_standby_to_primary(self, new_primary_host_id: str) -> Tuple[bool, int, str]:
        """Promotes a standby host to primary with monotonically incremented generation."""
        if new_primary_host_id not in self.hosts:
            return False, self.active_generation, f"Host '{new_primary_host_id}' not found in registry"

        candidate = self.hosts[new_primary_host_id]
        if candidate.is_fenced:
            return False, self.active_generation, f"Host '{new_primary_host_id}' is fenced off"

        # 1. Fence all previous primaries
        for hid, h in self.hosts.items():
            if h.role == HostRole.PRIMARY.value and hid != new_primary_host_id:
                self.fence_host(hid, reason=f"SUPERSEDED_BY_NEW_PRIMARY_{new_primary_host_id}")

        # 2. Increment cluster generation
        self.active_generation += 1
        candidate.role = HostRole.PRIMARY.value
        candidate.current_generation = self.active_generation
        candidate.health_state = HostHealthState.HEALTHY.value
        candidate.last_heartbeat_at = utc_now()

        self.save_registry()
        return True, self.active_generation, "PROMOTED_SUCCESSFULLY"

    def save_registry(self) -> Path:
        data = {
            "schema_version": "GENERIC_HOST_REGISTRY_V1",
            "cluster_epoch": self.cluster_epoch,
            "active_generation": self.active_generation,
            "updated_at": utc_now(),
            "autonomous_spend_limit_eur": 0.0,
            "hosts": {k: v.to_dict() for k, v in self.hosts.items()},
        }
        temp = self.registry_file.with_suffix(".tmp")
        temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temp.replace(self.registry_file)
        return self.registry_file

    def load_registry(self) -> None:
        if not self.registry_file.exists():
            return
        try:
            data = json.loads(self.registry_file.read_text(encoding="utf-8"))
            self.cluster_epoch = data.get("cluster_epoch", "EPOCH_2026")
            self.active_generation = data.get("active_generation", 1)
            for k, v in data.get("hosts", {}).items():
                self.hosts[k] = HostNodeRecord(**v)
        except Exception as e:
            print(f"Warning: could not load host registry: {e}")


def init_host_registry() -> GenericHostRegistry:
    reg = GenericHostRegistry()
    if not reg.hosts:
        reg.register_host("home-mac-primary", HostRole.PRIMARY, "APPLE_SILICON_M_SERIES", ["HEAVY_RENDER", "CODE_BUILD", "LIGHT_OPS"])
        reg.register_host("standby-mac-02", HostRole.STANDBY_HOT, "APPLE_SILICON_M_SERIES", ["HEAVY_RENDER", "CODE_BUILD", "LIGHT_OPS"])
        reg.register_host("sentinel-rpi-01", HostRole.SENTINEL, "RPI_ARM64", ["SENTINEL_PROBE"])
    return reg


if __name__ == "__main__":
    reg = init_host_registry()
    p = reg.get_active_primary()
    print(f"✅ Host Registry Initialized: Active Primary={p.host_id if p else 'NONE'} (Gen {reg.active_generation})")
