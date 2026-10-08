# Continuity demo: interrupted agent work resumes, with a receipt

One command shows the core Courier promise on the real V1 code path:

```bash
python -m pip install -e ".[test]"
python scripts/continuity_demo.py run --out ./continuity-run
python scripts/continuity_demo.py verify ./continuity-run
```

What `run` does (about 30 seconds, loopback only, nothing leaves the machine):

1. Starts one V1 controller and one worker with the ledger idle tick in a fresh
   `COURIER_HOME` under the output dir.
2. Seeds one goal with two missions in the coordination ledger: A, then B (B depends on A).
3. The worker's own idle tick posts A. A completes.
4. The worker is killed hard (kill -9 / TerminateProcess) before A is fed back
   to the ledger and before B is posted.
5. The worker is started once more. It resumes: A is fed back, B is posted and
   completes. Nothing is done twice.
6. One more idle pass after DONE must change nothing.
7. All processes are stopped and `receipt.json` + `receipt.md` are written.

What `verify` checks, from the files alone (no process, no network, no writes):

- the journal hash chain is intact,
- exactly 2 tasks for 2 missions (0 duplicates), each with exactly one accepted
  result and one completion,
- exactly one ledger FINAL per mission, bound to its task and goal,
- the expected artifact digest of each unit is present,
- the recomputed evidence equals the receipt, and the receipt digest matches.

Editing the receipt, the ledger or the journal makes `verify` fail
(see `tests/test_continuity_demo.py`).

Limits, stated plainly: the demo uses the synthetic adapter. It proves the
contract (resume without duplicate work, checkable evidence), not a run with a
production AI provider.
