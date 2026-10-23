# Courier Symphony — Ledger Closure & Four-Hour Autonomous Engineering Contract
**Public engineering work contract · 23 October 2026 · window ends 24 October 2026 at 03:35 Europe/Berlin**

> This page is a scoped execution plan, **not** proof that the Ledger is complete, a valid writer lease, an instruction to merge, or an actual background scheduler. Recheck current PR/branch SHAs before testing. No secrets, private customer files or machine-specific paths belong here.

## Single objective / truth criterion

**Obtain reproducible negative and positive tests that establish one authorized ledger/controller task creation path with enforced cost admission, verified A→B→C artifact dependency, journal-bound RESULT_ACCEPTED proof, idempotent crash/replay, and one canonical writer, while leaving unknown spend at BLOCK.**

Set `LEDGER_DONE=VERIFIED` only after the actual integrated product path, not just an isolated worktree or mock, satisfies every gate below. `REAL_PROVIDER=UNPROVEN` until independently evidenced; no real paid provider or wallet signing is authorized.

Current relevant code on `integration/v1` at the time of creation:
- `courier_runtime/ledger_engine.py`: `cost_admission` and `LedgerEngine.submit` gate cost; `proof()` verifies an accepted journal result; `submit()` currently explicitly rejects `depends_on`.
- `courier_core/controller.py`: `Controller.create_task` accepts a task with `params` but has no equivalent mandatory cost-admission guard at this entry point. This is the documented F-C1 raw-controller bypass.
- PR [#528](https://github.com/happyhippovip/2026-courier/pull/528): real `depends_on` artifact input contract in controller/worker/adapter, but open and not mergeable in the last independent status read.
- PR [#836](https://github.com/happyhippovip/2026-courier/pull/836): provider DONE must not become FINAL on its own, including stale campaign state.
- PR [#837](https://github.com/happyhippovip/2026-courier/pull/837): A→B→C journal evidence; compare synthetic canaries against real input/dispatch behavior.
- PR [#843](https://github.com/happyhippovip/2026-courier/pull/843): test-only resource-pressure isolation. This is not a claim that the production daemon's RESULT_READY delivery is repaired.
- PR [#844](https://github.com/happyhippovip/2026-courier/pull/844): independent negative test candidate.

## Gates for the authorized L2/ledger owner

| Gate | Mandatory evidence | Failure must be red |
| --- | --- | --- |
| L2-01 F-C1 | A direct `Controller.create_task` call with missing or invalid cost is rejected **before** the journal's `TASK_CREATED`; `LedgerEngine.submit` and direct API share one enforceable policy | `params` missing numeric estimated cost; omitted, boolean, string, NaN, Inf, negative, or positive cost with limit=0 |
| L2-02 Admission architecture | One reused, cycle-free cost policy (if shared helper, avoid importing runtime LedgerEngine inside core controller); existing replay/idempotency and API compatibility understood and tested | Alternate raw controller path bypasses gate; rejected call leaves journal event |
| L2-03 Real dependencies | Controller and LedgerEngine correctly apply `depends_on` when authorized, while ensuring B claims only after verified A and C only after verified B | dependency missing, FAILED, CANCELLED, or human-confirmed without verifier; unknown downstream cost |
| L2-04 Byte proof | Worker obtains accepted upstream `RESULT_READY` artifact input and independently checks current disk bytes, digest, task/dispatch/attempt binding before dependent adapter execution | swapped artifact, mismatched digest, wrong task/attempt, deleted bytes |
| L2-05 Finality | Provider text DONE without matching `RESULT_ACCEPTED` is `NOT_PROVEN`; journal proof must identify same task, accepted result and dispatch; no stale image overwrites DONE | provider-only done; foreign receipt; replay after crash; duplicate FINAL |
| L2-06 One writer / restart | Ledger controller and host loop retain exactly one campaign/queue owner, lock/fencing and single journal writer | concurrent claim, stale nonce, restart split brain |
| L2-07 Integrated acceptance | Specific Linux and Windows negative tests fail on unfixed code, pass on authorized fix; integration branch CI and release gates confirmed by L1 | untested cherry-pick; isolated synthetic PASS falsely marked release |
| L2-08 Cost / authorization | No PAYG, real trades, wallet signing, auto-upgrade, arbitrary shell cost falsely declared 0, or unauthorized merge | unknown or externally billable action admitted |

**Migration trap:** A blanket cost guard in `Controller.create_task` can fail legacy tests and packet formats that omit costs. Authoritative L2 owner must choose and document compatibility migration without silently admitting unknown cost or introducing a second bypass. Do not mark the gate PASS merely because local test stubs supply `estimated_cost_eur: 0.0`.

## Distinct four-hour lanes — never two production writers

**GrokBot Windows Relay — coordinator and reports:** Read the existing authorized private ledger/workkey status, deduplicate completed work; keep the morning report task unchanged; collate new test results and exact current GitHub SHAs; prepare private owner handoffs. Do not create a second central dispatcher/claim store or authorize code merges. No new scheduler if existing routine already covers reporting.

**Google Antigravity Windows Upper — CI event watch:** Keep exactly one scoped `/schedule` task for CI/diff checks; confirm active task and next wake. If a short preexisting schedule exists, safely update in place or cancel before replacing. Up to eight half-hour wake-ups beginning at or after 00:00 local, stopping by 03:35. Each wake evaluates only changed SHA/check-status and reports new errors privately. Light CI-only; no simultaneous heavy tests.

**Cursor Windows Lower Left — technical owner only if lease valid:** Use `/goal` immediately, then `/loop` only if supported, one scoped bounded existing/new loop. Priority: single real F-C1 admission entry under L2 ownership; otherwise read-only proof and a minimal diff proposal. Respect Windows daemon and L2 ownership. Verify no worker live lease is stolen. Running changes exclusively in owned branch; no merges.

**Google Antigravity Windows Lower Right — independent ledger verifier:** Work with a distinct read-only negative test fixture/worktree; check actual Controller.create_task bypass, #528 dependency input vs LedgerEngine's depends_on refusal, accepted receipt binding, and crash replay. Avoid copying local mock validators as production proof. Do not run a second heavy test while the Cursor Windows process owns the heavy slot. If existing model quota is exhausted, preserve checkpoint and do not switch to paid API or a different account to evade a block.

## Completion artifacts

Existing private workkey/checkpoint locations are canonical and must be located by the authorized agent, not invented from this public plan.

For each new workkey store: `workkey_id`, `owner`, `scope`, `head_sha`, `test_file`, `red_command`, `green_command`, `exit_code`, `journal_proof`, `cost_verdict`, `lease_status`, `private_handoff_id`.

Coordinator produces a consolidated status `LEDGER_CLOSEOUT_2026-10-24` with each L2-01..08 marked `VERIFIED`, `FAIL`, `PENDING_L2` or `BLOCKED`. Never invent green tests, real-provider execution, recipient delivery, a routine registration or active runtime.

## Wake-up policy / silence

- One native recurring task **per distinct purpose per session**. A `/goal` is not a schedule. A text mention of `/schedule` or `/loop` is not proof that the command activated.
- `/schedule` belongs to its conversation; if full process/restart persistence is required, inspect a supported persistent automation separately and its exact billing before choosing it.
- End of each wake: no-op if same event fingerprint and no new authorized work; no repeated heavy tests or filler reports.
- **Deadline hard bound: 24.10.2026 03:35 Europe/Berlin**, and never extend automatically. One existing independent morning report may execute at its separately authorized time.

```text
SINGLE_WRITER=YES
HEAVY_JOB_LIMIT=1 per host
UNKNOWN_COST=BLOCK
AUTONOMOUS_SPEND_LIMIT_EUR=0
NO_UNAUTHORIZED_MERGE=YES
REAL_TRADES=0
WALLET_SIGNING=NO
```
