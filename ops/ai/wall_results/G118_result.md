TASK_ID=G118
STATUS=PROVEN
INPUTS_READ=ops/ai/coordination_reports/FAMILY_07_RESTART_MATRIX_A4.md, tests/test_p3_server_idempotency.py:84-90
RESULTS_REUSED=Scenario 8: Identical replay acknowledged idempotently with HTTP 200 and ACK_DUPLICATE; attempt count and state remain unmodified
NEW_EVIDENCE=Central Writer fix expands match tuple to include worker_id and attempt_id (P0 Defect 3).
MISSING_EVIDENCE=Windows Central Writer commit delivering expanded duplicate tuple
BLOCKER=AWAITING_WINDOWS_CENTRAL_WRITER_FINAL_SHA
CRITICAL_PATH_IMPACT=RESTART_SCENARIO_8_PROVEN
NEXT_DEPENDENCY=G119
DO_NOT_REPEAT_FINGERPRINT=G118_IDENTICAL_DUPLICATE_COVERAGE_PROVEN

DO_NOT_REPEAT_FINGERPRINT=sha256-73354fb3c2a7ecc4

DO_NOT_REPEAT_FINGERPRINT=sha256-7717692998950548
