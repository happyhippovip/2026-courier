# MUSE AUTONOMY SHARD 21 — Correlation / Identity

SHARD=21
STATUS=SHARD_COMPLETE (4 fresh subcases + 1 duplicate-skip, 1 doc-defect minor)
CLAIM.c2=elm-triton / HOST=MAC / 2026-09-28
MODE=READ_ONLY_C2, 0 source edits, 0 runs, 0 ledger. CODEX_HIGH_RESULT_CURRENT.md
absent (phase recheck this run) → autonomy shards continue.
result_id multi-authority = banned-known (cited only, NOT re-reported).

## Subcases
- C1 vocabulary: execution_id + workflow_id have ZERO occurrences in server/,
  integration_contract.py, artifact_store.py (bounded grep, empty). Of the
  shard's 5 IDs only task_id/attempt_id/result_id (+dispatch_id/run_id) exist
  in code; goal_id ≈ workflow scope and attempt+dispatch ≈ execution is
  nowhere documented. → EVIDENCE_DOC_DEFECT (minor, doc-only: 2/5 shard names
  unmappable from code alone).
- C2 planner goal_id: submit planner branch sets "goal_id": goal_id on every
  appended step (verified this run) — the feared planner-path gap does not
  exist; task_result's task["goal_id"] lookup is safe for planner goals.
  → DISPROVEN.
- C3 mint chain (single-writer, ordered): claim mints attempt_id
  task:attempt:N (server/app.py:351) + dispatch uuid4 (:352), run_id/result_id
  None (:353-354) until observed; contract requires observed run_id
  (scripts/integration_contract.py:80) and equality-binds goal/task/attempt/
  dispatch/worker (:68-74). task→attempt→dispatch→run→result strictly ordered,
  one minter. → NO_ISSUE.
- C4 resend binding: intake equality checks (contract :72-74) admit only
  identical attempt/dispatch — cross-attempt replay cannot bind (complements
  F1-writeups without repeating them). → NO_ISSUE.
- result_id authority schemes → DUPLICATE_SKIP (banned-known triple-authority,
  not re-examined).

SUBCASES_DONE=C1,C2,C3,C4 (+result_id DUPLICATE_SKIP)
CONFIRMED_SOURCE_DEFECTS=(none)
EVIDENCE_GAPS=C1 (ID-vocabulary mapping doc, minor)
DISPROVEN=C2 (planner goal_id gap)
FIX_PACKETS=(none)
NEXT_OWNER=(none — doc-only gap, no code owner needed; optional central-writer footnote)
DO_NOT_REPEAT=muse-autonomy-shard-21-01
