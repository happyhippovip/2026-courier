# MAC03 Isolation Prep — fresh state/logs/artifacts/temp/run IDs (RUN_1/RUN_2)

Slot: MAC03_ISOLATION (unique C2 claim, RUN_1/RUN_2 preflight).
Host: Mac, repo `/Users/user/Downloads/2026-courier`, HEAD `bd539f18`.
Selftest: MUSE_SELFTEST_REPO=PASS, MUSE_SELFTEST_STATE_READ=PASS,
MUSE_SELFTEST_CLAIM_PATH=PASS, MUSE_SELFTEST_READY=YES (prep only).
Gate: PRE_CODEX=DURABILITY_PENDING — no SHA revalidation done. LEDGER_WORK=SKIP.

## Created fresh (empty, verified with ls)

- `server/state/isolated_run1/{artifacts,logs,temp}` + `run_id.txt` = `75821131-730A-480A-B4BE-AD8B251E15C6`
- `server/state/isolated_run2/{artifacts,logs,temp}` + `run_id.txt` = `9783F60C-0290-4D59-905E-21C87DAC42F2`
- `/tmp/courier_run*` absent, `/tmp/courier_heavy_job.lock` absent — no leak, no lock held.

## Untouched production state

- `server/state/central_state.json` (28 Sep 00:13), `server/state/artifacts/{blobs,records}` — not modified.
- `logs/courier_motor.err`, `scripts/mac_worker/logs/*`, `website/public` dirt — foreign, untouched.
- Stale candidates recorded only, NOT deleted: `logs/courier_daemon.pid` (46397, dead),
  `logs/courier_daemon.log` + `logs/courier_motor.log` (25 Sep), `state/wall/supervisor.lock` (0 B).

## Result block

TASK_ID=MAC03_ISOLATION
FAMILY=run-isolation-preflight
STATUS=PREP_DONE (dirs fresh+empty, zero production writes, zero deletes)
RESULTS_REUSED=MAC_RUN1_ISOLATION_CHECKLIST + RUN2_HARNESS + EVIDENCE_DESIGN (read as contract)
FINDING=isolated_run1/2 ready; production state clean-separated
MISSING_EVIDENCE=boot-time liveness (only at RUN_1 execution)
NEXT_EXACT_ACTION=hold dirs empty; RUN_1 boot only after MAC08 resource gate passes
DO_NOT_REPEAT_FINGERPRINT=MAC03-isolated-dirs-20260928-bd539f18
