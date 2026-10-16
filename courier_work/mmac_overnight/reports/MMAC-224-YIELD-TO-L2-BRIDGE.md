# MMAC-224 — Yield: L2 owns the bridge (PR #267)

The canonical bridge now lives on lane/L2-ledger-v1-bridge (PR #267, L2 lane,
#153 lineage): live dispatch, idempotent keys (`ledger:` + claim event, same
scheme), fail-closed receipts with double-guarded FINAL, restart + redaction
coverage. My muse/bridge-ledger-controller is superseded — a parallel
implementation of a subset. Yielding per no-duplicate rule: no PR, no more
commits, branch left untouched (no deletion without explicit ask).
