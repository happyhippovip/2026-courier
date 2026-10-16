# MMAC-201 — #234 fully green on real Windows + six ledger audits (resume, read-only)

Base `origin/integration/v1` = `f425d328`. Zero mutations.

## Closed loop: PR #234 fully green including real Windows
MMAC-197's blind-fallback fix (GREEN→UNKNOWN) is now CI-proven: pytest ubuntu PASS (5m16s), pytest windows PASS (12m36s) — the new `test_blind_measurement_reports_unknown_not_green` runs green on an actual native Windows host, plus acceptance ubuntu+windows, JS, ratchet all pass. PR #234 MERGEABLE, awaiting L1 merge decision (not mine to merge).

## Audit verdicts (branch diff + test-body reads + live CI)
- #220 spreadsheet-sample: message fix real (script deletes the fixture it told users to inspect). Trivial, no test needed. No action.
- #221 check-safety scrub: genuine — scrubs finding text at the source (CI logs + reports) while deliberately keeping the dedup key raw; test pins both. Same truncate-before-scrub fragment residual as #217, already recorded. No action.
- #222 429 contract: honest behavior pin (429 → RETRYING_SAFELY, never fail-hard, 3 messages). No action.
- #223 openapi generator: two real defects fixed — regex mangled `<task_id>` into `{d}`, and import-time CWD-dependent side effects; refactored to pure `build_spec` + anchored `main(root)`, tests pin params/CWD-independence/no-side-effects. No action.
- #225 host-guardian: genuine hardening (configurable root + fallbacks, psutil fail-soft, 10 MB swap-surge threshold replacing any-increase trigger); jitter/surge/root/metrics tests pin the new logic. One vacuous pre-existing-style test noted (`memory_warning_light_only` mocks the method it claims to test) — harmless, no patch. No action.
- #229 provider-circuit: genuine — shared-restore split-brain (instance re-pointed at fresh dict, class shared state stale) plus `classify_error(None)` crash and bad-`reset_time` restore crash; two-instance sync test fails pre-fix by construction. No action.

## Ownership respected
Untouched as active: #239 (branch moving), L1 golden-blocked lane (pushing), new L2 retry-authorized and L6 install-service lanes.
