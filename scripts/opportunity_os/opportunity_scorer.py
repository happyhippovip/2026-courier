"""Deterministic Opportunity Scorer & Dual-Output Daily Question Engine (Mission 225-R1).

Scores opportunities objectively according to Old-School business principles.
Enforces that:
1. High score alone NEVER bypasses action eligibility.
2. The best of a bad pool is NOT chosen for action.
3. Produces two outputs:
   - BEST_RESEARCH_CANDIDATE
   - BEST_ACTION_ELIGIBLE_CANDIDATE
"""

from __future__ import annotations

from typing import List, Tuple, Dict, Any, Optional
from scripts.opportunity_os.opportunity_record import OpportunityRecord, OpportunityDomain
from scripts.opportunity_os.evidence_hierarchy import EvidenceEvaluator, EvidenceLevel


class OpportunityScorer:
    MIN_ACTION_SCORE_THRESHOLD = 20.0  # Must be clearly positive to authorize action

    @classmethod
    def score_opportunity(cls, opp: OpportunityRecord) -> float:
        """Returns a deterministic composite score from -100.0 to +100.0."""
        score = 0.0

        # 1. Evidence Quality (0 to 30 pts)
        ev_score = EvidenceEvaluator.calculate_evidence_score(opp.evidence_sources)
        score += ev_score * 30.0

        # Penalize if demand is completely unverified (no Level A or B)
        has_verified_demand = any(
            item.verified and item.level in [EvidenceLevel.LEVEL_A, EvidenceLevel.LEVEL_B]
            for item in opp.evidence_sources
        )
        if not has_verified_demand:
            score -= 15.0  # Harsh penalty for unverified demand

        # 2. Capital & Cost Efficiency (0 to 20 pts)
        if opp.initial_capital_required_eur == 0.0:
            score += 20.0
        elif opp.initial_capital_required_eur <= 10.0:
            score += 15.0
        elif opp.initial_capital_required_eur <= 50.0:
            score += 5.0
        else:
            score -= (opp.initial_capital_required_eur / 10.0)

        # 3. Time to First Revenue (0 to 15 pts)
        if opp.time_to_first_revenue_days <= 1:
            score += 15.0
        elif opp.time_to_first_revenue_days <= 3:
            score += 10.0
        elif opp.time_to_first_revenue_days <= 7:
            score += 5.0
        else:
            score -= 5.0

        # 4. Unit Economics & Gross Margin (0 to 15 pts)
        if opp.unit_economics:
            if opp.unit_economics.is_positive:
                if opp.unit_economics.gross_margin_pct >= 80.0:
                    score += 15.0
                elif opp.unit_economics.gross_margin_pct >= 50.0:
                    score += 10.0
                else:
                    score += 5.0
            else:
                score -= 30.0  # Massive penalty for negative unit economics!
        else:
            score -= 20.0  # Heavy penalty for unknown costs (cannot authorize)

        # 5. Automation Fit & Repeatability (0 to 10 pts)
        score += (opp.automation_percentage * 5.0)
        score += (opp.repeatability_score * 5.0)

        # 6. Reversibility & Low Financial Risk (0 to 10 pts)
        if opp.reversibility:
            score += 10.0
        else:
            score -= 20.0

        # 7. Penalties (Risks, Hype Dependence, Leverage)
        score -= (opp.legal_risk * 30.0)
        score -= (opp.platform_risk * 15.0)
        score -= (opp.fraud_risk * 50.0)
        score -= (opp.execution_risk * 10.0)

        # Hype dependence check
        if opp.social_signals and opp.social_signals.likes > 1000 and ev_score < 0.2:
            score -= 20.0

        # Domain Priority Weighting
        if opp.domain == OpportunityDomain.B2B_AUTOMATION:
            score += 10.0  # Priority Lane A
        elif opp.domain == OpportunityDomain.RESEARCH_SERVICES:
            score += 8.0   # Priority Lane B
        elif opp.domain == OpportunityDomain.PUBLISHING:
            score += 5.0   # Priority Lane C
        elif opp.domain == OpportunityDomain.FINANCIAL_RESEARCH:
            score -= 10.0  # Paper only!

        return round(score, 2)

    @classmethod
    def rank_opportunities(cls, opportunities: List[OpportunityRecord]) -> List[Tuple[OpportunityRecord, float]]:
        """Ranks all candidates descending by deterministic score."""
        scored = [(opp, cls.score_opportunity(opp)) for opp in opportunities]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    @classmethod
    def answer_daily_question(cls, opportunities: List[OpportunityRecord]) -> Dict[str, Any]:
        """Answers the Daily Question with two distinct outputs:
        1. BEST_RESEARCH_CANDIDATE (may need more evidence or unknown cost check)
        2. BEST_ACTION_ELIGIBLE_CANDIDATE (must pass all strict eligibility gates and min score threshold)
        """
        ranked = cls.rank_opportunities(opportunities)
        if not ranked:
            return {
                "best_research_candidate": None,
                "best_action_eligible_candidate": None,
                "selected_opportunity_id": None,
                "status": "NO_VIABLE_CANDIDATE",
                "reasoning": "No opportunities in pool."
            }

        # Best research candidate is the highest scored researchable candidate
        best_research: Optional[OpportunityRecord] = None
        best_research_score = -999.0
        for opp, score in ranked:
            if opp.is_researchable:
                best_research = opp
                best_research_score = score
                break

        # Best action eligible candidate must strictly pass is_action_eligible AND minimum score
        best_action: Optional[OpportunityRecord] = None
        best_action_score = -999.0
        for opp, score in ranked:
            if opp.is_action_eligible and score >= cls.MIN_ACTION_SCORE_THRESHOLD:
                best_action = opp
                best_action_score = score
                break

        status = "ACTION_ELIGIBLE_FOUND" if best_action else "NO_ACTION_ELIGIBLE_CANDIDATE"

        return {
            "best_research_candidate": {
                "opportunity_id": best_research.opportunity_id,
                "title": best_research.title,
                "domain": best_research.domain.value,
                "score": best_research_score
            } if best_research else None,
            "best_action_eligible_candidate": {
                "opportunity_id": best_action.opportunity_id,
                "title": best_action.title,
                "domain": best_action.domain.value,
                "score": best_action_score
            } if best_action else None,
            "selected_opportunity_id": best_action.opportunity_id if best_action else None,
            "score": best_action_score if best_action else 0.0,
            "status": status,
            "reasoning": (
                f"Action candidate: {best_action.title if best_action else 'NONE'}. "
                f"Research candidate: {best_research.title if best_research else 'NONE'}."
            )
        }
