# Opus 4.6 — 1H Elite Decision Queue — 2026-09-28

Status: HIGH-VALUE / READ-ONLY / C4 ONLY
Purpose: use a limited Opus window for the hardest unresolved judgment tasks, reusing O46-O53 instead of repeating them.

## Rules

- RESULT_REUSE_FIRST=YES
- Read durable O46-O53 results before raw source.
- No deterministic work.
- No broad repo scan.
- No PRE_CODEX revalidation for unchanged fingerprint.
- No source edits.
- No Codex invocation.
- No physical RUN_1/RUN_2.
- UNKNOWN stays UNKNOWN.
- One live claim per task.
- If a task is already answered by durable evidence, mark RESULT_REUSED.
- Prefer one sharp decision over long prose.

## Elite tasks

### E46-01 — Single biggest causal blocker
Using current durable truth + O46-O53 results, identify the single earliest causal blocker that most constrains progress.
Output:
BLOCKER=
WHY_CAUSAL=
WHAT_IT_BLOCKS=
SMALLEST_TRUE_NEXT_ACTION=
WHAT_NOT_TO_DO=

### E46-02 — Proof economy
Find where Courier is collecting more evidence than needed and where it is still under-proven.
Output:
OVERPROVED=
UNDERPROVED=
REMOVE=
ADD=
NET_EFFECT_ON_CONFIDENCE=
NET_EFFECT_ON_COST=

### E46-03 — False-confidence attack
Adversarially identify the strongest plausible way Courier could appear green while still being wrong.
Focus:
- stale evidence
- wrong candidate/runtime
- replay equivalence
- failed execution contamination
- human relay hidden in setup
- restart ambiguity
Output:
FALSE_GREEN_SCENARIO=
WHY_PLAUSIBLE=
CURRENT_DEFENSE=
MISSING_DEFENSE=
FALSIFYING_EVIDENCE=

### E46-04 — Critical-path compression
Given current state, compress the path from now to first honest pilot into the fewest dependency-safe steps.
Output:
STEP_1=
STEP_2=
...
MUST_NOT_PARALLELIZE=
CAN_PARALLELIZE=
EARLIEST_PILOT_UNLOCK=

### E46-05 — Model-routing economics
Review current Google/Muse/Sonnet/Opus/Codex use and find the best model-cost allocation.
Output:
ROUTING_WASTE=
CHEAPER_SUBSTITUTE=
KEEP_OPUS_FOR=
KEEP_CODEX_FOR=
BEST_DEFAULT_MODEL_CLASS=
EXPECTED_DUPLICATION_RISK=

### E46-06 — Shared-capability moat test
Using O49-O53, decide whether the shared capability/update fabric has a real moat or is just a feature.
Output:
MOAT_MECHANISM=
WHAT_COMPOUNDS=
WHAT_DOES_NOT_COMPOUND=
COPYABILITY_RISK=
DEFENSIBILITY_REQUIREMENT=
FIRST_MEASURABLE_SIGNAL=

### E46-07 — Business model pressure test
Pressure-test the current pilot/business model against:
- willingness to pay
- support burden
- setup cost
- provider cost
- update/support obligations
- liability/privacy expectations
Output:
STRONGEST_REVENUE_LOGIC=
BIGGEST_MARGIN_RISK=
BIGGEST_SUPPORT_RISK=
FIRST_PRICE_TEST=
KILL_SIGNAL=

### E46-08 — Update/security governance decision
Review weekly/monthly/emergency release plan + Time-Machine + capability packs.
Output:
SAFE_DEFAULT_CHANNEL=
WHAT_MUST_AUTO_UPDATE=
WHAT_MUST_REQUIRE_APPROVAL=
ROLLBACK_INVARIANT=
REVOCATION_INVARIANT=
CRYPTO_AGILITY_MINIMUM=

### E46-09 — User-trust architecture
Review whether a normal user can understand:
- what Courier did
- what changed
- what is shared
- what is private
- why it stopped
- how to undo
Output:
TRUST_PRIMITIVES=
CONFUSION_RISK=
MINIMUM_UI_SURFACE=
PROOF_TO_SHOW=
PROOF_TO_HIDE=

### E46-10 — One-year strategic failure mode
Assume Courier fails in 12 months despite good engineering.
Identify the most likely non-technical reason.
Output:
FAILURE_MODE=
EARLY_WARNING_SIGNAL=
CURRENT_PLAN_GAP=
CHEAPEST_TEST_THIS_MONTH=
DECISION_IF_SIGNAL_BAD=

### E46-11 — Product invariant set
Reduce Courier to 7-12 invariants that must remain true even as models/providers/features change.
Output:
INVARIANT_1=
...
INVARIANT_N=
WHICH_INVARIANTS_ARE_CURRENTLY_UNPROVEN=

### E46-12 — Final 1H executive synthesis
Inputs: E46-01..E46-11 only.
Output:
TOP_3_BLOCKERS=
TOP_3_MOATS=
TOP_3_COST_LEAKS=
TOP_3_RISKS=
NEXT_24H=
NEXT_7D=
DO_NOT_BUILD=
MODEL_ROUTING_NEXT=
PILOT_READINESS=
ONE_SENTENCE_COMPANY_THESIS=

## End

Do not create E46-13.
If all tasks are complete/reused/blocked, TRUE_IDLE.
