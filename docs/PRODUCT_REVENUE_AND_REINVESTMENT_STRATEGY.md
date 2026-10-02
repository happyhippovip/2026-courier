# Product Revenue and Reinvestment Strategy

## Purpose

This document gives future Courier/agent runs a durable economic decision framework. It is a planning and prioritization policy, not standing authorization for external sales, spending, deployment or payment activation.

## Core objective

Build a product that creates real user value, can become commercially viable, and can eventually help fund its own continued development and tooling.

When choosing among several safe, technically valid and goal-consistent product directions, prefer the option with the strongest evidence-adjusted economic value.

## Priority order

Use this ordering as a default decision heuristic:

1. Solve a real, important user problem.
2. Prefer workflows that can become sellable sooner.
3. Prefer stronger expected net revenue when evidence supports it.
4. Prefer shorter time-to-validation and willingness-to-pay evidence.
5. Prefer lower build and operating cost when value is comparable.
6. Prefer options that create reusable product learning and strategic leverage.
7. Preserve trust, privacy, safety, reliability and long-term viability.

Revenue never overrides safety, legality, product integrity or explicit human gates.

## Revenue-first interpretation

"Revenue-first" means:

- do not optimize for feature count;
- do not build technical primitives with weak user value merely because they are interesting;
- do not spend scarce model/tool capacity on low-value work;
- among comparably useful opportunities, prioritize the one most likely to create validated willingness to pay and positive net value;
- distinguish expected gross revenue from expected net value after operating cost, support burden and risk.

## Self-funding loop

Desired long-term loop:

`USER VALUE → SELLABLE PRODUCT → REVENUE → HUMAN-APPROVED REINVESTMENT → BETTER TOOLING/CAPACITY/INFRASTRUCTURE → FASTER/BETTER PRODUCT DEVELOPMENT → MORE USER VALUE`

Potential future reinvestment categories include:

- higher-quality model/tool subscriptions;
- additional legitimate model capacity;
- testing and reliability infrastructure;
- hosting/deployment infrastructure;
- observability and security;
- product design/usability work;
- market validation and distribution tooling.

Actual purchases, subscription upgrades, overages or other spend require explicit human approval.

## What agents may do autonomously

Inside the repository and within the active product goal, agents may:

- analyze target users and pain points;
- identify commercially meaningful product gaps;
- compare candidate features by user value, sellability, expected net revenue, validation speed and cost;
- prepare pricing/packaging hypotheses;
- estimate operating/support cost;
- improve internal product readiness for future commercialization;
- design low-cost validation experiments that stop before any external action;
- define metrics for activation, retention, willingness to pay and conversion;
- rank roadmap items economically;
- identify concrete product improvements that could increase willingness to pay;
- improve Courier only when real product work exposes a reproducible blocker or high-value friction.

## Human approval gates

The following remain explicit human gates and must fail closed without approval:

- public deployment or publication;
- contacting prospects/customers/users;
- sending emails/messages externally;
- activating payments or billing;
- accepting or moving real funds;
- making purchases;
- subscription/model/tool upgrades;
- enabling paid overages;
- changing account/billing arrangements;
- signing contracts or accepting legal terms;
- KYC or identity verification;
- wallet signing or real-money financial activity.

## Candidate-work scoring

When useful, score candidate internal product work using a lightweight evidence-adjusted model:

- USER_VALUE: 0–5
- SELLABILITY: 0–5
- REVENUE_POTENTIAL: 0–5
- TIME_TO_VALIDATION: 0–5, higher = faster
- COST_EFFICIENCY: 0–5, higher = cheaper
- STRATEGIC_LEARNING: 0–5
- TRUST_AND_SAFETY: PASS/FAIL
- GOAL_ALIGNMENT: PASS/FAIL

A candidate must pass TRUST_AND_SAFETY and GOAL_ALIGNMENT before economic scoring matters.

Suggested ranking signal:

`ECONOMIC_PRIORITY = USER_VALUE + SELLABILITY + REVENUE_POTENTIAL + TIME_TO_VALIDATION + COST_EFFICIENCY + STRATEGIC_LEARNING`

This score is a heuristic, not a guarantee of revenue. Evidence beats numeric theater.

## Product vs. agent-system allocation

Default bias:

- PRODUCT WORK first when Courier is operational.
- AGENT-SYSTEM WORK only when a real product run exposes a concrete reproducible blocker, repeated material friction, or a clearly evidenced improvement whose expected benefit exceeds its cost.

Avoid turning Courier itself into the endless product.

## Model/tool economics

Use the cheapest sufficient capability first.

Preferred routing principle:

`CHEAP DETERMINISTIC CHECK → CHEAP/PRIMARY BUILDER → EXPENSIVE SPECIALIST ONLY FOR HIGH INFORMATION GAIN`

Do not consume expensive capacity merely because it exists. Preserve specialist capacity for architecture, adversarial review, hard root-cause analysis or other cases where cheaper paths are insufficient.

## Required handoff awareness

Before a major planning phase, future agents should read:

- `docs/CANONICAL_COMPLETION_HANDOFF.md`
- `docs/IMPORTANT_SIDE_THOUGHTS.md`
- this file

The next agent should continue from the last proven checkpoint and use this strategy only when it is relevant to the current goal.

## Suggested phase-end economic fields

Where economically relevant, future handoffs may record:

- `COMMERCIALIZATION_RELEVANT: YES/NO`
- `TARGET_USER_HYPOTHESIS: <text/NONE>`
- `WILLINGNESS_TO_PAY_EVIDENCE: <text/NONE>`
- `SELLABILITY_GAP: <text/NONE>`
- `HIGHEST_VALUE_NEXT_PRODUCT_MOVE: <text/NONE>`
- `REVENUE_ACTION_REQUIRES_HUMAN_GATE: YES/NO`
- `REINVESTMENT_OPPORTUNITY: <text/NONE>`

These fields do not authorize external action.

Last updated: 2026-09-06


## 2026-09-20 packaging direction — included outcome plan

Founder working hypothesis:

- target an initial package around **EUR 99–100/month**;
- include a useful amount of routine Courier AI and agent work;
- describe customer value as **included in the plan**, not "free";
- meter real variable cost internally;
- route work through the cheapest sufficient capability;
- require an explicit extra quote before unusually expensive work;
- never create silent overages.

Commercial decision model:

`CUSTOMER GOAL -> ESTIMATE COST/RISK -> INCLUDED | EXTRA_QUOTE_REQUIRED -> HUMAN APPROVAL IF EXTRA -> EXECUTE -> VERIFIED RESULT -> RECORD ACTUAL COST`

Required unit-economics reasoning should consider model/API, cloud compute, storage, egress, tools and support burden.

The exact public price and plan limits remain a Human Gate pending real cost and willingness-to-pay evidence.

Working detail:
`docs/agent-warehouse/CUSTOMER_PACKAGING_AND_COST_GUARDRAILS_2026-09-20.md`
