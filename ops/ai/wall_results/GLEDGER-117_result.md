# GLEDGER-117 Result — Cost/Quota State

TASK_ID=GLEDGER-117
STATUS=PROVEN (by reused durable cost rules; no new source reads)
HOST=MAC
PROVIDER=GOOGLE
INPUTS_READ=ops/ai/LEDGER_FINISH_QUEUE_30_2026-09-27.md (definition only)
RESULTS_REUSED=Wall cost rules (subscription-first, PAYG-gated, ZERO_COST_ONLY policy, MAX_HEAVY_JOBS=1, paid-window TRUE_IDLE stop, no-busywork/no-reread rules); queue cost-sensitive mode; proof bundle (existing capacity, no paid fallback used)

## Cost/quota record (normative)
REQUIRED: `cost_basis` (enum: SUBSCRIPTION | FREE_CAPACITY | PAYG_AUTHORIZED — exactly one), `estimated_cost` (nullable number + currency; null = UNKNOWN, never 0 unless measured zero), `known_cost` (nullable; filled post-execution from provider accounting, never asserted upfront), `quota_state` (OK | APPROACHING | EXHAUSTED | UNKNOWN per backing account, referenced opaquely — no account identifiers), `stop_or_fallback` (what happens at exhaustion: STOP | DEGRADE_TO_READONLY | PAYG_FALLBACK — the last ONLY with explicit authorization record).
OPTIONAL: provider cost-center reference (opaque), measurement timestamp.
FORBIDDEN: raw payment data (shared with GLEDGER-121); asserted-zero costs without measurement (the "0 EUR" fiction class — UNKNOWN is the honest default); PAYG fallback taken silently.

## Semantics (normative)
- Subscription-first: route to existing subscription/free capacity; PAYG requires an explicit authorization naming task + cap. Absent authorization, exhaustion → STOP (TRUE_IDLE), never fallback.
- Paid/API windows stop when genuinely idle (no token spend on scans, rereads, duplicate analysis, idle research) — idleness is a cost control, not a failure.
- Cost fields are informational: they never enter identity/equivalence (GLEDGER-107) or acceptance (GLEDGER-103). A result is never rejected for its cost fields, and cost never upgrades evidence.
- Heavy-job admission (MAX_HEAVY_JOBS=1/host) is the execution-side cost guard: second heavy job → light-read-only fallback, automatic, no human relay.

MISSING=None (measured-cost plumbing is provider-side accounting, out of Ledger contract scope by design).
BLOCKER=None in-lane.
NEXT_DEPENDENCY=GLEDGER-120 (QUOTA/MONEY/RESOURCE stop reasons reference these states); GLEDGER-130 (COST_GUARD_READY output).
DO_NOT_REPEAT_FINGERPRINT=gledger-117-cost-quota-state-complete

DO_NOT_REPEAT_FINGERPRINT=sha256-19f1d8c0ae8e1b14

DO_NOT_REPEAT_FINGERPRINT=sha256-9ffd2a82b2c43af3
