# W03-T6 RESULT — Windows daemon instruction boundary (static, read-only)

File: scripts/windows_worker/daemon.py run path (:149-250) + claim loop (:330-403).
No edits (worker scope; Google writer active). Shell down, no execution.

## Provenance (OBSERVED)
- instruction arrives ONLY via server POST /tasks/claim (:371-376), executed
  :186-190 as ["powershell", "-Command", instruction].
- Trust boundary = server API auth (keyring/env key, FATAL+exit1 if missing
  :19-29). Task author = whoever holds a valid API key. No instruction
  allowlist/sandbox exists in the daemon — CORRECT BY WORKER DESIGN (CI-runner
  model), documented here, not a defect. Server-side submission auth is P3
  (not opened, out of scope).

## Corroborated GOOD (no action)
- argv-list exec, no shell=True (:188) → no local quoting injection.
- text=utf-8 errors=replace (:188), stdin=DEVNULL, CREATE_NEW_PROCESS_GROUP.
- Key never printed (single "(redacted)" line :31); P-2 already records the
  Windows hygiene-test gap (theirs, cited not claimed).

## Findings (owner triage)
W03-T6-1 (P2) RESULT OMITS THE EXECUTED INSTRUCTION (audit gap).
res_json (:229-243) carries stdout/stderr + all identity fields but no
instruction/argv echo. Post-hoc audit ("what ran for dispatch X?") must join
the server-side dispatch record; the durable result is not self-describing.
Suggest owner echo instruction (or its sha256) in res_json. Trivial + test.

W03-T6-2 (P2, TEST GAP, no code change) NOTHING PINS DAEMON INSTRUCTION HANDLING.
Repo-wide search: powershell tests cover ONLY wall-launcher scripts;
"trust_boundary" hits are archive/patch + ledger-label + dispatcher-path tests
— zero daemon-instruction coverage. Suggest one targeted test module (owner,
needs shell): argv-form pin (never shell=True), utf-8/OEM-error-text pin,
PROVIDER_WAIT-heuristic negatives (my T3-2 strings must NOT flip crafted
benign outputs), instruction-echo pin (after T6-1). Timeout-path cases are
WIN-01/W1 territory (theirs, NOT duplicated here).

## Adjacency (explicit non-dup)
- Daemon timeout PID-reuse window / unreaped kill / NameError path: WIN-01 W1
  summary (theirs; report file not yet on disk, NOT claimed here).
- PROVIDER_WAIT substring heuristic + partial-output loss: my W01-T3-2/T3-3
  (kept, distinct from W1 summary lines).
- Secret hygiene / worker_id default: P-2/P-3 (theirs, cited).

BRANCH=ledger-reconciliation-final (per Google checkpoint; git unverified, shell
down). SHA=UNKNOWN (no git). FILES_CHANGED=0. TESTS_PASSED=0. TESTS_FAILED=0
(shell down). RESULT_STATE=STATIC_FINDINGS_PARKED.
