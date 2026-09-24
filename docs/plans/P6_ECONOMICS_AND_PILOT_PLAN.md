# P6: Pilot & Economics (Wirtschaftlichkeit) - Definition & Plan

This document defines the baseline economics, budget controls, and operational costs for the Courier Pilot (P4) and subsequent production phases. It explicitly discards previous unvalidated marketing proposals (e.g., "249 EUR/month") in favor of a bottom-up cost model derived from physical execution data.

## 1. Klarer Leistungsumfang (Scope of Services)
The Courier managed pilot provides:
- **Central Orchestration (Server):** Highly available state management (`central_state.json`), API routing, and ledger verification.
- **Worker Infrastructure:** Default generic compute workers for execution, with the ability for customers to connect their own "Bring Your Own Worker" (BYOW) nodes.
- **Support:** Break-fix support for the orchestration engine. Task-level failures (e.g., an agent writing bad code) are considered user-space errors and are not covered by platform SLA.

## 2. Betriebskosten (Operational Costs - Platform)
The core architecture is extremely lightweight (Python/Flask + JSON state).
- **Control Plane:** 1x Standard VM (e.g., e2-medium or equivalent) = ~25 EUR/month.
- **Storage:** Local SSD + periodic snapshots to object storage = ~5 EUR/month.
- **Network Egress:** Dependent on artifact payload sizes. Expected <10 EUR/month for text/json workloads.
- **Total Fixed Platform Cost:** ~40 EUR/month.

## 3. Providerkosten & Budgetkontrollen (LLM/API Costs)
Agentic workflows consume significant LLM tokens. Courier must protect both the platform and the customer from runaway loops.
- **Model:** Tasks run via `Google-Antigravity` or `Opus`.
- **Cost per Task:** A typical complex task loop consumes ~50k-100k tokens. At average API rates, this is ~0.10 - 0.50 EUR per task.
- **Budget Controls (Crucial):**
  - **Hard Caps:** Every Goal MUST have a `max_budget_eur` field.
  - **Token Tracking:** The server must aggregate `usage` metadata from worker result payloads.
  - **Fail-Closed on Quota:** If `accumulated_cost >= max_budget_eur`, the dispatcher returns `402 Payment Required` and sets the Goal to `BLOCKED`.

## 4. Supportaufwand (Support Overhead)
- Pilot customers will require onboarding assistance to configure their local Mac/Windows workers.
- Estimated 2-4 hours of human support per pilot customer in the first week.
- Support scaling requires automated diagnostic scripts (like `run_debug_server.py`) to minimize manual log parsing.

## 5. Passende Preise (Pricing Strategy)
Pricing must be based on actual utility and compute overhead, not arbitrary tiers.
- **Base Orchestration Fee:** Covers the fixed platform costs and support overhead. Estimated at 49 EUR/month for the pilot phase.
- **Pass-through Compute (Usage-based):** 
  - If using Courier's hosted models, cost is API cost + 15% markup to cover network and variability.
  - If the customer uses BYOK (Bring Your Own Key), model compute cost is 0 EUR to Courier.
- **Storage/Bandwidth:** Included up to 10GB, then 0.15 EUR/GB (cost-plus).
- *Note: No guaranteed revenue or fictional launch dates are promised. This is a pilot validation model.*

## 6. Pilot-Abrechnung (Sandbox)
For P4 (Solo-Pilot), real payment gateways (Stripe) will NOT be used.
- Instead, a mock billing adapter (`sandbox_billing.py`) will be implemented to deduct virtual credits and test the 402 Fail-Closed circuit breaker without actual financial risk.
