# Billing & Token Limits

This guide provides an overview of billing models, cost governance, and token limit configurations in Courier.

## Overview

Courier coordinates autonomous agents across heterogeneous environments while enforcing deterministic cost controls. To prevent runaway provider expenditures and context bloat, Courier implements a multi-tier resource accounting framework.

---

## Pricing Tiers (Draft)

| Tier | Target Audience | Worker Nodes | Included Monthly Allocation | Extra Token Pricing |
| :--- | :--- | :--- | :--- | :--- |
| **Community / Local** | Open source developers | Unlimited self-hosted | BYOK (Bring Your Own Key) | Provider direct rates |
| **Solo Pilot** | Independent operators | Up to 2 active workers | 10M tokens / month | Standard pilot schedule |
| **Team / Enterprise** | Multi-machine clusters | Scalable worker pools | Dedicated allocation pools | Volume negotiated pricing |

---

## Token Limits & Efficiency Layer

Courier's token optimization framework ensures that task execution remains within predictable financial and operational boundaries.

### 1. Minimal Task Packets
Rather than streaming conversational histories, Courier encapsulates tasks into bounded task packets with fixed context allocations:
- Explicit context budgets per task packet
- Forward-only diffs and causal evidence rather than full-repository transfers
- Elimination of repetitive background polling

### 2. Token Consumption Metrics
Every worker reports detailed execution metrics back to the action and cost ledgers:
- `INPUT_TOKENS`: Measured prompt tokens processed by the assigned model.
- `OUTPUT_TOKENS`: Generation tokens produced by the agent.
- `CONTEXT_SIZE`: Total context window footprint per invocation.
- `TOKENS_PER_VERIFIED_TASK`: Efficiency ratio for accepted deliverables.

---

## Budget Boundaries & Pacing Controls

To ensure continuous unattended operations without unexpected costs:
- **Soft Thresholds**: Notifications dispatched when account consumption reaches 80% of defined boundaries.
- **Hard Thresholds**: Dispatches halt fail-safe when reaching monthly budgetary caps.
- **Model Escalation Path**: Tasks default to the lowest-cost sufficient worker model, escalating to higher-tier models only when verification evidence demonstrates necessity.

---

## Frequently Asked Questions

### How does Courier handle BYOK (Bring Your Own Key)?
When using self-hosted worker daemons, API credentials remain secure in local system keychains or environment variables. Credentials are never synchronized through central state servers.

### Can custom per-task token limits be defined?
Yes. Workflows defined in goal plans can specify granular `CONTEXT_BUDGET` constraints within individual task definitions.
