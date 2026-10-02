# Muse Wall Result Harvester Spec

## 1. Zero-Human Continuation
The harvester provides the automated feedback loop. The normal path MUST require ZERO human copy/paste relay. When a provider or agent returns a result, the harvester intercepts and automatically advances the system state through the deterministic flow.

## 2. Deterministic Harvester Flow

1. **RESULT**: A raw output is received from a worker/provider lease.
2. **validate identity**: Enforce schema constraints. Verify that `task_id`, `goal_id`, `dispatch_id`, and `worker_id` match the active dispatch lease.
3. **fingerprint**: Compute the `result_id` (deterministic SHA256 of the validated identity and payload).
4. **deduplicate**: Check if this exact `result_id` or `dispatch_id`'s terminal state already exists in the ledger.
5. **attach evidence**: Identify generated artifacts, assert their paths, and append their expected vs actual SHA256 signatures.
6. **update Ledger**: Append the `RESULT_RECEIVED` event securely to the append-only `extended-ledger-1.0` JSONL file.
7. **verify**: An independent verification rule (or agent) evaluates the evidence against the contract requirements.
8. **reconcile**: Sync the `PASS`/`FAIL` verdict back to the active goal's workflow. Transition the step to `RECONCILED` or `FAILED_VERIFICATION`.
9. **determine NEXT_READY**: Traverse the explicit DAG. Any `QUEUED` tasks whose dependencies are now fully `RECONCILED` transition to `READY`.
10. **refill free logical slot**: Allocate the newly unblocked `READY` task to a requested motor, subject to Device-Adaptive Admission.

## 3. Edge Case Handling

- **duplicate result**: A result with an identical `result_id` or matching a `RECONCILED` step. Discarded as a harmless no-op.
- **contradictory result**: A result received for a task that is already `RECONCILED` with a different `result_id`. Rejected and flagged; the ledger is immutable.
- **stale result**: A result bound to an old `attempt_id` or an expired/reclaimed `dispatch_id`. Rejected.
- **RETEST_AFTER_FINAL_SHA**: If a critical integration boundary or contract signature changes (Final SHA), previously `RECONCILED` downstream tasks must be invalidated and re-queued automatically.
- **queue generation change**: If the workflow graph dynamically mutates due to a branch/loop, the queue is regenerated. Unchanged tasks retain their identity and `RECONCILED` status.
- **restart/session change**: Provider limits, network drops, or UI restarts do NOT affect the ledger. The harvester automatically resumes processing the active ledger state upon startup.
- **provider change**: If a task fails verification due to capability limits, it may be re-queued with a new `attempt_id` mapped to an alternative provider route (e.g., Mac -> Windows -> Linux fallback), preserving the underlying task identity.
- **morning handoff**: If a goal is completed entirely via the Night Queue, the harvester finalizes the evidence dossier and enters `DONE`. The human owner receives a summarized, artifact-backed report in the morning with no required action other than review.
