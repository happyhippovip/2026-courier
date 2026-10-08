# MMAC-223 — Ledger-controller bridge built, pushed, SHA-verified

Branch muse/bridge-ledger-controller @ ff955659 (local == remote).
New files only: scripts/ledger_controller_bridge.py (pure mint/receipt
translation, stdlib-only, no ledger/controller edits) + regression tests.
py_compile + logic smoke green; full pytest left for CI (host swap-critical).
No PR opened: L1 promotion domain. #258 grants branch intact.
