# T17 RESULT — FAILURE_SIGNATURES cross-check at HEAD b927f106

MODE: shell-less LIGHT. All 9 signatures checked against current code.
Doc bound to 0c8d1edd (2026-09-18); code at b927f106.

## Verdicts
1. pytest-OOM-SIGKILL — TIMELESS (env/process guidance). OK.
2. motor-drain-flake — HISTORICAL-ACCURATE (fix present: hung-abandon +
   bounded drain in courier_continue.py:530-539, T11-read). OK as record.
3. werkzeug-sandbox-stall — TIMELESS but INCOMPLETE (see F-T17-4).
4. mid-commit-read-race — TIMELESS. OK.
5. launchd-absent-torture-gate — PIN DRIFTED: cites
   test_tomato_two_torture.py:130; gate assert now at :141. Same re-pin
   family as S-T11-3. LOW.
6. ledger-zero-update-preset — LABEL STALE: says "live 2026-09-18" but
   PROVISIONAL forcing is present (ledger:683,816,836). Should read
   GUARDED (test re-run needed when shell returns). LOW.
7. ledger-future-proof-promotion — LABEL STALE: says "live" but skew/age
   guards present (MAX_FUTURE_CLOCK_SKEW_SECONDS=300,
   MAX_EVIDENCE_AGE_SECONDS=172800 at :77-78, enforced :301-305,783-784).
   Should read GUARDED. LOW.
8. ledger-ghost-attester-promotion — LABEL STALE: says "live" but
   introducer_map writer-independence present (:734-804, T11). GUARDED. LOW.
9. uncoordinated-provider-429 — PARTIALLY STALE: response prescribes
   "provider_locks per worker quota pool"; deployed granularity is
   worker-level (T16: map never populated). Entry needs the granularity
   caveat. LOW.

## Finding
F-T17-4 (INFO) MISSING SIGNATURE: CURRENT SANDBOX FAILURE MODE.
werkzeug-stall covers "accepted-but-hung". This session (and 3 priors per
memory) shows a different mode: sandbox setup fails BEFORE execution
("admit deny-read ... unproved ACL/owner mutation") — no command runs at
all. Suggest a new signature shell-sandbox-setup-deny with response:
do not retry-loop; fall back to read/search LIGHT work; escalate via
owner channel, not per-command approval spam. Hands to doc steward —
no shared-doc edit made here (read-only mission).

## Disposition
Read-only mission: NO DOC EDITS. 3 stale "live" labels + 1 pin + 1
granularity caveat + 1 missing signature handed to steward.
No files outside runtime/slots/MUSE-45 touched.
