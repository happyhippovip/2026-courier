# GLEDGER-113 Result — Do-Not-Repeat Fingerprint + RETEST_TRIGGER Rules

TASK_ID=GLEDGER-113
STATUS=PROVEN (by reused durable evidence; no new source reads)
HOST=MAC
PROVIDER=GOOGLE
INPUTS_READ=ops/ai/LEDGER_FINISH_QUEUE_30_2026-09-27.md (definition only)
RESULTS_REUSED=GLEDGER-112 (fingerprint role); ledger fingerprint history (phys-*, post200-021-*, gledger-10x-*); POST200-021 packet "Do Not Repeat Fingerprint" field; queue end-condition (no filler queue, no auto-131)

## Fingerprint composition (normative)
`do_not_repeat` = short stable slug covering {task_id, generation_id, canonical input set hash or explicit input list, scope boundary}. Observed convention: `{task}-{scope}-{outcome}` (e.g. gledger-107-result-identity-complete). REQUIRED properties: stable across sessions (same inputs → same string), scoped (different task or different inputs → different string), human-readable (a worker must match it without recomputation), recorded in BOTH the result file and the ledger line.
Ledger match rule: a new claim with identical (task_id, generation_id, fingerprint) against a RECONCILED ledger line → adopt, do not execute. Any component differs → new work (or stale-check per GLEDGER-114 first).

## RETEST_TRIGGER invalidation rules (normative — the done condition)
A fingerprint is INVALIDATED (result must be re-earned, prior result kept as history not truth) iff ANY of:
1. Canonical base SHA changed (new candidate) for evidence bound to code behavior.
2. Generation superseded with different packet inputs for that task.
3. Explicit RETEST_TRIGGER issued naming {task_id, reason, invalidating change} — triggers MUST be explicit records, never inferred from chatter, recency, or session change.
4. Contradiction proven against the result (→ GLEDGER-115 procedure; the old fingerprint is marked CONTRADICTED, not silently replaced).
NOT invalidations: /clear, new session, new host, provider change, elapsed time, re-prompting, duplicate prompts. Repeating an invalidated task without a trigger is busywork; executing a completed fingerprint without invalidation is duplicate work.

MISSING=None.
BLOCKER=None in-lane.
NEXT_DEPENDENCY=GLEDGER-114 (stale handling consumes invalidation rules); GLEDGER-115 (contradiction marking); GLEDGER-130 (finish gate checks trigger ledger empty).
DO_NOT_REPEAT_FINGERPRINT=gledger-113-fingerprint-trigger-rules-complete

DO_NOT_REPEAT_FINGERPRINT=sha256-09e6380782d82a13

DO_NOT_REPEAT_FINGERPRINT=sha256-cc49741f765542f7
