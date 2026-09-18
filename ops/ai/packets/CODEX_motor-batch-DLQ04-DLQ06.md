# CODEX REVIEW PACKET — motor batch DLQ-04 fix + DLQ-06 tripwire (COMPLETE)

CURRENT_HEAD=ceba1fe0085cf4c2b02d9689df2731a5c5364779
COMMITS_UNDER_REVIEW=
- ceba1fe0 fix(motor): drain loop double submission and dependent task race (DLQ-04)

INVARIANTS=
1. --once exits only after futures settle OR bounded drain timeout, independent
   of iteration count.
2. A non-empty done_edges set forces loop continuation (finished tasks unblock
   dependents; frontier must be recomputed, not exited).
3. Concurrent ledger readers must not crash writers (DLQ-06, OPEN — tripwire
   test pins the defect, fix pending Google/Windows).

DIFF_SCOPE=scripts/courier_continue.py main(): The loop over done_edges now explicitly calls `continue` if any edges finished, forcing a re-evaluation of `check_freshness` and `safe_executable_tasks`. This prevents the "double submission" bug where completed tasks were deleted from `running_tasks` but immediately re-submitted by the still-stale `safe_executable_tasks` dictionary later in the same loop iteration. tests/test_motor_dlq04_adversarial.py was added to prove correct dependent-task unblocking.

EXACT_FILES=scripts/courier_continue.py, tests/test_motor_dlq04_adversarial.py
EXACT_FUNCTIONS=main()

REPRODUCERS=
- DLQ-04: python3 -m pytest tests/test_motor_dlq04_adversarial.py -q (verifies the race and double-submission fixes)

T2_RESULTS=tests/test_courier_continue.py and tests/test_motor_dlq04_adversarial.py passed.
T3_RESULTS=Adversarial testing added for dependent task unblocking, avoiding the early exit issue.

KNOWN_ATTACKS=
- Double Submission Attack: Submitting the same task multiple times concurrently by omitting `continue` after clearing from `running_tasks`.
- Unproven Ledger Resets: Missing `has_physical_proof` logic causing the mock test ledger to be silently wiped by `update_ledger` on the first iteration, obscuring actual motor behavior.

FILES_TO_READ (bounded)=
- scripts/courier_continue.py:530-580
- tests/test_motor_dlq04_adversarial.py

QUESTIONS_TO_ANSWER=
1. Does the `continue` completely resolve the starvation of dependent tasks when `--once` is used?
2. Are there other side effects in the `while True` loop that might be skipped by the early `continue`?

EXPECTED_FAILURE_MODE=If the double submission bug survives: tests fail via executor exhaustion or mock_iters limit due to rapidly submitting the same task repeatedly without refreshing the ledger.

CODEX_READY=YES 
PHYSICAL_PENDING=DLQ-06 Windows proof still outstanding (tripwire only).
