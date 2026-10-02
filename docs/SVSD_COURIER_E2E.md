# SVSD — Courier End-to-End

**System Verification Specification Document (SVSD) for the Courier task plane:
goal submission → claim → execution → result → independent verification →
reconciliation, including the artifact-evidence chain and crash/stale recovery.**

Status: DRAFT v0.1 · Date: 2026-09-29
Observed baseline: branch `fix-cb1-new`, HEAD `4926a3725a34b44e9778836bc6ac2ae8e8df5ac2`
(`.git/HEAD` + loose ref; worktree-cleanliness unverified, no shell).
Method: static reads only. No command was executed; no test was run in this
session. All `file:line` citations below were read at this baseline.

## 1. Scope

In scope: the server-owned task plane — `server/app.py`, the worker contract
(`scripts/integration_contract.py`), the server-owned artifact store
(`scripts/artifact_store.py`), the native workers (`scripts/windows_worker/
daemon.py`, `scripts/mac_worker/daemon.py`), and the independent verifier
(`scripts/courier_verifier.py`).

Out of scope (referenced, not duplicated):

- Event envelope / GitHub↔Codex bridge: `docs/COURIER_PROTOCOL.md`.
- P3 cutover notes (partly stale, see §12): `docs/p3/README.md`.
- GitHub dispatch lane internals: `scripts/courier_github_dispatcher.py`.
- Operator acceptance criteria A–Z: `ops/ai/USER_ACCEPTANCE_*.md`
  (esp. `USER_ACCEPTANCE_D_PROOF_VERIFICATION.md` D-1/D-2/D-3).
- Wall/slots/supervisor and revenue lanes: not part of this spec.

Conformance language: MUST/MUST NOT = required by cited code; SHOULD = required
for a passing end-to-end run.

## 2. Actors, identities, authentication

- Two credentials, both from environment, both mandatory at server import:
  `COURIER_API_KEY` (workers) and `COURIER_VERIFIER_API_KEY` (verifier);
  missing → `SystemExit` (`server/app.py:15-21`).
- Insecure values (`""`, `dev-secret-key`, `your_secure_api_key_here`) → `503`;
  wrong/missing bearer → `401`. The verifier key MUST differ from the worker
  key, else `503` (`server/app.py:25-48`).
- Open route: `GET /health`. Verifier-only routes: `GET /tasks/
  pending_verification`, `POST /tasks/verify`, `GET /artifacts/<id>[/meta]`.
  Everything else needs the worker key (`server/app.py:83-96,443-455`;
  `scripts/artifact_store.py:162-216`).
- `worker_id` is operator-chosen (`config.json` / env). `verifier_id` MUST be
  a non-empty string different from the executing `worker_id`
  (`server/app.py:471-473`); the shipped verifier uses `VERIFIER-01`
  (`scripts/courier_verifier.py:15`).
- Workers MUST fail closed without a key: Windows raises
  `MissingCredentialError` before any network call
  (`scripts/windows_worker/daemon.py:32-35`); Mac exits 2
  (`scripts/mac_worker/daemon.py:421-423`).

## 3. State, persistence, concurrency

- Live state file: `server/state/central_state.json` (override:
  `COURIER_STATE_FILE`), shape `{goals, tasks, workers}` with `setdefault`
  repair on load (`server/app.py:15,59-67`).
- Every save is atomic: temp file + `flush` + `os.fsync` + `os.replace`
  (`server/app.py:69-76`). Artifact blobs/records likewise
  (`scripts/artifact_store.py:52-64,100-115`).
- All mutating routes hold a process-wide `threading.RLock`
  (`serialize_state_mutation`, `server/app.py:51-57`).
  Atomicity holds for ONE server process only; multi-worker serving is
  outside this spec.
- A background thread runs stale-reclaim every 60 s
  (`server/app.py:548-555`). The dev server listens on `0.0.0.0:8080`
  (`server/app.py:557-560`).

## 4. Lifecycle state machines

Task/step states (closed vocabulary, `scripts/integration_contract.py:16-24`):

`QUEUED → DISPATCHED → RESULT_RECEIVED → RECONCILED`
(all steps), plus `FAILED_VERIFICATION`, `FAILED_TERMINAL`, `HUMAN_REQUIRED`.

Result states: `SUCCESS | FAILED` (`scripts/integration_contract.py:25`).

Goal states: `ACTIVE` (claimable) → `DONE` (all steps reconciled) or
`BLOCKED` (terminal failure / failed verification / quarantine)
(`server/app.py:108-112,385-386,490-497,412-429`).

Worker-side durable phase (`current_task.json`), identical on both daemons:

`CLAIMED → STARTED → RESULT_READY → (delivered)` with `RELEASE_PENDING`
after a rejected result; Mac additionally uses transient `RESULT_PENDING`
(durable write gate) and `RECOVERY_BLOCKED` (storage failure)
(`scripts/windows_worker/daemon.py:137-141`;
`scripts/mac_worker/daemon.py:70-77,561-569,595-598`).

## 5. API contract (18 routes)

Server (`server/app.py`), worker key unless noted:

| Method + route | Success | Key errors |
|---|---|---|
| `GET /health` (open) | 200 `{status,time}` | — |
| `GET /status` | 200 counts | — |
| `POST /goals` | 200 `{goal_id, ACTIVE}` | 400 goal_text/planner, 503 planner |
| `GET /goals/<id>` | 200 `{goal, tasks}` | 404 |
| `GET /workers` | 200 map | — |
| `GET /walls` | 200 BLOCKED goals | — |
| `POST /workers/register` | 200 `REGISTERED` | 400 worker_id |
| `POST /workers/unregister` | 200 `UNREGISTERED` (sticky) | 404 |
| `POST /workers/heartbeat` | 200 `OK` | 404 |
| `POST /tasks/claim` | 200 `{task}` or `{task: null}` | 404 worker, 400 contract |
| `POST /tasks/result` | 200 `ACK_RESULT_RECEIVED` / `ACK_DUPLICATE` | 400 invalid, 409 conflict/late |
| `POST /tasks/reclaim_stale` | 200 `{reclaimed_tasks: 0, quarantined_tasks: n}` | — |
| `GET /tasks/pending_verification` (verifier) | 200 `{tasks}` | — |
| `POST /tasks/verify` (verifier) | 200 `{status}` / `ACK_DUPLICATE` | 400 guards, 404, 409 |
| `POST /tasks/<id>/resume` | 200 `RESUMED` | 400 status/action, 404 |

Artifact store (`scripts/artifact_store.py:171-216`):

| Method + route | Success | Key errors |
|---|---|---|
| `POST /artifacts` (worker) | 201 record | 400 meta/binding/name, 409 not DISPATCHED, 413 size |
| `GET /artifacts/<id>/meta` (verifier) | 200 record | 400 id, 404 |
| `GET /artifacts/<id>` (verifier) | 200 bytes | 404 |

## 6. Claim rules (`server/app.py:264-330`)

1. Worker MUST be registered, MUST NOT hold `current_task`, MUST be
   `available`; else `{task: null, reason: WORKER_BUSY}`.
2. Only `ACTIVE` goals are scanned, and only the head step
   (`workflow_plan[current_step_index]`) in `QUEUED` is claimable —
   later steps are never dispatched early.
3. Capability match (target substring × capability exact):
   `github→github`, `mac→macos`, `windows→windows`, `linux→linux`,
   `antigravity→antigravity` (`server/app.py:289-295`).
4. `CostGate.evaluate_spend_request` MUST allow; a task lease MUST be
   acquired (`server/app.py:296-305`).
5. The claim mints `attempt_id` (`<task>:attempt:<n>`) and a fresh
   `dispatch_id`, sets `run_id`/`result_id` to null, stamps
   `target_capability`, and runs `prepare_task` (`ContractError` → 400).
   Then: step = `DISPATCHED`, worker busy, task mirrored to `state["tasks"]`.
6. Specified subtlety: matching is substring-based, but `prepare_task`
   accepts `target_capability` ONLY if exactly `github|mac|windows|linux`
   (`scripts/integration_contract.py:51-52`; keys at `:26-31`), because
   the server stamps the full target string (`server/app.py:314`).
   De-facto, `target_agent` MUST be one of those four tokens.

## 7. Result rules (`server/app.py:332-395`)

1. Exact resend of the stored result (equal `dispatch_id`, `result_id`,
   `status`, `worker_id`, `attempt_id`, `artifacts`) → `ACK_DUPLICATE`.
2. Any other result for `RECONCILED | FAILED_TERMINAL | RESULT_RECEIVED |
   FAILED_VERIFICATION` → `409`. Result for a non-`DISPATCHED` task or
   from a foreign worker → `409` / `400`.
3. Payload MUST pass `validate_durable_result`: required fields `goal_id`,
   `task_id`, `attempt_id`, `dispatch_id`, `worker_id`, `run_id`,
   `result_id`, `status`, `artifacts` (+ preserved `run_attempt` for GH
   retries); identity fields MUST equal the dispatch; `SUCCESS` REQUIRES
   non-empty artifact evidence; artifact entries MUST be
   `{path, sha256}` or `{path, sha256, artifact_id, size}` with safe
   relative paths and 64-hex fingerprints
   (`scripts/integration_contract.py:114-172`).
4. Every `artifact_id` reference MUST pass `check_reference`: record
   exists, all five binding fields (`goal_id, task_id, attempt_id,
   dispatch_id, worker_id`) equal the task, name/hash/size match
   (`scripts/artifact_store.py:23,133-144`).
5. `SUCCESS` → `RESULT_RECEIVED` (waits for independent `/verify`).
   `FAILED` with attempts < 3 → requeue (`QUEUED`, worker cleared);
   else `FAILED_TERMINAL` + goal `BLOCKED`. Step mirror and worker
   release happen on every accepted result.

## 8. Artifact-evidence chain

- Upload (`POST /artifacts`, worker key): task MUST be `DISPATCHED`
  (else 409); all binding fields MUST match; the name MUST be expected
  by the task; bytes MUST match claimed sha256/size (else 400); over
  `COURIER_ARTIFACT_MAX_BYTES` (default 16 MiB) → 413. Success → 201
  with a deterministic id `art-<sha256(binding+name+hash)>`, making
  re-upload idempotent (`scripts/artifact_store.py:43-49,171-198`).
- Layout: `blobs/<sha[:2]>/<sha>` (content-addressed) +
  `records/<artifact_id>.json` (write-once; conflicting rewrite → error)
  under `COURIER_ARTIFACT_DIR` (default `server/state/artifacts`)
  (`scripts/artifact_store.py:10-12,72-116`).
- Verifier re-hashes the SERVER copy and checks every binding
  (`verify_uploaded_artifact`, `scripts/artifact_store.py:147-159`).
  Artifacts from `mac|windows` targets MUST be uploaded — the verifier
  never opens a remote worker path and FAILs path-only remote evidence
  (`scripts/courier_verifier.py:69-70,87-89`).
- Config gate: upload is opt-in on BOTH daemons
  (`COURIER_ARTIFACT_UPLOAD=1` or config `ARTIFACT_UPLOAD=true`;
  default OFF). A default-config Mac/Windows `SUCCESS` therefore ends
  as `FAILED_VERIFICATION` + goal `BLOCKED` (see §12.3).

## 9. Worker behavior

Common: poll loop (register → heartbeat → claim only when idle →
execute → upload → deliver → delete marker); single-instance lock per
state dir (Windows: `msvcrt LK_NBLCK`; Mac: `flock`, exit 3 if held);
result POST retried on transport/5xx only — a 4xx is final
(`scripts/windows_worker/daemon.py:266-371`;
`scripts/mac_worker/daemon.py:410-602`).

Windows (`scripts/windows_worker/daemon.py`):

- Executes the instruction as native PowerShell via base64
  (`-EncodedCommand`, UTF-8 console), 600 s `communicate` timeout;
  exit 0 = `SUCCESS`, else `FAILED` (`:200-237`).
- Observed: on timeout NO kill/terminate primitive runs in the file —
  the child is orphaned while the result is `FAILED`
  (`:214-223`; zero kill primitives in file). See §12.1.
- `run_id` = child PID string (`"win-native"` if spawn failed).
- Poll 10 s; result POST ≤5 attempts with `2^attempt` backoff; heartbeat
  404 → re-register; CPU > 85% pauses claims 60 s.

Mac (`scripts/mac_worker/daemon.py`):

- Modes: `NATIVE` (6-action allowlist; `echo`/`git_status` implemented),
  `ANTIGRAVITY` (`agy -p …`, 300 s), `MUSE` (adapter-built argv, orphan
  guard, 30 s in-task heartbeat, timeout/output cap, process-group
  cleanup — ambiguous outcomes raise instead of retry)
  (`:250-390`).
- Registers `capabilities: [macos, linux, antigravity]`
  (`:468-476`); keychain-first credentials with env override
  (`:21-46`); poll 5 s; result POST ≤8 attempts; `SIGTERM`/`SIGINT`
  exit cleanly (`:604-612`); `COURIER_WORKER_ONE_TASK=1` exits after
  one delivery for slot supervision (`:417,591-593`).

## 10. Restart / crash recovery (at-most-once execution)

Both daemons persist `current_task.json` BEFORE the effect can happen
and obey the marker after a restart:

- `CLAIMED` → execution never began → safe to run.
- `STARTED` → effects possible → NEVER re-run; re-register with
  `current_task: null`, delete the marker; the server quarantines the
  server-side task to `HUMAN_REQUIRED` (`WORKER_RESTARTED_AND_LOST_STATE`,
  goal `BLOCKED`) (`server/app.py:199-212`).
- `RESULT_READY` → payload final → only (re)deliver, never recompute
  (server answers `ACK_DUPLICATE` on redelivery).
- `REJECTED` (4xx) → snapshot to `rejected_result_<task>.json`, persist
  `RELEASE_PENDING`, then release — never `WORKER_BUSY` forever.

Stale workers: `last_seen` older than 300 s → unavailable; their
`DISPATCHED` steps in `ACTIVE` goals are quarantined to `HUMAN_REQUIRED`
(`STALE_WORKER_EFFECT_AMBIGUOUS`, goal `BLOCKED`); leases released.
The endpoint hardcodes `reclaimed_tasks: 0` — nothing is ever replayed
(`server/app.py:398-441`).

## 11. Verification and resume

- `GET /tasks/pending_verification` lists exactly `RESULT_RECEIVED`
  tasks (`server/app.py:443-451`). The verifier polls every 5 s, needs
  `COURIER_VERIFIER_API_KEY`, and posts `{task_id, verifier_id,
  result_id, verdict, artifacts}` (`scripts/courier_verifier.py:94-151`).
- `/tasks/verify`: re-verify of `RECONCILED` with the same `result_id` →
  `ACK_DUPLICATE`, else 409; non-`RESULT_RECEIVED` → 409; independent
  `verifier_id`, `result_id` match, artifact-list equality, and
  `verdict ∈ {PASS, FAIL}` are all enforced (400 otherwise).
  `PASS` → `RECONCILED` + step mirror + `current_step_index+1`
  (`DONE` when the plan is exhausted); `FAIL` →
  `FAILED_VERIFICATION` + goal `BLOCKED`
  (`server/app.py:453-502`). The server trusts the verifier's verdict
  after the equality gates — evidence checking is the verifier's job
  (§8), including the deterministic `revenue_safety_audit` lane
  (`scripts/courier_verifier.py:112-131`).
- `POST /tasks/<id>/resume`: allowed ONLY from `HUMAN_REQUIRED |
  FAILED_VERIFICATION | FAILED_TERMINAL`. `retry` requeues task+step
  (records `resumed_from`), clears the worker, re-`ACTIVE`s the goal;
  the next claim mints a fresh attempt/dispatch identity so superseded
  results can no longer bind. `force_success` is REFUSED (400) — success
  requires a bound DurableResult plus an independent verifier
  (`server/app.py:505-537`).
- `unregister` is sticky: only explicit re-`register` returns a worker
  to service (`server/app.py:229-262`).

## 12. Specified deltas and open points (observed, not changed)

Recorded behavior / doc drift found while writing this spec. Changing any
of them is an owner decision, not part of this document.

1. **Windows timeout orphans the child.** `run_task` has `communicate
   (timeout=600)` with a bare `except → FAILED` and no kill primitive
   (`scripts/windows_worker/daemon.py:214-223`). A timed-out task's
   effect window stays open while the server may already retry.
2. **`docs/p3/README.md` is stale.** It says the server "needs the
   patch" (`:4-5`), but the artifact blueprint is live
   (`server/app.py:78-81`), as is the idempotency series
   (`ACK_DUPLICATE`, step mirror, `force_success` refusal — §7/§11).
   The `.patch` files are dead artifacts; the doc's canary gate (one
   Mac + one Windows canary → `RECONCILED`, `:28-29`) still stands.
3. **Upload default OFF vs verifier FAIL.** Both daemons default
   `COURIER_ARTIFACT_UPLOAD` to off while the verifier FAILs
   non-uploaded Mac/Windows evidence (§8). Steady state at default
   config: remote `SUCCESS` → `FAILED_VERIFICATION`. Flip the default
   or gate rollout on the flag — owner call.
4. **P3 tests pin the patch series, not the live file.** Both P3 suites
   run against a temp-copy patched server (`tests/
   test_artifact_upload_flow.py:1-3`, `tests/
   test_p3_server_idempotency.py:1-2`, via `tests/p3_preview.py`).
   Live-file coverage comes from `tests/
   test_server_integration_contract.py` (monkeypatched keys, `:15-19`)
   and the daemon suites (`tests/test_mac_worker_contract.py`, `tests/
   test_mac_worker_recovery.py`, `tests/test_windows_worker_contract.py`,
   `tests/test_windows_worker_binding.py`, `tests/
   test_windows_worker_credentials.py`; existence verified this session) —
   pass/fail was NOT established here.
5. **Server emits no logs.** No logging/prints in `server/app.py`;
   external evidence checkers that grep server logs can never pass
   (previously noted in `ops/ai/USER_ACCEPTANCE_D_PROOF_VERIFICATION.
   md:28-32`). The `/status` + `GET /goals/<id>` endpoints are the
   observable surface (`server/app.py:87-96,158-166`).
6. **Minor:** `/tasks/verify` assumes the goal row exists (no 404 path,
   `server/app.py:489`); `/tasks/reclaim_stale` scans `ACTIVE` goals
   only (`:412-413`); unknown `target_agent` tokens 400 via `prepare_task`
   after matching (§6.6); `GET /health` and `GET /status` have no test
   pins observed in this pass.

## 13. Verification of THIS document

- Every behavioral sentence cites a file+line read in this session at the
  baseline above. Unread files are cited as references only
  (`scripts/courier_github_dispatcher.py`, `tests/p3_preview.py`,
  `scripts/mac_worker/muse_adapter.py`, `runtime_state.py`).
- Acceptance bar for the system (not redefined here):
  `ops/ai/USER_ACCEPTANCE_D_PROOF_VERIFICATION.md` D-1 (one proof
  record per claim), D-2 (readiness derived, never hand-set), D-3 (no
  DONE for unexecuted runs).
- Physical gates still open at write time: Mac + Windows canary to
  `RECONCILED` (§12.2); any runtime pass/fail (shell unavailable).

## 14. Document control

- v0.1 DRAFT (2026-09-29): initial spec from static reads. Author: Muse
  session `01a0ee09`; Shell-Runner down (sandbox setup), 0 files
  executed, 0 tests run, 0 commits.
- Suggested next: owner review of §12, then Mac/Windows canary per
  `docs/p3/README.md:28-29` with proof records per D-1.
