"""Multitask Capability Router (Mission 225).

Routes work across reusable capabilities rather than spawning redundant isolated agents.

Capabilities:
- RESEARCH, SOURCE_VERIFICATION, COST_ANALYSIS, MARKET_ANALYSIS,
  COMPETITOR_ANALYSIS, CUSTOMER_ANALYSIS, DOCUMENT_ANALYSIS, DATA_COLLECTION,
  UNIT_ECONOMICS, BACKTESTING, SIMULATION, CONTENT_CREATION, SOFTWARE_BUILDING,
  QA, SECURITY_REVIEW, OPERATIONAL_MONITORING, OPPORTUNITY_COMPARISON.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Dict, Any, Callable, List


class Capability(enum.Enum):
    RESEARCH = "RESEARCH"
    SOURCE_VERIFICATION = "SOURCE_VERIFICATION"
    COST_ANALYSIS = "COST_ANALYSIS"
    MARKET_ANALYSIS = "MARKET_ANALYSIS"
    COMPETITOR_ANALYSIS = "COMPETITOR_ANALYSIS"
    CUSTOMER_ANALYSIS = "CUSTOMER_ANALYSIS"
    DOCUMENT_ANALYSIS = "DOCUMENT_ANALYSIS"
    DATA_COLLECTION = "DATA_COLLECTION"
    UNIT_ECONOMICS = "UNIT_ECONOMICS"
    BACKTESTING = "BACKTESTING"
    SIMULATION = "SIMULATION"
    CONTENT_CREATION = "CONTENT_CREATION"
    SOFTWARE_BUILDING = "SOFTWARE_BUILDING"
    QA = "QA"
    SECURITY_REVIEW = "SECURITY_REVIEW"
    OPERATIONAL_MONITORING = "OPERATIONAL_MONITORING"
    OPPORTUNITY_COMPARISON = "OPPORTUNITY_COMPARISON"


@dataclass
class CapabilityTask:
    task_id: str
    capability: Capability
    payload: Dict[str, Any]


@dataclass
class CapabilityResult:
    task_id: str
    capability: Capability
    success: bool
    output: Dict[str, Any]
    error: str = ""


class CapabilityRouter:
    def __init__(self):
        self._handlers: Dict[Capability, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}
        self._register_default_handlers()

    def register_handler(self, cap: Capability, handler: Callable[[Dict[str, Any]], Dict[str, Any]]):
        self._handlers[cap] = handler

    def dispatch(self, task: CapabilityTask) -> CapabilityResult:
        handler = self._handlers.get(task.capability)
        if not handler:
            return CapabilityResult(
                task_id=task.task_id,
                capability=task.capability,
                success=False,
                output={},
                error=f"No registered handler for capability {task.capability.value}"
            )
        try:
            res = handler(task.payload)
            return CapabilityResult(
                task_id=task.task_id,
                capability=task.capability,
                success=True,
                output=res
            )
        except Exception as e:
            return CapabilityResult(
                task_id=task.task_id,
                capability=task.capability,
                success=False,
                output={},
                error=str(e)
            )

    def _register_default_handlers(self):
        """Registers deterministic handlers for standard capabilities."""
        def handle_unit_economics(payload: Dict[str, Any]) -> Dict[str, Any]:
            price = float(payload.get("price", 0.0))
            cost = float(payload.get("cost", 0.0))
            fee = float(payload.get("fee", 0.0))
            cac = float(payload.get("cac", 0.0))
            margin = price - (cost + fee)
            margin_pct = (margin / price * 100.0) if price > 0 else 0.0
            net = margin - cac
            return {
                "margin_eur": round(margin, 2),
                "margin_pct": round(margin_pct, 2),
                "net_contribution_eur": round(net, 2),
                "viable": net > 0.0
            }

        def handle_source_verification(payload: Dict[str, Any]) -> Dict[str, Any]:
            sources = payload.get("sources", [])
            has_primary = any(s.get("type") in ["OFFICIAL_API", "CONTRACT", "GOV_RECORD"] for s in sources)
            return {
                "verified_count": len(sources),
                "has_primary_evidence": has_primary,
                "confidence_rating": "HIGH" if has_primary and len(sources) >= 2 else "MODERATE"
            }

        def handle_cost_analysis(payload: Dict[str, Any]) -> Dict[str, Any]:
            components = payload.get("components", {})
            total = sum(float(v) for v in components.values())
            return {
                "total_cost_eur": round(total, 2),
                "breakdown": components
            }

        self.register_handler(Capability.UNIT_ECONOMICS, handle_unit_economics)
        self.register_handler(Capability.SOURCE_VERIFICATION, handle_source_verification)
        self.register_handler(Capability.COST_ANALYSIS, handle_cost_analysis)
