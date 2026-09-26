# CANARY 1 runbook — candidate-b-1 @ 4c1e24cc (PREP ONLY, nothing started)

CANDIDATE: `origin/candidate-b-1` = 4c1e24cc (verified `git rev-parse`; tip:
"fix: daemon powershell encoding and robust locking"). No checkout performed here.

## 0. Preconditions (runner checks, in order)
1. `git rev-parse origin/candidate-b-1` still = 4c1e24cc, else STOP (base moved).
2. Port 8080 free: `lsof -iTCP:8080 -sTCP:LISTEN` empty (was free at prep time;
   server hardcodes `app.run(port=8080)`, no PORT env).
3. Writer/heavy locks: proceed only if no live foreign writer on the canary paths.
4. Muse CLI = /Users/user/.local/bin/muse 1.4.0 (see MAC_REAL_MUSE_BINDING.md).

## 1. Isolated worktree (runner executes, not done here)
`git worktree add /private/tmp/canary-b1 origin/candidate-b-1`
Never inside /Users/user/Downloads/2026-courier (shared checkout stays clean).

## 2. Isolated runtime paths (env, placeholders only — no real secrets here)
- `COURIER_STATE_FILE=/private/tmp/canary-b1/state.json`
- `COURIER_API_KEY=<test-only key>` , `COURIER_VERIFIER_API_KEY=<test-only key>`
- Artifacts: `/private/tmp/canary-b1/artifacts/` ; logs: `/private/tmp/canary-b1/logs/`
- Server start (foreground, own terminal): `cd /private/tmp/canary-b1 && python3 server/app.py`

## 3. Task A / Task B bytes + hashes (MMAC4 fixtures, /tmp/mmac4/)
- A bytes: `courier-fixture-v1` (18 bytes, no newline), sha256
  `7cbf5bee...577d8ee8`; write to `/private/tmp/canary-b1/artifacts/a.bin`.
- B bytes: derived from A's PASS (chain gate): `courier-fixture-v1+verified`
  — exact B bytes fixed at run time and recorded before B starts; B expected
  hash computed and logged pre-execution (no guessing).

## 4. Goal workflow JSON (POST /goals, auth bearer test key)
{
  "goal_text": "canary-b1 deterministisk A->VERIFY->B",
  "workflow_plan": [
    {"task_id": "canary-b1-a", "instruction": "write A bytes", "target_agent": "mac"},
    {"task_id": "canary-b1-b", "instruction": "verify A then write B", "target_agent": "mac"}
  ]
}
Server fills goal_id/status/attempts; fixed task_ids keep observation deterministic.

## 5. Execution (Muse CLI, template from binding proof)
`muse exec --provider meta --json --workspace /private/tmp/canary-b1 --reasoning-effort medium --approval-mode on-request --session-id <UUID> --prompt-file <TASK_FILE>`
Never `--reasoning-effort auto` (invalid). Parse terminal JSON event, not exit code.

## 6. State observation (human-relay=0 evidence)
- `GET /goals/<id>` — step statuses QUEUED->RESULT_RECEIVED->(B auto-queued).
- `GET /tasks/pending_verification` — A awaiting verdict.
- `POST /tasks/verify` — verdict recording.
- A execution-count evidence: `attempts` field on step A == 1 AND exactly one
  result file for canary-b1-a AND server state shows single dispatch_id.
- B automatic-start evidence: step B leaves QUEUED only after A verify PASS,
  with no human-issued command between (shell history + timestamps).

## 7. Abort conditions (any one aborts the run, records state, stops)
- port 8080 taken at start; candidate SHA mismatch; any step `attempts` > 1;
  duplicate result_id observed; artifacts hash mismatch on A; server 500;
  human command needed to advance (relay > 0 fails the canary goal).

## 8. Restart-run checkpoint
- Snapshot: state.json + artifacts/ + server log copied to
  `/private/tmp/canary-b1-restart-<ts>/` BEFORE any restart.
- Restart must show: same result preserved, A not re-executed (attempts still 1),
  verification continues, B starts automatically.
- If restart replays A execution (new dispatch or attempts increment): FAIL,
  file restart-matrix defect, stop scaling.
