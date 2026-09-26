# CANARY-1 EXECUTABLE RUNBOOK (prep-only, no run started)

CANDIDATE: `4c1e24ccc522042af826bc4c2b595daf85d097f9` = commit on `origin/candidate-b-1`
(verified: `git cat-file -t` → commit; `branch -a --contains` → `remotes/origin/candidate-b-1`).
REPO: `/Users/user/Downloads/2026-courier` (untouched; HEAD stays `332a42f9` supervisor checkout).
MUSE CLI on host: `/Users/user/.local/bin/muse`, `Muse Code 1.4.0` (observed `muse --version`).
NOTHING was started, killed, or modified for this prep. Worktree below is NOT yet created.

## 0. Isolated worktree (prep step 1, allowed: modifies nothing in candidate)

```sh
git -C /Users/user/Downloads/2026-courier worktree add /private/tmp/canary-b1-4c1e24c 4c1e24ccc522042af826bc4c2b595daf85d097f9
git -C /Users/user/Downloads/2026-courier worktree list | grep canary-b1-4c1e24c
WT=/private/tmp/canary-b1-4c1e24c
```
No listed worktree uses this path (checked full `worktree list` 2026-09-26).
Teardown after run: `git -C /Users/user/Downloads/2026-courier worktree remove /private/tmp/canary-b1-4c1e24c`.

## 1. HARD PRECHECKS (abort if any fails; all read-only)

P1. Port 8080: `lsof -iTCP:8080 -sTCP:LISTEN -P -n`.
    2026-09-26 OBSERVED: `Python PID 69407 ... TCP 127.0.0.1:8080 (LISTEN)`,
    `ps` → PPID 1, ETIME 1-03:23:21, CMD `python -m server.app`. FOREIGN, do not touch.
    Server binds fixed `0.0.0.0:8080` (`server/app.py:562` at candidate).
    → Server phase ABORTS until operator resolves the occupant. No alternate port
      exists without modifying the candidate (forbidden).
P2. Wall dir: `/Users/user/Downloads/courier_work/muse_wall/` ABSENT (observed 2026-09-26)
    → supervisor lock `.../muse_wall/supervisor.lock` cannot be held; re-check at runtime.
P3. Operator-supplied secrets (never invented, never logged):
    `COURIER_API_KEY` and `COURIER_VERIFIER_API_KEY`, distinct, neither in
    `{"", "dev-secret-key", "your_secure_api_key_here"}` else server answers 503
    (`server/app.py:12-40`).
P4. Fresh isolated state paths per run (never reuse the foreign server's state):
    `COURIER_STATE_FILE=/private/tmp/canary-b1/state.json`
    (`server/app.py:16`, default `server/state/central_state.json`)
    `COURIER_ARTIFACT_DIR=/private/tmp/canary-b1/artifacts`
    (`scripts/artifact_store.py:73-75`, default `server/state/artifacts`).

## 2. Phase 0 — supervisor connectivity canary (no queue, 60 s ceiling)

From `$WT`, run ONLY (`docs/CANONICAL_MUSE_CANARY.md` + `muse_supervisor.py:428-496`):
```sh
cd "$WT" && python3 scripts/mac_worker/muse_supervisor.py canary
```
What it does itself (no operator env needed): wall =
`~/Downloads/courier_work/muse_wall` (`muse_supervisor.py:40`); task ids fixed
`physical-muse-canary-01`, attempt/dispatch `:attempt:1`/`:dispatch:1`, worker
`MUSE-CANARY-01`, instruction = connectivity-only fixed string (`:462-467`);
sets `COURIER_MUSE_CLI={"protocol":"headless-v1"}`, timeout 60 s (`:473-476`);
CLI contract `muse exec --workspace /Users/user/Downloads/2026-courier`
(`muse_adapter.py:build_muse_command`; `CANONICAL_WORKSPACE`, `runtime_state.py:13`).
Evidence dir: `~/Downloads/courier_work/muse_wall/canary/01/state/`
(`current_task.json`, `muse.stdout`, `muse.stderr`, `muse_process.json`, checkpoint).
Exit semantics: `RESULT_READY` present → prints status, NO re-execution (`:452-454`);
phase `STARTED`/other non-`CLAIMED` → exit 1, operator reconciles, NEVER delete
evidence (`:455-457` + doc). Prints `CANARY_STATUS=<status> OUTPUT_DIR=<dir>`.
Refusals (exit 1): lock held (`:436-438`), STOP file (`:445-447`), live slot pid
(`:448-450`), `CapacityGovernor(1)==0` (`:459-461`), `MuseAdmissionBlocked`
→ phase back to `CLAIMED`, no exec (`:477-480`).

## 3. Phase 1 — goal workflow Task A → Task B (server path; needs P1 cleared)

3.1 Start (from `$WT`, operator keys from P3, paths from P4):
```sh
cd "$WT" && COURIER_API_KEY="$K1" COURIER_VERIFIER_API_KEY="$K2" \
  COURIER_STATE_FILE=/private/tmp/canary-b1/state.json \
  COURIER_ARTIFACT_DIR=/private/tmp/canary-b1/artifacts \
  nohup python3 -m server.app >/private/tmp/canary-b1/server.log 2>&1 &
curl -s http://127.0.0.1:8080/health   # → {"status":"healthy",...}, no auth (app.py:78-81)
```
Missing env → `SystemExit` refusal, nothing listens (`app.py:13-19`).

3.2 Goal JSON (exact template; `task_id`s pinned, `goal_id` minted by server):
```json
{"goal_text": "CANARY1 physical A->B",
 "workflow_plan": [
  {"task_id": "task-A", "target_agent": "linux", "instruction": "echo TASK_A"},
  {"task_id": "task-B", "target_agent": "linux", "instruction": "echo TASK_B"}]}
```
(`submit_goal` keeps submitter `task_id`, sets `status=QUEUED`, `attempts=0`: app.py:110-119.)
```sh
BODY='{"goal_text":"CANARY1 physical A->B","workflow_plan":[{"task_id":"task-A","target_agent":"linux","instruction":"echo TASK_A"},{"task_id":"task-B","target_agent":"linux","instruction":"echo TASK_B"}]}'
printf '%s' "$BODY" | shasum -a 256   # Task A/B exact bytes hash, recorded
curl -s -X POST http://127.0.0.1:8080/goals -H "Authorization: Bearer $K1" \
  -H 'Content-Type: application/json' -d "$BODY"  # → {"goal_id":"goal-<8hex>","status":"ACTIVE"}
```
Worker (omit `cost_class` → `"unknown"`, skips cost-routing decline; `linux`
capability matches `linux` target: app.py:283-294):
```sh
curl -s -X POST http://127.0.0.1:8080/workers/register -H "Authorization: Bearer $K1" \
  -H 'Content-Type: application/json' \
  -d '{"worker_id":"canary-mac-01","platform":"macos","capabilities":["linux"]}'
```

3.3 Claim A → `attempts` 1, fresh `attempt:1`/`dispatch-*` ids (app.py:328-347).
A-execution-count evidence: `state goals.<gid>.workflow_plan[0].attempts == 1`.

3.4 Artifact A (default expected name `courier_canary_task-A.txt`:
`integration_contract.py:59`; upload binds goal/task/attempt/dispatch/worker:
`artifact_store.py:23,171-198`):
```sh
printf 'CANARY1-TASK-A' > /private/tmp/canary-b1/courier_canary_task-A.txt
SHA=$(shasum -a 256 /private/tmp/canary-b1/courier_canary_task-A.txt | cut -d' ' -f1)
SIZE=$(stat -f%z /private/tmp/canary-b1/courier_canary_task-A.txt)
curl -s -X POST http://127.0.0.1:8080/artifacts -H "Authorization: Bearer $K1" \
  -H "X-Courier-Artifact: {\"goal_id\":\"$G\",\"task_id\":\"task-A\",\"attempt_id\":\"task-A:attempt:1\",\"dispatch_id\":\"$D_A\",\"worker_id\":\"canary-mac-01\",\"name\":\"courier_canary_task-A.txt\",\"sha256\":\"$SHA\",\"size\":$SIZE}" \
  --data-binary @/private/tmp/canary-b1/courier_canary_task-A.txt  # → 201 {"artifact_id":"art-<64hex>",...}
```
3.5 Result A (all 9 fields required: `integration_contract.py:114-135`):
goal_id, task_id, attempt_id, dispatch_id, worker_id, run_id (observable non-empty),
result_id (non-empty), status SUCCESS|FAILED, artifacts `[{"path","sha256","artifact_id"(,"size")}]`
(`artifact_store.py:134-147`). → `ACK_RESULT_RECEIVED`; resend identical →
`ACK_DUPLICATE`; otherwise 409 (app.py:360-370).
3.6 Verify A with VERIFIER key (`$K2`, `verifier_id` != worker, echo result_id +
artifacts, verdict PASS): `POST /tasks/verify` → `RECONCILED`, index 0→1
(app.py:469-514). B-automatic-start evidence: next `POST /tasks/claim`
returns `task-B` with NO new goal submit and NO human call.
3.7 Repeat 3.3–3.6 for B (artifact `courier_canary_task-B.txt`). DONE evidence:
`goal.status==DONE`, `current_step_index==2` (app.py:510-513).
3.8 human-relay=0 evidence (jq on the FRESH state file only):
```sh
jq -e '[..|objects|select(.status=="HUMAN_REQUIRED")]|length==0' /private/tmp/canary-b1/state.json
jq -c '.goals[$G]|{status,idx:.current_step_index,steps:[.workflow_plan[]|{task_id,status,attempts}]}' ...
```

## 4. Observation commands (read-only, anytime)

- `curl -s http://127.0.0.1:8080/health` (no auth)
- `curl -s http://127.0.0.1:8080/status -H "Authorization: Bearer $K1"`
- `curl -s http://127.0.0.1:8080/goals/$G -H "Authorization: Bearer $K1"`
- `curl -s http://127.0.0.1:8080/tasks/pending_verification -H "Authorization: Bearer $K2"`
- `cd $WT && python3 scripts/mac_worker/muse_supervisor.py status`
- `ls -la ~/Downloads/courier_work/muse_wall/canary/01/state/`

## 5. Abort conditions (operator stops, no retry-by-deleting)

Server: goal `BLOCKED` (B-FAIL verify / FAILED_TERMINAL: app.py:404-414,511-513);
`HUMAN_REQUIRED` anywhere (stale-worker quarantine: app.py:419-455; restart-loss:
app.py:192-204) → only `/tasks/<id>/resume {"action":"retry"}` requeues with
fresh attempt/dispatch; `force_success` is rejected (app.py:521-552).
Worker exec: `STOP` file, lock held, `MuseAdmissionBlocked`, timeout/output-limit
→ "ambiguous: reconcile, do not retry" (`daemon.py:360-372`); inner
`communicate(timeout=300)` (`daemon.py:305`).
Global: port occupant still present (P1); any `*.tmp`/evidence deletion is forbidden.

## 6. Restart-run checkpoint

Every run uses FRESH `COURIER_STATE_FILE` + `COURIER_ARTIFACT_DIR` (§1 P4) so fixed
`task-A`/`task-B` ids stay unique per run via the minted `goal_id`/attempt/dispatch.
Stale-worker rule: `last_seen` > 300 s → worker unavailable; `DISPATCHED` step of a
stale worker → `HUMAN_REQUIRED` + goal `BLOCKED`, never replayed (app.py:419-455,
`reclaimed_tasks` is always 0 by design). Heartbeat keeps worker alive:
`POST /workers/heartbeat {"worker_id":...}` (app.py:244-261).
Supervisor rerun after `RESULT_READY` is a no-op by design; after `STARTED`
interrupted mid-flight, reconcile `current_task.json` first (§2).

## 7. Prep gaps remaining

G1. P1 port conflict (foreign PID 69407) — needs operator decision; blocks §3 only.
G2. Operator keys (P3) — not discoverable by prep (and must not be).
G3. Physical `muse exec` output envelope — confirmable ONLY by executing Phase 0
    (`muse.stdout`/`muse.stderr`); doc explicitly forbids assuming a format
    (`docs/CANONICAL_MUSE_CANARY.md`). No gap closable by more reading.
No other preparation gap remains; every command above is grounded in the cited
candidate file:line. End of prep — no run started.
