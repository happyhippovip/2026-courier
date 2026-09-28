# GLEDGER-112 Result — Queue Generation Contract

TASK_ID=GLEDGER-112
STATUS=PROVEN (by reused durable evidence; no new source reads)
HOST=MAC
PROVIDER=GOOGLE
INPUTS_READ=ops/ai/LEDGER_FINISH_QUEUE_30_2026-09-27.md (definition only)
RESULTS_REUSED=WALL_QUEUE_CURRENT generations (V2 → V4_OVR observed live); ledger fingerprints + do-not-repeat convention; candidate-b-1/b-2 SHAs; POST200-021 fingerprint; GLEDGER-101..111 fingerprints this run; TRUE_IDLE semantics

## generation_id (normative)
Format: `YYYY-MM-DD.V<n>[_<suffix>]` (observed: 2026-09-27.V2, 2026-09-27.V4_OVR). A generation binds: {queue source file, packet set, canonical base SHA, result fingerprint set}. Every ledger entry SHOULD carry the generation it was reconciled under (observed: fingerprints present; explicit generation field on entries is recommended for GLEDGER-129 — flagged, not invented here).

## Truth/result fingerprints (normative)
- Truth fingerprint: canonical base SHA (candidate-b-1 4c1e24cc) + coordination tip at read time. Evidence evaluated against one truth is not portable to another without re-binding (GLEDGER-114 owns the stale decision table).
- Result fingerprint: `do_not_repeat` string per packet (observed convention: short stable slugs, e.g. gledger-101-entity-chain-complete). Fingerprint equality between a prior result and a new claim on the same task+inputs → reuse, do not redo (RESULT_REUSE_FIRST with teeth).

## Supersession (normative)
A newer generation supersedes an older one ONLY by explicit pointer (queue file's QUEUE_SOURCE + GENERATION fields), never by recency inference. Superseded generations remain readable (audit trail); their un-reconciled claims do NOT auto-migrate — each live claim is either re-issued under the new generation or released. Completed (RECONCILED) results carry forward by fingerprint match without re-execution.

## Migration + no-session-reset (normative)
`/clear`, fresh session, or account change MUST NOT duplicate completed work: continuity key = (generation_id, task_id, do_not_repeat fingerprint) resolved against the ledger, never chat memory (SESSION_MEMORY_IS_CACHE). A new session re-harvests the ledger first; fingerprint hit → adopt result; miss → execute. Session reset is therefore a no-op for completed tasks by construction.

MISSING=Explicit per-entry generation_id field in current ledger.jsonl lines (convention recommended; backfill is writer/owner decision, not this task).
BLOCKER=None in-lane.
NEXT_DEPENDENCY=GLEDGER-113 (fingerprint composition); GLEDGER-114 (stale binding); GLEDGER-119 (continuity uses migration rule).
DO_NOT_REPEAT_FINGERPRINT=gledger-112-generation-contract-complete

DO_NOT_REPEAT_FINGERPRINT=sha256-bb52a4d82fd1d083

DO_NOT_REPEAT_FINGERPRINT=sha256-512cf83fbb05e803
