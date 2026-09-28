# MUSE POST-FREEZE 01 — Idempotency / Liveness / B-Advance (candidate-independent)

BASE=bd539f18. READ_ONLY, no runs, no PRE_CODEX revalidation.
GATE NOTE (process, not a finding): working-tree `ops/ai/GATE_STATE_CURRENT.md`
claims DURABLE/AUTHORITATIVE_READY=YES but is UNCOMMITTED → CODEX_NOW stays
NO until committed; posture remains candidate-independent. No FINAL_SHA touched.

## S1 — verify-FAIL resend asymmetry (NEW, low)
`verify_task_result` ACKs duplicate PASS verdicts on RECONCILED tasks
(app.py:476-480) but a retried identical FAIL verdict lands on 409
("no result awaiting verification", app.py:481-482) because status is already
FAILED_VERIFICATION. Transport-loss retry is indistinguishable from rejection;
verifier cannot get a positive receipt for a delivered FAIL. Intake side has
ACK_DUPLICATE; verify side only for PASS. CLASS=MISSING_EVIDENCE(delivery).
CAN_DEFER=YES. No source touch (writer scope).

## S2 — heartbeat liveness (NO_ISSUE, confirmed sound)
Heartbeat revives `available=True` when task-free and not unregistered
(app.py:262-269); `unregistered` is sticky by documented design (244-252);
reclaim marks stale unavailable (419-428) and clears matching current_task
(446-447). No stuck-worker sink by read.

## S3 — register restart handling (NO_ISSUE with observation)
Re-register with diverged `current_task` quarantines server task to
HUMAN_REQUIRED + goal BLOCKED (197-221). Observation (no defect filed):
re-register silently overwrites capabilities/cost_class; auth scope untouched
per lane rules.

## S4 — B-advance scoping (MISSING_EVIDENCE pointer)
Server advances `current_step_index` on PASS (app.py:503-507) but never
auto-dispatches: B starts only via worker claim (claim_task). Any Proof-Card
B_AUTOSTART assertion must cite worker-side autostart evidence, never server
state. Adjacent to peer autonomy gaps, distinct as server-side scoping rule.

DO_NOT_REPEAT=MUSE_POSTFREEZE_01:S1-S4; prior fingerprints unchanged.
NEXT=open lanes: RUN_1 witness/failure-stickiness, RUN_2 no-replay, cross-host binding.
