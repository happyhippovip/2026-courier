"""Fail-closed provider cost guard enforcing zero spend and unknown cost block.

Lane L2. Enforces:
- CostGate before provider dispatch
- UNKNOWN_COST=BLOCK: Missing, unparseable or unquoted costs are strictly blocked
- AUTONOMOUS_SPEND_LIMIT_EUR=0: Zero spend limit strictly enforced
- Single Writer & Audit logging
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


@dataclass
class CostGateVerdict:
    allowed: bool
    reason: str
    cost_eur: Optional[float]
    provider: str
    model: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def evaluate_cost_gate(
    provider_spec: dict[str, Any],
    autonomous_limit_eur: float = 0.0,
) -> CostGateVerdict:
    if not isinstance(provider_spec, dict) or not provider_spec:
        return CostGateVerdict(
            allowed=False,
            reason="INVALID_SPEC",
            cost_eur=None,
            provider="",
            model="",
        )

    provider = str(provider_spec.get("provider") or "").strip()
    model = str(provider_spec.get("model") or "").strip()

    if not provider or not model:
        return CostGateVerdict(
            allowed=False,
            reason="INVALID_SPEC",
            cost_eur=None,
            provider=provider,
            model=model,
        )

    # Check cost_estimate_eur
    if "cost_estimate_eur" not in provider_spec or provider_spec["cost_estimate_eur"] is None:
        return CostGateVerdict(
            allowed=False,
            reason="UNKNOWN_COST_BLOCKED",
            cost_eur=None,
            provider=provider,
            model=model,
        )

    raw_cost = provider_spec["cost_estimate_eur"]
    if isinstance(raw_cost, bool) or not isinstance(raw_cost, (int, float)):
        return CostGateVerdict(
            allowed=False,
            reason="INVALID_SPEC",
            cost_eur=None,
            provider=provider,
            model=model,
        )
    try:
        cost_val = float(raw_cost)
    except (ValueError, TypeError):
        return CostGateVerdict(
            allowed=False,
            reason="INVALID_SPEC",
            cost_eur=None,
            provider=provider,
            model=model,
        )

    if (
        cost_val < 0.0
        or (cost_val == 0.0 and math.copysign(1.0, cost_val) < 0.0)
        or not math.isfinite(cost_val)
    ):
        return CostGateVerdict(
            allowed=False,
            reason="INVALID_SPEC",
            cost_eur=cost_val,
            provider=provider,
            model=model,
        )

    if (
        isinstance(autonomous_limit_eur, bool)
        or not isinstance(autonomous_limit_eur, (int, float))
        or autonomous_limit_eur != autonomous_limit_eur
        or autonomous_limit_eur < 0.0
    ):
        return CostGateVerdict(
            allowed=False,
            reason="INVALID_SPEC",
            cost_eur=cost_val,
            provider=provider,
            model=model,
        )

    if cost_val > autonomous_limit_eur:
        return CostGateVerdict(
            allowed=False,
            reason="AUTONOMOUS_SPEND_LIMIT_EXCEEDED",
            cost_eur=cost_val,
            provider=provider,
            model=model,
        )

    return CostGateVerdict(
        allowed=True,
        reason="ZERO_COST_APPROVED",
        cost_eur=cost_val,
        provider=provider,
        model=model,
    )


def record_cost_gate_audit(
    ledger_path: str | Path,
    verdict: CostGateVerdict,
    context: Optional[dict[str, Any]] = None,
) -> None:
    p = Path(ledger_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "at": _utc_now(),
        **verdict.to_dict(),
        "context": context or {},
    }
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
        fh.flush()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="courier_core.provider_cost_guard",
        description="Fail-closed provider cost guard enforcing zero spend limit.",
    )
    parser.add_argument("spec_path", help="Path to provider call spec JSON")
    parser.add_argument("--limit-eur", type=float, default=0.0, help="Autonomous spend limit in EUR (default: 0.0)")
    parser.add_argument("--audit-ledger", help="Optional path to append audit record")
    args = parser.parse_args(argv)

    try:
        with open(args.spec_path, "r", encoding="utf-8") as f:
            spec = json.load(f)
    except Exception as exc:
        err = CostGateVerdict(
            allowed=False,
            reason="INVALID_SPEC",
            cost_eur=None,
            provider="",
            model="",
        )
        print(json.dumps(err.to_dict(), indent=2))
        return 1

    verdict = evaluate_cost_gate(spec, autonomous_limit_eur=args.limit_eur)
    if args.audit_ledger:
        record_cost_gate_audit(args.audit_ledger, verdict, context={"spec_file": args.spec_path})

    print(json.dumps(verdict.to_dict(), indent=2))
    return 0 if verdict.allowed else 1


if __name__ == "__main__":
    sys.exit(main())
