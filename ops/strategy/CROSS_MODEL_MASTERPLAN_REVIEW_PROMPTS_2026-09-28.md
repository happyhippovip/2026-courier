# Cross-Model Masterplan Review — 2026-09-28

Use these prompts against the current MASTERPLAN V2 DRAFT.
Do not let reviewers replace the proof-gated core plan.

## Reviewer A — Claude Opus 5.5

ROLE=BOARD_LEVEL_PRODUCT_SYSTEMS_REVIEWER

Read:
docs/COURIER_SYMPHONY_CANONICAL_PRODUCT_PLAN.md
docs/COURIER_SYMPHONY_MASTERPLAN_V2_DRAFT_2026-09-28.md
ops/ai/COURIER_REVENUE_TRACK_CURRENT.md

Mission:
Attack the plan as if your job is to prevent a technically interesting company from wasting 18 months.

Optimize simultaneously for:
1 fastest honest revenue;
2 fastest real product;
3 strongest durable moat;
4 future relevance to physical/humanoid autonomy;
5 minimum scope.

Do not change the existing proof-gate order unless you can show a concrete contradiction.

Return:
KEEP=
CUT=
MOVE_EARLIER=
MOVE_LATER=
REVENUE_WEDGE=
PRODUCT_WEDGE=
ROBOTICS_WEDGE=
MOAT_RISK=
CATEGORY_RISK=
TOP_5_CHANGES=
ONE_SENTENCE_COMPANY_THESIS=

Be adversarial. No motivational prose.

## Reviewer B — Claude Sonnet 5.5

ROLE=EXECUTION_AND_GO_TO_MARKET_SIMPLIFIER

Read the same three files.

Mission:
Turn the strategy into the smallest plan that can get:
- first payment;
- first successful pilot;
- first repeat-use signal;
- first simple product;
without increasing core engineering scope.

Focus on:
pricing;
offer clarity;
sales friction;
pilot onboarding;
measurement;
what can be manual;
what absolutely needs software;
what should be deleted.

Return:
FIRST_7_DAYS=
FIRST_3_CUSTOMERS=
MINIMUM_DELIVERABLE=
WHAT_NOT_TO_BUILD=
PRICE_TESTS=
SALES_SCRIPT_CORE=
PILOT_SUCCESS_RULE=
TOP_10_EXECUTION_CUTS=

## Reviewer C — Grok 4.7

ROLE=CONTRARIAN_MARKET_AND_SCALE_REVIEWER

Read the same three files.

Mission:
Try to falsify the large-company thesis.

Questions:
- Is "verified autonomy infrastructure" a real category or just wording?
- What gets commoditized by model providers?
- What would OpenAI/Anthropic/xAI/Google build natively that could crush this?
- What remains valuable if persistent agents become free?
- Does the digital-to-physical worker abstraction actually hold?
- What would make humanoid robotics teams care?
- What would make them ignore Courier?
- What could become a real protocol/platform moat?
- What is the fastest path to cash while preserving the upside?

Return:
THESIS_SURVIVES=YES|PARTIAL|NO
COMMODITIZED_LAYER=
DEFENSIBLE_LAYER=
ROBOTICS_REALITY_CHECK=
FASTEST_REVENUE=
BIGGEST_DELUSION_RISK=
MISSING_COMPETITOR=
PROTOCOL_OPPORTUNITY=
TOP_5_CHANGES=
KILL_CRITERIA=

No hype. No valuation prediction.

## Final synthesis prompt

After all three reviews exist:

ROLE=MASTERPLAN_SYNTHESIS

Inputs:
- current canonical plan;
- Masterplan V2 draft;
- Opus review;
- Sonnet review;
- Grok review.

Rules:
- evidence over model authority;
- majority vote is not truth;
- preserve core gate order unless concrete evidence requires change;
- prefer cuts over additions;
- no robotics implementation before allowed trigger;
- distinguish immediate revenue, product, and strategic optionality.

Produce:
AGREEMENT=
DISAGREEMENT=
CHANGES_ACCEPTED=
CHANGES_REJECTED=
WHY=
FINAL_REVENUE_PLAN=
FINAL_PRODUCT_PLAN=
FINAL_ROBOTICS_OPTION=
FINAL_MOAT=
NEXT_30_DAYS=
