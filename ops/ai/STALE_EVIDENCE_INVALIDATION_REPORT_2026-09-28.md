# Courier Stale Evidence Invalidation Report — 2026-09-28

**Audit Authority**: GOOGLE_CLI / MUSE (Read-Only QA Parity)  
**Status**: 100% COMPLETE & DURABLE  
**Scope**: Invalidation Audit of Historical Evidence Surfaces  
**Reference Pointers**: [`ops/ai/WALL_SYSTEM.md`](file:///Users/user/Downloads/2026-courier/ops/ai/WALL_SYSTEM.md), [`ops/ai/RETURNED_RESULT_POLICY.md`](file:///Users/user/Downloads/2026-courier/ops/ai/RETURNED_RESULT_POLICY.md)  

---

## 1. Executive Summary

This report identifies, catalogs, and explicitly marks obsolete or superseded evidence to prevent stale historical artifacts from silently supporting a PASS verdict on the final candidate.

Per the durable rule: **Evidence is not deleted; it is explicitly marked STALE / SUPERSEDED so it cannot contaminate active gates.**

---

## 2. Invalidation Ledger

### Item 1: Unisolated Port 8080 Physical Canary
- **EVIDENCE_ID**: `PHYS-CANARY-8080-PRE-SPLIT`
- **BOUND_TO**: Old runtime listening on Port 8080 prior to port split architecture.
- **CURRENT_TRUTH**: Staging port `8081` is the only authorized isolated staging environment; port 8080 is reserved for production.
- **STALE**: `YES`
- **WHY**: Unisolated runs on port 8080 risk race conditions with live services and do not verify staging isolation.
- **INVALIDATES**: Any historical claim of physical Canary completion bound to port 8080.
- **EXACT_RETEST_TRIGGER**: Execution on Port 8081 via [`PHYSICAL_CANARY_PROOF_BUNDLE_2026-09-27.md`](file:///Users/user/Downloads/2026-courier/ops/ai/wall_v2/publish_queue/PHYSICAL_CANARY_PROOF_BUNDLE_2026-09-27.md).

### Item 2: Candidate-b-2 Branch Results
- **EVIDENCE_ID**: `CANDIDATE-B-2-RESULTS`
- **BOUND_TO**: Commit `83940de3d7d33776a712e7506aa76726d16f8587` (`origin/candidate-b-2`).
- **CURRENT_TRUTH**: Canonical truth explicitly rejected `candidate-b-2` in favor of `candidate-b-1` (`4c1e24cc`).
- **STALE**: `YES`
- **WHY**: Candidate lineage rejected due to architectural drift and unverified locking mechanisms.
- **INVALIDATES**: All test passes, benchmark metrics, and attestations stemming from candidate-b-2.
- **EXACT_RETEST_TRIGGER**: Must test strictly on candidate-b-1 lineage (`4c1e24cc` + 5 files).

### Item 3: Volatile Fallback Result IDs
- **EVIDENCE_ID**: `YOLO-VOLATILE-RESULT-ID`
- **BOUND_TO**: Pre-cannon fallback result binding prior to commit `8eadc254`.
- **CURRENT_TRUTH**: Deterministic result ID binding `res-{task_id}-{attempt_id}` pinned in `scripts/integration_contract.py`.
- **STALE**: `YES`
- **WHY**: Volatile or randomized result IDs allow duplicate generation and corrupt deduplication logic.
- **INVALIDATES**: Any historic result relying on unpinned result IDs.
- **EXACT_RETEST_TRIGGER**: Automated identity pin `test_result_identity_binding.py`.

### Item 4: Open-Ended Muse Research Artifacts
- **EVIDENCE_ID**: `PRE-0200-MUSE-UNBOUND-TASKS`
- **BOUND_TO**: Unconstrained prompt queries prior to Muse Preflight Pack (`MPREP-01..10`).
- **CURRENT_TRUTH**: Exactly 4 bounded QA tasks (`MUSE-01..04`) in [`ops/ai/mprep_results/MUSE_READY_TASK_BANK.md`](file:///Users/user/Downloads/2026-courier/ops/ai/mprep_results/MUSE_READY_TASK_BANK.md).
- **STALE**: `YES`
- **WHY**: Open-ended research prompts cause token waste and lack deterministic done criteria.
- **INVALIDATES**: Any speculative findings generated without a durable task packet.
- **EXACT_RETEST_TRIGGER**: Execution of strictly `MUSE-01..04` at 02:00.

### Item 5: Base 4c1e24cc 12-Case Matrix (Historical Baseline)
- **EVIDENCE_ID**: `BASE-4C1E24CC-12-CASE-BASELINE`
- **BOUND_TO**: Unpatched base commit `4c1e24ccc522042af826bc4c2b595daf85d097f9`.
- **CURRENT_TRUTH**: Baseline is 5 PASS, 7 FAIL.
- **STALE**: `NO (ACCURATE BASELINE)`, but **WILL BE SUPERSEDED** upon Central Writer patch commit.
- **WHY**: Serves as the accurate diagnostic baseline proving the 4 causal defects exist on base.
- **INVALIDATES**: Cannot be used as candidate final proof.
- **EXACT_RETEST_TRIGGER**: Commit of `FINAL_SHA` triggers retest to establish 12/12 PASS.

---

## 3. Invalidation Summary

All 4 stale evidence artifacts are classified as `SUPERSEDED_AND_QUARANTINED`. They cannot silently satisfy any gate in [`ops/ai/GOOGLE_PRE_CODEX_GATE_2026-09-27.md`](file:///Users/user/Downloads/2026-courier/ops/ai/GOOGLE_PRE_CODEX_GATE_2026-09-27.md) or Core Freeze.
