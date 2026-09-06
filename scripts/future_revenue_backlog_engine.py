#!/usr/bin/env python3
"""Mission 228: Zero-Spend Evidence Accumulation & Future Revenue Backlog.

Deterministic, zero-spend revenue preparation engine for Computer A:
- Curates structured candidate backlog across lawful domains
- Tracks 22-point evidence schema (problem, buyer, primary/secondary evidence,
  unit economics, failure modes, what we can do better, next zero-cost test)
- Social Metric Policy: Likes/followers quality weight = 0 (never counts as proof of demand)
- Failure Pattern Library: Maps 3 common failures -> 3 concrete preventions
- Launch Readiness Packets: Structured pre-launch collateral with status READY_TO_TEST_LATER
- Validation State Machine: IDEA -> HYPOTHESIS -> RESEARCHABLE -> SIMULATION_PASS ->
  DEMAND_EVIDENCE_FOUND -> TEST_READY -> EXTERNAL_TEST_REQUIRED -> VALIDATED
- Top-3 Pipeline:
  * TOP_1_FASTEST_LOW_RISK_REVENUE
  * TOP_2_BEST_REPEATABLE_REVENUE
  * TOP_3_BEST_LONG_TERM_ASSET
  * TOP_RESEARCH_ONLY
- Financial Research Lab: PAPER / SIMULATION ONLY (REAL_TRADES = 0)
- Durable State Files:
  * future_revenue_backlog.json
  * daily_opportunity_ranking.json
  * evidence_fingerprints.json
  * failure_pattern_library.json
  * launch_readiness.json
- Financial Firewall: REAL_TRADES=0, REAL_FUNDS_TOUCHED=NO, WALLET_SIGNING=NO, SPEND_EUR=0
"""

from __future__ import annotations

import argparse
import datetime as dt
import enum
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


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def safe_load_json(path: Path) -> dict[str, Any]:
    try:
        if not path.is_file():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def safe_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{uuid.uuid4().hex[:6]}")
    temp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


class CandidateDomain(str, enum.Enum):
    B2B_AUTOMATION = "B2B_AUTOMATION"
    RESEARCH_EVIDENCE_SERVICES = "RESEARCH_EVIDENCE_SERVICES"
    SOFTWARE = "SOFTWARE"
    DATA_PRODUCTS = "DATA_PRODUCTS"
    PUBLISHING = "PUBLISHING"
    EDUCATION = "EDUCATION"
    LOCAL_SERVICES = "LOCAL_SERVICES"
    DIGITAL_PRODUCTS = "DIGITAL_PRODUCTS"
    PHYSICAL_PRODUCTS = "PHYSICAL_PRODUCTS"
    OPERATIONAL_AUTOMATION = "OPERATIONAL_AUTOMATION"
    LOW_CAPITAL_OPPORTUNITY = "LOW_CAPITAL_OPPORTUNITY"
    FINANCIAL_RESEARCH_PAPER_ONLY = "FINANCIAL_RESEARCH_PAPER_ONLY"


class ValidationState(str, enum.Enum):
    IDEA = "IDEA"
    HYPOTHESIS = "HYPOTHESIS"
    RESEARCHABLE = "RESEARCHABLE"
    SIMULATION_PASS = "SIMULATION_PASS"
    DEMAND_EVIDENCE_FOUND = "DEMAND_EVIDENCE_FOUND"
    TEST_READY = "TEST_READY"
    EXTERNAL_TEST_REQUIRED = "EXTERNAL_TEST_REQUIRED"
    VALIDATED = "VALIDATED"


@dataclass
class FailurePreventionPair:
    common_failure_1: str
    our_prevention_1: str
    common_failure_2: str
    our_prevention_2: str
    common_failure_3: str
    our_prevention_3: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LaunchPacket:
    packet_id: str
    candidate_id: str
    offer_description: str
    target_customer: str
    demo_plan: str
    sample_deliverable: str
    price_hypothesis: str
    unit_economics: Dict[str, Any]
    delivery_workflow: List[str]
    qa_checklist: List[str]
    security_checklist: List[str]
    customer_onboarding: List[str]
    success_metrics: Dict[str, Any]
    status: str = "READY_TO_TEST_LATER"
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CandidateProfile:
    candidate_id: str
    title: str
    domain: CandidateDomain
    problem: str
    buyer: str
    primary_evidence: List[str]
    secondary_evidence: List[str]
    current_alternatives: List[str]
    competitors: List[str]
    pricing: str
    customer_pain: str
    market_demand: str
    startup_cost_eur: float
    delivery_cost_eur: float
    platform_fees_pct: float
    time_to_first_revenue: str
    expected_margin_pct: float
    automation_fit: float  # 0.0 to 1.0
    human_work_required: str
    legal_risk: str  # "LOW", "MEDIUM", "HIGH"
    platform_risk: str  # "LOW", "MEDIUM", "HIGH"
    failure_modes: List[str]
    why_others_fail: str
    what_we_can_do_better: str
    next_zero_cost_test: str
    validation_state: ValidationState = ValidationState.HYPOTHESIS
    confidence_score: float = 0.0
    failure_prevention: Optional[FailurePreventionPair] = None
    launch_packet: Optional[LaunchPacket] = None
    fingerprint: str = ""

    def calculate_fingerprint(self) -> str:
        content = f"{self.candidate_id}|{self.title}|{self.domain.value}|{self.startup_cost_eur}|{self.pricing}|{self.next_zero_cost_test}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["domain"] = self.domain.value
        d["validation_state"] = self.validation_state.value
        return d


class FutureRevenueBacklogEngine:
    """Deterministic future revenue preparation engine."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir.resolve()
        self.runtime_dir = self.repo_dir / "events" / "runtime-state"
        self.evidence_dir = self.repo_dir / "events" / "evidence-ledger"

        self.backlog_file = self.runtime_dir / "future_revenue_backlog.json"
        self.ranking_file = self.runtime_dir / "daily_opportunity_ranking.json"
        self.fingerprints_file = self.runtime_dir / "evidence_fingerprints.json"
        self.failure_library_file = self.runtime_dir / "failure_pattern_library.json"
        self.launch_readiness_file = self.runtime_dir / "launch_readiness.json"

        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

        self.candidates: Dict[str, CandidateProfile] = {}
        self.fingerprints: Dict[str, str] = {}
        self._load_state()

    def _load_state(self) -> None:
        raw_backlog = safe_load_json(self.backlog_file)
        for cid, data in raw_backlog.get("candidates", {}).items():
            try:
                cand = CandidateProfile(
                    candidate_id=data["candidate_id"],
                    title=data["title"],
                    domain=CandidateDomain(data["domain"]),
                    problem=data.get("problem", ""),
                    buyer=data.get("buyer", ""),
                    primary_evidence=data.get("primary_evidence", []),
                    secondary_evidence=data.get("secondary_evidence", []),
                    current_alternatives=data.get("current_alternatives", []),
                    competitors=data.get("competitors", []),
                    pricing=data.get("pricing", ""),
                    customer_pain=data.get("customer_pain", ""),
                    market_demand=data.get("market_demand", ""),
                    startup_cost_eur=float(data.get("startup_cost_eur", 0.0)),
                    delivery_cost_eur=float(data.get("delivery_cost_eur", 0.0)),
                    platform_fees_pct=float(data.get("platform_fees_pct", 0.0)),
                    time_to_first_revenue=data.get("time_to_first_revenue", "1-3 days"),
                    expected_margin_pct=float(data.get("expected_margin_pct", 80.0)),
                    automation_fit=float(data.get("automation_fit", 0.8)),
                    human_work_required=data.get("human_work_required", "Low"),
                    legal_risk=data.get("legal_risk", "LOW"),
                    platform_risk=data.get("platform_risk", "LOW"),
                    failure_modes=data.get("failure_modes", []),
                    why_others_fail=data.get("why_others_fail", ""),
                    what_we_can_do_better=data.get("what_we_can_do_better", ""),
                    next_zero_cost_test=data.get("next_zero_cost_test", ""),
                    validation_state=ValidationState(data.get("validation_state", ValidationState.HYPOTHESIS.value)),
                    confidence_score=float(data.get("confidence_score", 0.0)),
                )
                cand.fingerprint = cand.calculate_fingerprint()
                self.candidates[cid] = cand
            except Exception:
                pass

        self.fingerprints = safe_load_json(self.fingerprints_file).get("fingerprints", {})

    def register_or_update_candidate(self, candidate: CandidateProfile) -> bool:
        """Registers candidate deterministically and fingerprints evidence."""
        candidate.fingerprint = candidate.calculate_fingerprint()
        is_new = candidate.candidate_id not in self.candidates
        self.candidates[candidate.candidate_id] = candidate
        self.fingerprints[candidate.candidate_id] = candidate.fingerprint
        return is_new

    def evaluate_candidate_confidence(self, candidate: CandidateProfile) -> float:
        """Computes deterministic confidence score (0.0 to 1.0)."""
        # Primary evidence weight (up to 0.35)
        primary_score = min(0.35, len(candidate.primary_evidence) * 0.10)
        # Unit economics & margin (up to 0.25)
        margin_score = min(0.25, (candidate.expected_margin_pct / 100.0) * 0.25)
        # Automation fit (up to 0.25)
        auto_score = candidate.automation_fit * 0.25
        # Startup cost bonus (up to 0.15 for <= 10 EUR)
        cost_score = 0.15 if candidate.startup_cost_eur <= 10.0 else (0.05 if candidate.startup_cost_eur <= 100.0 else 0.0)

        raw = primary_score + margin_score + auto_score + cost_score
        candidate.confidence_score = round(min(1.0, max(0.0, raw)), 3)
        return candidate.confidence_score

    def build_failure_library(self) -> Dict[str, Any]:
        """Generates failure pattern and prevention library across all active candidates."""
        library = {}
        for cid, cand in self.candidates.items():
            if cand.failure_prevention:
                library[cid] = {
                    "candidate_title": cand.title,
                    "domain": cand.domain.value,
                    "common_failures": [
                        cand.failure_prevention.common_failure_1,
                        cand.failure_prevention.common_failure_2,
                        cand.failure_prevention.common_failure_3,
                    ],
                    "our_preventions": [
                        cand.failure_prevention.our_prevention_1,
                        cand.failure_prevention.our_prevention_2,
                        cand.failure_prevention.our_prevention_3,
                    ],
                }
        safe_write_json(self.failure_library_file, {"failure_patterns": library, "updated_at": utc_now()})
        return library

    def build_launch_readiness(self) -> Dict[str, Any]:
        """Collects future launch packets with status READY_TO_TEST_LATER."""
        readiness = {}
        for cid, cand in self.candidates.items():
            if cand.launch_packet:
                readiness[cid] = cand.launch_packet.to_dict()

        safe_write_json(self.launch_readiness_file, {"launch_packets": readiness, "updated_at": utc_now()})
        return readiness

    def generate_top_3_pipeline(self) -> Dict[str, Any]:
        """Calculates Top-1, Top-2, Top-3, and Top-Research-Only rankings."""
        all_cands = list(self.candidates.values())
        for c in all_cands:
            self.evaluate_candidate_confidence(c)

        # Sort non-financial candidates by confidence descending
        commercial_cands = [c for c in all_cands if c.domain != CandidateDomain.FINANCIAL_RESEARCH_PAPER_ONLY]
        sorted_commercial = sorted(commercial_cands, key=lambda c: c.confidence_score, reverse=True)

        fast_revenue = [c for c in sorted_commercial if "1" in c.time_to_first_revenue or "2" in c.time_to_first_revenue]
        repeatable = [c for c in sorted_commercial if c.domain in [CandidateDomain.B2B_AUTOMATION, CandidateDomain.OPERATIONAL_AUTOMATION, CandidateDomain.RESEARCH_EVIDENCE_SERVICES]]
        long_term = [c for c in sorted_commercial if c.domain in [CandidateDomain.SOFTWARE, CandidateDomain.DATA_PRODUCTS, CandidateDomain.DIGITAL_PRODUCTS]]

        top_1 = fast_revenue[0].to_dict() if fast_revenue else (sorted_commercial[0].to_dict() if sorted_commercial else None)
        top_2 = repeatable[0].to_dict() if repeatable else (sorted_commercial[1].to_dict() if len(sorted_commercial) > 1 else None)
        top_3 = long_term[0].to_dict() if long_term else (sorted_commercial[2].to_dict() if len(sorted_commercial) > 2 else None)

        financial_cands = [c for c in all_cands if c.domain == CandidateDomain.FINANCIAL_RESEARCH_PAPER_ONLY]
        top_research = financial_cands[0].to_dict() if financial_cands else None

        pipeline = {
            "ranking_date": utc_now(),
            "top_1_fastest_low_risk_revenue": top_1,
            "top_2_best_repeatable_revenue": top_2,
            "top_3_best_long_term_asset": top_3,
            "top_research_only": top_research,
            "total_candidates": len(all_cands),
            "model_calls_used": 0,
            "spend_eur": 0.0,
        }

        safe_write_json(self.ranking_file, pipeline)
        return pipeline

    def persist_all_state(self) -> None:
        """Persists all 5 canonical durable files."""
        # 1. Backlog
        safe_write_json(self.backlog_file, {
            "updated_at": utc_now(),
            "candidates": {cid: c.to_dict() for cid, c in self.candidates.items()},
        })
        # 2. Fingerprints
        safe_write_json(self.fingerprints_file, {
            "updated_at": utc_now(),
            "fingerprints": self.fingerprints,
        })
        # 3. Failure Library
        self.build_failure_library()
        # 4. Launch Readiness
        self.build_launch_readiness()
        # 5. Top-3 Pipeline Ranking
        self.generate_top_3_pipeline()


def main() -> int:
    parser = argparse.ArgumentParser(description="Future Revenue Backlog Engine")
    parser.add_argument("--once", action="store_true", help="Run single backlog update and exit")
    args = parser.parse_args()

    engine = FutureRevenueBacklogEngine()
    engine.persist_all_state()
    ranking = safe_load_json(engine.ranking_file)
    print(json.dumps(ranking, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
