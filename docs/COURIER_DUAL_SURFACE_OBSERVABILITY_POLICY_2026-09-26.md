# Courier Dual-Surface Observability Policy — 2026-09-26

Status: product/architecture guardrail for AFTER the physical core proof.

## Rule 5 — DUAL_SURFACE_TRUTH

Courier presents one reconciled truth through two views.

This does **not** mean there is literally one storage file. The UI truth must be derived from the currently authoritative server state plus the matching worker/slot/process observations, joined only when task/attempt/dispatch/worker/slot identities agree.

If observations conflict or are stale, the UI must show UNKNOWN / WAITING. It must never pick the "greener" source.

### User surface

Beautiful, calm, featherlight. It answers only:

- What did I ask for?
- What is happening now?
- What is verified?
- What finished?
- Does Courier need me?
- What happens next?
- What capacity is available?

No infrastructure dashboard by default. No fake activity. No animation that substitutes for evidence.

### Owner / advanced surface

Optional detail drawer that gives EYES, not a control cockpit.

Useful fields may include:
- task / step identity
- server state
- worker phase
- why this state / blocker / waiting-for
- attempts / attempt identity
- dispatch and result identity
- verification verdict and method
- worker / host / slot state
- governor state when durably available
- last error
- candidate SHA / server fingerprint when runtime-bound evidence exists
- proof level only when derived from real acceptance evidence

Global owner checks:
- Is Courier progressing?
- Where is it stuck?
- Why?
- What should happen next?
- Does UI disagree with runtime?
- Was work retried or replayed?
- Is a result only reported or actually verified?
- Which host/worker currently owns the step?

## Code-grounded observation sources

Current code review identified these sources:

- Goal/workflow/current step: server goals + workflow_plan + current_step_index.
- Task/attempt/dispatch/result/verification: server tasks[task_id].
- Local execution phase and undelivered RESULT_READY: slot state/current_task.json.
- Process binding: slot state/muse_process.json.
- Slot status/restart control: slots.json.
- Governor decision/resource measurement: live CapacityGovernor object; not fully persisted.
- checkpoint.json may describe previous worker context but is **not** scheduler/runtime authority.

Server state + slots.json alone are insufficient for an honest live UI.

A local checkpoint task ID can describe the last task rather than a currently active task, so it must not be used as active-task truth without matching live identity evidence.

## State truth rules

- RESULT_RECEIVED means reported, not independently verified.
- RECONCILED + verification.verdict=PASS for the matching result means the server accepted a verifier PASS.
- A PASS proves only the property actually implemented by that verifier.
- EXACT_CONTENT and INTEGRITY must remain visibly distinct verification methods.
- Until the final trusted-hash correction is physically accepted, do not present current B1/B2 content verification as independent exact-content proof.
- "Working" requires real execution/process evidence plus matching identities; heartbeat alone is insufficient.
- Contradictory or missing evidence must display UNKNOWN / WAITING, never reassuring progress.
- "Recovered" requires real recovery evidence.
- Human intervention is shown only for an explicit gate or ambiguous-effect state.

## Honest UI-state mapping

Supported / partially supported mappings:

- QUEUED -> "wartet auf Start"
- DISPATCHED + matching CLAIMED -> "startet"
- DISPATCHED + matching STARTED + current process evidence -> "arbeitet" (PARTIAL)
- local RESULT_READY before delivery -> "Ergebnis liegt vor / wird zugestellt"
- RESULT_RECEIVED -> "gemeldet / wird geprüft"
- RECONCILED + matching verifier PASS -> "geprüft" (name the actual verification method/property)
- FAILED_VERIFICATION -> "Prüfung fehlgeschlagen"
- HUMAN_REQUIRED / recovery blocker -> "braucht dich"
- resource-blocked state -> "wartet auf Rechnerleistung" only at a generic level unless a durable governor reason is available
- conflicting/missing bindings -> "UNBEKANNT"

Not honestly derivable today:

- "arbeitet erfolgreich" from slot RUNNING alone
- "Prüfung läuft gerade" from RESULT_RECEIVED alone
- "B automatisch gestartet" from current_step_index alone
- a specific RAM/resource cause from RESOURCE_BLOCKED alone
- "physisch bewiesen" from verifier PASS alone
- "keine Wiederholung jemals" from a current snapshot alone

## Debugging signals

The owner surface should make these easy to spot:
- attempts > 1
- new dispatch identity for the same logical step
- server/worker disagreement
- stale or missing live process evidence
- ACK/redelivery mismatch
- blocked verification
- replay risk
- provider/resource wait
- human-required state
- candidate/runtime binding mismatch

## Transition-time gap

Code review confirms transition timing is only partial.

Currently available examples:
- slot last_started_at / last_finished_at
- STOP stopped_at
- worker last_seen as contact time

Important task/workflow transitions do not consistently persist a transition timestamp, including:
- QUEUED -> DISPATCHED
- local CLAIMED / STARTED / RESULT_READY
- RESULT_RECEIVED
- RECONCILED / FAILED_VERIFICATION
- full recovery/blocker transitions

Therefore reliable TIME_IN_CURRENT_STATE cannot currently be computed for all important states.

After RUN_2, if the first owner UI promises "how long has this been stuck?", the smallest sensible follow-up is an explicit status_changed_at / phase_changed_at written only when the state changes. This requires its own authorization and must not delay RUN_1/RUN_2.

Until then the UI may show approximate "since first observed" timing only when clearly labelled approximate.

## Existing dashboard reuse

The existing dashboard may be reused for:
- CSS
- cards
- filters
- basic layout

It must **not** be reused unchanged as the real owner/runtime view.

Current demo behavior includes locally advanced mission stages, static/local agent counts, prewritten success messages, and status defaults that may look real without matching runtime evidence.

Therefore:
- remove/disable demo-success and fake-activity logic from any real-runtime path
- connect both user and owner views to one reconciled read-only observation path
- never mix demo events with live proof
- do not create a new per-slot background process

## Owner fields

Available or derivable now:
- task_id
- workflow step index/total for the current workflow
- task/goal status
- worker phase
- blocker/recovery reason (partial)
- attempt count / attempt_id
- dispatch_id / result_id
- verification verdict / verifier_id
- worker_id
- slot status
- provider/platform field (not equivalent to authenticated host identity)

Missing or unsafe to infer:
- persisted verification method/version in the verdict
- strongly bound host identity in the UI contract
- durable governor status/reason
- durable resource measurement + age
- one normalized last-error field
- runtime-bound loaded candidate SHA
- server fingerprint in the dashboard payload
- proof level without matching acceptance evidence

Do not use checkpoint next_task as approved next-work truth.
Do not use checkpoint last_commit as proof of the actually loaded runtime version.

## Public / private boundary

Hide by default:
- internal IDs
- worker/slot state
- governor metrics
- candidate SHA
- raw logs
- retry details

Owner-only:
- raw stderr/stdout tails
- prompt/masterprompt content
- local paths
- PID/PGID
- provider/session bindings
- resource values
- rejected/orphan/quarantine files

Never public / never in a social Proof Card:
- prompts/instructions
- private filenames/content
- user or repo paths
- credentials, keys, sessions
- customer data
- raw logs/artifact bytes
- internal architecture details unnecessary for proof

A public Proof Card may use only evidence-backed, privacy-safe values such as:
- opt-in call sign
- verified-task count
- human intervention count
- duplicate/lost-result count
- runtime
- verification-method label
- date
- short proof ID/hash with no path

Important: USER is not automatically PUBLIC. A simple customer view may still contain private customer data.

## Security requirements before the first real UI

The current dashboard implementation is not yet an approved private/public boundary.

Before using it as a real product surface:
- constrain reachability appropriately (local/controlled binding unless intentionally exposed)
- use an explicit field allowlist rather than returning raw worker/HQ objects
- do not send provider/server credentials to the browser
- render dynamic text safely rather than trusting raw HTML insertion
- do not treat CSS-hidden owner fields as authorization
- keep public/social proof generation as a separately redacted output

## Minimum UI timing

Do not build the full world before the physical core proof.

Target sequence:

final candidate
-> real targeted tests
-> Muse output contract
-> exact Mac binding
-> RUN_1: physical A -> VERIFY -> B
-> RUN_2: restart with no A replay
-> smallest real read-only UI
-> owner uses it to find state/UX problems
-> first friend trial
-> broader world/community later

No UI-driven change is required before RUN_1 or RUN_2.

## Minimum post-RUN_2 UI

Use one read-only reconciliation/projection path for both USER and OWNER views.

Requirements:
- read existing authoritative state sources
- join observations only on matching identities
- USER shows plain-language summary
- OWNER shows the same observation with technical detail
- UI does not claim/dispatch/start workers
- no new process per slot
- bounded refresh cadence, no overlapping requests, backoff when unavailable
- governor/resource reasons show only when actually available; otherwise UNKNOWN
- demo activity remains physically/logically separated from live progress

## Owner-debug acceptance test

The first owner UI is useful only if it can correctly show a deterministic sequence containing:

1. claimed/started task without fake percentage progress
2. waiting/uncertain state without fake movement
3. local RESULT_READY = delivery pending
4. RESULT_RECEIVED = reported, not verified
5. matching RECONCILED/PASS = verified property
6. same-attempt redelivery = delivery repetition, not new execution
7. new attempt = visible reexecution
8. server/worker dispatch mismatch = conflict/UNKNOWN
9. HUMAN_REQUIRED with concrete reason
10. candidate binding mismatch = version conflict, not green PASS
11. B shown as automatically continued only after actual post-verification dispatch evidence

A snapshot alone cannot prove that no short-lived duplicate execution happened between observations; physical/run evidence remains required.

## Future-world compatibility

Current review found **no proven irreversible architecture dead end** requiring world/community work before RUN_2.

Therefore defer:
- world map
- full levels engine
- LFG backend
- marketplace
- social graph
- guilds
- plugin marketplace
- public reputation economy
- X/Facebook connectors
- multi-user control surface
- rich charts/history
- mobile-specific experience

## Product principle

The user sees simplicity.
The owner can inspect truth.
Both views describe the same reconciled evidence.

No evidence -> no reassuring UI state.

## Critical-path decision

Keep the current critical path unchanged.

No UI work should delay:
- final candidate correction
- targeted tests
- physical Muse output contract
- exact Mac binding
- RUN_1
- RUN_2

Immediately after RUN_2, build the smallest honest read-only surface and use it for owner-led product validation.
