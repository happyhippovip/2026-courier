# Deferred Ledger & Guard Backlog

CANONICAL QUEUE:
ops/ai/DEFERRED_LEDGER_QUEUE.yaml

This file no longer carries active backlog items. Resolved history:
LEDGER-01 (atomic state persistence) and LEDGER-02 (verifier authority
for merge approvals) were fixed and removed in d45db37e. LEDGER-03
(Uncoordinated Provider Quota Backoff) was revalidated against current
HEAD and migrated as DLQ-05 with the corrected invariant: per-provider
`provider`-string sleep (the shared credential pool), not a global lock,
so unrelated providers keep WAITING_PROVIDER isolation.
