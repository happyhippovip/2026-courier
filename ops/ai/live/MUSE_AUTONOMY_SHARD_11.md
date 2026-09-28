# Autonomy shard checkpoint

SHARD=11
STATUS=SHARD_COMPLETE
SUBCASES_DONE=4 (S1 semantics, S2 dead-gate defect, S3 task-label inert, S4 stale-window disproven) + 1 DUPLICATE_SKIP
CONFIRMED_SOURCE_DEFECTS=1 (S2 dead CostGate)
EVIDENCE_GAPS=1 (S3 task cost_class routing-inert)
DISPROVEN=1 (S4 stale cheap-worker block)
FIX_PACKETS=1 (FP1 below)
NEXT_OWNER=server-lane owner (server/app.py claim path; foreign scope — no edit made)
DO_NOT_REPEAT=sha256-autonomy-shard11-costgate-01

## S1 — CostGate semantics fail-closed (NO_ISSUE on the gate itself)
- `scripts/resource_policy.py:103-146`: unknown/not-active resource → deny
  (:124-130 UNAUTHORIZED_RESOURCE_TIER); any estimated_cost>0 or
  upgrade/purchase action → deny (:133-139 SPEND_NOT_ALLOWED_BY_POLICY).
  Covered by `tests/test_resource_policy_mission_093.py:69-80`.
  REUSE_EVIDENCE=test_resource_policy_mission_093.py.

## S2 — Dead gate: zero production invocations (CONFIRMED_SOURCE_DEFECT)
- Bounded grep: `CostGate.`/`evaluate_spend_request(` occur ONLY in
  `scripts/resource_policy.py` (def), the test, and bare imports
  (`scripts/run_autonomous_loop.py:59,81`,
  `scripts/run_chief_commander.py:54,70` — never called).
- `server/app.py` claim_task (:269-360) performs NO cost/budget decision
  before DISPATCHED; only soft cost_class routing (:302-334). Shard-11 goal
  ("Kostenentscheidung vor Dispatch, fail-closed") is NOT implemented at runtime.
- FIX_PACKET FP1: FILES=server/app.py (claim_task) + scripts/resource_policy.py;
  CAUSAL_BUG=CostGate imported, never invoked on any dispatch path;
  MIN_FIX=invoke CostGate.evaluate_spend_request in claim_task before
  next_task DISPATCHED (:348); deny → fail-closed (400/503), no dispatch;
  TARGETED_TEST=new: claim with unauthorized/over-budget tier → denied, task
  stays QUEUED; OWNER=server-lane owner (app.py foreign scope);
  BEFORE_CODEX=NO, BEFORE_RUN1=YES.

## S3 — Task-level cost_class routing-inert (MISSING_EVIDENCE)
- `scripts/run_chief_commander.py` stamps `cost_class="ZERO_COST_LOCAL"`
  on steps/tasks (:106, :371-526); claim_task reads ONLY worker cost_class
  (`server/app.py:317`; 3 cost_class refs total in app.py: :240, :317, :326).
  "ZERO_COST_LOCAL" matches no routing branch anywhere.
- MISSING_EVIDENCE: no consumer of task cost_class; wire task→routing or drop
  the labels (owner decision, chief lane).

## S4 — Stale cheap-worker block risk (DISPROVEN)
- Feared: stale last_seen lets dead cheap workers block expensive claims.
  Refuted: claim loop skips workers with last_seen age >300s
  (`server/app.py:308-312`), and last_seen refreshes every claim (:281).
  Bounded 300s window, source-grounded.

## DUPLICATE_SKIP
- cost_class default "unknown" bypassing arbitration (app.py:240 vs :305-317):
  already filed as MISSING_EVIDENCE minor in
  ops/ai/live/MUSE_SMARTWALL_FREEZE_ROUND.md:11 — not re-explained.
