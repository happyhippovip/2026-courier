"""Opportunity Record Model (Mission 225-R1).

Represents a general-purpose legal opportunity candidate across B2B,
research services, publishing, local services, physical/digital products,
and observational financial research.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from scripts.opportunity_os.evidence_hierarchy import EvidenceItem, SocialSignalAnalysis, EvidenceEvaluator


class OpportunityDomain(enum.Enum):
    B2B_AUTOMATION = "B2B_AUTOMATION"
    RESEARCH_SERVICES = "RESEARCH_SERVICES"
    PUBLISHING = "PUBLISHING"
    EDUCATION = "EDUCATION"
    DIGITAL_PRODUCTS = "DIGITAL_PRODUCTS"
    SOFTWARE = "SOFTWARE"
    LOCAL_SERVICES = "LOCAL_SERVICES"
    DATA_PRODUCTS = "DATA_PRODUCTS"
    MEDIA = "MEDIA"
    PHYSICAL_GOODS = "PHYSICAL_GOODS"
    AGRICULTURE = "AGRICULTURE"
    FINANCIAL_RESEARCH = "FINANCIAL_RESEARCH"  # Paper only!
    OTHER_LAWFUL = "OTHER_LAWFUL"


class OpportunityStatus(enum.Enum):
    DISCOVERED = "DISCOVERED"
    RESEARCHABLE = "RESEARCHABLE"
    NEEDS_MORE_EVIDENCE = "NEEDS_MORE_EVIDENCE"
    ACTION_ELIGIBLE = "ACTION_ELIGIBLE"
    SIMULATION_ONLY = "SIMULATION_ONLY"
    CHEAP_TEST_DESIGNED = "CHEAP_TEST_DESIGNED"
    TEST_READY = "TEST_READY"
    TEST_EXECUTED = "TEST_EXECUTED"
    TEST_RESULT_VERIFIED = "TEST_RESULT_VERIFIED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    PARKED = "PARKED"


@dataclass
class UnitEconomics:
    selling_price_eur: float
    cost_of_delivery_eur: float
    platform_fee_eur: float = 0.0
    customer_acquisition_cost_est_eur: float = 0.0

    @property
    def gross_margin_eur(self) -> float:
        return self.selling_price_eur - (self.cost_of_delivery_eur + self.platform_fee_eur)

    @property
    def gross_margin_pct(self) -> float:
        if self.selling_price_eur <= 0:
            return 0.0
        return (self.gross_margin_eur / self.selling_price_eur) * 100.0

    @property
    def net_contribution_eur(self) -> float:
        return self.gross_margin_eur - self.customer_acquisition_cost_est_eur

    @property
    def is_positive(self) -> bool:
        return self.net_contribution_eur > 0.0


@dataclass
class OpportunityRecord:
    opportunity_id: str
    title: str
    domain: OpportunityDomain
    problem: str
    customer: str
    evidence_sources: List[EvidenceItem] = field(default_factory=list)
    social_signals: Optional[SocialSignalAnalysis] = None
    expected_revenue_eur: float = 0.0
    expected_cost_eur: float = 0.0
    initial_capital_required_eur: float = 0.0
    time_to_first_revenue_days: int = 1
    automation_percentage: float = 0.8  # 0.0 to 1.0
    human_effort_hours_per_unit: float = 0.5
    legal_risk: float = 0.1             # 0.0 (none) to 1.0 (extreme)
    platform_risk: float = 0.2          # 0.0 to 1.0
    fraud_risk: float = 0.0             # 0.0 to 1.0
    execution_risk: float = 0.2         # 0.0 to 1.0
    market_size_evidence: str = ""
    competition_intensity: float = 0.4  # 0.0 to 1.0
    unit_economics: Optional[UnitEconomics] = None
    repeatability_score: float = 0.8    # 0.0 to 1.0
    scalability_score: float = 0.8      # 0.0 to 1.0
    failure_modes: List[str] = field(default_factory=list)
    reversibility: bool = True          # Can we undo/exit without catastrophic loss?
    confidence_score: float = 0.5       # Derived from evidence
    next_safe_test: str = ""
    status: OpportunityStatus = OpportunityStatus.DISCOVERED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_paper_only: bool = False         # Enforced True for FINANCIAL_RESEARCH
    customer_demand_verified: bool = False
    revenue_verified: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.domain == OpportunityDomain.FINANCIAL_RESEARCH:
            self.is_paper_only = True

    @property
    def is_action_eligible(self) -> bool:
        """Strict Action Eligibility Gate:
        1. Financial domain is ALWAYS paper-only (never action eligible for live trades)
        2. Unit economics must be known (not None)
        3. Unit economics must be positive
        4. EvidenceEvaluator.can_authorize_action(evidence_sources) must be True
        5. Legal risk must not be severe (< 0.5)
        6. Fraud risk must be 0.0
        """
        if self.domain == OpportunityDomain.FINANCIAL_RESEARCH:
            return False
        if self.unit_economics is None:
            return False
        if not self.unit_economics.is_positive:
            return False
        if not EvidenceEvaluator.can_authorize_action(self.evidence_sources):
            return False
        if self.legal_risk >= 0.5 or self.fraud_risk > 0.0:
            return False
        return True

    @property
    def is_researchable(self) -> bool:
        """An opportunity is researchable if it is lawful and has a defined problem."""
        return self.fraud_risk == 0.0 and self.legal_risk < 0.8
