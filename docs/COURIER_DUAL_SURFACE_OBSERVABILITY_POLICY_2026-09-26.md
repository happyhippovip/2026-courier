# Courier Dual-Surface Observability Policy — 2026-09-26

Status: product/architecture guardrail for AFTER the physical core proof.

## Rule 5 — DUAL_SURFACE_TRUTH

Courier uses one source of truth and two views of it.

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
- attempt, dispatch and result identity
- verification verdict + method
- worker/host/slot state
- governor state
- last error
- candidate SHA / server fingerprint
- proof level

Global owner checks:
- Is Courier progressing?
- Where is it stuck?
- Why?
- What should happen next?
- Does UI disagree with runtime?
- Was work retried or replayed?
- Is a result only reported or actually verified?
- Which host/worker currently owns the step?

## State truth rules

- RESULT_RECEIVED means reported, not verified.
- RECONCILED + PASS means verified.
- EXACT_CONTENT and INTEGRITY must remain visibly distinct verification methods.
- "Working" requires real execution evidence and a fresh enough heartbeat/source.
- Contradictory or missing evidence must display UNKNOWN / WAITING, never reassuring progress.
- "Recovered" requires real recovery evidence.
- Human intervention is shown only for an explicit gate or ambiguous effect state.

## Debugging signals

The owner surface should make these easy to spot:
- attempts > 1
- repeated dispatch identity
- server/worker disagreement
- stale or missing heartbeat
- ACK/redelivery mismatch
- blocked verification
- replay risk
- provider/resource wait
- human-required state

## Transition-time gap

Current review reported that server transition timestamps may be insufficient for reliably answering "how long has this been stuck?".

Until independently verified in code:
- treat this as a candidate post-RUN_2 observability gap, not as proven fact.
- use snapshots/logs only as approximate timing.

If confirmed after RUN_2, the smallest proposed remedy is an explicit transition timestamp such as status_changed_at on each state transition. This requires its own authorization and must not delay RUN_1/RUN_2.

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

## Minimum UI timing

Do not build the full world before the physical core proof.

Target sequence:

final candidate
-> real targeted tests
-> Muse output contract
-> RUN_1: physical A -> VERIFY -> B
-> RUN_2: restart with no A replay
-> smallest real read-only UI
-> owner uses it to find state/UX problems
-> first friend trial
-> broader world/community later

The first UI should be based on existing real state and existing dashboard assets where practical. It should not introduce one new background process per slot.

## Can wait

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
Both views describe the same underlying evidence.

No evidence -> no reassuring UI state.
