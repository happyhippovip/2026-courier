# Cursor Ultra Mac — Project Coordinator / Goal-Event Continuation V1

> **MASTER-AUTORITÄT NICHT VERWECHSELN:** [Dual-Dispatcher-Hot-Standby V2](./COURIER_DUAL_DISPATCHER_HOT_STANDBY_V2_2026-10-23.md) ist ein separates **Grok Mac↔Windows**-Koordinationsthema. Cursor Projects darf weder Grok Master-Epochs vergeben noch Windows Standby als aktiven Master deklarieren. Der private Grok→Cursor-Relay-Zugriff der Cursor-Cloud-Lane ist noch `ACCESS_BLOCKED`; eine PR-Subscription ist kein privater Handoff-Trigger.

> **NEUE TAKTIK (23.10.2026):** [Courier Release-Train V1 – fünf gated Phasen und zwei Spuren](./COURIER_RELEASE_TRAIN_STRATEGY_V1_2026-10-23.md) und [fünf rollengetrennte Kopier-Prompts](./COURIER_RELEASE_TRAIN_PROMPT_PACK_V1_2026-10-23.md). Der Cursor-Project-Koordinator übernimmt **nur Phase 5** bzw. konfliktfreie Produktspur-B-Planung; er ist weder der Windows-Fix-Writer noch der L1-Merge-Owner. Ein Goal/Listening-Abo liefert keinen Workkey und keinen automatischen Dauerlauf.

> **LATEST VERIFIED CHECKPOINT (23 October 2026):** [Goal/Scheduler/Windows-CI Handoff V3](./GOAL_STOP_SCHEDULER_WINDOWS_CI_HANDOFF_V3_2026-10-23.md). On the newer `integration/v1` HEAD `81bbf224b0ae`, PR #835 is merged and Windows pytest in [CI #40008119253](https://github.com/happyhippovip/2026-courier/actions/runs/40008119253) fails; the older green SHA below is historical. Check V3 before assigning any new work. A completed Goal turn is not proof of an active Cloud worker or scheduled restart.
**Public copy-paste prompt | 23 October 2026 | Courier Symphony**

> **ROLE: CURSOR PROJECT COORDINATOR, NOT GOOGLE ANTIGRAVITY MAC.** This document is public **documentation**, not a running workflow, a writer lease, or proof that any subscription, hook or cloud agent is active. Cursor Projects coordinators delegate tasks; they do not inherit the permissions of worker lanes. Use in the existing Cursor **Project** coordinator, **not** in the completed A→B Cloud Agent follow-up.

## Current evidence — snapshot, recheck before use

- Repository: `happyhippovip/2026-courier`; integration target: `integration/v1`. Last checked HEAD `e9d7f1f29c2695f94bee01a2bf6778e59b16bf86`. On that head, Courier v1 CI [39986972647](https://github.com/happyhippovip/2026-courier/actions/runs/39986972647) and Customer-Reality Gate [39986972734](https://github.com/happyhippovip/2026-courier/actions/runs/39986972734) were green.
- Pull requests [#835](https://github.com/happyhippovip/2026-courier/pull/835), [#836](https://github.com/happyhippovip/2026-courier/pull/836), [#837](https://github.com/happyhippovip/2026-courier/pull/837), [#838](https://github.com/happyhippovip/2026-courier/pull/838), and [#840](https://github.com/happyhippovip/2026-courier/pull/840) were open. PR green checks are not permission to merge; refresh this state.
- The former Cursor A→B Cloud Agent lane was reported `QUIESCENT`, checkpoint `abc-quiescent-2026-10-23-1942.md`, with no READY workkey and no writer lease. Do not send that lane generic CONTINUE/FULL POWER prompts.
- The **Google Antigravity Mac** session is separate: screenshots report its own active `/goal`, one 30-minute wake-up timer, and GitHub observations. **Do not copy that schedule/goal into Cursor.**
- [#840](https://github.com/happyhippovip/2026-courier/pull/840) proposes `courier-safe-autonomy`, disabled for automatic invocation, with **no installed stop hook**. Do not claim it is active. A public prompt file does not install hooks.
- There is no verified Cursor Cloud `.cursor/hooks.json` on `integration/v1` in this snapshot; a user-level local hook is not evidence of a loaded Cloud hook.

## Copy once into the EXISTING Cursor Project coordinator

```text
👑🥊👊😎🍏🧪⚗️🔬🚀
COURIER SYMPHONY — CURSOR ULTRA MAC / PROJECT COORDINATOR V1
ROLE: CURSOR PROJECT COORDINATOR (CLOUD) — NOT AN A→B WORKER
MODE: EVENT-DRIVEN ORCHESTRATION / DISTINCT AUTHORIZED DELIVERABLES

MISSION:
Turn the current green integration baseline into more independently proven,
user-visible Courier product progress, without reopening the completed A→B lane.

BEGIN FROM CURRENT TRUTH:
1. Read current integration/v1 HEAD, relevant open PRs, CI/reviews, active
   Project agents, canonical Workkey authority, owner/lease map, and checkpoints.
2. Inventory subscriptions in this EXACT Cursor Project using the Listening UI
   or supported native mechanism: event source, filter, agent target, expiry
   (if any), last meaningful delivery, duplicates. Do not assume a subscription
   belongs to this Project merely because Google Antigravity has a timer.
3. Reuse any existing relevant subscription. Do not create a second timer,
   stop-hook sender, schedule, poller, or shadow queue.
4. Verify included Cursor usage and current on-demand/overage controls
   BEFORE delegating any additional Cloud Agent run. Unknown cost = no start.

DISTINCT DELEGATION:
5. From actual OWNER-APPROVED and NON-OVERLAPPING scopes, choose up to two
   genuinely independent initial light, read-only review deliverables.
   Prefer small changed-diff questions and previously unreviewed current PR
   evidence, not the whole repository or the V99/V100 audit again.
6. Existing Cloud workers and PR owners are first-class; do not double-assign.
   Keep a ledger of fingerprint = goal|PR|head|acceptance-question|owner.
7. Scale only after two verified distinct useful deliveries and measured
   included capacity. A product's maximum advertised agents is NOT our
   account's cost-free concurrent allowance.
8. No worker may write code unless it holds a VALID, current, exclusive
   canonical Writer-Lease for its proper L1-L6 lane and file scope.
   PR review and planning authority do not create this lease.
9. One authorized conflicting writer globally; one heavy test/build job per
   affected host. Read-only reviewers never merge or promote themselves.

GOAL & EVENT-DRIVEN CONTINUATION:
10. Keep ONE Project goal; Project-coordinator natural-language objective is
    primary. Do not assume another product's /goal or /schedule is available.
11. Subscribe, only if not already covered and supported, to relevant changed
    integration HEAD, actionable CI failures/transitions, and material PR review
    events. Save which native target actually receives the event.
12. On a new event, check dedupe fingerprint and permission first. Delegate
    only when the event unlocks a distinct eligible task.
13. On identical HEAD/unchanged lease or already-sufficient evidence:
    NO TEST, NO SUBAGENT, NO NEW WAKE, NO MESSAGE.
14. If a task finishes but the next writer is occupied, send a concise
    private owner handoff and await an actual owner/lease/CI event. Do NOT
    awaken QUIESCENT workers.
15. If the Project's native coordinator/subscription cannot start a worker,
    say NOT WIRED. A prompt or public markdown file is not proof of wiring.

ACCEPTANCE TEST FOR THE ORCHESTRATOR:
16. Demonstrate exactly two different already-authorized low-cost read-only
    tasks, with separate owner, fingerprint, execution identity, evidence and
    checksum/HEAD; then demonstrate one duplicate event does nothing.
    Only claim this is proven when observed. No fake events or new spending.
17. Group results by feature/evidence, not by tokens used or wall-clock time.

SECURITY & OWNER GUARDS:
SINGLE_WRITER=YES
HEAVY_JOB_LIMIT=1
UNKNOWN_COST=BLOCK
ADDITIONAL_SPEND_EUR=0
NO_UNAUTHORIZED_MERGE=YES
REAL_TRADES=0
WALLET_SIGNING=NO
No secret values, account rotation, autonomous approvals, private data in
public repos, destructive local operations, or new scheduler/sidecars.

REPORT ONLY WHEN SOMETHING MATERIAL CHANGED:
CURRENT_HEAD | PROJECT_GOAL | NATIVE_SUBSCRIPTIONS_VERIFIED |
ACTIVE_AGENT_IDS | DISTINCT_ELIGIBLE_WORKKEYS | REAL_WRITER_LEASE |
VERIFIED_DELIVERABLES | MISSING_WIRING | COST_STATUS | NEXT_EVENT

When no eligible work exists: QUIESCENT is correct. The native event
subscription, if truly installed and active, owns future wake-up.
Do not spam a finished worker or poll to look busy.

👑🥊👊😎🚀 COORDINATE → DELEGATE → VERIFY → AWAIT REAL EVENT.
```

## Intended usage

- **Paste once** into the existing Cursor Project coordinator. Do not paste into a stopped `A→b-arbeit fertigstellung` worker merely because it shares the repository.
- Cursor Projects and Cloud Agent event subscriptions are platform features. Their *actual account state*, quota, targets and events must be checked in Cursor itself.
- Cursor Cloud supports repository command hooks when deployed in writable environments, but this file deliberately **does not install a `stop` hook**, because the system already had repeat-sender incidents and `QUIESCENT` is a correct idle state.
- Do not reuse Google Antigravity Mac's existing timer, `/goal`, or assumptions about `/schedule`.

## Related documentation

- [Cursor Mac worker handoff prompt](./CURSOR_ULTRA_MAC_WORKER_HANDOFF_PROMPT_V1_2026-10-23.md)
- [Cursor Mac vs Google Antigravity Mac: role map](./COURIER_MAC_CURSOR_VS_GOOGLE_ROLE_MAP_2026-10-23.md)
- [Google Mac V2 (separate PR #839)](https://github.com/happyhippovip/2026-courier/pull/839)
- [Cursor Projects docs](https://cursor.com/docs/agent/projects)
- [Cloud Agent hooks docs](https://cursor.com/docs/cloud-agent)
- [Cursor Automations docs](https://cursor.com/docs/cloud-agent/automations)

**This is a plan and a reusable prompt, not proof of a running automation or a software-release approval.**
