# Result for MPREP-03: Contradiction Shortlist

TASK=MPREP-03
STATUS=PASS
RESULTS_REUSED=ops/ai/wall_results/POST200-021_result.md, ops/ai/coordination_reports/FAMILY_01_HARVEST_DELTA_MAC-MEGA-002.md, ops/ai/GOOGLE_PRE_CODEX_GATE_2026-09-27.md, ops/ai/coordination_reports/FAMILY_18_CENTRAL_WRITER_COMPRESSED.md
OUTPUT=Unresolved Contradictions Shortlist for Independent Muse Review:
1. **Worker-Supplied Hash Authority**: `courier_verifier.py:78` trusts worker `art["expected_sha256"]` vs invariant that task specification owns the expected hash (`POST200 Case 1/4`).
2. **Result Schema Boundary**: `integration_contract.py:156` permits `"expected_sha256"` in `result["artifacts"]` schema, allowing worker hash injection (`POST200 Case 4/10`).
3. **Duplicate Match Completeness**: `server/app.py:367` matches duplicate result only on `(dispatch_id, result_id, status)` rather than full 5-tuple `(dispatch_id, result_id, status, worker_id, attempt_id)` and artifact list identity (`POST200 Case 12`).
4. **Artifact Omission Scope**: Empty artifact list rejection is proven, but partial omission of task-declared artifacts fails on base code (`FAMILY_01 Adjudication Note A1`).
5. **Verifier Loop Poison Pill Resilience**: `courier_verifier.py:98` lacks per-task `try...except` handling, allowing a single malformed result to crash the poller (`Gate Matrix Case 9`).
6. **Trailing Whitespace Lints**: `server/app.py` lines 358, 511, 518, 535 and `courier_verifier.py` have trailing whitespace violating `git diff --check` (`Gate Matrix Case 21`).
7. **Dangling GL Evidence Pointers**: Ledger GL002..GL036 reference uncreated `GLxxx_result.md` files; logical spec already captured in `EXTENDED_EXECUTION_LEDGER_SPEC_2026-09-27.md` (`Finding H1`).
MISSING=Zero other contradictions found across 109 ledger tasks and 20 work families.
BLOCKER=Items 1, 2, 3, 5, 6 are blocked on Windows Central Writer 5-file patch.
MUSE_INPUT=Muse review should focus strictly on verifying that Central Writer fix resolves contradictions 1..6 on FINAL_SHA.
DO_NOT_REPEAT_FINGERPRINT=mprep-03-contradiction-shortlist-v1

DO_NOT_REPEAT_FINGERPRINT=sha256-056ff048d0ee798f
