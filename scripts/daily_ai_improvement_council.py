#!/usr/bin/env python3
"""Daily AI Improvement Council, External Solution Discovery & Competitive Learning Engine.

Permanent Directive & Motto:
"WIR MÜSSEN JEDEN TAG BESSER WERDEN WIE DIE ANDEREN."

Core Capabilities:
1. Multi-AI Improvement Council (Google Builder, Codex Reviewer, Research Scout, Snitch, Deterministic Tools)
2. Evidence-Weighted Decision Engine (No fake democracy, evidence beats opinion)
3. Shared Canonical Improvement Backlog
4. Competitive Self-Benchmarking (Today vs. Yesterday vs. 7-Day Baseline)
5. Challenger vs. Incumbent Workflow Trials
6. Distilled Knowledge Base Sharing across all agents
7. Bounded Discussion & Project-Work Priority Protection
8. Visual HQ Learning State Integration
9. 100% Deterministic: 0 Model Calls unless new evidence warrants, 0.00 EUR Spend.
"""

from __future__ import annotations

import argparse
import datetime as dt
import enum
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(COURIER_DIR) not in sys.path:
    sys.path.insert(0, str(COURIER_DIR))

EVENTS_DIR = COURIER_DIR / "events"
INTEL_DIR = EVENTS_DIR / "resource-intelligence"
KNOWLEDGE_DIR = EVENTS_DIR / "knowledge-base"
STATE_DIR = EVENTS_DIR / "runtime-state"

COUNCIL_STATE_FILE = INTEL_DIR / "daily_improvement_council.json"
BACKLOG_FILE = INTEL_DIR / "improvement_backlog.json"
LESSONS_FILE = KNOWLEDGE_DIR / "distilled_lessons.json"
BENCHMARK_FILE = INTEL_DIR / "competitive_daily_benchmarks.json"
CENTRAL_MOTTO_FILE = STATE_DIR / "central_motto.json"

PERMANENT_MOTTO = "WIR MÜSSEN JEDEN TAG BESSER WERDEN WIE DIE ANDEREN."


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def parse_iso(ts: str) -> Optional[dt.datetime]:
    try:
        return dt.datetime.fromisoformat(ts)
    except Exception:
        return None


class PerspectiveRole(str, enum.Enum):
    GOOGLE_BUILDER = "GOOGLE_BUILDER"
    CODEX_REVIEWER = "CODEX_REVIEWER"
    RESEARCH_SCOUT = "RESEARCH_SCOUT"
    DETERMINISTIC_ORACLE = "DETERMINISTIC_ORACLE"
    SNITCH_OBSERVER = "SNITCH_OBSERVER"
    CHIEF_STRATEGY = "CHIEF_STRATEGY"


class CouncilVerdict(str, enum.Enum):
    ADOPT = "ADOPT"
    REJECT = "REJECT"
    DEFER = "DEFER"
    SAFE_EXPERIMENT = "SAFE_EXPERIMENT"
    CURRENT_METHOD_RETAINED = "CURRENT_METHOD_RETAINED"


class KnowledgeType(str, enum.Enum):
    VERIFIED_FACT = "VERIFIED_FACT"
    MEASUREMENT = "MEASUREMENT"
    INFERENCE = "INFERENCE"
    HYPOTHESIS = "HYPOTHESIS"
    EXPERIMENT_RESULT = "EXPERIMENT_RESULT"
    EXTERNAL_INFORMATION = "EXTERNAL_INFORMATION"


@dataclass
class ImprovementProposal:
    proposal_id: str
    role: PerspectiveRole
    question: str
    current_method: str
    proposed_alternative: str
    evidence: Dict[str, Any]
    expected_benefit: str
    risk: str = "LOW"  # LOW, MEDIUM, HIGH
    estimated_cost: float = 0.0
    test_method: str = ""
    confidence: float = 0.85
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["role"] = self.role.value
        return d


@dataclass
class CouncilDeliberation:
    deliberation_id: str
    question: str
    proposals: List[ImprovementProposal]
    challenges: List[Dict[str, Any]]
    verdict: CouncilVerdict
    evidence_weighted_score: float
    decision_reason: str
    rollback_plan: Optional[str] = None
    executed_at: str = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["proposals"] = [p.to_dict() for p in self.proposals]
        d["verdict"] = self.verdict.value
        return d


@dataclass
class DistilledLesson:
    lesson_id: str
    knowledge_type: KnowledgeType
    topic: str
    concise_lesson: str
    source_role: PerspectiveRole
    confidence: float
    verified_by: str
    created_at: str = field(default_factory=utc_now)
    applicability: List[str] = field(default_factory=list)
    recheck_trigger: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["knowledge_type"] = self.knowledge_type.value if hasattr(self.knowledge_type, "value") else str(self.knowledge_type)
        d["source_role"] = self.source_role.value if hasattr(self.source_role, "value") else str(self.source_role)
        return d


@dataclass
class DailyBenchmarkSnapshot:
    date_str: str  # YYYY-MM-DD
    useful_tasks_completed: int = 0
    failure_rate: float = 0.0
    recovery_success_rate: float = 1.0
    duplicate_executions: int = 0
    human_interventions: int = 0
    weiter_prompts_required: int = 0
    model_calls_per_useful_result: float = 0.0
    unnecessary_model_calls: int = 0
    permission_blocks: int = 0
    meaningful_deltas: int = 0
    safe_autonomous_runtime_seconds: float = 0.0
    is_better_than_yesterday: bool = True
    learning_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DailyAIImprovementCouncil:
    """Master controller for multi-AI improvement, competitive benchmarking & continuous learning."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir.resolve()
        self.events_dir = self.repo_dir / "events"
        self.intel_dir = self.events_dir / "resource-intelligence"
        self.knowledge_dir = self.events_dir / "knowledge-base"
        self.state_dir = self.events_dir / "runtime-state"

        self.intel_dir.mkdir(parents=True, exist_ok=True)
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.council_state_file = self.intel_dir / "daily_improvement_council.json"
        self.backlog_file = self.intel_dir / "improvement_backlog.json"
        self.lessons_file = self.knowledge_dir / "distilled_lessons.json"
        self.benchmark_file = self.intel_dir / "competitive_daily_benchmarks.json"
        self.motto_file = self.state_dir / "central_motto.json"

        self.motto = PERMANENT_MOTTO
        self.backlog: Dict[str, Dict[str, Any]] = {}
        self.lessons: Dict[str, DistilledLesson] = {}
        self.deliberations: List[CouncilDeliberation] = []
        self.benchmarks: Dict[str, DailyBenchmarkSnapshot] = {}

        self._persist_motto()
        self.load_all()

    def _persist_motto(self) -> None:
        """Persists the permanent motto into central runtime state."""
        payload = {
            "permanent_motto": self.motto,
            "updated_at": utc_now(),
            "status": "ACTIVE_DIRECTIVE",
            "principles": [
                "LEARN_EVERY_DAY",
                "QUESTION_OUR_METHODS",
                "LEARN_FROM_OTHER_AIS",
                "SEARCH_FOR_BETTER_SOLUTIONS",
                "TEST_INSTEAD_OF_GUESSING",
                "KEEP_WHAT_WORKS",
                "REPLACE_WHAT_IS_PROVEN_WORSE",
                "SHARE_VERIFIED_KNOWLEDGE",
                "REDUCE_WASTE",
                "REDUCE_HUMAN_ATTENTION",
                "KEEP_MOVING_TOWARD_THE_REAL_GOAL",
            ],
        }
        self.motto_file.parent.mkdir(parents=True, exist_ok=True)
        self.motto_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load_all(self) -> None:
        if self.backlog_file.exists():
            try:
                self.backlog = json.loads(self.backlog_file.read_text(encoding="utf-8"))
            except Exception:
                self.backlog = {}

        if self.lessons_file.exists():
            try:
                ldata = json.loads(self.lessons_file.read_text(encoding="utf-8"))
                for k, v in ldata.items():
                    self.lessons[k] = DistilledLesson(
                        lesson_id=v.get("lesson_id", k),
                        knowledge_type=KnowledgeType(v.get("knowledge_type", KnowledgeType.VERIFIED_FACT.value)),
                        topic=v.get("topic", "GENERAL"),
                        concise_lesson=v.get("concise_lesson", ""),
                        source_role=PerspectiveRole(v.get("source_role", PerspectiveRole.GOOGLE_BUILDER.value)),
                        confidence=v.get("confidence", 0.9),
                        verified_by=v.get("verified_by", "DETERMINISTIC_TEST"),
                        created_at=v.get("created_at", utc_now()),
                        applicability=v.get("applicability", []),
                        recheck_trigger=v.get("recheck_trigger", ""),
                    )
            except Exception:
                self.lessons = {}

        if self.benchmark_file.exists():
            try:
                bdata = json.loads(self.benchmark_file.read_text(encoding="utf-8"))
                for k, v in bdata.items():
                    self.benchmarks[k] = DailyBenchmarkSnapshot(**v)
            except Exception:
                self.benchmarks = {}

    def save_all(self) -> None:
        self.backlog_file.write_text(json.dumps(self.backlog, indent=2), encoding="utf-8")
        self.lessons_file.write_text(
            json.dumps({k: v.to_dict() for k, v in self.lessons.items()}, indent=2),
            encoding="utf-8",
        )
        self.benchmark_file.write_text(
            json.dumps({k: v.to_dict() for k, v in self.benchmarks.items()}, indent=2),
            encoding="utf-8",
        )

        council_state = {
            "permanent_motto": self.motto,
            "last_council_at": utc_now(),
            "backlog_items_count": len(self.backlog),
            "lessons_learned_count": len(self.lessons),
            "recent_benchmarks_count": len(self.benchmarks),
            "latest_deliberation": self.deliberations[-1].to_dict() if self.deliberations else None,
        }
        self.council_state_file.write_text(json.dumps(council_state, indent=2), encoding="utf-8")

    def submit_improvement_candidate(
        self,
        question: str,
        source_role: PerspectiveRole,
        current_method: str,
        proposed_alternative: str,
        evidence: Dict[str, Any],
        expected_value: str,
        safety: str = "SAFE_LOCAL",
        reversibility: str = "REVERSIBLE",
        cost: float = 0.0,
        human_attention_saved: str = "HIGH",
        project_goal_impact: str = "HIGH",
        confidence: float = 0.85,
    ) -> str:
        """Adds a verified candidate question/idea to the canonical improvement backlog."""
        raw_id = f"{question}|{current_method}|{proposed_alternative}"
        imp_id = f"IMP-{hashlib.sha256(raw_id.encode('utf-8')).hexdigest()[:12]}"

        self.backlog[imp_id] = {
            "improvement_id": imp_id,
            "question": question,
            "source_role": source_role.value,
            "current_method": current_method,
            "proposed_alternative": proposed_alternative,
            "evidence": evidence,
            "expected_value": expected_value,
            "safety": safety,
            "reversibility": reversibility,
            "cost": cost,
            "human_attention_saved": human_attention_saved,
            "project_goal_impact": project_goal_impact,
            "confidence": confidence,
            "status": "PENDING_DELIBERATION",
            "created_at": utc_now(),
            "decision": None,
        }
        self.save_all()
        return imp_id

    def hold_bounded_council(
        self,
        question: str,
        proposals: List[ImprovementProposal],
        challenges: Optional[List[Dict[str, Any]]] = None,
    ) -> CouncilDeliberation:
        """Conducts an evidence-weighted multi-AI improvement deliberation without endless loops."""
        challenges = challenges or []
        delib_id = f"DELIB-{int(time.time()*1000)}"

        # 1. Evaluate Proposals by Evidence Weight
        best_proposal: Optional[ImprovementProposal] = None
        best_score = 0.0

        for prop in proposals:
            # Score factors: evidence quality (0-1), confidence (0-1), safety (1.0 for low, 0.5 for med, 0 for high)
            safety_factor = 1.0 if prop.risk == "LOW" else (0.5 if prop.risk == "MEDIUM" else 0.0)
            evidence_weight = float(prop.evidence.get("sample_count", 1)) * 0.2
            evidence_weight = min(1.0, max(0.4, evidence_weight))
            cost_factor = 1.0 if prop.estimated_cost == 0.0 else 0.2

            score = (prop.confidence * 0.4) + (evidence_weight * 0.3) + (safety_factor * 0.2) + (cost_factor * 0.1)

            if score > best_score:
                best_score = score
                best_proposal = prop

        # 2. Factor in Challenges
        has_critical_challenge = any(c.get("severity") == "CRITICAL" for c in challenges)

        if has_critical_challenge or best_score < 0.65 or not best_proposal:
            verdict = CouncilVerdict.CURRENT_METHOD_RETAINED
            reason = "Challenger failed evidence threshold or critical safety challenge raised -> Current incumbent retained"
            rollback = None
        elif best_score >= 0.85 and best_proposal.risk == "LOW":
            verdict = CouncilVerdict.ADOPT
            reason = f"Proposal by {best_proposal.role.value} demonstrably superior (score {round(best_score, 2)}) with verified local evidence"
            rollback = f"Restore prior method: {best_proposal.current_method}"
        else:
            verdict = CouncilVerdict.SAFE_EXPERIMENT
            reason = f"Proposal shows promise (score {round(best_score, 2)}) -> Authorized bounded safe experiment on low-risk scope"
            rollback = f"Revert experiment back to {best_proposal.current_method}"

        deliberation = CouncilDeliberation(
            deliberation_id=delib_id,
            question=question,
            proposals=proposals,
            challenges=challenges,
            verdict=verdict,
            evidence_weighted_score=best_score,
            decision_reason=reason,
            rollback_plan=rollback,
        )

        self.deliberations.append(deliberation)
        if len(self.deliberations) > 30:
            self.deliberations = self.deliberations[-30:]

        # 3. Store distilled lesson
        if best_proposal and verdict in (CouncilVerdict.ADOPT, CouncilVerdict.CURRENT_METHOD_RETAINED):
            lesson_id = f"LES-{int(time.time()*1000)}"
            self.record_distilled_lesson(
                lesson_id=lesson_id,
                knowledge_type=KnowledgeType.EXPERIMENT_RESULT,
                topic=question[:50],
                concise_lesson=f"Verdict: {verdict.value}. {reason}",
                source_role=best_proposal.role,
                confidence=best_score,
                verified_by="COUNCIL_DELIBERATION",
                applicability=["DISPATCHER", "ROUTER", "GOOGLE_BUILDER"],
            )

        self.save_all()
        return deliberation

    def record_distilled_lesson(
        self,
        lesson_id: str,
        knowledge_type: KnowledgeType,
        topic: str,
        concise_lesson: str,
        source_role: PerspectiveRole,
        confidence: float = 0.95,
        verified_by: str = "DETERMINISTIC_TEST",
        applicability: Optional[List[str]] = None,
        recheck_trigger: str = "",
    ) -> DistilledLesson:
        """Records a concise verified lesson for organizational memory."""
        lesson = DistilledLesson(
            lesson_id=lesson_id,
            knowledge_type=knowledge_type,
            topic=topic,
            concise_lesson=concise_lesson,
            source_role=source_role,
            confidence=confidence,
            verified_by=verified_by,
            applicability=applicability or ["ALL_WORKERS"],
            recheck_trigger=recheck_trigger,
        )
        self.lessons[lesson_id] = lesson
        self.save_all()
        return lesson

    def record_daily_benchmark(
        self,
        useful_tasks_completed: int,
        failure_rate: float = 0.0,
        duplicate_executions: int = 0,
        human_interventions: int = 0,
        weiter_prompts: int = 0,
        runtime_seconds: float = 0.0,
        summary: str = "",
    ) -> DailyBenchmarkSnapshot:
        """Records today's operational metrics and evaluates if we are better than yesterday."""
        today_str = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
        yesterday_str = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).strftime("%Y-%m-%d")

        yesterday = self.benchmarks.get(yesterday_str)
        is_better = True

        if yesterday:
            # We are better if: more/equal useful tasks, lower/equal failures, 0 duplicates, 0 weiter prompts
            is_better = (
                useful_tasks_completed >= yesterday.useful_tasks_completed
                and failure_rate <= yesterday.failure_rate
                and duplicate_executions <= yesterday.duplicate_executions
                and human_interventions <= yesterday.human_interventions
                and weiter_prompts == 0
            )

        snap = DailyBenchmarkSnapshot(
            date_str=today_str,
            useful_tasks_completed=useful_tasks_completed,
            failure_rate=failure_rate,
            duplicate_executions=duplicate_executions,
            human_interventions=human_interventions,
            weiter_prompts_required=weiter_prompts,
            safe_autonomous_runtime_seconds=runtime_seconds,
            is_better_than_yesterday=is_better,
            learning_summary=summary or f"Completed {useful_tasks_completed} tasks with 0 EUR spend, 0 weiter prompts.",
        )

        self.benchmarks[today_str] = snap
        self.save_all()
        return snap


if __name__ == "__main__":
    council = DailyAIImprovementCouncil()
    print("=== DAILY AI IMPROVEMENT COUNCIL ACTIVE ===")
    print(f"Permanent Motto: {council.motto}")
    # Run test deliberation
    p1 = ImprovementProposal(
        proposal_id="PROP-01",
        role=PerspectiveRole.GOOGLE_BUILDER,
        question="Should we use AST deterministic test gap scanning before LLM generation?",
        current_method="Manual test gap specification",
        proposed_alternative="GeneralEngineeringDiscoveryEngine AST parsing",
        evidence={"sample_count": 5, "accuracy": 1.0},
        expected_benefit="100% deterministic test gap detection with 0 model calls",
        confidence=0.98,
    )
    p2 = ImprovementProposal(
        proposal_id="PROP-02",
        role=PerspectiveRole.CODEX_REVIEWER,
        question="Should we use AST deterministic test gap scanning before LLM generation?",
        current_method="Manual test gap specification",
        proposed_alternative="LLM-driven test gap discovery",
        evidence={"sample_count": 2, "cost": 0.0},
        expected_benefit="Broad heuristic coverage",
        confidence=0.70,
    )
    delib = council.hold_bounded_council(
        question="Should we use AST deterministic test gap scanning before LLM generation?",
        proposals=[p1, p2],
    )
    print(json.dumps(delib.to_dict(), indent=2))
