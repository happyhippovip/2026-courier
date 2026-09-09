# Courier Money Factory — P0 Architecture & Integration Blueprint

## 1. What Was Reused
- **Scoring & Metric Concepts**: Adapted 24-metric principles from `project-memory/money_factory/money_scoring.js` and `courier/content_os/opportunity_evaluator.py`, integrating velocity multipliers and explicit UNKNOWN handling.
- **Evidence & Truth Discipline**: Adapted the Money Truth Firewall (`project-memory/engine/money_truth_ladder.js`) to reject synthetic test data (`FAST_TEST_MODE`) from ever counting as real revenue.
- **Cycle & Fingerprint Logic**: Reused the immutable SHA-256 fingerprinting pattern from `project-memory/money_factory/cycle_ledger.js` to enforce strict cycle idempotency and catch-up capabilities.
- **Spend Interceptor**: Reused the hard invariants (`AUTONOMOUS_SPEND_LIMIT_EUR = 0`, no wallets, no trading) from `project-memory/money_factory/spend_safety.js`.

---

## 2. What Was Built
- **Durable Warehouse Directory Structure (`opportunity_warehouse/`)**:
  - `opportunities.yaml` & `opportunities.json`: Canonical machine & human-readable database with 32 required economic record fields.
  - `LEADERBOARD.md`: Automatically updated markdown radar across all 4 horizons (`NOW`, `30D`, `365D`, `ASYMMETRIC`).
  - `MONEY_FACTORY_POLICY.md`: Hard-coded safety policies, human gate definitions, and anti-loop invariants.
  - `history_ledger.json`: Append-only audit trail guaranteeing no opportunity history can ever be overwritten or lost.
  - `research/2026/`, `evidence/`, `experiments/`, `winners/`, `archive/`: Standardized folder hierarchy.
- **Core Autonomous Engine (`money_factory/`)**:
  - `warehouse.js`: Full lifecycle state machine (`SEED` -> `ACTIVE` -> `PROVING` -> `WINNER` | `ARCHIVED` / `KILLED`) with zero-dependency YAML serialization.
  - `scoring.js`: Deterministic ranking engine:
    $$\text{Score} = \frac{\text{RevProb} \times \text{ExpectedProfit} \times \text{Automation} \times \text{Speed} \times \text{Distribution} \times \text{Evidence}}{\max(1, \text{Capital}) \times \text{AgentHours} \times \text{HumanHours} \times \text{Risk}}$$
    Always stores component evidence and confidence alongside the scalar score.
  - `portfolios.js`: Automatic categorization into `CASH_NOW` (~50%), `GROWTH` (~35%), and `MOONSHOTS` (~15%).
  - `seed_classes.js`: Initialized 7 strategic classes with explicit `UNKNOWN` evidence fallbacks.
  - `cycle_ledger.js`: Scheduled cycle identity `MONEY-YYYY-MM-DD` requiring concrete sources before achieving `VERIFIED` status.
  - `prediction_calibration.js`: Immutable prediction history recording predictions at decision time and reconciling against empirical actuals with absolute and relative error metrics.
  - `safety_gates.js`: Interceptor routing 14 critical operations to `HUMAN_GATE` and producing structured `SPEND_REQUEST` objects instead of spending money.
  - `anti_loop_policy.js`: Post-freeze invariant blocking Courier infrastructure changes unless a reproducible defect blocks revenue.
  - `leaderboard_generator.js`: Automated Markdown leaderboard generator.
  - `index.js`: Unified programmatic interface.
- **Deterministic Test Suite (`tests/test_money_factory_p0.js`)**:
  - 18 comprehensive tests proving 100% pass rate with zero fake strings.

---

## 3. What Remains Intentionally Unbuilt (P1 / P2 Scope)
- **Autonomous Billing/Stripe Connector**: Intentionally excluded. Real money collection requires physical human gateway setup.
- **Automated Social Media / Browser Uploaders**: Intentionally excluded to avoid credential compromise and account suspension.
- **Complex Multi-Tier Agent Orchestration**: Intentionally excluded. Money Factory is a deterministic domain layer, NOT a second workflow orchestrator.
- **Dynamic Price Optimization / Trading Algorithmic Engines**: Strictly prohibited by safety policy.

---

## 4. How Courier Will Invoke This Post-Freeze With ONE Goal
Post-freeze, Courier receives a single top-level economic instruction:
```text
"Courier: Advance the top CASH_NOW opportunity to first €5 proof under zero-spend policy."
```
Courier's execution loop:
1. Queries `MoneyFactory.getWarehouse().getAllOpportunities()` sorted by `NOW` horizon.
2. Selects the #1 ranked candidate (e.g. `OPP-SEED-DIGITAL-01`).
3. Evaluates `opportunity.next_test`.
4. Executes the local prototype build (e.g., creates single-file CLI tool and deterministic test harness).
5. Gathers local verification evidence and appends it to `evidence/`.
6. Generates a structured `HUMAN_GATE` artifact with the built deliverable for the human to publish or list.
7. Logs the prediction snapshot via `PredictionCalibrator.recordPrediction()`.
8. Pauses and awaits external revenue reconciliation.

---

## 5. How First €5 Can Be Proven Without Manual Founder Selling
- **Micro-Tool / Digital Asset Self-Checkout**:
  - Build a high-utility, single-purpose CLI tool or template (e.g., developer token auditor or Godot state-machine boilerplate).
  - Human Gate performs a one-time listing on an automated self-serve platform (e.g., Gumroad, Itch.io, or GitHub Marketplace) at €5.00 with a public link.
  - Inbound search / organic forum discovery drives direct programmatic purchase without the founder engaging in 1-on-1 sales calls or manual outreach.
  - Webhook or bank statement provides verifiable external settlement artifact (`external_bank_or_stripe_proof: true`).
  - Money Factory validates the evidence, reconciles prediction error, and promotes the candidate to `WINNER`.

---

## 6. Which Actions Remain Human-Gated
1. `PAYMENT` / `REAL_SPEND` (€0 autonomous limit)
2. `SUBSCRIPTION` / `UPGRADE` / `OVERAGE`
3. `PUBLICATION` (making content or tools public)
4. `PRODUCTION_DEPLOYMENT` (pushing code to live servers)
5. `CUSTOMER_OUTREACH` / `EXTERNAL_MESSAGING` (preventing spam/harassment)
6. `ACCOUNT_CREATION` / `LOGIN_2FA_KYC` (identity protection)
7. `REAL_TRADES` / `WALLET_SIGNING` (financial protection)
