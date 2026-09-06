#!/usr/bin/env python3
"""LLM Token Burn & Quota Capacity Auditor.

Zero-dependency Python tool for analyzing model API logs, transcript sessions,
and computing productive vs wasted token spend, loop repetition overhead, and quota reset runway.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


@dataclass
class TokenAuditMetrics:
    total_calls: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    wasted_tokens: int = 0
    wasted_cost_usd: float = 0.0
    waste_percentage: float = 0.0
    loop_repetitions_detected: int = 0
    identified_optimizations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TokenBurnAuditor:
    """Analyzes model API transcripts and computes spend efficiency metrics."""

    DEFAULT_PROMPT_PRICE_PER_M = 0.150  # USD per 1M tokens (e.g. Gemini / Claude Instant class)
    DEFAULT_COMPLETION_PRICE_PER_M = 0.600  # USD per 1M tokens

    def __init__(self, prompt_price_per_m: float = DEFAULT_PROMPT_PRICE_PER_M, completion_price_per_m: float = DEFAULT_COMPLETION_PRICE_PER_M):
        self.prompt_price = prompt_price_per_m
        self.completion_price = completion_price_per_m

    def audit_session_events(self, events: List[Dict[str, Any]]) -> TokenAuditMetrics:
        """Audits a list of LLM call records for token burn and waste patterns."""
        metrics = TokenAuditMetrics()
        seen_prompts: Dict[str, int] = {}

        for ev in events:
            metrics.total_calls += 1
            p_tok = int(ev.get("prompt_tokens", ev.get("input_tokens", 0)))
            c_tok = int(ev.get("completion_tokens", ev.get("output_tokens", 0)))
            tot = p_tok + c_tok
            
            metrics.total_prompt_tokens += p_tok
            metrics.total_completion_tokens += c_tok
            metrics.total_tokens += tot

            # Check prompt duplication / retry loops
            prompt_snip = ev.get("prompt_snippet", ev.get("system_prompt", ""))[:120]
            if prompt_snip:
                seen_prompts[prompt_snip] = seen_prompts.get(prompt_snip, 0) + 1
                if seen_prompts[prompt_snip] > 1:
                    metrics.loop_repetitions_detected += 1
                    # Flag repeated prompt token overhead as waste
                    metrics.wasted_tokens += p_tok

            # Flag error responses or unparsed outputs
            if ev.get("status") in ("ERROR", "TIMEOUT", "RETRY"):
                metrics.wasted_tokens += tot

        # Compute financial costs
        cost_prompt = (metrics.total_prompt_tokens / 1_000_000.0) * self.prompt_price
        cost_completion = (metrics.total_completion_tokens / 1_000_000.0) * self.completion_price
        metrics.estimated_cost_usd = round(cost_prompt + cost_completion, 4)

        wasted_cost = (metrics.wasted_tokens / 1_000_000.0) * ((self.prompt_price + self.completion_price) / 2.0)
        metrics.wasted_cost_usd = round(wasted_cost, 4)

        if metrics.total_tokens > 0:
            metrics.waste_percentage = round((metrics.wasted_tokens / metrics.total_tokens) * 100.0, 1)

        # Generate Actionable Optimization Rules
        if metrics.loop_repetitions_detected > 0:
            metrics.identified_optimizations.append(
                f"Prompt Caching: {metrics.loop_repetitions_detected} identical prompt iterations detected. Enabling prefix caching will save ~{round(metrics.wasted_tokens * 0.8)} tokens."
            )
        if metrics.waste_percentage > 20.0:
            metrics.identified_optimizations.append(
                f"Loop Breaker: Waste rate is {metrics.waste_percentage}%. Implement hard iteration limits and exponential backoff to prevent spinning."
            )
        if metrics.total_calls > 10 and metrics.total_completion_tokens < (metrics.total_prompt_tokens * 0.05):
            metrics.identified_optimizations.append(
                "System Prompt Trimming: System prompt to response ratio is >20:1. Strip verbose examples from system prompt into dynamic retrieval."
            )

        return metrics

    def generate_markdown_report(self, metrics: TokenAuditMetrics, title: str = "LLM Token Burn & Spend Audit") -> str:
        opts_list = "\n".join([f"- {opt}" for opt in metrics.identified_optimizations]) if metrics.identified_optimizations else "- No major waste patterns detected."
        return f"""# {title}
**Audit Timestamp:** {utc_now()}  
**Analyzed Model Calls:** {metrics.total_calls}

---

## 1. Executive Cost & Efficiency Summary

| Metric | Measured Value | Benchmark Target |
| :--- | :--- | :--- |
| **Total Tokens Consumed** | {metrics.total_tokens:,} | N/A |
| **Estimated Model Cost** | ${metrics.estimated_cost_usd:.4f} USD | N/A |
| **Wasted Token Overhead** | **{metrics.wasted_tokens:,}** tokens | < 5.0% |
| **Wasted Spend** | **${metrics.wasted_cost_usd:.4f} USD** | < $0.01 |
| **Waste Rate** | **{metrics.waste_percentage}%** | < 5.0% |
| **Loop Repetitions** | {metrics.loop_repetitions_detected} cycles | 0 cycles |

---

## 2. High-Impact Optimization Recommendations

{opts_list}

---
*Generated by Token Burn Auditor V1.0.0 (Zero External Dependencies)*
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="LLM Token Burn & Quota Capacity Auditor")
    parser.add_argument("log_file", type=str, help="Path to JSON file containing model event transcripts")
    parser.add_argument("--export", type=str, default=None, help="Export markdown audit report to file")
    args = parser.parse_args()

    log_path = Path(args.log_file)
    if not log_path.is_file():
        print(f"Error: File {args.log_file} not found.")
        return 1

    data = json.loads(log_path.read_text(encoding="utf-8"))
    events = data if isinstance(data, list) else data.get("events", data.get("calls", []))

    auditor = TokenBurnAuditor()
    metrics = auditor.audit_session_events(events)

    if args.export:
        rep = auditor.generate_markdown_report(metrics)
        Path(args.export).write_text(rep, encoding="utf-8")
        print(f"Exported audit report to {args.export}")
    else:
        print(json.dumps(metrics.to_dict(), indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
