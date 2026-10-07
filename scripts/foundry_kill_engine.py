#!/usr/bin/env python3
"""Idea Foundry Red Team / Kill Engine.

Before product work, attempt to kill weak candidates using:
- weak/unclear problem
- unclear buyer
- no believable value path
- excessive support/human labor
- regulatory/security burden
- commodity differentiation
- high implementation cost vs evidence
- unverifiable acceptance criteria

The system must be rewarded for dropping weak work.
"""

from __future__ import annotations
from typing import Any

KILL_CRITERIA = [
    {"id": "weak_problem", "pattern": ["maybe", "perhaps", "could be useful", "might want"]},
    {"id": "unclear_buyer", "pattern": ["everyone", "anyone", "all users"]},
    {"id": "regulatory_burden", "pattern": ["gdpr", "hipaa", "compliance", "medical", "financial", "legal"]},
    {"id": "excessive_support", "pattern": ["manual review", "human-in-the-loop", "concierge"]},
    {"id": "unverifiable_acceptance", "pattern": ["feels better", "looks good", "user likes it"]},
]

def evaluate_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    """Evaluates a candidate and returns kill signals if it violates constraints."""
    summary = str(candidate.get("summary", "")).lower()
    signals = []
    
    for criterion in KILL_CRITERIA:
        for pattern in criterion["pattern"]:
            if pattern in summary:
                signals.append({
                    "reason": f"Violates {criterion['id']}",
                    "evidence": pattern
                })
                break  # One match per criterion is enough
                
    if len(signals) >= 1:
        return {"action": "KILL", "signals": signals}
    
    return {"action": "PASS", "signals": []}

def run_kill_engine(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Filters candidates through the Red Team engine."""
    survivors = []
    killed = []
    
    for candidate in candidates:
        evaluation = evaluate_candidate(candidate)
        if evaluation["action"] == "KILL":
            candidate_copy = dict(candidate)
            candidate_copy["status_label"] = "KILLED"
            candidate_copy["kill_reasons"] = evaluation["signals"]
            killed.append(candidate_copy)
        else:
            survivors.append(candidate)
            
    return {
        "engine": "RED_TEAM_KILL_ENGINE",
        "candidates_evaluated": len(candidates),
        "survivors": survivors,
        "killed": killed
    }
