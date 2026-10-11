#!/usr/bin/env python3
"""Idea Foundry Red Team / Kill Engine (Issue #3).

Operates ONLY on derived Foundry synthesis candidates, never on raw thoughts,
tasks, decisions or memory proposals.

Decisions:
* KILL  — explicit evidence of a kill criterion (structured ``risk_flags``).
* PARK  — decision-relevant information is UNKNOWN or contradictory. Missing
          evidence is not invented and is not treated as a kill.
* EXPERIMENT_READY — survived; eligible for portfolio scoring.

The engine reports how much weak work it dropped; dropping weak work is the
goal, not maximizing candidate counts.
"""

from __future__ import annotations

from typing import Any

UNKNOWN = "UNKNOWN"

# Explicit structured flags (set by a reviewer/bridge in thought facets) -> kill criterion.
KILL_FLAGS = {
    "regulatory_burden": "regulatory/security burden",
    "excessive_support_labor": "excessive support/human labor",
    "commodity": "commodity differentiation",
    "no_value_path": "no believable value path",
    "unverifiable_acceptance": "unverifiable acceptance criteria",
    "cost_exceeds_evidence": "high implementation cost vs evidence",
}


def evaluate_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    flags = candidate.get("risk_flags") or {}
    kill = [{"criterion": key, "reason": label, "evidence": f"risk_flags.{key}=true"}
            for key, label in KILL_FLAGS.items() if flags.get(key) is True]
    if kill:
        return {"decision": "KILL", "reasons": kill}
    park = []
    if candidate.get("problem_hypothesis", UNKNOWN) == UNKNOWN:
        park.append({"criterion": "weak_problem", "reason": "problem hypothesis UNKNOWN"})
    if candidate.get("target_user_hypothesis", UNKNOWN) == UNKNOWN:
        park.append({"criterion": "unclear_buyer", "reason": "target user/buyer UNKNOWN"})
    if candidate.get("contradictions"):
        park.append({"criterion": "unresolved_contradiction", "reason": f"{len(candidate['contradictions'])} contradiction(s) open"})
    if park:
        return {"decision": "PARK", "reasons": park}
    return {"decision": "EXPERIMENT_READY", "reasons": []}


def run_kill_engine(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, list[dict[str, Any]]] = {"KILL": [], "PARK": [], "EXPERIMENT_READY": []}
    for candidate in candidates:
        verdict = evaluate_candidate(candidate)
        record = dict(candidate)  # never mutate the synthesis record
        record["status"] = {"KILL": "KILLED", "PARK": "PARKED", "EXPERIMENT_READY": "EXPERIMENT_READY"}[verdict["decision"]]
        record["red_team_reasons"] = verdict["reasons"]
        out[verdict["decision"]].append(record)
    return {
        "engine": "RED_TEAM_KILL_ENGINE",
        "candidates_evaluated": len(candidates),
        "killed": out["KILL"],
        "parked": out["PARK"],
        "experiment_ready": out["EXPERIMENT_READY"],
        "weak_work_dropped": len(out["KILL"]) + len(out["PARK"]),
    }
