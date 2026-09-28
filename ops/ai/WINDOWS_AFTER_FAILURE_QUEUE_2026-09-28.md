# Windows After-Failure Queue — 2026-09-28

Use one mutable Windows writer only.

W0 current local test triage:
- inspect the exact 1 failed + 1 skipped tests from the latest local targeted run;
- do not accept/apply queued edits blindly;
- classify failure as PRODUCT_DEFECT / TEST_HARNESS / STALE_EXPECTATION / ENVIRONMENT;
- SKIPPED invalidates handoff unless explicitly outside authoritative matrix.

Then queue:
W1 local-diff causality review
W2 failure-minimal patch
W3 targeted retest + no-skip check
W4 source-scope/invalidation audit
W5 Mac handoff delta
W6 stop/phase router

No physical Mac run from Windows.
