# RUN_1 Evidence Layout (Mac)

This document specifies the exact layout and expected contents for RUN_1 Evidence gathering, ensuring proof of correct execution.

## Expected Directory Layout
```
artifacts/run1/
├── ledger_run1.db              # The database proving state transitions
├── server_run1.log             # API interaction proofs
├── worker_run1.log             # Worker execution trace
├── verifier_run1.log           # Verifier confirmation trace
├── A_executes_once.proof       # Specific grep/extract of A task exactly once
├── A_final_status.json         # Reconciled status of A
└── bindings.json               # Environment exact binding verification
```

## Evidence Requirements

### A-executes-exactly-once (GQ15)
- **Log Source**: `server_run1.log`
- **Proof**: Exactly one `POST /tasks/claim` resulting in assigning Task A to `MAC-01`. Exactly one `POST /tasks/result` for Task A. No redundant dispatch.

### Expected-Hash-Survival (GQ16)
- **Log Source**: `verifier_run1.log`
- **Proof**: The file downloaded from `/artifacts/{id}` matches `expected_sha256` exactly.

### Server-Bytes/Hash Evidence (GQ17)
- **Log Source**: `server_run1.log` & `worker_run1.log`
- **Proof**: Uploaded chunk sizes sum up exactly to the reported file size. Checksum is calculated server-side identically.

### RECONCILED Terminal State Evidence (GQ18)
- **Log Source**: `ledger_run1.db` (dump)
- **Proof**: Task A state transitions `QUEUED -> DISPATCHED -> RESULT_RECEIVED -> RECONCILED`.

### RUN_1 Success Synthesis (GQ19)
- A single markdown file summarizing the run success matching these fields, allowing the move to RUN_2 without requiring Codex.
