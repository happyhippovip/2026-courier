# Google Pre-Codex Gate — 2026-09-27

Status: ACTIVE STOP CONDITION

Use existing queues:
- ops/ai/WALL_BUILD_QUEUE_V1.md
- ops/ai/GOOGLE_WINDOWS_NIGHT_QUEUE_50_2026-09-27.md

Do not create new speculative work after those queues are exhausted.

PRE_CODEX_READY=YES only when all are true:

1. FINAL_SHA is known.
2. FINAL_SHA is based on candidate-b-1 @ 4c1e24ccc522042af826bc4c2b595daf85d097f9.
3. Exact changed-file scope contains only:
   - scripts/courier_verifier.py
   - scripts/integration_contract.py
   - tests/test_artifact_upload_flow.py
   - server/app.py
   - tests/test_p3_server_idempotency.py
4. The 12 required acceptance cases are mapped against FINAL_SHA.
5. Required targeted tests were actually executed against FINAL_SHA.
6. SKIPPED_COUNT=0 for required targeted tests.
7. git diff --check for the final delta is clean.
8. No stale older-SHA PASS is reused as final evidence.
9. No known unresolved causal P0 blocker remains.
10. A compact pre-Codex handoff exists.
11. FINAL_SHA is durably resolvable from a canonical remote ref/commit or explicitly referenced durable candidate bundle; a SHA visible only in one local session is DURABILITY_PENDING, not cross-host PRE_CODEX_READY.

Required handoff:

PRE_CODEX_READY=
FINAL_SHA=
BASE_SHA=
EXACT_CHANGED_FILES=
TWELVE_CASE_MATRIX_REF=
TARGETED_TEST_COMMANDS=
TARGETED_TEST_RESULTS=
SKIPPED_COUNT=
DIFF_CHECK=
KNOWN_BLOCKERS=
NEXT=

If PRE_CODEX_READY=YES:
NEXT=CODEX_HIGH_ONCE

If FINAL_SHA changes:
invalidate only candidate-sensitive evidence and rerun the exact affected final-gate checks.
Do not restart all completed queue work.


COST-SAFE RESULT REUSE:
Use ops/ai/COST_SAFE_GATE_TRANSITION_POLICY_2026-09-28.md. Same gate fingerprint is validated once. New windows/providers reuse the durable gate result rather than re-running the gate.
