#!/usr/bin/env python3
"""Mission 226: Daily Evidence Scout & Opportunity Ranker.

Deterministic, zero-model-quota evidence scout for Computer A:
- Observes, normalizes, verifies, dedups, and scores candidate business/software opportunities
- Ingests demand signals across: B2B automation, freelance demand, verification services,
  publishing niches, digital products, software, and local service opportunities
- Social Metric Policy: Likes/views/followers NEVER count as quality evidence (flagged as HYPE/CROWDING)
- Generates Daily Top Three:
  * TOP_1_LOW_RISK_REVENUE
  * TOP_2_LOW_RISK_REVENUE
  * TOP_3_LONGER_TERM_OPTION
- Zero model calls on unchanged data (Deterministic First, 0 EUR spend)
- Wakes builder ONLY when NEW_HIGH_CONFIDENCE_OPPORTUNITY (confidence >= 0.85) is verified
- Financial Firewall: REAL_TRADES=0, REAL_FUNDS_TOUCHED=NO, WALLET_SIGNING=NO
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


class OpportunityDomain(str, enum.Enum):
    B2B_AUTOMATION = "B2B_AUTOMATION"
    FREELANCE_DEMAND = "FREELANCE_DEMAND"
    RESEARCH_VERIFICATION = "RESEARCH_VERIFICATION"
    PUBLISHING_NICHES = "PUBLISHING_NICHES"
    DIGITAL_PRODUCTS = "DIGITAL_PRODUCTS"
    SOFTWARE_OPPORTUNITY = "SOFTWARE_OPPORTUNITY"
    LOCAL_SERVICES = "LOCAL_SERVICES"
    LOW_CAPITAL_BUSINESS = "LOW_CAPITAL_BUSINESS"
    FINANCIAL_RESEARCH = "FINANCIAL_RESEARCH"


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Reversibility(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class EvidenceSignal:
    source_uri: str
    source_type: str  # "PRIMARY_BUYER_REQUEST", "CUSTOMER_CONVERSATION", "PUBLIC_JOB_BOARD", "SOCIAL_METRIC"
    signal_text: str
    is_primary_source: bool = True
    social_metric_flag: Optional[str] = None  # "HYPE", "CROWDING", "INORGANIC_ACTIVITY_RISK"
    timestamp: str = field(default_factory=utc_now)


@dataclass
class OpportunityCandidate:
    opportunity_id: str
    title: str
    domain: OpportunityDomain
    evidence_count: int
    primary_source_count: int
    demand_evidence: List[Dict[str, Any]]
    startup_cost_eur: float
    time_to_test: str
    time_to_revenue: str
    unit_economics_confidence: float  # 0.0 to 1.0
    automation_fit: float  # 0.0 to 1.0
    reversibility: Reversibility
    risk: RiskLevel
    next_cheap_test: str
    overall_confidence_score: float = 0.0
    is_top_performer: bool = False
    fingerprint: str = ""

    def calculate_fingerprint(self) -> str:
        content = f"{self.title}|{self.domain.value}|{self.startup_cost_eur}|{self.time_to_test}|{self.next_cheap_test}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["domain"] = self.domain.value
        d["risk"] = self.risk.value
        d["reversibility"] = self.reversibility.value
        return d


@dataclass
class DailyRankings:
    ranking_date: str = field(default_factory=utc_now)
    top_1_low_risk_revenue: Optional[Dict[str, Any]] = None
    top_2_low_risk_revenue: Optional[Dict[str, Any]] = None
    top_3_longer_term_option: Optional[Dict[str, Any]] = None
    all_ranked_candidates: List[Dict[str, Any]] = field(default_factory=list)
    new_high_confidence_found: bool = False
    model_calls_used: int = 0
    spend_eur: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DailyEvidenceScout:
    """Deterministic evidence scout & opportunity ranker."""

    HIGH_CONFIDENCE_THRESHOLD = 0.85

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir.resolve()
        self.evidence_dir = self.repo_dir / "events" / "evidence-ledger"
        self.runtime_dir = self.repo_dir / "events" / "runtime-state"
        self.ranking_file = self.runtime_dir / "daily_opportunity_ranking.json"
        self.scout_state_file = self.runtime_dir / "daily_evidence_scout_state.json"

        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)

        self._seen_fingerprints: Set[str] = set()
        self._load_prior_state()

    def _load_prior_state(self) -> None:
        state = safe_load_json(self.scout_state_file)
        for fp in state.get("seen_fingerprints", []):
            self._seen_fingerprints.add(fp)

    def _save_state(self) -> None:
        safe_write_json(self.scout_state_file, {
            "last_run": utc_now(),
            "seen_fingerprints": list(self._seen_fingerprints),
            "model_calls_used": 0,
            "spend_eur": 0.0,
        })

    def normalize_evidence_signal(
        self,
        source_uri: str,
        source_type: str,
        signal_text: str,
        likes_or_followers_count: Optional[int] = None,
    ) -> EvidenceSignal:
        """Normalizes and flags social vanity metrics according to strict social policy."""
        is_primary = source_type in ["PRIMARY_BUYER_REQUEST", "CUSTOMER_CONVERSATION", "PUBLIC_JOB_BOARD"]
        social_flag = None

        if source_type == "SOCIAL_METRIC" or likes_or_followers_count is not None:
            is_primary = False
            if likes_or_followers_count and likes_or_followers_count > 10000:
                social_flag = "HYPE"
            else:
                social_flag = "INORGANIC_ACTIVITY_RISK"

        return EvidenceSignal(
            source_uri=source_uri,
            source_type=source_type,
            signal_text=signal_text,
            is_primary_source=is_primary,
            social_metric_flag=social_flag,
        )

    def evaluate_and_score_candidate(
        self,
        candidate_data: Dict[str, Any],
        signals: List[EvidenceSignal],
    ) -> OpportunityCandidate:
        """Scores candidate deterministically without LLM calls."""
        primary_sources = [s for s in signals if s.is_primary_source and not s.social_metric_flag]
        hype_signals = [s for s in signals if s.social_metric_flag is not None]

        evidence_count = len(signals)
        primary_count = len(primary_sources)

        startup_cost = float(candidate_data.get("startup_cost_eur", 0.0))
        unit_econ = float(candidate_data.get("unit_economics_confidence", 0.5))
        auto_fit = float(candidate_data.get("automation_fit", 0.5))

        # Scoring Formula:
        # 1. Base on primary evidence count (up to 0.35)
        evidence_score = min(0.35, primary_count * 0.10)
        # 2. Automation fit weight (up to 0.25)
        auto_score = auto_fit * 0.25
        # 3. Unit economics confidence (up to 0.25)
        econ_score = unit_econ * 0.25
        # 4. Low cost bonus (up to 0.15)
        cost_bonus = 0.15 if startup_cost <= 50.0 else (0.05 if startup_cost <= 200.0 else 0.0)

        raw_score = evidence_score + auto_score + econ_score + cost_bonus

        # Social Penalty (Hype / Crowding reduces confidence)
        if hype_signals:
            raw_score *= 0.85

        final_score = round(min(1.0, max(0.0, raw_score)), 3)

        opp = OpportunityCandidate(
            opportunity_id=candidate_data.get("opportunity_id", f"opp-scout-{uuid.uuid4().hex[:6]}"),
            title=candidate_data.get("title", "Untitled Opportunity"),
            domain=OpportunityDomain(candidate_data.get("domain", OpportunityDomain.B2B_AUTOMATION.value)),
            evidence_count=evidence_count,
            primary_source_count=primary_count,
            demand_evidence=[asdict(s) for s in signals],
            startup_cost_eur=startup_cost,
            time_to_test=candidate_data.get("time_to_test", "1-2 days"),
            time_to_revenue=candidate_data.get("time_to_revenue", "< 7 days"),
            unit_economics_confidence=unit_econ,
            automation_fit=auto_fit,
            reversibility=Reversibility(candidate_data.get("reversibility", Reversibility.HIGH.value)),
            risk=RiskLevel(candidate_data.get("risk", RiskLevel.LOW.value)),
            next_cheap_test=candidate_data.get("next_cheap_test", "Deterministic dry run outreach simulation"),
            overall_confidence_score=final_score,
        )
        opp.fingerprint = opp.calculate_fingerprint()
        return opp

    def rank_daily_opportunities(
        self,
        candidates: List[OpportunityCandidate],
    ) -> DailyRankings:
        """Ranks opportunities into Daily Top Three and identifies new high-confidence items."""
        # Sort candidates descending by confidence score
        sorted_cands = sorted(candidates, key=lambda c: c.overall_confidence_score, reverse=True)

        low_risk_cands = [c for c in sorted_cands if c.risk == RiskLevel.LOW and c.startup_cost_eur <= 100.0]
        long_term_cands = [c for c in sorted_cands if c.domain in [OpportunityDomain.SOFTWARE_OPPORTUNITY, OpportunityDomain.DIGITAL_PRODUCTS]]

        top_1 = low_risk_cands[0].to_dict() if len(low_risk_cands) > 0 else (sorted_cands[0].to_dict() if sorted_cands else None)
        top_2 = low_risk_cands[1].to_dict() if len(low_risk_cands) > 1 else (sorted_cands[1].to_dict() if len(sorted_cands) > 1 else None)
        top_3 = long_term_cands[0].to_dict() if long_term_cands else (sorted_cands[2].to_dict() if len(sorted_cands) > 2 else None)

        new_high_conf = False
        for c in sorted_cands:
            if c.overall_confidence_score >= self.HIGH_CONFIDENCE_THRESHOLD and c.fingerprint not in self._seen_fingerprints:
                new_high_conf = True
                self._seen_fingerprints.add(c.fingerprint)

        ranking = DailyRankings(
            ranking_date=utc_now(),
            top_1_low_risk_revenue=top_1,
            top_2_low_risk_revenue=top_2,
            top_3_longer_term_option=top_3,
            all_ranked_candidates=[c.to_dict() for c in sorted_cands],
            new_high_confidence_found=new_high_conf,
            model_calls_used=0,
            spend_eur=0.0,
        )

        safe_write_json(self.ranking_file, ranking.to_dict())
        self._save_state()
        return ranking

    def run_evidence_scout_cycle(self) -> DailyRankings:
        """Executes full deterministic observe, evaluate, rank cycle from canonical files."""
        # Check if there are evidence definition files in events/evidence-ledger/
        candidates: List[OpportunityCandidate] = []
        evidence_files = list(self.evidence_dir.glob("*.json"))

        for ef in evidence_files:
            data = safe_load_json(ef)
            if not data or "title" not in data:
                continue
            signals = []
            for s in data.get("raw_signals", []):
                signals.append(self.normalize_evidence_signal(
                    source_uri=s.get("source_uri", "unknown"),
                    source_type=s.get("source_type", "PRIMARY_BUYER_REQUEST"),
                    signal_text=s.get("signal_text", ""),
                    likes_or_followers_count=s.get("likes_count"),
                ))
            cand = self.evaluate_and_score_candidate(data, signals)
            candidates.append(cand)

        return self.rank_daily_opportunities(candidates)


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily Evidence Scout & Opportunity Ranker")
    parser.add_argument("--once", action="store_true", help="Run single evidence scout cycle and exit")
    args = parser.parse_args()

    scout = DailyEvidenceScout()
    ranking = scout.run_evidence_scout_cycle()
    print(json.dumps(ranking.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
