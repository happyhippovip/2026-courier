# TASK_30 — Exact Deterministic Acceptance Conditions

STATUS=DONE

## Acceptance Conditions for Canary 1 (A→VERIFY→B)

### Condition 1: Exact artifact content
File written by worker (or script) must match expected_sha256 byte-for-byte.
CANARY_A_SHA256=96c1471cc2dfc55d49de5a3279dc927774a84b0f5c5bdc7c5755f19d8de9391c
CANARY_B_SHA256=b9032958fc90e7380195fcc51eca5822d60bb31eb15d370a44c3c15e60942a50 (COURIER-A2B-B\n)

### Condition 2: Binding match
result_id must match dispatch-bound result_id ("result-" + dispatch_id).
goal_id, task_id, attempt_id, dispatch_id, worker_id must match claimed task.

### Condition 3: Independent verification
Verifier must independently fetch artifact, compute hash, compare to expected_sha256.
Worker-reported sha256 alone is insufficient.

### Condition 4: No replay
After server restart, server reloads state. RECONCILED tasks do NOT re-enter the claim queue.
Next task (B) is a NEW task_id with NEW dispatch_id → mathematically distinct result_id.

### Condition 5: Zero human relay
Human_relay=0 from A claim → verify → reconcile → B claim.

## Boundary
This proves ONLY deterministic expected Canary content for fixed inputs.
NOT a general semantic verifier for arbitrary agent tasks.

PROVEN=All conditions source-audited and physically validated for task-canary-A.
UNKNOWN=None
BLOCKER=None
NEXT=TASK_31
