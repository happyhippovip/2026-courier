# T18 RESULT — VERIFY_done_slots UPDATE: per-slot logs FOUND (read-only delta)

SUPERSEDES: VERIFY_done_slots.md lines 9-10 ("logs ABSENT for all 16").
MODE: shell-less LIGHT. All paths OBSERVED via file reads this session.

## Evidence (OBSERVED)
- runtime/slots/MUSE-01/logs/job-JOB-01.log: 4 lines, each `JOB-01 on MUSE-01 OK`
- runtime/slots/MUSE-04/logs/job-JOB-04.log: 3 lines, each `JOB-04 on MUSE-04 OK`
- runtime/slots/MUSE-08/logs/job-JOB-08.log: 2 lines, each `JOB-08 on MUSE-08 OK`
- runtime/slots/MUSE-16/logs/job-JOB-16.log: 1 line, `JOB-16 on MUSE-16 OK`
- All 16 logs/job-JOB-NN.log exist (MUSE-01..16 file enumeration).
- job.json 01 + 16 re-read: kind=test, status DONE, command ==
  [.venv python, -c, "print('JOB-NN on MUSE-NN OK')"] — exact
  supervisor.test_job_snippet template match. created<started<finished sane.
- run_job opens the log with mode "ab" (supervisor.py:186) => re-runs APPEND.

## Analysis (INFERRED from above, high confidence)
Line counts 4/3/2/1 at slots 01/04/08/16 EXACTLY match cumulative staged
re-runs 1->4->8->16 (slot N re-runs at every stage >= its band: MUSE-01 at
stages 1,4,8,16 = 4x; MUSE-04 at 4,8,16 = 3x; MUSE-08 at 8,16 = 2x;
MUSE-16 at 16 = 1x). Prediction made BEFORE reading MUSE-04 (3x) and
confirmed. This quantitatively corroborates the overnight staged narrative
in GOOGLE_WINDOWS_LOCAL_CHECKPOINT.md + commit b927f106.

## Revised verdict
- DONE-by-record: YES (stands, re-confirmed).
- DONE-by-proof-output: YES for sampled slots (unique stdout on disk,
  template-exact, counts stage-consistent). Prior "NO" is REFUTED for
  current tree state.
- SCOPE LIMIT (unchanged): kind=test python one-liners prove slot plumbing
  (assign->run->reap->DONE), NOT real provider/Muse sessions. Do not cite
  as YOLO-16 proof. provider_launch_enabled=false in committed config.

## Open (needs shell; parked for owner/runner-alive session)
- Whether logs postdate the prior VERIFY check (late re-run) or were missed
  by it: compare log mtimes vs job.json finished_at (1790401521-27 window).
- Full 16/16 line-count census (sampled 4/16 here; pattern predicts
  01:4, 02-04:3, 05-08:2, 09-16:1).
- No action taken (other sessions' results; this delta report only).
