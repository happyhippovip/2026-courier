#!/usr/bin/env python3
"""Mission PRODUCT-7 — Real Work Backlog & First Autonomous Shift.

Constructs a small, bounded, high-value provider-neutral backlog of real work
derived from canonical project state (Chief Brain, Creator Factory, FruitKI product assets)
ready for execution in the first autonomous work shift.

Key Invariants:
1. Zero busywork, zero routine reviews, zero mission-number inflation.
2. 0 EUR autonomous spend; publication strictly human-gated.
3. Strict scope isolation allowing parallel Google + Codex pairings in Wave 1.
4. Objective, deterministic acceptance conditions for every work item.
5. Cockpit compatible with 0 model calls.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import sys
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from autonomous_opportunity_discovery import (
        AutonomousOpportunityDiscoveryEngine,
        CanonicalOpportunity,
    )
except ImportError:
    from scripts.autonomous_opportunity_discovery import (
        AutonomousOpportunityDiscoveryEngine,
        CanonicalOpportunity,
    )


def load_json_safe(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}")
    temp_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp_path, path)


def sha256_digest(value: Any) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass
class RealWorkItem:
    work_id: str
    goal_id: str
    description: str
    expected_useful_state_change: str
    priority: int = 5
    critical_path: bool = False
    provider: str = "LOCAL_DETERMINISTIC"  # LOCAL_DETERMINISTIC, GOOGLE_PRO, CODEX
    target_agent: str = "antigravity"
    scope: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    risk: str = "LOW"
    cost_class: str = "FREE_LOCAL"
    gate: str = "READY"  # READY, HUMAN_GATE, MONEY_GATE, PUBLICATION_GATE
    acceptance_condition: str = ""
    source_fingerprint: str = ""
    parallel_safe: bool = True
    wave: int = 1
    created_at: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())

    def to_canonical_opportunity(self) -> CanonicalOpportunity:
        return CanonicalOpportunity(
            opportunity_id=self.work_id,
            goal_id=self.goal_id,
            description=self.description,
            target_agent=self.target_agent,
            provider=self.provider,
            status=self.gate if self.gate != "READY" else "READY",
            priority=self.priority,
            risk=self.risk,
            cost_class=self.cost_class,
            source="REAL_WORK_BACKLOG",
            source_fingerprint=self.source_fingerprint,
            expected_outcome=self.expected_useful_state_change,
            scope=self.scope,
            dependencies=self.dependencies,
            critical_path=self.critical_path,
            parallel_safe=self.parallel_safe,
            reason=f"First Shift Wave {self.wave} Item: {self.acceptance_condition}",
            estimated_cost=0.0,
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["opportunity_id"] = self.work_id
        d["problem_or_goal"] = self.description
        d["expected_outcome"] = self.expected_useful_state_change
        return d


class RealWorkBacklogBuilder:
    """Constructs the authoritative First Autonomous Shift backlog from canonical state."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir
        self.events_dir = repo_dir / "events"
        self.queue_dir = self.events_dir / "opportunity-queue"
        self.autonomy_dir = self.events_dir / "autonomy-runtime"
        self.content_dir = repo_dir / "runtime/content"
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.autonomy_dir.mkdir(parents=True, exist_ok=True)

    def build_first_shift_backlog(self) -> list[RealWorkItem]:
        """Generates bounded, 6-item real work backlog for First Shift."""
        items = [
            # Wave 1: Independent Parallel Pairing (Google + Codex + Local)
            RealWorkItem(
                work_id="work-fruitki-catalog-enrichment",
                goal_id="goal-creator-factory-autonomy",
                description="Generate comprehensive FruitKI 3D asset catalog manifest with duration, resolution, and theme metadata",
                expected_useful_state_change="Authoritative catalog manifest written to runtime/content/catalog_manifest.json",
                priority=9,
                critical_path=True,
                provider="GOOGLE_PRO",
                target_agent="creator_director",
                scope=["runtime/content/catalog_manifest.json"],
                dependencies=[],
                risk="LOW",
                cost_class="FREE_LOCAL",
                gate="READY",
                acceptance_condition="File runtime/content/catalog_manifest.json exists and contains valid JSON with >=10 packages",
                source_fingerprint="fp-catalog-01",
                parallel_safe=True,
                wave=1,
            ),
            RealWorkItem(
                work_id="work-creator-compliance-oracle",
                goal_id="goal-creator-factory-autonomy",
                description="Implement automated creator package compliance oracle verifying video codec, audio stream, and duration limits",
                expected_useful_state_change="Automated compliance test suite established in tests/test_creator_package_compliance.py",
                priority=9,
                critical_path=True,
                provider="CODEX",
                target_agent="codex",
                scope=["tests/test_creator_package_compliance.py"],
                dependencies=[],
                risk="LOW",
                cost_class="FREE_LOCAL",
                gate="READY",
                acceptance_condition="Test file tests/test_creator_package_compliance.py passes with >=5 assertions",
                source_fingerprint="fp-oracle-01",
                parallel_safe=True,
                wave=1,
            ),
            RealWorkItem(
                work_id="work-fruitki-inventory-summary",
                goal_id="goal-creator-factory-autonomy",
                description="Compute deterministic inventory summary of all rendered and unrendered FruitKI shorts",
                expected_useful_state_change="Inventory summary written to runtime/content/inventory_summary.json",
                priority=8,
                critical_path=False,
                provider="LOCAL_DETERMINISTIC",
                target_agent="qa_guardian",
                scope=["runtime/content/inventory_summary.json"],
                dependencies=[],
                risk="LOW",
                cost_class="FREE_LOCAL",
                gate="READY",
                acceptance_condition="File runtime/content/inventory_summary.json exists with package counts",
                source_fingerprint="fp-inv-01",
                parallel_safe=True,
                wave=1,
            ),

            # Wave 2: Unlocked Work (Product & Pricing Preparation)
            RealWorkItem(
                work_id="work-fruitki-pricing-manifest",
                goal_id="goal-creator-factory-autonomy",
                description="Construct revenue-path asset licensing tier structure and pricing metadata specification",
                expected_useful_state_change="Pricing metadata specification written to runtime/content/licensing_tiers.json",
                priority=7,
                critical_path=True,
                provider="LOCAL_DETERMINISTIC",
                target_agent="antigravity",
                scope=["runtime/content/licensing_tiers.json"],
                dependencies=["work-fruitki-catalog-enrichment"],
                risk="LOW",
                cost_class="FREE_LOCAL",
                gate="READY",
                acceptance_condition="File runtime/content/licensing_tiers.json exists with valid non-empty pricing tiers",
                source_fingerprint="fp-pricing-01",
                parallel_safe=True,
                wave=2,
            ),
            RealWorkItem(
                work_id="work-creator-package-qc-batch",
                goal_id="goal-creator-factory-autonomy",
                description="Execute deterministic batch QC verification across Golden Trophy, Mystery Box, and Banana Ninja packages",
                expected_useful_state_change="QC batch validation report saved in runtime/content/qc_batch_report.json",
                priority=8,
                critical_path=True,
                provider="GOOGLE_PRO",
                target_agent="qa_guardian",
                scope=["runtime/content/qc_batch_report.json"],
                dependencies=["work-creator-compliance-oracle"],
                risk="LOW",
                cost_class="FREE_LOCAL",
                gate="READY",
                acceptance_condition="File runtime/content/qc_batch_report.json exists with PASS verdict for inspected assets",
                source_fingerprint="fp-qc-batch-01",
                parallel_safe=True,
                wave=2,
            ),

            # Wave 3: Release Proposal (Human/Publication Gated)
            RealWorkItem(
                work_id="work-fruitki-release-proposal",
                goal_id="goal-creator-factory-autonomy",
                description="Prepare human-reviewable release proposal dossier for verified FruitKI video packages",
                expected_useful_state_change="Release proposal dossier generated at runtime/human_gates/release_proposal_dossier.json",
                priority=7,
                critical_path=False,
                provider="LOCAL_DETERMINISTIC",
                target_agent="publication_officer",
                scope=["runtime/human_gates/release_proposal_dossier.json"],
                dependencies=["work-fruitki-pricing-manifest", "work-creator-package-qc-batch"],
                risk="MEDIUM",
                cost_class="FREE_LOCAL",
                gate="HUMAN_GATE",
                acceptance_condition="Dossier file generated; stays strictly in HUMAN_GATE status until explicit human approval",
                source_fingerprint="fp-release-dossier-01",
                parallel_safe=True,
                wave=3,
            ),
        ]
        return items

    def persist_backlog_to_queue(self) -> list[RealWorkItem]:
        """Writes all backlog items to events/opportunity-queue/ and returns items."""
        items = self.build_first_shift_backlog()
        for item in items:
            opp = item.to_canonical_opportunity()
            save_json_atomic(self.queue_dir / f"{opp.opportunity_id}.json", opp.to_dict())

        # Also save consolidated first shift manifest
        manifest = {
            "shift_id": "first-autonomous-shift-001",
            "goal_id": "goal-creator-factory-autonomy",
            "total_items": len(items),
            "wave_1": [i.work_id for i in items if i.wave == 1],
            "wave_2": [i.work_id for i in items if i.wave == 2],
            "wave_3": [i.work_id for i in items if i.wave == 3],
            "parallel_pair": ["work-fruitki-catalog-enrichment", "work-creator-compliance-oracle"],
            "human_gates": [i.work_id for i in items if i.gate == "HUMAN_GATE"],
            "money_gates": [i.work_id for i in items if i.gate == "MONEY_GATE"],
            "autonomous_spend_eur": 0.0,
            "items": [i.to_dict() for i in items],
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        save_json_atomic(self.autonomy_dir / "first_shift_backlog.json", manifest)
        return items


def main():
    builder = RealWorkBacklogBuilder()
    items = builder.persist_backlog_to_queue()
    print("==================================================")
    print(f"REAL WORK BACKLOG PREPARED: {len(items)} items")
    print("==================================================")
    for it in items:
        print(f"  [Wave {it.wave}] [{it.provider}] [{it.gate}] {it.work_id}: {it.description}")
        print(f"    Acceptance: {it.acceptance_condition}")
    print("==================================================")


if __name__ == "__main__":
    main()
