# MMAC-206 — 48h continuity preflight: lifecycle facts + 5 owner-gated gaps

Base `origin/integration/v1` = `f425d328`. Read-only; no batches fired, no runner state touched. Host MAC/Intel, load ~6.6 (reads only).

## Verified from the installed CLI (`muse exec --help`, this host)
- Bounded steps: `--max-model-steps N` exists. Session logs persist by default. `--session-id UUID` flag exists (cross-process resume semantics not verified here).
- Approvals: `--approval-mode untrusted|on-request|never` (default on-request), judge on, safety ON by default. `--permission-profile`, policy-gated `--workspace`, `--user-input-auto-resolve` (headless auto-cancel), `--sandbox-network` (default proxy-only) all exist. `--yolo` et al are per-run session flags — never product path.

## Runner invocation gap (the missing production path, precisely)
`scripts/macos_muse_night_once.sh:123` runs bare `muse exec --prompt-file`: no step bound, no approval-mode, no permission-profile, no auto-resolve. Every hardening flag the 48h mission needs exists in the CLI but none is wired in. Wiring them is owner-gated: the step bound has no principled value available, and approval-mode is a security-posture human decision. No patch from here.

## Network preflight (observed, unknowns marked)
Needs `github.com:443` (fetch + `gh` API, observed). Workspace skills/rules NOT loaded by default (no `--trust-workspace`). Provider-backend endpoint for the default meta provider: UNKNOWN (no traffic capture performed — not probed, not invented).

## Clone blocker (owner queue, do not touch)
`/Users/user/courier-night` dirty since 2026-10-07T22:00 CEST (`server/app.py` state-lock hardening + contract test = parked Units 157–162, owner decision pending) → every 300s run logs update-skipped and executes a stale tree. Preserved as-is per dirty-work rule.

## 48h acceptance status: NOT STARTED
No honest 48h proof exists anywhere (runner proves per-batch idleness: 162 stand / 0 runnable). Targeted fault-injection first, then a bounded wall-clock run — needs Dennis authorization, not manufactured here.
