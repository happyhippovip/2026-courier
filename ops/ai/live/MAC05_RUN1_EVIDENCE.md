# MAC05 RUN_1 Evidence Checkpoint — PREPARATION ONLY

Status: PREPARED_NOT_EXECUTED. No process stopped, started, or run.
Execution gate: RUN_1 has NOT passed; physical approval pending
(`docs/proofs/CORE_FREEZE_CLOSEOUT_CHECKLIST.md`: Physical Execution
Approval = pending; `ops/ai/GATE_STATE_CURRENT.md`:
PRE_CODEX_STATE=DURABILITY_PENDING, AUTHORITATIVE_READY=NO).
Per physical law: no RUN_1 execution before READY_FOR_PHYSICAL_RUN=YES,
no RUN_2 before RUN_1 PASS. This file prepares the evidence layout only.

Repo: /Users/user/Downloads/2026-courier, HEAD bd539f18 (detached).

## Evidence slots (all PENDING_EXECUTION)

| # | Slot | Contract | Required evidence at execution |
|---|------|----------|-------------------------------|
| 1 | A once | scripts/run1_physical/RUN1_A_ONCE_PROOF_CONTRACT.md | Single A execution proof, count remains 1 |
| 2 | Result A | scripts/run1_physical/RUN1_RESULT_TEMPLATE.json | Result-A payload conforming to template |
| 3 | Trusted hash | scripts/run1_physical/RUN1_EXPECTED_HASH_CHAIN.md | Expected hash chain, pre-declared values |
| 4 | Server bytes | scripts/run1_physical/RUN1_SERVER_BYTES_PROOF_CONTRACT.md | Server-bytes capture + comparison |
| 5 | Verify | scripts/run1_physical/RUN1_VERIFY_RECONCILE_PROOF_CONTRACT.md | Verify proof (same contract covers reconcile) |
| 6 | Reconcile | scripts/run1_physical/RUN1_VERIFY_RECONCILE_PROOF_CONTRACT.md | Reconcile proof, A-VERIFY-B-zero-relay chain |
| 7 | B auto-start | scripts/run1_physical/RUN1_B_AUTOSTART_PROOF_CONTRACT.md | B automatic-start evidence |
| 8 | relay=0 | scripts/run1_physical/RUN1_ZERO_RELAY_PROOF_CONTRACT.md | Zero-relay proof |
| 9 | No failed execution | scripts/run1_physical/RUN1_FAILED_EXECUTION_GUARD.md | Failed-execution guard, no failed run |

Layout binder: scripts/run1_physical/RUN1_EVIDENCE_LAYOUT.md.
Binding template: scripts/run1_physical/RUN1_PHYSICAL_BINDING_TEMPLATE.sh.
Contract verifier: scripts/run1_physical/verify_proof_contracts.py (not run).

## Resume / next

NEXT_EXACT_ACTION=await READY_FOR_PHYSICAL_RUN=YES + RUN_1 PASS verdict
(MUSE-HNI-13/14 QA lane owns falsifiability/minimal-evidence acceptance);
only then bind FINAL_SHA (MAC_HNI_16, currently
WAITING_FOR_DURABILITY_ON_FINAL_SHA) and execute via scripts/run1_physical/.
No A replay permitted after RUN_1 PASS (RUN_2 contract family MAC_HNI_11..15).

DO_NOT_REPEAT_FINGERPRINT=MAC05_RUN1_EVIDENCE:PREPARED:bd539f18
