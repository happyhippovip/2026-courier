# WIN-07 CLAIM — WINDOWS_MUSE_15_CONTINUOUS (moved from WIN-02)

SLOT=WIN-07 (first free: state.json/WORKING enumeration shows MUSE-45 +
WIN-01..WIN-06 live; WIN-07..15 zero hits repo-wide, OBSERVED.)
HOST=WINDOWS (REPO matches. STATUS != WRONG_HOST.)
MODEL=MUSE, LEVEL=MAX, MODE=AUTO_SLOT_CONTINUOUS (LIGHT_ONLY: shell runner DOWN,
sandbox setup fails pre-exec; no git/test/process/proof/commit. ADDITIONAL
CONSTRAINT this session: read_file + pathed search fail for scripts/docs/ops
(os error 2) while unpathed search still returns their content — code reads
via search snippets only; runtime/ reads fully OK.)
SESSION=01a0dcbf-7be5-7a83-9a7d-502e53399312 (same worker as ex-WIN-02 claim)

VACATE NOTE: this worker claimed WIN-02 in good faith (zero hits at claim
time) and filed CLAIM.md + W02-01_stop_safe_audit.md + W02-02_soak_review.md
there. A live peer co-worker has since filed runtime/slots/WIN-02/state.json
(WORKING) + RESULT_01_verify_and_audit.md in the same slot. Per "never
knowingly duplicate another live slot", WIN-02 is VACATED by this worker as
of this claim. Own WIN-02 artifacts LEFT IN PLACE (peers already index them:
WIN-03 W5 re-checked WIN-02 x3, 14/14 confirmed). No peer files touched.
Prior WIN-02 work remains attributed to SESSION 01a0dcbf-7be5; new work files
as WIN-07 (W07-NN series).

WRITER POLICY: Google/Antigravity primary writer ACTIVE (checkpoint
2026-09-26T07:45, scope scripts/windows_muse_wall/config.json, tree DIRTY;
peer packets confirm ongoing tree mutation — LINE DRIFT observed, e.g.
daemon.py lock_file line moved since my W02-01 read) → WRITE_SCOPE=NONE.
DEFAULT READ ONLY outside own slot dir. P3 files READ ONLY. No wall/config
writes, no merges, no kills, no branches, no process interference.

SCOPE (shell-less, non-disturbing):
- READ: repo via search snippets + runtime/ reads. Windows scope only (no Mac).
- WRITE: ONLY runtime/slots/WIN-07/* (own slot). WIN-02 dir: no further writes.
- RESPECT: all live peers (WIN-01..06 reports read-only, MUSE-45 read-only).
- DEDUP: read peer headers before staking; classic-launcher audit DROPPED
  (WIN-01 W2 ps1 audit DONE); provider_launch_enabled dispute RESOLVED by
  peers (shipped config pins false).

WORK LOG (CLAIM -> WORK -> RESULT -> NEXT):
- CLAIM WIN-07 done (state.json first, then this file). NEXT: W07-01 freshness
  re-verification of WIN-02 findings (SS-1/SS-2/SK-1/SK-2) against the MUTATED
  tree via search snippets (ladder #1 verify + #9 stale assumptions).
- W07-01 done: fix-cb1-new @ 329abd80 established via .git; stop_safe/
  worker_status/soak/supervisor ABSENT (old-rev verdicts); SS-1 hazard moot
  (no lock readers) but handoff step 4 stale; N3 stop.bat rewritten
  (title filter, unverified); N1 finally-remove-while-open (inferred).
  Report: W07-01_freshness_reverify.md. NEXT: W07-02 daemon task-path audit
  on fix-cb1-new (run_task/persist/upload/claim/timeout paths, CURRENT rev
  only) — check WIN-01..06 tails + T25/T26 first to avoid dup.
