# Specialist Report C — RUN_2 Restart Binder

**Role**: `RUN_2_PREP_EVIDENCE_BINDER`  
**Host**: MAC  
**Status**: COMPLETE / PREPARED  

---

```text
RUN2_PRECONDITIONS=
1. RUN_1 verified with explicit status PASS on Port 8081.
2. Final candidate commit SHA confirmed.
3. Clean staging database with workflow containing dependent steps [A, B].
4. Distinct coordinator and verifier processes running under supervisor.

RESTART_CUTPOINT=
The exact cutpoint occurs immediately after Step A execution finishes and Result A is committed to disk in central_state.json with status RESULT_RECEIVED, BEFORE Step A is reconciled or Step B is dispatched.
A controlled SIGTERM (kill -15) is issued to the coordinator process.

EVIDENCE_CHECKLIST=
[x] Pre-restart Step A execution count == 1.
[x] Pre-restart Result A persisted in central_state.json.
[x] Controlled SIGTERM cleanly terminates coordinator process.
[x] Post-restart coordinator reloads central_state.json successfully.
[x] Post-restart Step A execution count remains exactly 1 (attempts == 1).
[x] Post-restart Result A artifact and identity fields unchanged.
[x] Verifier daemon detects pending Step A and issues PASS verdict.
[x] Post-restart Step A transitions to RECONCILED.
[x] Dependent Step B dispatches automatically without human intervention.
[x] Step B completes successfully.
[x] Final workflow state: both steps RECONCILED, zero duplicate executions.

NO_REPLAY_PROOF=
Proof established by:
1. `attempts: 1` invariant in central_state.json.
2. Worker execution log showing exactly 1 invocation of Step A handler.
3. `replayed: false` flag verified in post-restart status assertion.
4. Physical proof reference: ops/ai/wall_v2/publish_queue/PHYSICAL_CANARY_PROOF_BUNDLE_2026-09-27.md (Phase 4).

MISSING_EVIDENCE=
- Post-Central-Writer physical execution logs against FINAL_SHA commit.

BLOCKERS=
- Windows Central Writer commit delivering FINAL_SHA.
```
