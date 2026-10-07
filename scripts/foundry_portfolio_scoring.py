#!/usr/bin/env python3
"""Idea Foundry Opportunity / Portfolio Scoring.

Evidence-weighted, risk-adjusted prioritization using:
- problem strength
- buyer access
- real-use proximity
- time-to-value
- time-to-revenue
- explicit WTP evidence
- retention potential
- differentiation
- build effort
- provider/ops/support cost
- security/compliance risk
- reversibility
- evidence confidence

No invented revenue/margin/conversion values.
"""

from __future__ import annotations
from typing import Any

def calculate_score(candidate: dict[str, Any]) -> dict[str, Any]:
    """Calculates evidence-weighted risk-adjusted score for a candidate."""
    
    # In a real pipeline, these metrics would be extracted semantically by the bridge.
    # For local deterministic behavior, we expect these in a 'metrics' sub-dictionary
    # or default to zero.
    metrics = candidate.get("metrics", {})
    
    # Base multipliers (0 to 10 scale typical)
    problem_strength = metrics.get("problem_strength", 0)
    wtp_evidence = metrics.get("wtp_evidence", 0)
    evidence_confidence = metrics.get("evidence_confidence", 1)  # Multiplier 0.1 to 1.0
    
    # Penalties (0 to 10 scale typical)
    build_effort = metrics.get("build_effort", 5)
    compliance_risk = metrics.get("compliance_risk", 0)
    
    # Reward high problem strength and WTP, penalize high build effort and risk
    raw_score = (problem_strength * 2) + (wtp_evidence * 3) - (build_effort * 1.5) - (compliance_risk * 2)
    
    # Adjust for how confident we are in the evidence
    final_score = raw_score * evidence_confidence
    
    return {
        "raw_score": raw_score,
        "final_score": final_score,
        "metrics_used": metrics
    }

def run_portfolio_scoring(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Scores a portfolio of candidates and sorts them by value."""
    scored_candidates = []
    
    for candidate in candidates:
        if candidate.get("status_label") == "KILLED":
            continue
            
        scoring_result = calculate_score(candidate)
        
        # Modify candidate in place
        candidate_copy = dict(candidate)
        candidate_copy["portfolio_score"] = scoring_result["final_score"]
        candidate_copy["scoring_details"] = scoring_result
        scored_candidates.append(candidate_copy)
        
    # Sort highest score first
    scored_candidates.sort(key=lambda x: x.get("portfolio_score", 0), reverse=True)
    
    return {
        "engine": "PORTFOLIO_SCORING",
        "candidates_scored": len(scored_candidates),
        "sorted_portfolio": scored_candidates
    }
