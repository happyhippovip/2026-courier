"""Evidence-First Opportunity OS Orchestrator (Mission 225-R1).

Executes the continuous autonomous cycle with strict validation contracts:
DISCOVER
→ VERIFY EVIDENCE & GATES
→ SCORE & DUAL-SELECTION (Research vs Action)
→ DESIGN CHEAP TEST
→ EXECUTE SAFE TEST
→ MEASURE TRUTHFULLY
→ RECORD EXPERIENCE (distinguishing SIMULATED vs REAL)
→ RE-RANK

Validation Contract:
- A synthetic simulation with revenue_eur = 0 CANNOT set VALIDATED status.
- It transitions to SIMULATION_ONLY or TEST_RESULT_VERIFIED (Synthetic).
- VALIDATED requires real market confirmation, known positive unit economics,
  and verified demand.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from scripts.opportunity_os.opportunity_record import (
    OpportunityRecord, OpportunityStatus, OpportunityDomain
)
from scripts.opportunity_os.opportunity_scorer import OpportunityScorer
from scripts.opportunity_os.evidence_hierarchy import EvidenceItem, EvidenceLevel, EvidenceEvaluator
from scripts.opportunity_os.experience_engine import (
    ExperienceEngine, ExperienceRecord, ExperienceEvidenceType
)
from scripts.opportunity_os.capability_router import CapabilityRouter, CapabilityTask, Capability


@dataclass
class OrchestratorCycleResult:
    cycle_timestamp: str
    discovered_count: int
    verified_count: int
    top_research_id: Optional[str]
    top_action_id: Optional[str]
    top_score: float
    test_designed: Optional[str]
    experience_recorded_id: Optional[str]
    cycle_outcome: str
    status: str


class OpportunityOsOrchestrator:
    def __init__(self, experience_engine: Optional[ExperienceEngine] = None):
        self.experience_engine = experience_engine or ExperienceEngine()
        self.capability_router = CapabilityRouter()
        self.opportunities: Dict[str, OpportunityRecord] = {}

    def ingest_opportunity(self, opp: OpportunityRecord):
        self.opportunities[opp.opportunity_id] = opp

    def run_autonomous_cycle(self) -> OrchestratorCycleResult:
        now_str = datetime.now(timezone.utc).isoformat()
        if not self.opportunities:
            return OrchestratorCycleResult(
                cycle_timestamp=now_str,
                discovered_count=0,
                verified_count=0,
                top_research_id=None,
                top_action_id=None,
                top_score=0.0,
                test_designed=None,
                experience_recorded_id=None,
                cycle_outcome="EMPTY_POOL",
                status="NO_VIABLE_CANDIDATE"
            )

        # 1. VERIFY: check evidence and update state for all opportunities
        verified_count = 0
        for opp in self.opportunities.values():
            if opp.is_action_eligible:
                opp.status = OpportunityStatus.ACTION_ELIGIBLE
                verified_count += 1
            elif opp.is_researchable:
                opp.status = OpportunityStatus.RESEARCHABLE
                if not opp.unit_economics:
                    opp.status = OpportunityStatus.NEEDS_MORE_EVIDENCE
            else:
                opp.status = OpportunityStatus.REJECTED

        # 2. SCORE & DUAL SELECTION
        answer = OpportunityScorer.answer_daily_question(list(self.opportunities.values()))
        research_info = answer.get("best_research_candidate")
        action_info = answer.get("best_action_eligible_candidate")

        top_research_id = research_info["opportunity_id"] if research_info else None
        top_action_id = action_info["opportunity_id"] if action_info else None
        top_score = action_info["score"] if action_info else (research_info["score"] if research_info else 0.0)

        # If no candidate is action eligible, we do NOT authorize action or force validation!
        if not top_action_id:
            # We can still research or safe idle
            target_opp = self.opportunities[top_research_id] if top_research_id else None
            return OrchestratorCycleResult(
                cycle_timestamp=now_str,
                discovered_count=len(self.opportunities),
                verified_count=verified_count,
                top_research_id=top_research_id,
                top_action_id=None,
                top_score=top_score,
                test_designed="Gather primary Level A/B evidence or quantify unit economics." if target_opp else None,
                experience_recorded_id=None,
                cycle_outcome="SAFE_IDLE_OR_RESEARCH",
                status="NO_ACTION_ELIGIBLE_CANDIDATE"
            )

        target_opp = self.opportunities[top_action_id]

        # 3. DESIGN CHEAP TEST & CHECK EXPERIENCE MEMORY
        precedents = self.experience_engine.check_precedents_before_proposal(
            domain=target_opp.domain.value,
            action_concept=target_opp.title
        )

        test_description = target_opp.next_safe_test or "Run synthetic unit economics & mechanics verification."
        target_opp.status = OpportunityStatus.CHEAP_TEST_DESIGNED

        # 4. EXECUTE TEST (Distinguishing Simulation vs Real Market Test)
        is_synthetic_simulation = True  # Safe local canary
        test_success = target_opp.unit_economics is not None and target_opp.unit_economics.is_positive

        # 5. MEASURE TRUTHFULLY & RECORD EXPERIENCE
        exp_id = f"EXP-{target_opp.opportunity_id}-{int(datetime.now().timestamp())}"
        
        if is_synthetic_simulation:
            # STRICT INVARIANT: Do NOT claim customer demand verified or revenue generated!
            target_opp.status = OpportunityStatus.SIMULATION_ONLY
            actual_res = "Unit economics model passed synthetic validation" if test_success else "Model failed margin test"
            lesson_txt = "Synthetic model confirmed margin structure; external customer test required before live commitment." if test_success else "Unit economics require restructuring."
            ev_type = ExperienceEvidenceType.SIMULATED
        else:
            actual_res = "External market validation completed"
            lesson_txt = "Customer engagement confirmed"
            ev_type = ExperienceEvidenceType.EXTERNAL_TEST

        exp = ExperienceRecord(
            experience_id=exp_id,
            opportunity_id=target_opp.opportunity_id,
            domain=target_opp.domain.value,
            hypothesis=f"Offer '{target_opp.title}' maintains positive unit contribution.",
            evidence_before=[e.description for e in target_opp.evidence_sources],
            action_taken=test_description,
            expected_result=f"Net margin > 0, price €{target_opp.expected_revenue_eur}",
            actual_result=actual_res,
            cost_eur=0.0,
            revenue_eur=0.0,  # Truthful: no real money was touched
            time_used_hours=0.5,
            success=test_success,
            evidence_type=ev_type,
            lesson=lesson_txt,
            confidence_delta=+0.05 if test_success else -0.10,
            reusable_pattern=f"MODEL_CHECK_{target_opp.domain.value}"
        )
        self.experience_engine.record_experience(exp)

        return OrchestratorCycleResult(
            cycle_timestamp=now_str,
            discovered_count=len(self.opportunities),
            verified_count=verified_count,
            top_research_id=top_research_id,
            top_action_id=target_opp.opportunity_id,
            top_score=top_score,
            test_designed=test_description,
            experience_recorded_id=exp_id,
            cycle_outcome="SIMULATION_COMPLETED_TRUTHFUL",
            status="CYCLE_COMPLETE"
        )
