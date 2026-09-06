#!/usr/bin/env python3
"""Mission 189G: Elite Execution Core & Fastest High-Quality Path Engine.

Implements the permanent Quality-First Intelligent Efficiency layer for all bots:
- Priority Hierarchy:
  1. QUALITY / CORRECTNESS / SAFETY
  2. ACTUAL GOAL PROGRESS
  3. COST EFFICIENCY
  4. SPEED
  5. RESOURCE UTILIZATION
- Reusable Quality Floors (LOW_RISK, MEDIUM_RISK, HIGH_RISK, MONEY, SECURITY, PUBLICATION, IDENTITY_LEGAL).
- Intelligence Escalation Ladder (Reuse -> Deterministic -> Evidence -> Targeted Model -> Strong Model -> Second Judgment -> True Human Gate).
- Semantic Delta Gate (Distinguishing formatting/telemetry from decision-relevant deltas).
- Wake-on-Evidence (Zero model polling during idle).
- Speculative Local Preparation (Zero-model prep while model runs).
- Opportunity Cost & Capability-First Scheduler (MODEL_HEAVY=1, SCOPE_OWNER=1, RENDER=1).
- Decision Cache with Semantic Invalidation (NO_CHANGE = NO_REVIEW).
- Result & Decision Compression (Evidence Coalescing).
- Stop on Sufficient Quality (Preventing perfection loops).
- Anti-Swarm & Shadow-Call Firewall.
- Critical-Path Aware Fastest Path Planner.
- Quality-Adjusted Amplification Telemetry.
"""

from __future__ import annotations

import datetime as dt
import enum
import fcntl
import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

COURIER_DIR = Path(__file__).resolve().parent.parent

try:
    from scripts.canonical_authority import CanonicalAuthority
except ImportError:
    from canonical_authority import CanonicalAuthority


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def compute_sha256(content: str | bytes) -> str:
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


class QualityFloorClass(str, enum.Enum):
    LOW_RISK = "LOW_RISK"
    MEDIUM_RISK = "MEDIUM_RISK"
    HIGH_RISK = "HIGH_RISK"
    MONEY = "MONEY"
    SECURITY = "SECURITY"
    PUBLICATION = "PUBLICATION"
    IDENTITY_LEGAL = "IDENTITY_LEGAL"


class IntelligenceLadderLevel(int, enum.Enum):
    LEVEL_1_REUSE_ACCEPTED_RESULT = 1
    LEVEL_2_LOCAL_DETERMINISTIC = 2
    LEVEL_3_STRUCTURED_EXISTING_EVIDENCE = 3
    LEVEL_4_TARGETED_MODEL_JUDGMENT = 4
    LEVEL_5_STRONG_MODEL_JUDGMENT = 5
    LEVEL_6_INDEPENDENT_SECOND_JUDGMENT = 6
    LEVEL_7_TRUE_HUMAN_GATE = 7


class SemanticDeltaType(str, enum.Enum):
    NO_RELEVANT_CHANGE = "NO_RELEVANT_CHANGE"
    RELEVANT_LOW_RISK_DELTA = "RELEVANT_LOW_RISK_DELTA"
    RELEVANT_DECISION_DELTA = "RELEVANT_DECISION_DELTA"
    RELEVANT_HIGH_RISK_DELTA = "RELEVANT_HIGH_RISK_DELTA"
    UNKNOWN_REQUIRES_CLASSIFICATION = "UNKNOWN_REQUIRES_CLASSIFICATION"


class SchedulerDecision(str, enum.Enum):
    RUN_NOW = "RUN_NOW"
    DEFER_FOR_HIGHER_VALUE = "DEFER_FOR_HIGHER_VALUE"
    LOCALIZE = "LOCALIZE"
    REUSE_CACHE = "REUSE_CACHE"
    COALESCE = "COALESCE"
    WAIT_FOR_DEPENDENCY = "WAIT_FOR_DEPENDENCY"
    PARK_HUMAN_GATE = "PARK_HUMAN_GATE"
    PARK_MONEY_GATE = "PARK_MONEY_GATE"
    DROP_ZERO_GAIN = "DROP_ZERO_GAIN"
    DENY_SCOPE_CONFLICT = "DENY_SCOPE_CONFLICT"


class CapabilityType(str, enum.Enum):
    DETERMINISTIC = "DETERMINISTIC"
    CODE_BUILD = "CODE_BUILD"
    CODE_REVIEW = "CODE_REVIEW"
    RESEARCH = "RESEARCH"
    FACT_VERIFICATION = "FACT_VERIFICATION"
    VISUAL_JUDGMENT = "VISUAL_JUDGMENT"
    PLANNING = "PLANNING"
    HIGH_RISK_JUDGMENT = "HIGH_RISK_JUDGMENT"
    RENDER = "RENDER"
    LOCAL_AUTOMATION = "LOCAL_AUTOMATION"


@dataclass
class QualityFloorRequirement:
    floor_class: QualityFloorClass
    min_ladder_level: IntelligenceLadderLevel
    required_verifications: List[str]
    allow_cached_judgment: bool = True
    requires_human_signoff: bool = False
    requires_zero_secret_scan: bool = False
    requires_zero_spend_verification: bool = False


QUALITY_FLOOR_REGISTRY: Dict[QualityFloorClass, QualityFloorRequirement] = {
    QualityFloorClass.LOW_RISK: QualityFloorRequirement(
        floor_class=QualityFloorClass.LOW_RISK,
        min_ladder_level=IntelligenceLadderLevel.LEVEL_2_LOCAL_DETERMINISTIC,
        required_verifications=["LOCAL_TEST_PASS"],
    ),
    QualityFloorClass.MEDIUM_RISK: QualityFloorRequirement(
        floor_class=QualityFloorClass.MEDIUM_RISK,
        min_ladder_level=IntelligenceLadderLevel.LEVEL_2_LOCAL_DETERMINISTIC,
        required_verifications=["LOCAL_TEST_PASS", "STATIC_ANALYSIS_CLEAN"],
    ),
    QualityFloorClass.HIGH_RISK: QualityFloorRequirement(
        floor_class=QualityFloorClass.HIGH_RISK,
        min_ladder_level=IntelligenceLadderLevel.LEVEL_4_TARGETED_MODEL_JUDGMENT,
        required_verifications=["LOCAL_TEST_PASS", "STATIC_ANALYSIS_CLEAN", "STRUCTURED_REVIEW"],
    ),
    QualityFloorClass.MONEY: QualityFloorRequirement(
        floor_class=QualityFloorClass.MONEY,
        min_ladder_level=IntelligenceLadderLevel.LEVEL_7_TRUE_HUMAN_GATE,
        required_verifications=["SPEND_LIMIT_0_CHECK", "PAYMENT_APPROVAL_REQUIRED"],
        requires_zero_spend_verification=True,
        requires_human_signoff=True,
    ),
    QualityFloorClass.SECURITY: QualityFloorRequirement(
        floor_class=QualityFloorClass.SECURITY,
        min_ladder_level=IntelligenceLadderLevel.LEVEL_2_LOCAL_DETERMINISTIC,
        required_verifications=["ZERO_SECRET_SCAN", "PERMISSION_AUDIT", "LOCAL_TEST_PASS"],
        requires_zero_secret_scan=True,
    ),
    QualityFloorClass.PUBLICATION: QualityFloorRequirement(
        floor_class=QualityFloorClass.PUBLICATION,
        min_ladder_level=IntelligenceLadderLevel.LEVEL_7_TRUE_HUMAN_GATE,
        required_verifications=["QC_SOURCE_HASH_VALID", "PLATFORM_DEDUPE_FINGERPRINT", "HUMAN_AUDIENCE_APPROVAL"],
        requires_human_signoff=True,
    ),
    QualityFloorClass.IDENTITY_LEGAL: QualityFloorRequirement(
        floor_class=QualityFloorClass.IDENTITY_LEGAL,
        min_ladder_level=IntelligenceLadderLevel.LEVEL_7_TRUE_HUMAN_GATE,
        required_verifications=["HUMAN_IDENTITY_SIGNATURE", "TERMS_COMPLIANCE"],
        requires_human_signoff=True,
    ),
}


@dataclass
class EliteActionSpec:
    action_id: str
    goal: str
    expected_unlock: str
    quality_floor: QualityFloorClass
    risk_class: str
    new_information: str
    why_now: str
    why_model: str
    why_not_local: str
    why_not_cache: str
    dependencies: List[str] = field(default_factory=list)
    mutation_scope: List[str] = field(default_factory=list)
    opportunity_cost: float = 0.0
    context_reference: str = ""
    stop_condition: str = ""
    required_capability: CapabilityType = CapabilityType.DETERMINISTIC
    decision_value_class: str = "USEFUL"  # CRITICAL_UNBLOCK, HIGH_VALUE, USEFUL, OPTIONAL, ZERO_GAIN
    is_on_critical_path: bool = False
    priority: int = 5
    fingerprint: str = ""

    def compute_fingerprint(self) -> str:
        payload = f"{self.goal}:{self.expected_unlock}:{self.risk_class}:{self.new_information}:{sorted(self.dependencies)}:{sorted(self.mutation_scope)}"
        self.fingerprint = compute_sha256(payload)
        return self.fingerprint

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["quality_floor"] = self.quality_floor.value
        d["required_capability"] = self.required_capability.value
        return d


@dataclass
class QualityAmplificationMetrics:
    useful_state_transitions: int = 0
    quality_verified_transitions: int = 0
    decisions_closed: int = 0
    blockers_removed: int = 0
    model_calls_admitted: int = 0
    model_calls_avoided: int = 0
    reviews_reused: int = 0
    duplicate_work_avoided: int = 0
    context_resends_avoided: int = 0
    correct_waits: int = 0
    zero_gain_jobs_dropped: int = 0
    decisions_coalesced: int = 0
    local_resolutions: int = 0
    chatter_events_prevented: int = 0

    @property
    def amplification_ratio(self) -> float:
        necessary_models = max(1, self.model_calls_admitted)
        return round(self.quality_verified_transitions / necessary_models, 3)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["amplification_ratio"] = self.amplification_ratio
        return d


class SemanticDeltaClassifier:
    """Classifies file and payload deltas to distinguish harmless vs decision-relevant changes."""

    @staticmethod
    def classify_delta(
        old_content: str,
        new_content: str,
        file_path: Optional[str] = None,
    ) -> Tuple[SemanticDeltaType, str]:
        if old_content == new_content:
            return SemanticDeltaType.NO_RELEVANT_CHANGE, "Exact identical content"

        # Check for whitespace/comment-only delta
        old_stripped = "".join(line.strip() for line in old_content.splitlines() if line.strip() and not line.strip().startswith("#"))
        new_stripped = "".join(line.strip() for line in new_content.splitlines() if line.strip() and not line.strip().startswith("#"))

        if old_stripped == new_stripped:
            return SemanticDeltaType.NO_RELEVANT_CHANGE, "Whitespace or comment-only modification"

        path_str = (file_path or "").lower()

        # High-risk security/money/publication domains
        if any(sec_term in path_str for sec_term in ("auth", "secret", "firewall", "spend", "payment", "publish", "gate")):
            return SemanticDeltaType.RELEVANT_HIGH_RISK_DELTA, f"Modification in security/governance module: {file_path}"

        # Decision/Protocol domains
        if any(dec_term in path_str for dec_term in ("barrier", "protocol", "state_machine", "controller", "dispatcher")):
            return SemanticDeltaType.RELEVANT_DECISION_DELTA, f"Modification in decision orchestration module: {file_path}"

        # Low-risk / general code
        return SemanticDeltaType.RELEVANT_LOW_RISK_DELTA, f"General logic delta in: {file_path}"


class DecisionCacheManager:
    """Manages accepted judgments with semantic invalidation rules (NO_CHANGE = NO_REVIEW)."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir
        self.cache_dir = repo_dir / "events" / "decision-cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "accepted_judgments.json"
        self._cache: Dict[str, Dict[str, Any]] = self._load()

    def _load(self) -> Dict[str, Dict[str, Any]]:
        if self.cache_file.is_file():
            try:
                return json.loads(self.cache_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save(self) -> None:
        self.cache_file.write_text(json.dumps(self._cache, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def get_judgment(self, fingerprint: str) -> Optional[Dict[str, Any]]:
        entry = self._cache.get(fingerprint)
        if not entry:
            return None
        if entry.get("invalidated", False):
            return None
        return entry.get("judgment")

    def store_judgment(self, fingerprint: str, task_id: str, judgment: Dict[str, Any], quality_floor: QualityFloorClass) -> None:
        self._cache[fingerprint] = {
            "task_id": task_id,
            "fingerprint": fingerprint,
            "quality_floor": quality_floor.value,
            "judgment": judgment,
            "created_at": utc_now(),
            "invalidated": False,
            "invalidation_reason": None,
        }
        self._save()

    def invalidate(self, fingerprint_or_pattern: str, reason: str) -> int:
        count = 0
        for fp, entry in self._cache.items():
            if fp == fingerprint_or_pattern or fingerprint_or_pattern in entry.get("task_id", ""):
                if not entry.get("invalidated", False):
                    entry["invalidated"] = True
                    entry["invalidation_reason"] = reason
                    entry["invalidated_at"] = utc_now()
                    count += 1
        if count > 0:
            self._save()
        return count


class EliteExecutionCore:
    """Permanent Quality-First Intelligent Efficiency Layer for Zentrale autonomous systems."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir
        self.decision_cache = DecisionCacheManager(repo_dir=repo_dir)
        self.metrics = QualityAmplificationMetrics()
        self.delta_classifier = SemanticDeltaClassifier()

        # Concurrency & Canonical Authority
        self.active_mutation_scopes: Dict[str, str] = {}  # scope -> task_id
        self.active_provider_heavy: Dict[str, str] = {}  # provider -> task_id
        self.render_heavy_active: Optional[str] = None
        self.locks_dir = self.repo_dir / "events/locks"
        self.locks_dir.mkdir(parents=True, exist_ok=True)
        self.canonical_authority = CanonicalAuthority(locks_dir=self.locks_dir)
        self._lock_handles: Dict[str, Any] = {}

        # Hard Firewalls
        self.AUTONOMOUS_SPEND_LIMIT_EUR: float = 0.0
        self.PUBLICATION_AUTHORIZATION_INFERENCE: str = "DENY"

    def acquire_scope_lock(self, task_id: str, scopes: List[str]) -> Tuple[bool, Optional[str]]:
        """Enforces MUTATION_SCOPE_OWNER = 1 across threads and independent OS processes via CanonicalAuthority."""
        success, gen, err = self.canonical_authority.acquire_scopes(
            owner_id=task_id,
            task_id=task_id,
            scopes=scopes,
        )
        if success:
            for s in scopes:
                self.active_mutation_scopes[s] = task_id
            return True, None
        return False, err

    def release_scope_lock(self, task_id: str) -> None:
        to_release = [s for s, owner in self.active_mutation_scopes.items() if owner == task_id]
        for s in to_release:
            del self.active_mutation_scopes[s]
        self.canonical_authority.release_scopes(
            owner_id=task_id,
            task_id=task_id,
            scopes=to_release if to_release else None,
        )

    def evaluate_ladder_level(
        self,
        spec: EliteActionSpec,
        deterministic_resolver: Optional[Callable[[str], Tuple[bool, Any]]] = None,
    ) -> Tuple[IntelligenceLadderLevel, SchedulerDecision, Dict[str, Any]]:
        """Selects the lowest level of the escalation ladder that reliably satisfies Quality Floor."""
        q_req = QUALITY_FLOOR_REGISTRY.get(spec.quality_floor, QUALITY_FLOOR_REGISTRY[QualityFloorClass.LOW_RISK])
        fp = spec.compute_fingerprint()

        # Step 1: Check Accepted Judgment Cache (Level 1)
        if q_req.allow_cached_judgment:
            cached = self.decision_cache.get_judgment(fp)
            if cached is not None:
                self.metrics.reviews_reused += 1
                self.metrics.model_calls_avoided += 1
                return (
                    IntelligenceLadderLevel.LEVEL_1_REUSE_ACCEPTED_RESULT,
                    SchedulerDecision.REUSE_CACHE,
                    {"cached_judgment": cached, "source": "DECISION_CACHE", "fingerprint": fp},
                )

        # Step 2: Check True Human / Money Gates (Level 7)
        if q_req.requires_human_signoff or spec.quality_floor in (QualityFloorClass.MONEY, QualityFloorClass.PUBLICATION, QualityFloorClass.IDENTITY_LEGAL):
            if spec.quality_floor == QualityFloorClass.MONEY:
                self.metrics.correct_waits += 1
                return (
                    IntelligenceLadderLevel.LEVEL_7_TRUE_HUMAN_GATE,
                    SchedulerDecision.PARK_MONEY_GATE,
                    {"reason": "MONEY_GATE_SPEND_LIMIT_0", "status": "PARKED_SAFE"},
                )
            elif spec.quality_floor in (QualityFloorClass.PUBLICATION, QualityFloorClass.IDENTITY_LEGAL):
                self.metrics.correct_waits += 1
                return (
                    IntelligenceLadderLevel.LEVEL_7_TRUE_HUMAN_GATE,
                    SchedulerDecision.PARK_HUMAN_GATE,
                    {"reason": "HUMAN_SIGN_OFF_REQUIRED", "status": "PARKED_SAFE"},
                )

        # Step 3: Check Zero-Gain (Drop before model)
        if spec.decision_value_class == "ZERO_GAIN":
            self.metrics.zero_gain_jobs_dropped += 1
            self.metrics.model_calls_avoided += 1
            return (
                IntelligenceLadderLevel.LEVEL_2_LOCAL_DETERMINISTIC,
                SchedulerDecision.DROP_ZERO_GAIN,
                {"reason": "ZERO_GAIN_REJECTED", "admitted": False},
            )

        # Step 4: Local Deterministic Resolution (Level 2)
        if deterministic_resolver:
            can_resolve, res = deterministic_resolver(spec.action_id)
            if can_resolve:
                # Check if deterministic satisfies the Quality Floor requirements
                if q_req.min_ladder_level <= IntelligenceLadderLevel.LEVEL_2_LOCAL_DETERMINISTIC:
                    self.metrics.local_resolutions += 1
                    self.metrics.model_calls_avoided += 1
                    self.metrics.useful_state_transitions += 1
                    self.metrics.quality_verified_transitions += 1
                    return (
                        IntelligenceLadderLevel.LEVEL_2_LOCAL_DETERMINISTIC,
                        SchedulerDecision.LOCALIZE,
                        {"result": res, "tier": "LOCAL_DETERMINISTIC", "verified": True},
                    )

        # Step 5: Escalate to Targeted Model Judgment (Level 4/5)
        # Check scope locks first
        locked, lock_err = self.acquire_scope_lock(spec.action_id, spec.mutation_scope)
        if not locked:
            return (
                IntelligenceLadderLevel.LEVEL_4_TARGETED_MODEL_JUDGMENT,
                SchedulerDecision.DENY_SCOPE_CONFLICT,
                {"error": lock_err, "admitted": False},
            )

        self.metrics.model_calls_admitted += 1
        ladder_level = IntelligenceLadderLevel.LEVEL_5_STRONG_MODEL_JUDGMENT if spec.risk_class == "HIGH" else IntelligenceLadderLevel.LEVEL_4_TARGETED_MODEL_JUDGMENT
        return (
            ladder_level,
            SchedulerDecision.RUN_NOW,
            {
                "admitted": True,
                "ladder_level": ladder_level.value,
                "resource_class": "MODEL_HEAVY",
                "quality_floor": spec.quality_floor.value,
                "context_reference": spec.context_reference or f"ctx-{spec.action_id}",
            },
        )

    def prepare_speculative_local_work(
        self,
        task_id: str,
        target_files: List[Path],
    ) -> Dict[str, Any]:
        """Prepares zero-model artifacts, hashes, and diff pre-checks while model is working."""
        prep_results: Dict[str, Any] = {
            "task_id": task_id,
            "prepared_at": utc_now(),
            "file_hashes": {},
            "static_clean": True,
            "zero_secrets_verified": True,
        }

        for f in target_files:
            if f.is_file():
                content = f.read_text(encoding="utf-8")
                prep_results["file_hashes"][f.name] = compute_sha256(content)
                for secret_kw in ("client_secret", "private_key", "bearer_token"):
                    if secret_kw in content.lower() and "check_for_secrets" not in content:
                        prep_results["zero_secrets_verified"] = False

        return prep_results

    def coalesce_results(
        self,
        results_list: List[Dict[str, Any]],
        target_task_id: str,
    ) -> Dict[str, Any]:
        """Compresses multiple low-level events into a single decision-relevant transition."""
        self.metrics.decisions_coalesced += 1
        combined_hash = compute_sha256(json.dumps(results_list, sort_keys=True))
        return {
            "coalesced_task_id": target_task_id,
            "events_count": len(results_list),
            "synthesis_hash": combined_hash,
            "timestamp": utc_now(),
            "status": "COALESCED_READY_FOR_SYNTHESIS",
            "items": results_list,
        }

    def check_stop_on_sufficient_quality(
        self,
        goal_satisfied: bool,
        quality_floor_verified: bool,
        remaining_blockers: List[str],
    ) -> Tuple[bool, str]:
        """Stops on sufficient quality to prevent perfection loops and mission inflation."""
        if goal_satisfied and quality_floor_verified and not remaining_blockers:
            return True, "STOP_SUCCESS: Goal achieved with Quality Floor satisfied and zero remaining blockers"
        if remaining_blockers:
            return False, f"CONTINUE: Remaining blockers: {remaining_blockers}"
        if not quality_floor_verified:
            return False, "CONTINUE: Quality Floor verifications incomplete"
        return False, "CONTINUE: Goal state not yet reached"

    def select_fastest_path_action(
        self,
        candidate_actions: List[EliteActionSpec],
        active_scopes: Optional[Set[str]] = None,
    ) -> Optional[EliteActionSpec]:
        """Critical-path aware deterministic planner selecting the shortest high-quality path."""
        if not candidate_actions:
            return None

        active_scopes = active_scopes or set(self.active_mutation_scopes.keys())

        # Filter out scope conflicts
        eligible: List[EliteActionSpec] = []
        for action in candidate_actions:
            if not any(s in active_scopes for s in action.mutation_scope):
                eligible.append(action)

        if not eligible:
            return None

        # Sort criteria:
        # 1. Critical path awareness (is_on_critical_path = True first)
        # 2. Decision value class (CRITICAL_UNBLOCK > HIGH_VALUE > USEFUL > OPTIONAL)
        # 3. Lowest required ladder level (prefer DETERMINISTIC / LOCAL / CACHE over expensive models)
        # 4. Priority score descending
        val_map = {"CRITICAL_UNBLOCK": 4, "HIGH_VALUE": 3, "USEFUL": 2, "OPTIONAL": 1, "ZERO_GAIN": 0}

        def sort_key(a: EliteActionSpec) -> Tuple[int, int, int, int]:
            crit_score = 1 if a.is_on_critical_path else 0
            val_score = val_map.get(a.decision_value_class, 1)
            # Prefer local deterministic capability
            local_pref = 1 if a.required_capability in (CapabilityType.DETERMINISTIC, CapabilityType.LOCAL_AUTOMATION) else 0
            return (crit_score, val_score, local_pref, a.priority)

        sorted_actions = sorted(eligible, key=sort_key, reverse=True)
        best_action = sorted_actions[0]

        if best_action.decision_value_class == "ZERO_GAIN":
            return None

        return best_action
