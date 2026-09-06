#!/usr/bin/env python3
"""Hot-Plug Dynamic Worker Registry (Mission Infinite Life).

Allows generic external or secondary workers (e.g. CODEX_2, CODEX_3, GOOGLE_RESERVE)
to dynamically join and leave the multi-agent cluster safely without altering
canonical execution authority or introducing spend risks.
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
REGISTRY_DIR = EVENTS_DIR / "worker-registry"
HOT_PLUG_FILE = REGISTRY_DIR / "hot_plug_registry.json"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


@dataclass
class HotPlugWorker:
    worker_id: str
    provider: str  # OPENAI | GOOGLE | ANTHROPIC | LOCAL
    capabilities: List[str]  # e.g. ["CODE_REVIEW", "ADVERSARIAL_TEST", "AUDIO_QC"]
    role: str  # BUILDER | REVIEWER | TESTER | OBSERVER
    resource_state: str  # AVAILABLE | BUSY | WAITING_RESOURCE | OFFLINE
    authorization_scope: str  # READ_ONLY | LOCAL_SANDBOX | REQUIRES_CANONICAL_AUTHORITY
    session_epoch: str = "EPOCH_2026"
    registered_at: str = ""
    last_seen_at: str = ""
    spend_limit_eur: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HotPlugWorkerRegistry:
    """Manages dynamic worker registration with zero-spend firewall."""

    def __init__(self, repo_dir: Optional[Path] = None):
        self.repo_dir = repo_dir or COURIER_DIR
        self.registry_dir = self.repo_dir / "events" / "worker-registry"
        self.registry_file = self.registry_dir / "hot_plug_registry.json"

        self.workers: Dict[str, HotPlugWorker] = {}
        self._ensure_dir()
        self.load_registry()

    def _ensure_dir(self) -> None:
        self.registry_dir.mkdir(parents=True, exist_ok=True)

    def register_worker(
        self,
        worker_id: str,
        provider: str,
        capabilities: List[str],
        role: str,
        authorization_scope: str = "READ_ONLY",
    ) -> HotPlugWorker:
        """Registers a new hot-plugged worker."""
        now = utc_now()
        worker = HotPlugWorker(
            worker_id=worker_id,
            provider=provider,
            capabilities=capabilities,
            role=role,
            resource_state="AVAILABLE",
            authorization_scope=authorization_scope,
            session_epoch="EPOCH_2026",
            registered_at=now,
            last_seen_at=now,
            spend_limit_eur=0.0,
        )
        self.workers[worker_id] = worker
        self.save_registry()
        return worker

    def unregister_worker(self, worker_id: str) -> bool:
        """Removes a dynamic worker from active participation."""
        if worker_id in self.workers:
            del self.workers[worker_id]
            self.save_registry()
            return True
        return False

    def update_worker_heartbeat(self, worker_id: str, state: str = "AVAILABLE") -> bool:
        """Updates last seen timestamp and status for registered worker."""
        if worker_id in self.workers:
            self.workers[worker_id].last_seen_at = utc_now()
            self.workers[worker_id].resource_state = state
            self.save_registry()
            return True
        return False

    def get_available_workers_for_capability(self, capability: str) -> List[HotPlugWorker]:
        """Finds active workers matching specific capability."""
        return [
            w for w in self.workers.values()
            if capability in w.capabilities and w.resource_state == "AVAILABLE"
        ]

    def save_registry(self) -> Path:
        data = {
            "schema_version": "HOT_PLUG_REGISTRY_V1",
            "autonomous_spend_limit_eur": 0.0,
            "updated_at": utc_now(),
            "workers": {k: v.to_dict() for k, v in self.workers.items()},
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
            for k, v in data.get("workers", {}).items():
                self.workers[k] = HotPlugWorker(**v)
        except Exception as e:
            print(f"Warning: could not load hot plug registry: {e}")


if __name__ == "__main__":
    reg = HotPlugWorkerRegistry()
    w = reg.register_worker("CODEX_2", "OPENAI", ["CODE_REVIEW", "ADVERSARIAL_TEST"], "REVIEWER")
    print(f"✅ Registered Worker: {w.worker_id} (Scope: {w.authorization_scope})")
