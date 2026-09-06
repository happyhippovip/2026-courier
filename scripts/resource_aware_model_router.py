#!/usr/bin/env python3
"""Resource-Aware Model & Worker Router (Mission Continuous Operations).

Dynamically schedules tasks to available, authorized model pools (e.g. Claude, GPT, Gemini)
without violating provider constraints, rotating unauthorized accounts, or incurring spend.

Invariants:
- AUTONOMOUS_NEW_SPEND = 0 EUR.
- Quota exhausted for all compatible providers -> WAITING_RESOURCE.
- Alternative authorized provider available -> route safely.
- No repeated spam retries against exhausted resources.
"""

from __future__ import annotations

import argparse
import datetime as dt
import enum
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

COURIER_DIR = Path(__file__).resolve().parent.parent
EVENTS_DIR = COURIER_DIR / "events"
ROUTER_DIR = EVENTS_DIR / "resource-intelligence"
ROUTER_STATE_FILE = ROUTER_DIR / "model_routing_state.json"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class ModelGroup(str, enum.Enum):
    GEMINI_MODELS = "GEMINI_MODELS"
    CLAUDE_MODELS = "CLAUDE_MODELS"
    GPT_MODELS = "GPT_MODELS"
    LOCAL_MODELS = "LOCAL_MODELS"


@dataclass
class ProviderQuotaStatus:
    provider_id: str
    model_group: str  # GEMINI_MODELS | CLAUDE_MODELS | GPT_MODELS | LOCAL_MODELS
    quota_available_pct: float  # 0.0 to 100.0
    is_exhausted: bool
    resets_in_seconds: Optional[float] = None
    last_checked_at: str = ""
    evidence_source: str = "PROVIDER_OBSERVED"  # PROVIDER_OBSERVED | UI_OBSERVED | UNKNOWN

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ModelRoutingDecision:
    task_id: str
    task_type: str
    assigned_worker_id: str
    assigned_model_group: str
    assigned_model_name: str
    routing_verdict: str  # ROUTED_SUCCESS | WAITING_RESOURCE | BLOCKED_PERMISSIONS
    spend_eur: float = 0.0
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ResourceAwareModelRouter:
    """Intelligently routes tasks to active model pools with remaining quota."""

    def __init__(self, repo_dir: Optional[Path] = None):
        self.repo_dir = repo_dir or COURIER_DIR
        self.router_dir = self.repo_dir / "events" / "resource-intelligence"
        self.state_file = self.router_dir / "model_routing_state.json"

        self.quota_registry: Dict[str, ProviderQuotaStatus] = {}
        self._ensure_dir()
        self.load_state()

    def _ensure_dir(self) -> None:
        self.router_dir.mkdir(parents=True, exist_ok=True)

    def record_quota_observation(
        self,
        provider_id: str,
        model_group: ModelGroup,
        quota_pct: float,
        resets_in_seconds: Optional[float] = None,
        evidence_source: str = "PROVIDER_OBSERVED",
    ) -> ProviderQuotaStatus:
        """Records observed provider quota."""
        status = ProviderQuotaStatus(
            provider_id=provider_id,
            model_group=model_group.value,
            quota_available_pct=quota_pct,
            is_exhausted=(quota_pct <= 0.0),
            resets_in_seconds=resets_in_seconds,
            last_checked_at=utc_now(),
            evidence_source=evidence_source,
        )
        key = f"{provider_id}:{model_group.value}"
        self.quota_registry[key] = status
        self.save_state()
        return status

    def select_best_model_for_task(
        self,
        task_id: str,
        task_type: str,
        preferred_worker_id: str = "CLI2",
        compatible_groups: Optional[List[ModelGroup]] = None,
    ) -> ModelRoutingDecision:
        """Evaluates available quotas and routes to the best authorized model pool."""
        groups = compatible_groups or [
            ModelGroup.CLAUDE_MODELS,
            ModelGroup.GPT_MODELS,
            ModelGroup.GEMINI_MODELS,
            ModelGroup.LOCAL_MODELS,
        ]

        for group in groups:
            # Check if any provider in this group has available quota
            available_provider = self._find_available_provider_in_group(group)
            if available_provider:
                model_name = self._default_model_name_for_group(group)
                return ModelRoutingDecision(
                    task_id=task_id,
                    task_type=task_type,
                    assigned_worker_id=preferred_worker_id,
                    assigned_model_group=group.value,
                    assigned_model_name=model_name,
                    routing_verdict="ROUTED_SUCCESS",
                    spend_eur=0.0,
                    rationale=f"Routed to {group.value} ({available_provider.provider_id}) with {available_provider.quota_available_pct:.1f}% quota remaining.",
                )

        # If all compatible groups are exhausted
        return ModelRoutingDecision(
            task_id=task_id,
            task_type=task_type,
            assigned_worker_id=preferred_worker_id,
            assigned_model_group="NONE",
            assigned_model_name="NONE",
            routing_verdict="WAITING_RESOURCE",
            spend_eur=0.0,
            rationale="All compatible authorized model groups have exhausted quotas. WAITING_RESOURCE.",
        )

    def _find_available_provider_in_group(self, group: ModelGroup) -> Optional[ProviderQuotaStatus]:
        grp_val = group.value if isinstance(group, ModelGroup) else str(group)
        group_statuses = [
            s for s in self.quota_registry.values()
            if s.model_group == grp_val
        ]
        if group_statuses:
            for status in group_statuses:
                if not status.is_exhausted and status.quota_available_pct > 0.0:
                    return status
            return None  # All registered providers in this group are exhausted

        # If no explicit observation recorded yet, assume default authorized availability
        return ProviderQuotaStatus(
            provider_id="DEFAULT_AUTHORIZED",
            model_group=grp_val,
            quota_available_pct=100.0,
            is_exhausted=False,
            last_checked_at=utc_now(),
        )

    def _default_model_name_for_group(self, group: ModelGroup) -> str:
        mapping = {
            ModelGroup.CLAUDE_MODELS: "claude-3-5-sonnet",
            ModelGroup.GPT_MODELS: "gpt-4o",
            ModelGroup.GEMINI_MODELS: "gemini-1.5-pro",
            ModelGroup.LOCAL_MODELS: "local-deterministic-oracle",
        }
        return mapping.get(group, "generic-model")

    def save_state(self) -> Path:
        data = {
            "schema_version": "MODEL_ROUTER_STATE_V1",
            "updated_at": utc_now(),
            "autonomous_spend_limit_eur": 0.0,
            "registry": {k: v.to_dict() for k, v in self.quota_registry.items()},
        }
        temp = self.state_file.with_suffix(".tmp")
        temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temp.replace(self.state_file)
        return self.state_file

    def load_state(self) -> None:
        if not self.state_file.exists():
            return
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            for k, v in data.get("registry", {}).items():
                self.quota_registry[k] = ProviderQuotaStatus(**v)
        except Exception as e:
            print(f"Warning: could not load model routing state: {e}")


def init_model_router() -> ResourceAwareModelRouter:
    router = ResourceAwareModelRouter()
    # Ingest baseline observation from CLI2 UI
    router.record_quota_observation("ANTIGRAVITY_BEATA", ModelGroup.GEMINI_MODELS, 0.0, resets_in_seconds=590400.0, evidence_source="UI_OBSERVED")
    router.record_quota_observation("ANTIGRAVITY_BEATA", ModelGroup.CLAUDE_MODELS, 100.0, evidence_source="UI_OBSERVED")
    router.record_quota_observation("ANTIGRAVITY_BEATA", ModelGroup.GPT_MODELS, 100.0, evidence_source="UI_OBSERVED")
    return router


if __name__ == "__main__":
    r = init_model_router()
    dec = r.select_best_model_for_task("task-qc-01", "ADVERSARIAL_TEST", "CLI2")
    print(f"✅ Model Routing Decision: {dec.routing_verdict} -> {dec.assigned_model_name} (Spend: {dec.spend_eur} EUR)")
