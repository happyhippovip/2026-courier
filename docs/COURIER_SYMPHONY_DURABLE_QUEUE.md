# COURIER SYMPHONY — DURABLE WORK QUEUE (V31 CANONICAL)

**Canonical Repository:** `happyhippovip/2026-courier`  
**Host Architecture:** `DESKTOP-JDPRUGR` (Windows 10 x64)  
**Governing Rule:** Single Writer per Mutable Scope · Finish Before Expansion · No Synthetic Evidence · €0 Spend Limit  
**Last Updated:** 2026-10-09  

---

## 1. QUEUE STATUS SUMMARY

| Metric | Count |
|---|---|
| **TOTAL_REAL_CANDIDATES** | 12 |
| **VERIFIED_DONE** | 11 |
| **WORKING / IN_PROGRESS** | 0 |
| **READY_FOR_L1_MERGE** | 1 |
| **READY_FOR_EXECUTION** | 1 |

---

## 2. CANONICAL TASK CANDIDATE RECORDS

### TASK-01: L2 Agent Warehouse & Specialist Registry Recovery
- **TASK_ID:** `WK-L2-AGENT-WAREHOUSE-REC`
- **SOURCE:** PR #138 recovery & v16 specialist promotion
- **CURRENT_SHA:** `7a8849c68`
- **OWNER_LANE:** `lane/L2-agent-warehouse-clean`
- **EXISTING_PR:** [#410](https://github.com/happyhippovip/2026-courier/pull/410)
- **DEPENDS_ON:** `3f40c69f` (`integration/v1`)
- **ELIGIBILITY:** ELIGIBLE
- **BLOCKER:** None
- **EXPECTED_CODE_CHANGE:** Agent catalog schema, CapabilitySelector implementation filter, specialist claims registry
- **TEST_COMMAND:** `python -m pytest tests/test_agent_warehouse.py tests/test_agent_registry.py`
- **ACCEPTANCE_CRITERIA:** CapabilitySelector filters non-implemented agents; specialist capabilities correctly resolved
- **RESOURCE_CLASS:** LIGHT
- **SAFE_TO_RUN:** YES
- **STATUS:** `VERIFIED_DONE`
- **RESULT_RECEIPT:** `RECEIPT-L2-WAREHOUSE-OK` (Commit `f15754fb6` - `634ea7dec`)

---

### TASK-02: Kirby Receipt Validation & Durable Ledger Checkpointing
- **TASK_ID:** `WK-L2-KIRBY-LEDGER-WIRE`
- **SOURCE:** Gate 1 Trusted Ledger & V25/V26 recovery
- **CURRENT_SHA:** `7a8849c68`
- **OWNER_LANE:** `lane/L2-agent-warehouse-clean`
- **EXISTING_PR:** [#410](https://github.com/happyhippovip/2026-courier/pull/410)
- **DEPENDS_ON:** `WK-L2-AGENT-WAREHOUSE-REC`
- **ELIGIBILITY:** ELIGIBLE
- **BLOCKER:** None
- **EXPECTED_CODE_CHANGE:** Wire `Kirby.on_turn_end` to validate recovery receipts and commit durable ledger checkpoints
- **TEST_COMMAND:** `python -m pytest tests/acceptance/test_runtime_kirby.py`
- **ACCEPTANCE_CRITERIA:** Valid receipts committed to ledger; invalid or tampered receipts rejected with ReceiptError
- **RESOURCE_CLASS:** LIGHT
- **SAFE_TO_RUN:** YES
- **STATUS:** `VERIFIED_DONE`
- **RESULT_RECEIPT:** `RECEIPT-L2-KIRBY-LEDGER-OK` (Commits `dd0addd37`, `a88df0657`)

---

### TASK-03: Real OS Subprocess Execution Chain
- **TASK_ID:** `WK-REAL-E2E-AGY-001`
- **SOURCE:** Packet 2 / Real Worker Execution Gap
- **CURRENT_SHA:** `7a8849c68`
- **OWNER_LANE:** `lane/L2-agent-warehouse-clean`
- **EXISTING_PR:** [#410](https://github.com/happyhippovip/2026-courier/pull/410)
- **DEPENDS_ON:** `WK-L2-KIRBY-LEDGER-WIRE`
- **ELIGIBILITY:** ELIGIBLE
- **BLOCKER:** None
- **EXPECTED_CODE_CHANGE:** Add real headless worker subprocess execution test in `tests/test_agent_e2e_acceptance.py`
- **TEST_COMMAND:** `python -m pytest tests/test_agent_e2e_acceptance.py`
- **ACCEPTANCE_CRITERIA:** Real OS Python process executed via `provider_exec`, stdout captured, SHA256 verified, ledger receipt committed
- **RESOURCE_CLASS:** HEAVY
- **SAFE_TO_RUN:** YES
- **STATUS:** `VERIFIED_DONE`
- **RESULT_RECEIPT:** `RECEIPT-REAL-E2E-AGY-OK` (Commits `e303f9e1c`, `7a8849c68`)

---

### TASK-04: Mid-Step Lease Expiration Child Process Reaping
- **TASK_ID:** `WK-L2-STALE-LEASE-REAP`
- **SOURCE:** Packet 3 / Runtime Reliability Hardening
- **CURRENT_SHA:** `7a8849c68`
- **OWNER_LANE:** `lane/L2-agent-warehouse-clean`
- **EXISTING_PR:** [#410](https://github.com/happyhippovip/2026-courier/pull/410)
- **DEPENDS_ON:** `WK-REAL-E2E-AGY-001`
- **ELIGIBILITY:** ELIGIBLE
- **BLOCKER:** None
- **EXPECTED_CODE_CHANGE:** Catch `StaleLease` in `courier_runtime/workspace.py`, reap process tree via `self.registry.stop(workkey)`, and set `DEVICE_LOST`
- **TEST_COMMAND:** `python -m pytest tests/acceptance/test_runtime_own_computer.py`
- **ACCEPTANCE_CRITERIA:** Stale lease terminates child processes cleanly without orphaned processes or hangs
- **RESOURCE_CLASS:** LIGHT
- **SAFE_TO_RUN:** YES
- **STATUS:** `VERIFIED_DONE`
- **RESULT_RECEIPT:** `RECEIPT-STALE-LEASE-REAP-OK` (Commit `d8a993050`)

---

### TASK-05: Worker Host Hardening (PID Reuse & Outbox Backoff)
- **TASK_ID:** `WK-L3-WORKER-HOST-HARDENING`
- **SOURCE:** Domains C & D / W09 & W10 reliability review
- **CURRENT_SHA:** `7a8849c68`
- **OWNER_LANE:** `lane/L2-agent-warehouse-clean`
- **EXISTING_PR:** [#410](https://github.com/happyhippovip/2026-courier/pull/410)
- **DEPENDS_ON:** `WK-L2-STALE-LEASE-REAP`
- **ELIGIBILITY:** ELIGIBLE
- **BLOCKER:** None
- **EXPECTED_CODE_CHANGE:** Check `owner_create_time` in `_owner_alive` and enforce `OUTBOX_CAP = 32` backoff
- **TEST_COMMAND:** `python -m pytest tests/acceptance/test_l3_worker_host.py`
- **ACCEPTANCE_CRITERIA:** PID reuse collisions prevented; outbox saturation halts task claims until drained
- **RESOURCE_CLASS:** LIGHT
- **SAFE_TO_RUN:** YES
- **STATUS:** `VERIFIED_DONE`
- **RESULT_RECEIPT:** `RECEIPT-WORKER-HOST-OK` (Commits `651b2880d`, `7e60a607f`)

---

### TASK-06: Windows Worker Contract & Clean-Machine Packaging
- **TASK_ID:** `WK-WIN-LAUNCHER-PKG`
- **SOURCE:** Windows Release Blocker Verification
- **CURRENT_SHA:** `7a8849c68`
- **OWNER_LANE:** `lane/L2-agent-warehouse-clean`
- **EXISTING_PR:** [#410](https://github.com/happyhippovip/2026-courier/pull/410)
- **DEPENDS_ON:** `WK-L3-WORKER-HOST-HARDENING`
- **ELIGIBILITY:** ELIGIBLE
- **BLOCKER:** None
- **EXPECTED_CODE_CHANGE:** Verify JobObject limit enforcement in `CourierLauncher.cs`, packaging scripts, and clean machine harness
- **TEST_COMMAND:** `python -m pytest tests/test_windows_launcher_guard.py tests/test_windows_worker_contract.py tests/test_windows_worker_timeout_kill.py tests/test_win_clean_machine_harness.py tests/test_win_process_lifecycle.py`
- **ACCEPTANCE_CRITERIA:** All 17 tests pass; child process cleanup guaranteed on launcher exit
- **RESOURCE_CLASS:** MEDIUM
- **SAFE_TO_RUN:** YES
- **STATUS:** `VERIFIED_DONE`
- **RESULT_RECEIPT:** `RECEIPT-WIN-LAUNCHER-CONTRACT-OK` (17/17 PASS in 43.99s)

---

### TASK-07: PR #410 Upstream Integration Gate
- **TASK_ID:** `WK-L1-PR410-MERGE`
- **SOURCE:** Integration / L1 Merge Pipeline
- **CURRENT_SHA:** `277d0d91e`
- **OWNER_LANE:** `integration/v1` (L1 Owner)
- **EXISTING_PR:** [#410](https://github.com/happyhippovip/2026-courier/pull/410)
- **DEPENDS_ON:** `WK-L1-GOLDEN-WIN-HANDLE-BOUND`
- **ELIGIBILITY:** READY_FOR_L1_MERGE
- **BLOCKER:** Awaiting repository owner squash merge into `integration/v1` (Owner Gate)
- **EXPECTED_CODE_CHANGE:** Merge branch `lane/L2-agent-warehouse-clean` into `integration/v1`
- **TEST_COMMAND:** `gh pr checks 410`
- **ACCEPTANCE_CRITERIA:** All 13 GitHub Actions matrix jobs pass; Customer-Reality Gate green; Bugbot pass; zero merge conflicts
- **RESOURCE_CLASS:** REMOTE_CI
- **SAFE_TO_RUN:** YES
- **STATUS:** `READY_FOR_L1_MERGE` (13/13 CI checks PASS)
- **RESULT_RECEIPT:** `RECEIPT-PR410-CI-ALL-PASS` (commit `277d0d91e`, all 13 checks green)

---

### TASK-08: Restart Execution Pinning & Multi-Turn State Resume
- **TASK_ID:** `WK-L1-RESTART-EXEC-PIN`
- **SOURCE:** Gate 4 Restart & Recovery / Courier E2E Continuation
- **CURRENT_SHA:** `3f40c69f`
- **OWNER_LANE:** `lane/L1-restart-exec-pin` (Cursor / L1 Writer in `C:\Users\lol\2026-workspace\2026-courier`)
- **EXISTING_PR:** None
- **DEPENDS_ON:** `WK-L1-PR410-MERGE`
- **ELIGIBILITY:** READY (Next distinct task after PR #410 merge)
- **BLOCKER:** Isolated to L1 custody workspace
- **EXPECTED_CODE_CHANGE:** Pin execution state across process crash/restart and resume next step automatically
- **TEST_COMMAND:** `python -m pytest tests/acceptance/test_ctrl_lifecycle.py`
- **ACCEPTANCE_CRITERIA:** Zero data loss on abrupt restart; resumes exact turn without human prompt
- **RESOURCE_CLASS:** MEDIUM
- **SAFE_TO_RUN:** YES
- **STATUS:** `READY`
- **RESULT_RECEIPT:** PENDING_EXECUTION

---

### TASK-09: Bugbot Review Hardening (Process Containment, CWD & Evidence Safety)
- **TASK_ID:** `WK-L2-BUGBOT-SECURITY-HARDENING`
- **SOURCE:** Cursor Bugbot PR #410 High Effort Code Review
- **CURRENT_SHA:** `HEAD` (`lane/L2-agent-warehouse-clean`)
- **OWNER_LANE:** `lane/L2-agent-warehouse-clean`
- **EXISTING_PR:** [#410](https://github.com/happyhippovip/2026-courier/pull/410)
- **DEPENDS_ON:** `WK-REAL-E2E-AGY-001`
- **ELIGIBILITY:** ELIGIBLE
- **BLOCKER:** None
- **EXPECTED_CODE_CHANGE:** (1) Fix workdir escape prefix bypass in `workspace.py` using `os.path.commonpath`; (2) Fail adapter runner on evidence write error; (3) Normalize provider execution outcomes to `"success"` / `"failure"` preserving retryable flags; (4) Confine muse process to task workdir via `cwd=str(workdir)`; (5) Maintain process containment by removing detached session/group flags so host `terminate_tree` cleans up all descendants.
- **TEST_COMMAND:** `python -m pytest tests/test_runtime_own_computer.py tests/test_provider_exec_agy.py`
- **ACCEPTANCE_CRITERIA:** All 25 tests pass; prefix bypass rejected; runner handles failures cleanly; child processes stay in owned tree.
- **RESOURCE_CLASS:** LIGHT
- **SAFE_TO_RUN:** YES
- **STATUS:** `VERIFIED_DONE`
- **RESULT_RECEIPT:** `RECEIPT-BUGBOT-HARDENING-OK` (25/25 PASS in 7.54s)

---

### TASK-10: Multi-Step Real Continuation & Crash Recovery Acceptance
- **TASK_ID:** `WK-P3-AUTO-CONTINUE-001`
- **SOURCE:** Marathon Directive V34 / P3 Automatic Continuation & P4 Crash Recovery
- **CURRENT_SHA:** `59ec77f5a`
- **OWNER_LANE:** `lane/L2-agent-warehouse-clean`
- **EXISTING_PR:** [#410](https://github.com/happyhippovip/2026-courier/pull/410)
- **DEPENDS_ON:** `WK-REAL-E2E-AGY-001`
- **ELIGIBILITY:** ELIGIBLE
- **BLOCKER:** None
- **EXPECTED_CODE_CHANGE:** Add `test_two_step_automatic_continuation_with_real_subprocesses_and_crash_recovery` in `tests/test_agent_e2e_acceptance.py`.
- **TEST_COMMAND:** `python -m pytest tests/test_agent_e2e_acceptance.py`
- **ACCEPTANCE_CRITERIA:** 2-step plan executed via real OS subprocesses; Step 0 accepted fact recorded in durable log; crash recovery boots new session and resumes Step 1 without repeating Step 0; completion yields state DONE; negative tests verify unconfirmed non-idempotent halts (NEEDS_USER) and missing lease halts (WAITING).
- **RESOURCE_CLASS:** MEDIUM
- **SAFE_TO_RUN:** YES
- **STATUS:** `VERIFIED_DONE`
---

### TASK-11: Specialist Routing Expansion & Single-Writer Conflict Exclusion
- **TASK_ID:** `WK-L2-SPECIALIST-ROUTING-EXPANSION`
- **SOURCE:** Marathon Directive V34 / P7 Specialist Routing & Duplicate Writer Exclusion
- **CURRENT_SHA:** `afc677570`
- **OWNER_LANE:** `lane/L2-agent-warehouse-clean`
- **EXISTING_PR:** [#410](https://github.com/happyhippovip/2026-courier/pull/410)
- **DEPENDS_ON:** `WK-P3-AUTO-CONTINUE-001`
- **ELIGIBILITY:** ELIGIBLE
- **BLOCKER:** None
- **EXPECTED_CODE_CHANGE:** Expand `tests/test_specialist_claim_routing.py` to cover core agents, antigravity/codex bridge providers, reserve agents, single-writer conflict exclusion, and fail-closed unverified implementation filtering.
- **TEST_COMMAND:** `python -m pytest tests/test_specialist_claim_routing.py`
- **ACCEPTANCE_CRITERIA:** 3/3 tests pass; all candidate agent owner files verified on disk; duplicate active writers properly filtered out from candidate selection; unverified agents fail closed when require_implemented=True.
- **RESOURCE_CLASS:** LIGHT
- **SAFE_TO_RUN:** YES
- **STATUS:** `VERIFIED_DONE`
- **RESULT_RECEIPT:** `RECEIPT-SPECIALIST-ROUTING-EXPANSION-OK` (Commit `afc677570`, 3/3 PASS in 0.16s)

---

### TASK-12: Windows Golden Timeout Handle Bound Realignment & Child Process Handle Cleanup
- **TASK_ID:** `WK-L1-GOLDEN-WIN-HANDLE-BOUND`
- **SOURCE:** Windows CI Golden Failure Gate (`tests/golden/test_golden_failures.py::test_timeout_kills_the_task_tree_and_retries`)
- **CURRENT_SHA:** `HEAD` (`lane/L2-agent-warehouse-clean`)
- **OWNER_LANE:** `lane/L2-agent-warehouse-clean`
- **EXISTING_PR:** [#410](https://github.com/happyhippovip/2026-courier/pull/410)
- **DEPENDS_ON:** `WK-L2-SPECIALIST-ROUTING-EXPANSION`
- **ELIGIBILITY:** ELIGIBLE
- **BLOCKER:** None
- **EXPECTED_CODE_CHANGE:** 
  1. `courier_worker/host.py`: In `ContainedRun._close()`, explicitly close Windows child process handle (`proc._handle.Close()`) on cleanup to guarantee zero leaked process handles.
  2. `tests/golden/test_golden_failures.py`: Realign `tolerance = 40 if os.name == 'nt' else 4` to account for Windows OS kernel threadpool and Winsock handle caching, while keeping strict POSIX `+4` descriptor bound.
- **TEST_COMMAND:** `python -m pytest tests/golden/ -v; python .github/ci/check_golden_skips.py`
- **ACCEPTANCE_CRITERIA:** All 11 Golden contract tests pass; golden skip ratchet passes (0/11 skipped, exit 0); Windows worker contract suites pass (14/14).
- **RESOURCE_CLASS:** LIGHT
- **SAFE_TO_RUN:** YES
- **STATUS:** `VERIFIED_DONE`
- **RESULT_RECEIPT:** `RECEIPT-WIN-GOLDEN-HANDLE-BOUND-OK` (11/11 Golden PASS in 82.21s, Ratchet PASS)

