# Cursor Windows — Delivery & Continuation Full-Force V10
**Public prompt · 23 October 2026 · Safe bounded mission**

> Paste only into the **existing authorized Cursor Windows owner** session. This file does not initiate an agent, restart or scheduler.

## Starting evidence (verify again at execution time)

- PR [#838](https://github.com/happyhippovip/2026-courier/pull/838): last checked head `eb6393d52e726c26d59f0770097647813f1511a6`, open. CI on this new head was still running at snapshot.
- Previous Windows CI failure involved a queued task staying `DISPATCHED` and `current_task.json` persisting when high-resource-pressure heartbeats exhausted a mocked four-call HTTP budget before RESULT delivery.
- The PR isolated the delivery tests by monkeypatching the pressure probe; it did not modify the owned production `daemon.py`. A targeted resource-probe test remains.
- PR #842 independent verifier is a separate lane. Do not modify its tests or release scope without a valid lease.

## Paste into Cursor Windows

```text
👑🥊👊😎🪟🚀 COURIER SYMPHONY — WINDOWS DELIVERY / CONTINUATION V10
ROLE: CURSOR WINDOWS / RESPONSIBLE DELIVERY OWNER ONLY IF LEASE VERIFIED
END: 2026-10-24 20:00 Europe/Berlin. EXTRA SPEND: 0 EUR.

THIS IS A NEW, BOUNDED WORK ORDER, NOT AN AUTHORIZATION TO INVADE
ANOTHER LANE. DO NOT REPLAY COMPLETED WORKKEYS.

STEP ZERO:
Inventory existing active goal, timer, stop-hook, sender and lease.
Do not create a second sender. Check current #838 head and CI.
Verify actual file ownership; daemon.py belongs to separate open owners.
If no ownership for production file: only write isolated tests/proposals.

TRACK A — P0 DELIVERY UNDER PRESSURE:
CW10-01 Snapshot current integration and #838 SHA, CI, test baseline.
CW10-02 Deduplicate previously passed 8 targeted delivery/resource tests.
CW10-03 Reproduce red test with original pressure probe in isolated test.
CW10-04 Trace HTTP call sequence: claim, heartbeat, execute, result, ACK.
CW10-05 Reproduce >85% pressure plus four-call budget without real load.
CW10-06 Show whether RESULT is built but never POSTed.
CW10-07 Prove StopLoop cleanup behavior is truthful.
CW10-08 Verify current_task.json remains until accepted RESULT only.
CW10-09 Verify successful RESULT_ACK clears current_task exactly once.
CW10-10 Verify network timeout after POST before ACK does not rerun provider.
CW10-11 Ensure bounded retry/reconnect eventually submits retained RESULT.
CW10-12 Verify no duplicate dispatch or fake terminal success after restart.
CW10-13 Verify resource pressure check still works independently.
CW10-14 Check test-only pressure monkeypatch does NOT disable production guard.
CW10-15 Create one negative regression for pressure heartbeat starvation.

TRACK B — REPLAY / LEASE / COST:
CW10-16 Cross-home stale lease and live-worker fencing in disposable fixture.
CW10-17 Corrupt checkpoint/symlink/partial JSON must fail closed.
CW10-18 Crash during atomic write: no duplicate sender on reboot.
CW10-19 Test one fingerprint per unique workkey+sha+attempt.
CW10-20 Different fingerprints may progress, completed ones not replayed.
CW10-21 Invalid/expired owner nonce cannot commit success.
CW10-22 Unknown/malformed cost never converted to 0 EUR.
CW10-23 Local shell cost classification must be independently justified.
CW10-24 Quota exhaustion and explicit kill flag stop all new admission.

TRACK C — INTEGRATION AND DELIVERY:
CW10-25 Check PR #838 versus #836/#837/#842 for ownership overlap.
CW10-26 Run targeted tests, then relevant Windows+Linux CI where permitted.
CW10-27 For each failure report test, SHA, log, root cause, owner.
CW10-28 Keep all fixes only within current exclusive write lease.
CW10-29 Generate exact H10/Windows-worker handoff for other owner files.
CW10-30 If changes pass, create PR in own lane only where authorized.
CW10-31 Wait on CI via existing deduplicated notifier, no busy-poll.
CW10-32 Summarize remaining release gates without claiming HG-02 approval.

EXECUTION:
PASS -> next NEW meaningful test.
FAIL -> reproduce, minimal fix if owned, verify.
BLOCKED -> independent owned work or explicit handoff.
NO NEW SAFE TASK -> QUIESCENT_SAFE, not fake progress.
Checkpoint after 5 genuinely new tasks; no chat per test.
One heavy job per Windows host; at most 2 lightweight distinct read-only
reviewers if already available and genuinely zero extra cost.

SINGLE_WRITER=YES
HEAVY_JOB_LIMIT=1
UNKNOWN_COST=BLOCK
AUTONOMOUS_SPEND_LIMIT_EUR=0
NO_UNAUTHORIZED_MERGE=YES
REAL_TRADES=0
WALLET_SIGNING=NO

Do not start an unapproved service, scheduler, provider or paid agent.
A written 24-hour window does NOT create a background worker.
START WITH CW10-01 TO CW10-05, THEN CONTINUE THROUGH REAL NEW WORK.
```

Read the current project rules and private authoritative checkpoints first. This public text must never hold secrets, host-specific private paths, subscription usage, or recovery files.
