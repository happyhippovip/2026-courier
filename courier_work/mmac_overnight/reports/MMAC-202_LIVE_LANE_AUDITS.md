# MMAC-202 — Four live-lane audits, writers untouched (resume, read-only)

Base `origin/integration/v1` = `f425d328`. All four branches pushed 03:11–03:19Z (minutes before fetch) → treated as live writers: zero mutations, zero claims, zero worktrees.

## #245 L2 human-retry budget: VERIFIED genuine
Old `max_attempts=max(max_attempts, attempt+1)` let a human retry inherit leftover automatic budget (1-of-3 blocked → up to 3 runs). New `max_attempts=attempt+1` grants exactly one. Test runs the full machine: blocked → authorized → granted attempt fails → RETRY_PENDING → decide FAIL → further `retry_scheduled` raises "retry forbidden". Fails pre-fix by construction. Ubuntu CI pass, windows pending.

## #246 L6 install-service user task: VERIFIED genuine
SYSTEM/Highest at startup → current-user/Limited at logon (least privilege + per-user LOCALAPPDATA match), with post-registration principal self-check and fail-closed exits. Test layers honestly disclosed in-docstring: static contract (all platforms, fails on trunk) + native Windows registration with throwaway-task cleanup. No action.

## #240 L1 golden blocked-unit: VERIFIED genuine test-only
270-line golden: failed-unit and blocked-unit cases each prove the queue advances to next units. Ubuntu pass, windows pending. No action.

## #239 runtime-deadlines: VERIFIED genuine
`_coerce_date` (None/date/datetime/ISO string, TypeError otherwise) + `int()` hardening + JSON CLI with exit code; tests pin coercion matrix, invalid-type rejection, and exact CLI output. No action.
