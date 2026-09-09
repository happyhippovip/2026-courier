"""
Revenue-First Content OS — Deterministic Opportunity Evaluator
Phase 0 / 1 Core Scoring Module

Calculates normalized REVENUE_OPPORTUNITY_SCORE (0..100) using multi-factor
decision metrics. Explicitly separates:
- OBSERVED DATA
- INFERENCE
- ESTIMATE
- UNKNOWN
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional


class EvidenceType(Enum):
    OBSERVED_DATA = "OBSERVED_DATA"
    INFERENCE = "INFERENCE"
    ESTIMATE = "ESTIMATE"
    UNKNOWN = "UNKNOWN"


@dataclass
class EvidenceEntry:
    dimension: str
    value: Any
    evidence_type: EvidenceType
    source_notes: str


@dataclass
class OpportunityDimensions:
    trend_velocity: float           # 0..10 (V)
    audience_size: float            # 0..10 (S)
    monetization_potential: float   # 0..10 (M)
    competition: float              # 0..10 (C)
    content_half_life: float        # 0..10 (H)
    production_cost: float          # 0..10 (P_cost, 0 is free local render)
    production_time: float          # 0..10 (P_time, lower is faster)
    automation_fit: float           # 0..10 (A)
    platform_fit: float             # 0..10 (F_plat)
    channel_fit: float              # 0..10 (F_chan)
    reuse_across_platforms: float   # 0..10 (R)
    originality: float              # 0..10 (O)
    policy_risk: float              # 0..10 (K, higher is riskier)


@dataclass
class EvaluationResult:
    topic_title: str
    lane_id: str
    revenue_opportunity_score: float
    is_production_ready: bool  # True if score >= threshold (e.g. 70.0)
    value_score: float
    feasibility_score: float
    penalty_factor: float
    evidence_breakdown: List[EvidenceEntry]
    raw_dimensions: OpportunityDimensions

    def summary(self) -> str:
        return (
            f"TOPIC: {self.topic_title}\n"
            f"LANE: {self.lane_id}\n"
            f"SCORE: {self.revenue_opportunity_score:.1f} / 100.0\n"
            f"READY: {'YES' if self.is_production_ready else 'NO (PARKED)'}\n"
            f"COMPONENTS: Value={self.value_score:.2f}, Feasibility={self.feasibility_score:.2f}, Penalty={self.penalty_factor:.2f}"
        )


class ContentOpportunityEvaluator:
    """
    Deterministic scoring engine implementing the Content OS opportunity model.
    Zero LLM tokens required for scoring computation.
    """

    DEFAULT_THRESHOLD = 70.0

    @staticmethod
    def clamp(val: float, min_val: float = 0.0, max_val: float = 10.0) -> float:
        return max(min_val, min(max_val, val))

    def evaluate(
        self,
        topic_title: str,
        lane_id: str,
        dims: OpportunityDimensions,
        evidence: Optional[List[EvidenceEntry]] = None,
        threshold: float = DEFAULT_THRESHOLD
    ) -> EvaluationResult:
        # Clamp inputs
        v = self.clamp(dims.trend_velocity)
        s = self.clamp(dims.audience_size)
        m = self.clamp(dims.monetization_potential)
        c = self.clamp(dims.competition)
        h = self.clamp(dims.content_half_life)
        p_cost = self.clamp(dims.production_cost)
        p_time = self.clamp(dims.production_time)
        a = self.clamp(dims.automation_fit)
        f_plat = self.clamp(dims.platform_fit)
        f_chan = self.clamp(dims.channel_fit)
        r = self.clamp(dims.reuse_across_platforms)
        o = self.clamp(dims.originality)
        k = self.clamp(dims.policy_risk)

        # 1. Value Component (Max 10.0)
        # Weights: Monetization (0.25), Velocity (0.20), Audience (0.15), Half-life (0.15), Reuse (0.15), Originality (0.10)
        value_score = (
            0.25 * m +
            0.20 * v +
            0.15 * s +
            0.15 * h +
            0.15 * r +
            0.10 * o
        )

        # 2. Feasibility Component (Max 10.0)
        # Weights: Automation (0.35), Inverted Cost (0.25), Inverted Time (0.20), Platform Fit (0.20)
        feasibility_score = (
            0.35 * a +
            0.25 * (10.0 - p_cost) +
            0.20 * (10.0 - p_time) +
            0.20 * f_plat
        )

        # 3. Penalty Factor (0.0 to 1.0)
        # Penalties: Competition saturation (up to 0.50), Policy/Copyright risk (up to 1.00)
        raw_penalty = 1.0 - (0.05 * c) - (0.10 * k)
        penalty_factor = max(0.0, min(1.0, raw_penalty))

        # 4. Combined Normalized Revenue Opportunity Score (0..100)
        combined_raw = (0.55 * value_score + 0.45 * feasibility_score) * 10.0
        final_score = max(0.0, min(100.0, combined_raw * penalty_factor))

        is_ready = (final_score >= threshold)

        return EvaluationResult(
            topic_title=topic_title,
            lane_id=lane_id,
            revenue_opportunity_score=round(final_score, 1),
            is_production_ready=is_ready,
            value_score=round(value_score, 2),
            feasibility_score=round(feasibility_score, 2),
            penalty_factor=round(penalty_factor, 2),
            evidence_breakdown=evidence or [],
            raw_dimensions=dims
        )
