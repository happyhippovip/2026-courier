# GLEDGER-118 Result — Device/Wall State Fields

TASK_ID=GLEDGER-118
STATUS=PROVEN (field semantics from live-observed guard behavior + queue rules; numeric thresholds flagged, see MISSING)
HOST=MAC
PROVIDER=GOOGLE
INPUTS_READ=ops/ai/LEDGER_FINISH_QUEUE_30_2026-09-27.md (definition only; device-admission doc not opened — not needed for field semantics)
RESULTS_REUSED=MAX_HEAVY_JOBS=1 guard observed live all shift (4 resident courier/pytest processes → automatic LIGHT_READ_ONLY fallback, no human relay); GLEDGER-105 (lease fields); GLEDGER-117 (heavy admission as cost guard); wall role rules

## Wall capacity record (normative — truthful representation)
REQUIRED: `requested` (what the worker asked: heavy slot | light lane | specific device), `admitted` (granted subset — server/lane authority decides, never the requester), `active` (currently running heavy jobs with PIDs/handles where observable), `guarded` (capacity held for higher-priority or in-flight work, not allocatable), `reserved` (held for a named upcoming task/generation), `heavy` (count + identities of heavy jobs now), `workload` (light-lane load marker: tasks in flight that are not heavy).
OPTIONAL: device class/host arch notes (informational), last-sweep timestamp.
FORBIDDEN: admitted exceeding capacity (admission must fail closed); self-admission by the requester; stale active entries (finished jobs must release — heartbeat/sweep owned by the lane authority).

## Truthfulness rules (normative)
- Reported capacity is measured (process table / job registry), never asserted: an `active: []` claim with unaccounted processes is VOID.
- Over-admission resolves by downgrade, not queueing: second heavy request → light lane automatically (observed behavior), recorded as `admitted: light` with reason CAPACITY.
- `guarded`/`reserved` are first-class so "why was I downgraded" is answerable from the record alone.
- Capacity never enters identity/equivalence; it gates routing only (GLEDGER-116).

MISSING=Numeric thresholds (heavy-job memory/CPU cutoffs, sweep intervals, lease durations) — operational tuning in device-admission/motor docs; not contract. Flagged for owner calibration, not Ledger definition.
BLOCKER=None in-lane.
NEXT_DEPENDENCY=GLEDGER-120 (RESOURCE stop reason reads these fields); GLEDGER-130 (BOUNDED_RESOURCES output references this record).
DO_NOT_REPEAT_FINGERPRINT=gledger-118-device-wall-state-complete

DO_NOT_REPEAT_FINGERPRINT=sha256-6416a4482730e1d1

DO_NOT_REPEAT_FINGERPRINT=sha256-7dfe34c1434b126f
