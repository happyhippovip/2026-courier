# Muse Wall Queue Harvest & Deduplication — 2026-09-27

Status: HARVEST COMPLETE  
Queue Source: `ops/ai/MUSE_WALL_QUEUE_NEXT_2026-09-27.md`  
Total Tasks Evaluated: 34 (MUSE-VERIFY-001 through MUSE-VERIFY-034)  
Ledger State File: `ops/ai/wall_ledger/ledger.jsonl` (82 total entries)

---

## 1. Executive Summary

| Category | Count | Tasks |
| :--- | :---: | :--- |
| **PASS / Confirmed Invariants** | 19 | MUSE-VERIFY-004, 008, 009, 010, 012, 013, 018, 021, 022, 023, 024, 025, 026, 027, 028, 031, 032, 033, 034 |
| **FAIL / Identified Defects** | 15 | MUSE-VERIFY-001, 002, 003, 005, 006, 007, 011, 014, 015, 016, 017, 019, 020, 029, 030 |

---

## 2. Deduplicated Defect Action Packet for Central Writer

### Group A: Verification & Trusted Content Security
1. **Worker-Supplied Hash Authority (MUSE-VERIFY-007, MUSE-VERIFY-030):**
   - Files: `scripts/courier_verifier.py`, `scripts/integration_contract.py`
   - Gap: Verifier derives expected hash from worker artifact dictionary `art.get("expected_sha256")`, and schema allows worker to inject this field.
   - Fix: Decouple expectation; derive strictly from `task["expected_artifacts"]` or `task["expected_sha256"]`.
2. **Verifier Loop Poison Pill (MUSE-VERIFY-029):**
   - File: `scripts/courier_verifier.py` (`run_loop`)
   - Gap: No per-task try/except block. A malformed task crashes the poller and starves all subsequent tasks.
   - Fix: Wrap task processing in `try...except Exception as e:` and submit FAIL verdict or quarantine.
3. **Unverified Result Fingerprint (MUSE-VERIFY-006):**
   - File: `scripts/integration_contract.py` (`validate_durable_result`)
   - Gap: Validates that `result_id` is a non-empty string, but does not re-compute `_canonical_hash(identity)` to prove cryptographic authenticity.
   - Fix: Re-compute and assert `result["result_id"] == f"result-{_canonical_hash(identity)}"`.

### Group B: Idempotency & Replay Protection
4. **Duplicate Match Check Omissions (MUSE-VERIFY-005):**
   - File: `server/app.py` line 367
   - Gap: Compares only `("dispatch_id", "result_id", "status")`, omitting `worker_id` and `attempt_id`.
   - Fix: Include `worker_id`, `attempt_id`, and `artifacts` deep equality in duplicate check.

### Group C: Extended Ledger & Operational Schema Envelopes
5. **Missing Extended Ledger Fields (MUSE-VERIFY-001, 002, 003, 011, 017):**
   - File: `server/app.py`
   - Gap: State dictionary lacks `truth_keys`, `contract_id`, `claim_id`, `queue_generation`, and `context_checkpoint`.
   - Fix: Add optional fields to state schema conforming to `EXTENDED_EXECUTION_LEDGER_SPEC_2026-09-27.md`.
6. **Device-Adaptive Admission & Cost Guards (MUSE-VERIFY-014, 015, 016, 019, 020):**
   - File: `server/app.py`
   - Gap: Missing 8-point admission envelope, `spend_limit_eur` guard, stop reason taxonomy, and `do_not_repeat_registry`.
   - Fix: Integrate capacity governor and budget guard before task dispatch.
