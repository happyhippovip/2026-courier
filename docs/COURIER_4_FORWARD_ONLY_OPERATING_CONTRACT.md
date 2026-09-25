# COURIER 4 — FORWARD-ONLY OPERATING CONTRACT

**Canonical date:** 2026-09-10
**Purpose:** Permanent operating contract for Chief, Courier, Gemini/Google workers, Codex, CLI1, Mac and Windows workers.

## 0. NORTH STAR

The human is not Courier. Chief is not Courier. Courier is Courier.

Target:

`FOUNDER GOAL -> OUTCOME CONTRACT -> DURABLE GOAL/TASK/ATTEMPT -> REAL PROGRAMMATIC WORKER -> ATTEMPT-SCOPED EFFECTS -> INDEPENDENT VERIFY -> NEXT SAFE ACTION -> AUTO-CONTINUE -> VERIFIED OUTCOME | HUMAN_GATE`

Primary metrics:
- `HUMAN_RELAYS_PER_GOAL -> 0`
- `FALSE_VERIFIED_PASS -> 0`
- `DUPLICATE_SIDE_EFFECTS -> 0`
- `VERIFIED_PROGRESS_PER_WALL_CLOCK -> maximize`
- `VERIFIED_PROGRESS_PER_MODEL_COST -> maximize`
- `ACTIVE_INFRASTRUCTURE_BLOCKERS <= 1`

More code, more agents, more tests, more dashboards, more prompts, or more completed tasks are NOT success metrics.

## 1. FORWARD-ONLY RULE

Every new discovery is classified as exactly one of:
- `CURRENT_BLOCKER`
- `FOLLOW_UP`
- `DEFERRED`
- `ALREADY_PROVEN`

Only a `CURRENT_BLOCKER` may interrupt the current critical path, and it MUST include reproducible evidence that it prevents a required end-to-end invariant.

`FOLLOW_UP` and `DEFERRED` items are durably captured and must not be silently deleted. They are not dispatched while a conflicting writer task is in flight.

Before repeating any proof/test/action ask: `ALREADY_PROVEN_WITH_VALID_EVIDENCE?` If yes, reuse the evidence.

Never replace stronger evidence with weaker evidence. Never restart a completed phase merely because a cleaner architecture was imagined.

## 2. NO-STACKING — PERMANENT

Writer lifecycle:

`PROPOSED -> NEGOTIATING -> APPROVED_FOR_DISPATCH -> STAMPED -> DISPATCHED -> IN_FLIGHT -> RESULT_RECEIVED -> VERIFIED -> CLOSED`

Alternative states: `QUESTION`, `CONFLICT`, `BLOCKED`, `HUMAN_GATE`, `CANCEL_REQUESTED`, `CANCELLED`, `FAILED`, `EXECUTION_UNCERTAIN`.

Once a writer task is `STAMPED/DISPATCHED/IN_FLIGHT`, no second conflicting writer task may be dispatched to the same worker/scope until the current task is `CLOSED`, explicitly `CANCELLED`, or safely `BLOCKED/HUMAN_GATE`.

New ideas during in-flight work go to the Follow-Up Inbox, never into an ad-hoc second prompt.

## 3. ONE AUTHORITY / ONE IDENTITY CHAIN

Exactly one component owns scheduling, claims, retries, reconciliation, and next-task dispatch.

Founder Mode, planners, queues, dispatcher, Supervisor, Border Guard, Result Customs, Verifier, worker adapters and UI must not become competing schedulers.

Required identity chain:

`goal_id -> task_id -> task_version -> attempt_id -> worker_execution_id -> result_fingerprint -> verification_reference -> outcome_state`

Worker/provider routing metadata must not mutate the logical identity of the work.

## 4. OUTCOME CONTRACT BEFORE TASKS

Every goal defines before execution:
- desired real-world/project state
- acceptance evidence
- forbidden effects
- human gates
- resource/spend budget
- stop conditions

Task completion is not goal completion. Worker prose is not outcome evidence. A planner reaching limits is not success.

## 5. PROGRAMMATIC WORKER BOUNDARY

Courier must never require the human to relay messages between workers.

Use a thin provider-neutral worker boundary conceptually equivalent to:

`start / events / status / cancel / resume / result / health`

Preferred current Gemini order:
1. existing proven programmatic adapter
2. Gemini CLI stable headless + structured `json`/`stream-json`
3. ACP only when durable/bidirectional coding-agent session control is concretely required

Future Codex, local, Muse or remote workers are adapters behind the same boundary; they must not change the Courier kernel.

Do not invent a new agent RPC protocol. MCP is for agent-to-tool integration; A2A is a future-compatible agent-to-agent boundary; use only when a concrete need exists.

## 6. ATTEMPT ISOLATION + EFFECT TRUTH

Writer attempts must have isolated or otherwise provably attempt-scoped effects.

Never accept as attempt evidence:
- global repository `git diff`
- unrelated untracked files
- pre-existing workspace changes
- worker prose alone
- synthetic logs
- manually fabricated outputs

Prefer standard Git worktree/workspace primitives rather than custom workspace infrastructure.

A builder cannot independently verify itself. A planner cannot declare terminal success. Terminal success requires independent evidence bound to the exact identity chain and current workspace/effect fingerprint.

## 7. FAKE-EVIDENCE BAN

Production-reachable synthetic success is forbidden.

No fake Gemini PASS, mocked real-worker proof, simulated duration, manually fabricated test output, unconditional CLEAN state, or generic PASS without evidence.

Unknown evidence -> `UNKNOWN/BLOCKED`, never PASS.

Execution that may have happened but cannot be proven -> `EXECUTION_UNCERTAIN_NO_PROOF`; never blind retry.

## 8. HUMAN GATES

Human-only gates include credentials/login/OAuth/2FA/CAPTCHA, sudo/admin/UAC, purchases/subscriptions/spend, publication, production deployment, customer outreach/external messages, real trading, wallet signing, KYC/legal and similar irreversible/restricted actions.

A Human Gate is durable and reopening/resume requires an exact authorized resolution linked to the same goal/task/attempt chain. Resume the same mission; do not restart from zero.

Current safety baseline:
- autonomous spend EUR 0
- no real trades
- no wallet signing
- no autonomous publication/deployment/outreach/purchases/subscriptions
- no credential/account modification
- never touch `universuX`

## 9. PERMANENT PROCESS OWNERSHIP / OPEN-TASK HYGIENE

Every spawned process/helper must belong to a durable process lease containing at minimum:

`process_lease_id, goal_id, task_id, task_version, attempt_id, worker_id, machine_id, pid/process_identity, command_fingerprint, purpose, parent_process, started_at, last_heartbeat_at, last_progress_at, expected_completion_condition, cleanup_policy, state, termination_reason`

Allowed process states:
`STARTING, RUNNING, WAITING_VALID, PROGRESSING, STALLED, HUNG, ORPHANED, DUPLICATE, EXECUTION_UNCERTAIN, COMPLETED, TERMINATED, HUMAN_GATE`.

Rules:
- no unowned background process
- no persistent `tail -f`, `grep`, polling, wait, debug or LLDB helper merely because it was once useful
- monitoring helper closes when the monitored task closes
- task/phase closure always runs process hygiene
- restart always reconciles durable leases against real processes before resuming/killing/retrying
- time alone never proves a process is hung
- soft check after ~5 min without progress evidence
- diagnostic bundle after ~15 min without progress evidence
- auto-clean only when evidence supports `HUNG`, `ORPHANED`, or `DUPLICATE`
- `STALLED` -> diagnose; `EXECUTION_UNCERTAIN` -> block, no blind retry

Progress evidence can include log growth, test completion, artifact creation, heartbeat, state transition, file output, CPU/activity evidence or new verification evidence.

### OS primitives — prefer them over custom process-tree hacks

POSIX/macOS: launch worker attempts in owned process sessions/groups (`start_new_session` / process groups where applicable) and terminate the owned group only with evidence and policy.

Windows: prefer Windows Job Objects for worker process trees; child processes inherit the job by default, job accounting is available, and `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` can guarantee cleanup of the owned process tree when appropriate.

Cross-platform telemetry/process inspection may use a small standard library such as `psutil` if already appropriate; do not build a bespoke process scanner unless necessary.

## 10. PER-MACHINE RESOURCE / THERMAL GOVERNOR

Machine resource state is independent per host. A hot Mac must never globally throttle a healthy Windows machine.

States:
`NORMAL, BUSY, PRESSURE, THERMAL_PRESSURE, RECOVERY, UNKNOWN`.

Mac default: `MAX_CONCURRENT_HEAVY_LOCAL_TASKS = 1` until evidence justifies otherwise.

Mac thermal policy should use the OS thermal-state signal where available (`nominal/fair/serious/critical`). At `serious/critical`, hold NEW heavy work on that Mac, clean obsolete helpers, preserve evidence, and allow the machine to recover. Do not kill genuinely progressing required work solely because the machine is warm or a timer expired.

Windows limits are independently evidence-based; do not throttle Windows due to Mac heat.

When a machine is pressured, route future eligible work to a healthy machine if safe and supported.

No sudo/admin or system power modification for thermal management.

## 11. TESTING / REPAIR DISCIPLINE

During implementation:

`REPRODUCE -> ROOT CAUSE -> MINIMAL REPAIR -> TARGETED TEST -> E2E VERIFY -> CONTINUE`

No repeated broad/full regression during active debugging. A broad regression may run once at a justified terminal/freeze boundary if required.

Empty verification target must fail closed; it must never silently trigger an expensive full-suite fallback.

## 12. CURRENT COPY-PASTE-EXIT CRITICAL PATH

Preserve already verified evidence. The immediate required sequence is:

1. real programmatic worker proof
2. auto-continue proof: Mission A verified -> Courier launches Mission B itself -> Mission B verified; `HUMAN_RELAY_BETWEEN_A_AND_B = 0`
3. one small real isolated coding E2E through the same path
4. deterministic Human-Gate pause/resume proof on the same identity chain
5. one controlled restart/recovery proof
6. adversarial false-positive check limited to current E2E P0s
7. kernel freeze if no unresolved P0 affects the path

Do not build future infrastructure between these steps unless a reproducible CURRENT_BLOCKER proves it is required.

## 13. COURIER KERNEL FREEZE GATE

Freeze candidate requires real evidence for:
- `ONE_GOAL_INPUT`
- `REAL_PROGRAMMATIC_WORKER`
- goal/task/attempt identity integrity
- attempt-scoped effects
- independent verification
- auto-continue with zero human relay
- one real small coding mission
- durable Human-Gate pause/resume
- controlled restart without duplicate execution
- no production synthetic PASS
- no unresolved P0 affecting this path

Then set `COURIER_KERNEL_FREEZE_CANDIDATE = YES` and stop adding infrastructure.

Post-freeze kernel changes require a reproducible safety, product, revenue, execution, or durability blocker.

## 14. BUILD-vs-BUY / STANDARDS POLICY

Do not reimplement commodity infrastructure merely to be unique.

Current reference primitives as of 2026-09-10:
- OpenAI Symphony: single authoritative orchestrator, deterministic per-issue workspaces, reconciliation, thin agent runner, remote worker pool patterns.
- Gemini CLI stable v0.59.0 (2026-09-08): recommended stable channel; headless automation plus fail-closed workspace trust/restricted-mode MCP filtering. Preview features are not production defaults.
- Meta Muse Spark 1.3 (2026-09-02): long-horizon improvements, plan-gap correction, fewer unnecessary turns/tool calls/tokens; use as efficiency/trajectory inspiration, not a reason to build a Muse clone.
- Meta Muse safety (2026-09-08): unattended agents require safety architecture; retain least-capability, durable human gates and effect evidence.
- A2A (AAIF Growth Stage as of 2026-08-27): future vendor-neutral agent-to-agent interoperability boundary; do not implement unless concrete multi-agent interoperability requires it.
- Google Gemini + Temporal durable-agent reference: valid escape hatch only if current Courier restart/durability is proven insufficient.
- Standard OS process primitives: POSIX process sessions/groups and Windows Job Objects for owned process-tree lifecycle.

Decision categories for every Courier component after the current E2E result:
`KEEP / DELETE / MERGE / REPLACE_WITH_STANDARD / REPLACE_WITH_OPEN_SOURCE / PATCH / DEFER`.

The unique Courier advantage should live in Founder Goals, Outcome Contracts, safe autonomous continuation, independent evidence, multi-machine/provider routing, resource/thermal governance, failure memory, trajectory control and economic outcome learning — not in reinventing process managers, RPC, worktrees or generic workflow engines.

## 15. RESEARCH REFERENCES (2026-09-10)

- https://openai.com/index/open-source-codex-orchestration-symphony/
- https://github.com/openai/symphony/blob/main/SPEC.md
- https://geminicli.com/docs/changelogs/latest/
- https://research.meta.ai/blog/introducing-muse-spark-1-3
- https://research.meta.ai/blog/security-and-safety-for-ai-agents-our-approach-with-muse
- https://a2a-protocol.org/latest/blog/2026/08/27/a-new-chapter-for-a2a-joining-the-agentic-ai-foundation/
- https://ai.google.dev/gemini-api/docs/temporal-example
- https://docs.python.org/3/library/subprocess.html
- https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
- https://developer.apple.com/documentation/foundation/processinfo/thermalstate-swift.property

## 16. WORKER STARTUP CONTRACT

Every Chief/Courier/Google/Codex/CLI1 session that can affect Courier must first read:
1. `CHIEF_BRAIN_STATE.md`
2. `docs/COURIER_4_FORWARD_ONLY_OPERATING_CONTRACT.md`
3. the exact current task stamp / active goal state / relevant evidence

If local state conflicts with the canonical operating contract, do not silently improvise. Preserve evidence and surface the conflict to Courier as `CONFLICT` or `EXECUTION_UNCERTAIN` as appropriate.

This document is the permanent anti-regression/anti-loop contract. Historical documents remain evidence/history but must not override this contract unless an explicitly newer canonical contract supersedes it.