# Courier Symphony — Mac Agent Role Map: Cursor Ultra vs. Google Antigravity
**Public coordination reference | 23 October 2026 | Happy Hippo VIP / Courier Symphony**

This page distinguishes tools, sessions and responsibilities. It does **not** link accounts or grant access. It intentionally contains no private account identities, credentials, local personal paths, or private project-memory contents.

| Topic | **Cursor Ultra Mac / Cursor Projects** | **Google Antigravity Mac** |
|---|---|---|
| Main role | **Project coordinator + distinct Cloud Agent workers**; plan, dispatch and verify new tasks | **Independent Mac verification**, focused read-only integration checks |
| Where to paste instructions | Existing **Cursor Project coordinator** uses [Coordinator V1](./CURSOR_ULTRA_MAC_PROJECT_COORDINATOR_PROMPT_V1_2026-10-23.md); assigned worker uses [Worker V1](./CURSOR_ULTRA_MAC_WORKER_HANDOFF_PROMPT_V1_2026-10-23.md) | Existing **Google Antigravity Mac goal session** uses [Google Auto-Resume V2 in PR #839](https://github.com/happyhippovip/2026-courier/blob/docs/public-workflow-2026-10-23/docs/public/GOOGLE_MAC_AUTO_RESUME_PROMPT_V2_2026-10-23.md) |
| Goal | Cursor **Project objective** in coordinator; not proof of an active worker; do not assume Google's slash commands | Screenshot reports **existing** `/goal`; do not create another |
| Wake / schedule | Project **Listening** subscriptions may watch PR, CI and other real events; inspect actual subscription state before adding anything | Screenshots report **one existing 30-minute timer + GitHub events**; expiry/time must be checked in that Google session; no second timer |
| Repeat / hooks | Repository `.cursor/hooks.json` required to run project Cloud command hooks; not present on inspected `integration/v1` snapshot. A public document is not an installed hook. No recursive `stop` sender | Antigravity hooks/sidecars are separate platform features. Screenshot session reports no installed JSON hook; do not add one over existing timer |
| Parallelism | Coordinator can delegate **distinct** Cloud Agents when actual plan capacity, included quota and canonical scope permit; avoid a made-up 129-agent entitlement | At most **two** independent light local read-only reviewers in the reported Mac session; heavy job limit one and resource-pressure STOP |
| Code-writing | Only worker with valid exclusive canonical L1–L6 Writer-Lease; L1 controls merges; no creation of extra writers | Read-only by default, no foreign writer scopes; tests in isolated allowed workspace only |
| Historical status | Former A→B worker lane `abc-quiescent-2026-10-23-1942.md` stopped correctly: no eligible READY key, no lease | Separate active Goal/timer observed in screenshots; this does not imply Cursor worker or repo scheduler is running |
| Common project | `happyhippovip/2026-courier`; integration target `integration/v1` | Same repository, **different application, execution context, identity and workload** |

## Shared invariants

```text
SINGLE_WRITER=YES
HEAVY_JOB_LIMIT=1
UNKNOWN_COST=BLOCK
ADDITIONAL_SPEND_EUR=0
NO_UNAUTHORIZED_MERGE=YES
REAL_TRADES=0
WALLET_SIGNING=NO
```

One repo does **not** mean one session, one subscription, one account, or one shared quota. Cursor's advertised multiagent scaling is not evidence of how many concurrent Cloud Agents a specific account can use at no extra charge. Included quota is permitted only when verified, and on-demand charges/overages require separate user approval.

## Public 23 October snapshot: what is known

- `integration/v1` at `e9d7f1f29c26`, with [Courier v1 CI](https://github.com/happyhippovip/2026-courier/actions/runs/39986972647) and [Customer-Reality Gate](https://github.com/happyhippovip/2026-courier/actions/runs/39986972734) successful at this commit.
- PR [#835](https://github.com/happyhippovip/2026-courier/pull/835), [#836](https://github.com/happyhippovip/2026-courier/pull/836) and [#837](https://github.com/happyhippovip/2026-courier/pull/837) were still separate open candidate changes when last checked. A green PR CI alone does not prove real provider execution.
- PR [#838](https://github.com/happyhippovip/2026-courier/pull/838) proposes one-shot deduplication of repeated Antigravity follow-ups. Until merged, it is a *proposal*, not applied runtime behavior.
- PR [#840](https://github.com/happyhippovip/2026-courier/pull/840) proposes the optional `courier-safe-autonomy` Cursor Skill. Its PR explicitly says no stop hook is installed and auto invocation is off.
- [PR #839](https://github.com/happyhippovip/2026-courier/pull/839) already owns **Google Mac public documentation**. The Cursor updates here intentionally live in a **separate public documentation PR**, never overwrite the active Google docs.
- `courier_motor.yml` on this snapshot has `workflow_dispatch`, not an enabled cron; a project-level subscription or Google timer does **not** magically enable the GitHub motor.

## Stop and resume rule

A worker returning `QUIESCENT` on unchanged HEAD and absent lease is **correct**, not broken. The Project coordinator may only dispatch an actually distinct, eligible scope; subscriptions provide event-driven wakeups but not new writer permissions. If there is no meaningful new event, quietly remain idle. A second timer, stop-hook or artificial queue would recreate the historical prompt storm.

## References

- [Cursor Projects](https://cursor.com/docs/agent/projects)
- [Cursor Cloud Agents and hooks](https://cursor.com/docs/cloud-agent)
- [Cursor Automations](https://cursor.com/docs/cloud-agent/automations)
- [Google Mac public workflow from separate PR #839](https://github.com/happyhippovip/2026-courier/pull/839)

**Use only the prompt for the actual application/window you are operating.** Don't copy Google Mac's active Goal/Timer into Cursor Ultra or send Cursor Project coordination directives to a finished worker.
