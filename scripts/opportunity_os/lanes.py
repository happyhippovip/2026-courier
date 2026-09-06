"""Top Priority Lanes & Specialized Factories (Mission 225).

Implements:
1. B2bAutomationFactory (Priority Lane A):
   - Email Triage, Lead Qualification, Appointment Workflow, Document Processing, etc.
2. EvidenceServiceFactory (Priority Lane B):
   - Competitor Brief, Supplier Check, Price Comparison, Fact Check, Executive Brief.
3. PublishingFactory (Priority Lane C):
   - Niche research (animals, nature, education, fruit trees), demand verification, copyright review.
4. FinancialResearchLab (Paper / Synthetic Only):
   - Chart Experience Engine / Pattern Evidence. Real trades = 0.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from scripts.opportunity_os.opportunity_record import (
    OpportunityRecord, OpportunityDomain, OpportunityStatus, UnitEconomics
)
from scripts.opportunity_os.evidence_hierarchy import EvidenceItem, EvidenceLevel


# ---------------------------------------------------------
# Priority Lane A: B2B Automation Factory
# ---------------------------------------------------------

@dataclass
class B2bOfferTemplate:
    offer_type: str
    target_buyer: str
    core_pain: str
    deliverable: str
    implementation_time_hours: float
    price_hypothesis_eur: float
    estimated_cost_eur: float
    maintenance_overhead: str
    security_risk: float

    def to_opportunity_record(self, opp_id: str, evidence: List[EvidenceItem]) -> OpportunityRecord:
        unit_econ = UnitEconomics(
            selling_price_eur=self.price_hypothesis_eur,
            cost_of_delivery_eur=self.estimated_cost_eur,
            platform_fee_eur=0.0,
            customer_acquisition_cost_est_eur=self.price_hypothesis_eur * 0.15
        )
        return OpportunityRecord(
            opportunity_id=opp_id,
            title=f"B2B Automation: {self.offer_type}",
            domain=OpportunityDomain.B2B_AUTOMATION,
            problem=self.core_pain,
            customer=self.target_buyer,
            evidence_sources=evidence,
            expected_revenue_eur=self.price_hypothesis_eur,
            expected_cost_eur=self.estimated_cost_eur,
            initial_capital_required_eur=0.0,
            time_to_first_revenue_days=2,
            automation_percentage=0.85,
            human_effort_hours_per_unit=self.implementation_time_hours,
            legal_risk=0.05,
            platform_risk=0.1,
            unit_economics=unit_econ,
            reversibility=True,
            next_safe_test="Send 1-page sample deliverable / interactive micro-demo to 3 qualified leads."
        )


class B2bAutomationFactory:
    TEMPLATES = {
        "EMAIL_TRIAGE_AUTOMATION": B2bOfferTemplate(
            offer_type="EMAIL_TRIAGE_AUTOMATION",
            target_buyer="B2B Agencies & High-Volume Consultants",
            core_pain="Inboxes flooded with unstructured customer requests causing 4h+ daily triage delay.",
            deliverable="Automated classification webhook + priority tag router.",
            implementation_time_hours=4.0,
            price_hypothesis_eur=149.0,
            estimated_cost_eur=5.0,
            maintenance_overhead="Low",
            security_risk=0.05
        ),
        "LEAD_QUALIFICATION": B2bOfferTemplate(
            offer_type="LEAD_QUALIFICATION",
            target_buyer="B2B SaaS & Services Sales Teams",
            core_pain="Sales reps wasting 50% of meetings on unqualified leads.",
            deliverable="Deterministic multi-point qualification scoring script.",
            implementation_time_hours=3.0,
            price_hypothesis_eur=199.0,
            estimated_cost_eur=8.0,
            maintenance_overhead="Low",
            security_risk=0.05
        ),
        "DOCUMENT_PROCESSING": B2bOfferTemplate(
            offer_type="DOCUMENT_PROCESSING",
            target_buyer="Logistics & Real Estate Brokers",
            core_pain="Manual copy-pasting from PDF contracts into ERP.",
            deliverable="Structured JSON extractor with schema validation.",
            implementation_time_hours=5.0,
            price_hypothesis_eur=299.0,
            estimated_cost_eur=10.0,
            maintenance_overhead="Moderate",
            security_risk=0.08
        )
    }

    @classmethod
    def create_offer(cls, template_name: str, opp_id: str, evidence: List[EvidenceItem]) -> OpportunityRecord:
        template = cls.TEMPLATES.get(template_name)
        if not template:
            raise ValueError(f"Unknown template: {template_name}")
        return template.to_opportunity_record(opp_id, evidence)


# ---------------------------------------------------------
# Priority Lane B: Evidence Service Factory
# ---------------------------------------------------------

@dataclass
class EvidenceServiceOffer:
    service_name: str
    target_client: str
    deliverable_format: str
    price_eur: float
    sources_required: List[str]

    def to_opportunity_record(self, opp_id: str, evidence: List[EvidenceItem]) -> OpportunityRecord:
        unit_econ = UnitEconomics(
            selling_price_eur=self.price_eur,
            cost_of_delivery_eur=2.0,
            platform_fee_eur=0.0,
            customer_acquisition_cost_est_eur=self.price_eur * 0.1
        )
        return OpportunityRecord(
            opportunity_id=opp_id,
            title=f"Evidence Service: {self.service_name}",
            domain=OpportunityDomain.RESEARCH_SERVICES,
            problem=f"Client lacks verified, timestamped facts on {self.service_name}.",
            customer=self.target_client,
            evidence_sources=evidence,
            expected_revenue_eur=self.price_eur,
            expected_cost_eur=2.0,
            initial_capital_required_eur=0.0,
            time_to_first_revenue_days=1,
            automation_percentage=0.90,
            human_effort_hours_per_unit=1.0,
            legal_risk=0.02,
            platform_risk=0.05,
            unit_economics=unit_econ,
            reversibility=True,
            next_safe_test="Compile sample 1-page intelligence brief with verified Level A/B sources."
        )


class EvidenceServiceFactory:
    SERVICES = {
        "COMPETITOR_BRIEF": EvidenceServiceOffer(
            service_name="COMPETITOR_BRIEF",
            target_client="Product Managers & Founders",
            deliverable_format="Timestamped competitor pricing & feature matrix (PDF/Markdown)",
            price_eur=99.0,
            sources_required=["Official pricing pages", "Release notes", "SEC/Financial filings"]
        ),
        "SUPPLIER_CHECK": EvidenceServiceOffer(
            service_name="SUPPLIER_CHECK",
            target_client="Procurement & E-commerce Operators",
            deliverable_format="Verified supplier registry & compliance dossier",
            price_eur=149.0,
            sources_required=["Corporate registries", "Import/Export trade data"]
        )
    }

    @classmethod
    def create_service(cls, service_name: str, opp_id: str, evidence: List[EvidenceItem]) -> OpportunityRecord:
        svc = cls.SERVICES.get(service_name)
        if not svc:
            raise ValueError(f"Unknown service: {service_name}")
        return svc.to_opportunity_record(opp_id, evidence)


# ---------------------------------------------------------
# Priority Lane C: Publishing Factory
# ---------------------------------------------------------

@dataclass
class PublishingNiche:
    topic: str
    target_reader: str
    demand_volume_monthly: int
    competition_score: float
    copyright_cleared: bool

    def to_opportunity_record(self, opp_id: str, evidence: List[EvidenceItem]) -> OpportunityRecord:
        unit_econ = UnitEconomics(
            selling_price_eur=12.99,
            cost_of_delivery_eur=0.50,
            platform_fee_eur=3.90,
            customer_acquisition_cost_est_eur=2.0
        )
        return OpportunityRecord(
            opportunity_id=opp_id,
            title=f"Publishing: {self.topic} Guide",
            domain=OpportunityDomain.PUBLISHING,
            problem=f"Readers seeking clear, well-illustrated guides on {self.topic}.",
            customer=self.target_reader,
            evidence_sources=evidence,
            expected_revenue_eur=500.0,
            expected_cost_eur=30.0,
            initial_capital_required_eur=0.0,
            time_to_first_revenue_days=14,
            automation_percentage=0.75,
            human_effort_hours_per_unit=3.0,
            legal_risk=0.05 if self.copyright_cleared else 0.8,
            platform_risk=0.25,
            unit_economics=unit_econ,
            reversibility=True,
            next_safe_test="Publish a free 5-page sample booklet and measure download demand."
        )


class PublishingFactory:
    NICHES = {
        "PENGUINS_NATURE": PublishingNiche(
            topic="Penguins & Polar Wildlife for Kids",
            target_reader="Parents & Young Readers",
            demand_volume_monthly=8500,
            competition_score=0.35,
            copyright_cleared=True
        ),
        "FRUIT_TREES_GARDENING": PublishingNiche(
            topic="Pruning & Caring for Backyard Fruit Trees",
            target_reader="Home Gardeners & Homesteaders",
            demand_volume_monthly=12000,
            competition_score=0.40,
            copyright_cleared=True
        )
    }

    @classmethod
    def create_publication(cls, niche_name: str, opp_id: str, evidence: List[EvidenceItem]) -> OpportunityRecord:
        niche = cls.NICHES.get(niche_name)
        if not niche:
            raise ValueError(f"Unknown niche: {niche_name}")
        return niche.to_opportunity_record(opp_id, evidence)


# ---------------------------------------------------------
# Observational Financial Research Lab (Paper Only)
# ---------------------------------------------------------

@dataclass
class PatternEvidence:
    pattern_id: str
    instrument: str
    pattern_type: str  # e.g., "DISLOCATION_RECOVERY", "SPREAD_SPIKE_REVERSAL"
    occurrences_observed: int
    win_rate_paper: float
    average_return_pct: float
    max_drawdown_pct: float
    fees_and_slippage_included: bool
    verified_regimes: List[str] = field(default_factory=list)

    @property
    def is_statistically_robust(self) -> bool:
        return (
            self.occurrences_observed >= 20 and
            self.fees_and_slippage_included and
            len(self.verified_regimes) >= 3 and
            self.win_rate_paper > 0.55
        )


class FinancialResearchLab:
    """Enforces strict observational / paper-only regime.
    
    REAL_TRADES = 0.
    Social hype quality weight = 0.
    """
    def __init__(self):
        self.patterns: Dict[str, PatternEvidence] = {}

    def record_pattern(self, pattern: PatternEvidence):
        self.patterns[pattern.pattern_id] = pattern

    def evaluate_financial_candidate(self, pattern_id: str) -> Dict[str, Any]:
        pat = self.patterns.get(pattern_id)
        if not pat:
            return {"status": "UNKNOWN_PATTERN", "authorized_for_live": False}
        
        if not pat.is_statistically_robust:
            return {
                "status": "INSUFFICIENT_OBSERVATION",
                "occurrences": pat.occurrences_observed,
                "required": 20,
                "authorized_for_live": False,
                "mode": "PAPER_ONLY"
            }

        return {
            "status": "STATISTICALLY_SOUND_PAPER_MODEL",
            "win_rate": pat.win_rate_paper,
            "authorized_for_live": False,  # Hard wall: Live trades strictly prohibited!
            "mode": "PAPER_ONLY"
        }
