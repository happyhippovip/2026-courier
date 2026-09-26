# Courier Canary Convergence Packet — 2026-09-26

Status: Current working checkpoint after Opus physical-plan review and Codex candidate-red-team attempt.

## Current target

Physical single-slot proof:

`TASK A -> real result -> deterministic verification -> reconcile -> TASK B starts automatically`

Required:

`HUMAN_RELAY_A_TO_B = 0`

Then separately:

deterministic restart/no-replay proof.

## Current first causal blocker

The final Windows Central Writer candidate is not yet durably bound for external review.

Required handoff:

- candidate branch;
- full HEAD SHA;
- base SHA;
- dirty/clean status;
- complete changed-file list;
- targeted test commands/results;
- remote branch availability for Codex.

No substitute branch should be assumed.

## Expected candidate scope

`FINAL_MINIMAL_DELTA=B`

Expected authorized scope:

1. `server/app.py`
   - artifact upload/verify cutover;
   - intended duplicate/idempotency patch.

2. already-authorized targeted test guard changes.

3. `scripts/courier_verifier.py`
   - `expected_sha256`;
   - comparison against verified server-side artifact hash/bytes.

4. deterministic tests covering changed behavior.

No unrelated architecture/scheduler/wall/product-shell work.

## Latest Opus physical-plan findings

Opus prepared a Canary execution plan and did not execute or modify the runtime.

Key findings:

- Canary workflow plan can supply explicit task IDs.
- Task IDs must be unique across runs because server task storage is global by ID.
- Deterministic exact-content hashes should be calculated from exact bytes.
- RUN 1: server + verifier + supervisor active before one goal submission; no human relay until B has completed/reconciled.
- RUN 2: verifier intentionally OFF while A reaches `RESULT_RECEIVED`; snapshot state/result evidence; controlled restart; then verifier ON; verify A is not executed again and B continues.
- If A becomes FAILED, current automatic retry/requeue behavior creates a side-effect-repeat risk. Canary run should abort rather than treating that run as valid.
- Canary content verification proves only the predetermined exact content for that Canary. It is not a claim of general semantic verification.

## Latest Codex result

Codex stopped correctly because the actual final Windows candidate could not be identified/accessed.

Observed result:

- CANDIDATE_IDENTIFIED=NO
- candidate branch/SHA unknown
- candidate delta not proven
- no candidate tests accepted
- SAFE_FOR_PHYSICAL_CANARY=NO

Reason:

No exact Central Writer handoff/remote candidate was available to that review session.

## Next sequence

1. Windows Central Writer binds/publishes exact candidate handoff.
2. Codex reviews that exact branch/SHA only.
3. Mac Muse CLI binding proves real provider/adapter contract.
4. Mac runtime/isolation preflight proves physical authority/workspace/ports/state paths.
5. If candidate review passes and Mac preflight has no blocker:
   - bind exact candidate;
   - execute RUN 1 A->VERIFY->B;
   - capture minimal evidence.
6. Execute separate deterministic restart/no-replay RUN 2.
7. Only after these proofs consider scale work.

## Canary abort rules

Abort/mark invalid if:

- candidate SHA changes during run;
- loaded runtime cannot be bound to candidate;
- A is manually injected;
- B is manually started;
- A reaches FAILED and enters unsafe execution retry;
- A is blindly re-executed after restart;
- deterministic content check is unavailable;
- critical state becomes UNKNOWN.

## Claim discipline

Allowed claim after a passing content Canary:

"Courier deterministically verified the exact expected Canary output and continued automatically."

Not allowed from that proof alone:

"Courier can generally understand whether arbitrary work is correct."
