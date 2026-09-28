# MUSE AUTONOMY SHARD 25 — Queue / Backoff

SHARD=25
STATUS=SHARD_COMPLETE (4 subcases, 0 defects, 0 gaps)
CLAIM.c2=elm-triton / HOST=MAC / 2026-09-28
MODE=READ_ONLY_C2, 0 source edits, 0 runs, 0 ledger. CODEX_HIGH_RESULT_CURRENT.md
absent (phase recheck this run) → autonomy lanes stay pre-Codex.
No peer backoff coverage found (bounded grep over shard checkpoints empty) —
this shard is fresh. UNDELIVERED-consumer paths NOT examined (boundary, no claim).

## Subcases (both daemons, current numbering)
- Q1 bounded result-post retries: mac for attempt in range(
  MAX_RESULT_POST_ATTEMPTS=8 ) with 2**attempt sleeps (:207-217, const :78);
  win range(5) (:122-135, const :43). 4xx → REJECTED permanent both (mac via
  is_retryable_post_error :211-214; win e.code<500 :128-131, documented
  :114-117). Total worst-case sleep bounded (~255s mac, ~31s win).
  → NO_ISSUE (bounded + fail-closed split).
- Q2 poll cadence capped: mac fixed POLL_INTERVAL_SECONDS default 5 on all
  loop paths (:448/:534/:596 area); win sleep 10 (:418) + error backoff
  doubling capped min(max_backoff=300, ...) (:322, :413-416). No unbounded
  growth anywhere (2**attempt only inside bounded ranges).
  → NO_ISSUE.
- Q3 no busy-spin on empty queue: every poll-loop path (empty claim, error,
  resource-pressure :358 sleep 60) sleeps before re-poll. Rate bounded to
  ~6-12 rpm/worker. → DISPROVEN (spin/hot-poll risk).
- Q4 resume-after-idle by construction: while-true poll loops re-claim each
  cycle; empty → sleep → re-poll → newly QUEUED tasks picked up without
  restart or human nudge. → NO_ISSUE.

SUBCASES_DONE=Q1,Q2,Q3,Q4
CONFIRMED_SOURCE_DEFECTS=(none)
EVIDENCE_GAPS=(none)
DISPROVEN=Q3 (busy-spin); Q1,Q2,Q4 closed as NO_ISSUE boundedness pins
FIX_PACKETS=(none)
NEXT_OWNER=(none — nothing to own)
DO_NOT_REPEAT=muse-autonomy-shard-25-01
