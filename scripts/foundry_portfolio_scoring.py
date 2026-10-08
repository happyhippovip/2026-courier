#!/usr/bin/env python3
"""Idea Foundry Opportunity / Portfolio Scoring (Issue #3, P1).

Evidence-weighted, risk-adjusted ordering of EXPERIMENT_READY candidates.
No invented values: if any required metric is missing, the score is
``UNKNOWN`` and the missing metrics are listed. UNKNOWN-scored candidates are
ordered after scored ones (then by ``candidate_id`` for determinism).
"""

from __future__ import annotations

from typing import Any

UNKNOWN = "UNKNOWN"
# metric -> weight; positive rewards, negative penalties. Values are 0..10.
WEIGHTS = {
    "problem_strength": 2.0,
    "wtp_evidence": 3.0,
    "buyer_access": 1.0,
    "build_effort": -1.5,
    "compliance_risk": -2.0,
}
REQUIRED = tuple(WEIGHTS) + ("evidence_confidence",)


def calculate_score(metrics: dict[str, Any]) -> dict[str, Any]:
    missing = [k for k in REQUIRED if not isinstance(metrics.get(k), (int, float)) or isinstance(metrics.get(k), bool)]
    if missing:
        return {"score": UNKNOWN, "missing_metrics": missing}
    confidence = min(max(float(metrics["evidence_confidence"]), 0.0), 1.0)
    raw = sum(float(metrics[k]) * w for k, w in WEIGHTS.items())
    return {"score": round(raw * confidence, 4), "raw_score": raw, "evidence_confidence": confidence, "missing_metrics": []}


def run_portfolio_scoring(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    scored = []
    for candidate in candidates:
        record = dict(candidate)
        record["portfolio_score"] = calculate_score(candidate.get("metrics") or {})
        scored.append(record)
    scored.sort(key=lambda c: (c["portfolio_score"]["score"] == UNKNOWN,
                               -(c["portfolio_score"]["score"] if c["portfolio_score"]["score"] != UNKNOWN else 0),
                               c.get("candidate_id", "")))
    return {
        "engine": "PORTFOLIO_SCORING",
        "candidates_scored": sum(1 for c in scored if c["portfolio_score"]["score"] != UNKNOWN),
        "candidates_unknown": sum(1 for c in scored if c["portfolio_score"]["score"] == UNKNOWN),
        "sorted_portfolio": scored,
    }
