# Claude/Codex HIGH Fixed-Candidate Review — result

Reviewer: Claude Code (Sonnet 5), read-plus-record-only (application source untouched).
Scope: exactly the material diff of the fixed candidate over its stated base. No Ledger,
no remote-durability redo, no broadening.

REVIEWED_SHA=34b0a4264bf763bc2a78f761ffba36e47706b2cf
BASE_SHA=4c1e24ccc522042af826bc4c2b595daf85d097f9
VERDICT=BLOCKED

## What the candidate actually changes

Application-source diff (verified via `git diff 4c1e24... 34b0a426... --stat`; everything
else in the commit is `ops/ai/*.md` documentation, out of this review's scope):

- `server/app.py` — `/tasks/result` duplicate-ACK equivalence tuple extended from
  `(dispatch_id, result_id, status)` to
  `(dispatch_id, result_id, status, worker_id, attempt_id, artifacts)`.
- `scripts/integration_contract.py` — worker-submitted artifact evidence may no longer
  carry an `expected_sha256` key at all (removed from the allowed key-set; present ->
  `ContractError`).
- `scripts/courier_verifier.py` — the byte-hash check now reads the expectation from the
  **task** (`task["expected_artifacts"][path]` or `task["expected_sha256"]`), never from
  the worker-submitted artifact dict; a new coverage check fails the verdict when the
  task's own required paths aren't all present in the submitted result; `run_loop()`
  gained a per-task `try/except` so one malformed task can't stop the poll loop.
- `tests/test_artifact_upload_flow.py` — updated/added tests for the above.

## Required semantics (12), checked against this diff

1. task-owned expected survives = CONFIRMED — `courier_verifier.py` reads only
   `task["expected_artifacts"]`/`task["expected_sha256"]`.
2. correct bytes PASS = CONFIRMED — `tests/test_artifact_upload_flow.py::test_verifier_checks_expected_sha256` case 1.
3. wrong bytes FAIL = CONFIRMED — same test, case 2 (tampered server blob) and case 3 (stale task expectation).
4. worker expected rejected = CONFIRMED — same test, case 4: a worker-supplied
   `expected_sha256` in the artifact dict is now ignored/untrusted, and
   `integration_contract.py` rejects the key outright as invalid evidence shape.
5. worker omission cannot bypass expectation = CONFIRMED for the case that matters: the
   expectation source moved entirely off the worker-controlled artifact dict, so omission
   there is moot — the task-owned value is what's checked, if the task declares one.
6. no task expectation legacy-only = CONFIRMED-AS-DESIGNED: if a task declares no
   `expected_artifacts`/`expected_sha256`, no hash-equality gate runs, but the following
   `verify_uploaded_artifact()` step (server-recorded upload hash) still runs — this is a
   real, not a silent, narrowing of what "verified" means for such tasks, not a bypass of
   a promise the task never made.
7. malformed/ambiguous target FAIL = **NOT CONFIRMED — this is the blocker.** See below.
8. identical replay ACK_DUPLICATE = CONFIRMED — full-tuple match (incl. `artifacts` list
   equality) is required; a byte-identical resend of `/tasks/result` still returns
   `ACK_DUPLICATE`.
9. changed status rejected = CONFIRMED — `status` is in the compared tuple; a mismatch
   falls through to the existing `409 Conflicting result for already processed task`.
10. changed worker rejected = CONFIRMED — `worker_id` is now in the compared tuple (it
    was not, before this candidate); this closes the exact gap flagged in this session's
    prior Case-10 analysis.
11. changed attempt/dispatch rejected = CONFIRMED — `attempt_id` and `dispatch_id` are
    both in the compared tuple.
12. changed artifact result rejected = CONFIRMED — `artifacts` (the full list) is in the
    compared tuple; Python list/dict equality makes this an exact-content match, not a
    length or hash-of-hash check.

Other material items in this review's checklist (negative idempotency/FAIL-retry,
synthetic-proof fail-closed, RUN_2 A-vs-B contract, producer/verifier hash-chain
compatibility): **not touched by this diff** (no changes outside the four files above),
so this candidate neither fixes nor regresses them. Not treated as blockers of this
candidate; carried over unchanged from base.

## The blocker (semantic #7)

`scripts/courier_verifier.py::verify_artifacts()`, new line:

    expected_paths = set(task.get("artifacts") or [])

`task["artifacts"]` is only ever tested, in this candidate's own new/updated tests, as a
flat list of path strings (matching how `/goals`'s `workflow_plan` step definitions build
it — see `tests/test_artifact_upload_flow.py::setup()`). But the rest of this same
codebase (`scripts/mac_worker/daemon.py::collect_artifact_evidence`,
`scripts/windows_worker/daemon.py::build_result_payload`) explicitly and currently
supports `task["artifacts"]` entries being **dicts** (`{"path": ..., ...}`), via
`expected.get("path") if isinstance(expected, dict) else expected`. `server/app.py`'s
`/goals` endpoint does not normalize or reject either shape at intake — it stores
whatever the caller supplies verbatim.

Reproduced directly (not guessed) against this exact candidate SHA, checked out in an
isolated worktree, standard library only:

    task = {"task_id": "t1", "artifacts": [{"path": "A.txt"}]}
    result = {"artifacts": [{"path": "A.txt", "sha256": "0"*64}]}
    courier_verifier.verify_artifacts(task, result, local_verify=lambda *a: True)
    -> TypeError: unhashable type: 'dict'

Because `run_loop()` in this same candidate wraps per-task processing in a bare
`try/except Exception: log(...)` (added specifically to isolate one bad task from
stopping the poll loop — a real, separately-good fix, confirmed by
`test_verifier_poison_pill_isolation`), this exception is swallowed silently. No verdict
is ever posted to `/tasks/verify` for that task. The task does not FAIL — it hangs at
`RESULT_RECEIVED` forever, re-logging the same crash every poll cycle, with zero
operator-visible verdict beyond a log line. That is not the required "malformed/ambiguous
target FAIL"; it's an unresolved permanent stall, which is worse for RUN_1's
`NEXT_READY`/no-`HUMAN_RELAY`/no-silent-hang requirements than a clean FAIL would be.

CONFIRMED=CASE-10 worker/attempt/dispatch/artifact equivalence fix; task-owned
expected_sha256 fix; worker-omission-cannot-bypass fix; identical-replay ACK_DUPLICATE.
All reproduced by running the candidate's own targeted tests
(`tests/test_artifact_upload_flow.py tests/test_server_integration_contract.py
tests/test_integration_contract.py`, real run this review, not the reported figure):
52 passed, 0 failed.

BLOCKERS=`scripts/courier_verifier.py::verify_artifacts()` crashes (does not FAIL-close)
on a `task["artifacts"]` shape (list of dicts) that this same codebase's own worker code
treats as valid and currently supported; the crash is silently swallowed by the new
per-task exception guard in `run_loop()`, producing a permanent, invisible stall instead
of the required clean FAIL.

MIN_SAFE_CHANGE=In `verify_artifacts()`, build `expected_paths` the same way the rest of
the codebase already extracts a path from an `artifacts` entry, e.g.:

    expected_paths = {a.get("path") if isinstance(a, dict) else a for a in (task.get("artifacts") or [])}

No new normalization convention invented — reuses the exact idiom already used in
`scripts/mac_worker/daemon.py` and `scripts/windows_worker/daemon.py`. One line.

MIN_TESTS=Two additions to `tests/test_artifact_upload_flow.py`:
1. `task["artifacts"] = [{"path": "A.txt"}, {"path": "B.txt"}]` (dict-shaped), result
   missing `B.txt` -> assert `verify_artifacts(...) == "FAIL"` (not a raised exception).
2. Same dict-shaped task, result containing both with correct hashes -> assert normal
   PASS/expected-verdict behavior (proves the fix doesn't regress the already-passing
   flat-string-list case, which stays covered by the existing
   `test_verifier_rejects_omitted_expected_artifact`).

INVALIDATES=Nothing already-proven for the flat-string-artifact task shape (that evidence
stands: 52/52 targeted tests genuinely pass, re-run in this review). What's invalidated is
any claim that this candidate's verifier-side fixes are proven for *all* currently-valid
`task["artifacts"]` shapes — they are proven only for the flat-string shape exercised by
this candidate's own tests.

NEXT=WINDOWS_CENTRAL_WRITER_EXACT_DEFECT_ONLY

---
Generated by Claude Code (read-only application-source review; this result file is the
only write this review made).
