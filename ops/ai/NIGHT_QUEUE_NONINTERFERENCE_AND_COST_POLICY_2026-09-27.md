# Night Queue Non-Interference + Cost Policy — 2026-09-27

Status: HARD OPERATING POLICY

## Why

Repeated broad repository reads, repeated unchanged analysis, and many workers rediscovering the same defects waste provider quota, PAYG spend, host resources, and human attention.

Courier overnight work must be queue-driven, durable, and non-interfering.

## Hard invariants

1. 50 queued tasks does NOT mean 50 physical windows.
2. A small admitted worker pool consumes a durable logical queue.
3. Every task has a concrete scope, inputs and done condition.
4. Broad repository census is forbidden unless an exact task explicitly requires it.
5. Completed task results are durable and survive context/session/account changes.
6. New sessions continue from queue state; they do not restart discovery.
7. Only one live worker may own a QID.
8. Workers write scratch evidence only to their own queue result/checkpoint paths.
9. Shared source checkout is read-only for queue workers.
10. Central Writer is not interrupted by queue workers.
11. MAX_HEAVY_JOBS=1 per host until newer proven policy changes it.
12. If no READY task exists, stop rather than inventing token-consuming work.

## Provider/account continuity

Courier should treat provider login/session as execution capacity, not project memory.

Project truth lives in the repo/ledger/queue result files.

If the user manually changes to another already-authorized account/session:
- preserve completed results;
- preserve open task identity;
- do not rerun completed work;
- resume the next READY QID.

Do not automate account rotation, CAPTCHA, 2FA, billing changes, or rate-limit evasion.

## Cost rule

Default:
MINIMUM_NECESSARY_READS=YES
NO_BROAD_READ_LOOPS=YES
NO_REPEATED_REPO_CENSUS=YES
NO_IDLE_ANALYSIS=YES
NO_DUPLICATE_REVIEW=YES

Every provider call should advance one concrete READY task or checkpoint a real blocker.

## Physical window admission

Logical queue depth may be 50 while active workers remain device-adaptive.

Use REQUESTED / ADMITTED / ACTIVE / GUARDED semantics from the device-adaptive motor policy.

Opening more windows is not progress if the same work is duplicated or the host becomes less responsive.
