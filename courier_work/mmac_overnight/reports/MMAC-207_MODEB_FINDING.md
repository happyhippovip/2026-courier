# MMAC-207 — #248/#250 genuine, HIGH finding on #249 Mode B (adversarial, read-only)

Base `origin/integration/v1` = `f425d328`. Zero mutations; #249 branch live (committed 03:28Z) — finding routed, no patch.

## #248 uninstall verify-removal: VERIFIED genuine
Exit 0 only when nothing remains (re-queried), exit 1 with itemized problems; process kill scoped to exact `Courier.exe` path (no broad kill); cross-profile `C:\Users` config sweep removed (privacy-positive); `$SimulateRemovalFailure` test hook; native tests cover throwaway-task removal + idempotency + non-stick reporting. One windows run passed, one pending.

## #250 install-state contract: VERIFIED substance (design level)
Evidence-derived status machine: HEALTHY requires process identity (pid+starttime+exe) AND fresh controller confirmation AND non-privileged scheduler — PID-alone never HEALTHY (PID-reuse answered); interrupted installs are REPAIR_REQUIRED; protected dirs never deleted; secrets redacted; 13 tests incl. unattributable-worker, stale-confirmation, privileged-scheduler refusals. Full 574-line logic not line-audited (stated scope).

## FINDING-249-MODEB (HIGH): self-attested model execution
`_execute_mode_b` ("Actual Google Antigravity model-driven code-building operation") performs zero model invocation — no subprocess, no API — and returns `status:PASS, model_invoked:True, model_driven:True`. `verify_result` checks `status==PASS` plus hash *presence* (never recomputed). `run_sequential_two_unit` defaults unit 2 to MODE_B, so the flagship proof passes with no model involved. Tests assert the self-set flag, hence green CI proves nothing about execution.
- Minimal regression: Mode B must fail when no model is reachable (remove fallback-PASS); verify must recompute the hash and reject forgeries.
- Real-host proof required: a Mode-B result whose payload contains model-observable output.
- Owner: branch author via existing coordination; L1 must gate #249 merge on this.
