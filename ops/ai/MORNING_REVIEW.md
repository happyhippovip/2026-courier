# CURRENT REVIEW CHECKPOINT

CODE_BASE_HEAD: 0c8d1eddacb15dedbebb8406e475917dc2ab1c2b
UPDATED_AT: 2026-09-18T09:23:33+02:00

## Proven from repository state

- The canonical branch contains server-enforced worker/runtime SHA matching.
- Human-gated merge approval requires verifier authority.
- DLQ-05 provider-quota isolation is implemented in `server/app.py` with
  server-owned worker-to-quota-pool mapping and focused regression coverage.
- The Cloud and ChatGPT operating models agree on packet-first work routing,
  one-writer ownership, staged tests, Codex economy, and Ledger-last truth.

## Not proven by this memory update

- The checked-in Ledger is revision 1227 and remains `PROVISIONAL`,
  `QUEUE_INDEPENDENT=NO`, `CLEAN_IDLE=NO`; its recorded SHA/runtime is stale and
  must not be presented as current acceptance evidence.
- Current physical Windows runtime identity is not freshly observed here.
- DLQ-05 is software-verified, but current physical quota-pool configuration and
  exact-SHA runtime behavior remain a Google/physical-runtime verification task.
- DLQ-01, DLQ-02, DLQ-03, and DLQ-04 remain queued exactly as documented in
  `DEFERRED_LEDGER_QUEUE.yaml`.

## Next routing

Use `NEXT_WORK.yaml`. Do not route Codex until a complete review packet includes
T2 and T3 evidence.
