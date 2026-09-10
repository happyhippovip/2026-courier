# COURIER COPY-PASTE EXIT PLAN

**Status:** CANONICAL STRATEGIC CONSTRAINT
**Captured:** 2026-09-10
**Primary objective:** stop using the human as the message bus between ChatGPT/Chief, Codex, Gemini/Antigravity, CLI1, Mac and Windows.

## 1. Non-negotiable user outcome

The user should primarily do only three things:
1. state a goal or idea;
2. make genuine human-only decisions/approvals;
3. receive high-signal completion/blocker notifications.

The user must **not** spend days or weeks copy-pasting prompts and reports between ChatGPT, Codex, Google Antigravity/Gemini CLI, local CLI workers, Mac and Windows.

North-star flow:

`USER GOAL -> CHIEF -> COURIER -> DISCOVER -> PLAN -> ROUTE -> EXECUTE -> VERIFY -> PERSIST -> NEXT SAFE STEP -> CONTINUE -> VERIFIED OUTCOME`

Human appears only at a true `HUMAN_GATE`.

## 2. Hard anti-loop rule

Courier infrastructure is not allowed to become an endless project.

**STOP BUILDING, START PROVING.**

A new Courier infrastructure component is permitted only when one of these is true:
- a reproducible defect blocks a real end-to-end goal;
- a safety invariant is demonstrably unprotected;
- a missing adapter prevents programmatic worker execution;
- durable state/recovery is proven insufficient by a concrete failure.

No feature may be added merely because it is architecturally attractive.

After the minimum end-to-end autonomous vertical slice is proven, Courier infrastructure enters **FREEZE**. Post-freeze changes require a reproducible product/revenue blocker.

## 3. Do not create 20 manual prompts

The previously discussed 20 proofs are a **definition of done**, not 20 human copy-paste tasks.

They must become one internal `COURIER_FINALIZATION_CAMPAIGN`:

`DISCOVER EXISTING EVIDENCE -> MAP PROOFS -> REUSE VALID EVIDENCE -> RUN ONLY GAPS -> REPAIR REAL DEFECTS -> VERIFY -> FREEZE DECISION`

Rules:
- `ALREADY_PROVEN?` before every proof.
- valid prior evidence may produce `PASS_BY_EXISTING_EVIDENCE`.
- failures remain inside the same mission: `FAIL -> REPRODUCE -> ROOT CAUSE -> MINIMAL REPAIR -> VERIFY -> CONTINUE`.
- do not stop for ordinary errors and ask the human for `weiter`.
- never accept worker prose, `echo PASS`, fabricated logs, fake counts or simulated duration as real proof.

## 4. Fastest path: four implementation units only

### A. Agent Gateway
Courier must programmatically invoke workers instead of requiring GUI copy-paste.

Priority adapters:
- Gemini CLI headless mode (`gemini -p`, structured JSON/JSONL output, real exit codes);
- existing native/local CLI1 adapter;
- Codex programmatic/managed execution path where available;
- optional ACP-compatible agent backend later if it materially reduces adapter complexity.

The gateway normalizes:
- task envelope;
- worker identity;
- logical work identity;
- start/ack/result events;
- stdout/stderr or structured stream;
- exit code;
- artifact references;
- verification reference;
- resource usage where available.

The gateway is not an orchestrator. Courier remains the only orchestrator.

### B. Durable Mission Runtime
Mission truth must live outside chat context.

Minimum durable objects:
- Goal;
- Mission;
- Task Stamp;
- Worker Lease;
- Process Lease;
- Follow-Up Inbox;
- Result;
- Verification;
- Human Gate;
- append-only Audit/Event record;
- resource state per machine.

Minimum long-run mission state:
- `mission_id`
- `goal_id`
- `mission_version`
- `scope`
- `scope_fingerprint`
- `acceptance_criteria`
- `current_phase`
- `last_verified_step`
- `current_in_flight_step`
- `open_defects`
- `safe_backlog`
- `do_not_repeat`
- `proof_debt`
- `execution_uncertainties`
- `human_gates`
- `resource_budget`
- `step_budget`
- `repair_budget`
- `last_progress_at`
- `exact_next_safe_action`
- `terminal_status`

Markdown checkpoints may be human-readable views, but they must not be the sole source of truth.

### C. Verification + Human Gates
Every terminal claim must bind to independent evidence.

Evidence classes:
- REAL
- SIMULATED
- MOCK
- SELF_REPORTED
- DERIVED
- INDEPENDENTLY_VERIFIED
- STALE
- INVALID

`SIMULATED`, `MOCK`, `SELF_REPORTED`, stale or manually fabricated output can never satisfy a real terminal gate.

High-risk actions pause durably and wait for explicit human approval. Current default remains:
- no autonomous spend;
- no purchases/subscriptions;
- no publication/production deploy;
- no customer outreach or external messages;
- no real trades;
- no wallet signing;
- no credentials/account changes.

### D. One Real End-to-End Goal
Before adding more architecture, prove one vertical slice where the human gives one goal and does not relay messages.

Required path:
`USER GOAL -> COURIER -> programmatic worker -> real result -> independent verifier -> durable state -> automatic next safe step -> terminal result or human gate`

If this slice works, the internal proof campaign can run itself.

## 5. Long-run mission policy

A long mission is not a gigantic prompt. It is a resumable state machine.

Required behavior:
- `AUTO_CONTINUE_WITHIN_SCOPE = true`
- `FAIL_IS_WORK = true`
- `EVIDENCE_REQUIRED_FOR_PASS = true`
- `NO_STACKING = true`
- `CHECKPOINT_AFTER_MEANINGFUL_PHASE = true`
- `TIME_ALONE_NEVER_KILLS = true`
- `REAL_DURATION_REQUIRED` for real soak/time claims
- newly discovered work goes to `SAFE_BACKLOG`, never mutates an IN_FLIGHT task silently
- stop only for `VERIFIED_COMPLETE`, genuine `HUMAN_GATE`, `EXECUTION_UNCERTAIN`, genuine `BLOCKED`, or resource/safety limit

## 6. Stable identity and recovery

Logical work identity must not change when worker, route or attempt changes.

Crash/restart policy:
- verified matching ledger evidence -> reconcile VERIFIED, no worker call;
- matching result exists -> `PENDING_VERIFY`, verifier once, no worker recall;
- dispatch may have occurred but proof is missing -> `EXECUTION_UNCERTAIN_NO_PROOF`, no retry, no redispatch, no fallback;
- retry is allowed only when durable evidence proves prior dispatch never started.

## 7. No-stacking and follow-up preservation

Once a writer task is `STAMPED/DISPATCHED/IN_FLIGHT`, no conflicting writer task may be issued to the same worker/scope until it is closed, safely blocked, or cancelled.

New ideas during work are captured as durable follow-ups, e.g.:
`CAPTURED -> NEEDS_DISCUSSION -> CANDIDATE -> APPROVED_NEXT -> DISPATCHED`

Historical follow-ups and audit events are never silently deleted.

## 8. Supervisor and resource policy

Supervisor is a support plane, not a second Courier.

Evidence-based process states include:
`STARTING, RUNNING, WAITING_VALID, PROGRESSING, STALLED, HUNG, ORPHANED, DUPLICATE, EXECUTION_UNCERTAIN, COMPLETED, TERMINATED, HUMAN_GATE`.

No-progress ladder:
- ~5m without progress evidence -> soft check;
- ~15m without progress evidence -> diagnostic bundle;
- time alone never terminates work;
- only proven HUNG/ORPHANED/DUPLICATE owned work may be auto-cleaned.

Resource governance is per machine. Mac pressure must not throttle a healthy Windows machine. Conservative Mac default: one heavy local job at a time.

## 9. Border Guard / Result Customs

Border Guard is an independent gate, not planner or writer. It may `PASS/REVISE/HOLD/BLOCK/ESCALATE` and write its own audit event. A decision must bind to task version and relevant state version to prevent TOCTOU/replay.

Result Customs checks identity, task version, scope/result/workspace fingerprints, tests/exit codes/artifacts, staleness/replay and any unexpected external/spend/deploy/publication actions. It cannot mark the goal satisfied by itself.

## 10. Trajectory Watchdog

Long-run safety must inspect the sequence, not only each action.

Detect:
- repeat work;
- thrashing;
- scope creep;
- test-only optimization;
- fake progress;
- changing acceptance criteria;
- declining information gain;
- repeated reopening of same defect;
- continuing after goal completion;
- unnecessary infrastructure work.

Suggested signals:
`verified_progress_rate`, `repeat_action_rate`, `defect_reopen_rate`, `proof_debt`, `scope_growth`, `rework_ratio`, `time_without_information_gain`.

Metrics are advisory and must not become gameable success criteria.

## 11. Programmatic worker options confirmed by current research

### OpenAI Agents SDK
OpenAI documents durable execution integrations for long-running agents with Dapr, Temporal, Restate and DBOS, including failure recovery and human-in-the-loop. DBOS is notably lightweight and can use SQLite or Postgres. The Agents SDK also provides managed loops, handoffs, guardrails, sessions and tracing.

Sources:
- https://openai.github.io/openai-agents-python/running_agents/
- https://openai.github.io/openai-agents-python/

### Codex
Codex supports long-running tasks, parallel isolated work, Automations and Goal Mode. Current OpenAI material explicitly describes work lasting hours/days/weeks and remote/mobile supervision for active work.

Sources:
- https://openai.com/index/codex-maxxing-long-running-work/
- https://openai.com/index/introducing-the-codex-app/
- https://openai.com/index/work-with-codex-from-anywhere/
- https://help.openai.com/en/articles/6825453

### Gemini CLI
Gemini CLI has a documented headless mode with structured JSON/JSONL output and exit codes. This is a direct candidate for eliminating manual Antigravity/Gemini copy-paste.

Sources:
- https://geminicli.com/docs/cli/headless/
- https://geminicli.com/docs/cli/tutorials/automation/

### OpenHands / ACP
OpenHands can use ACP-compatible backends such as Gemini CLI, and its Agent Server supports remote isolated workspaces with HTTP/WebSocket event streaming. This is an optional integration accelerator, not a requirement; avoid adding it if native adapters are simpler.

Sources:
- https://docs.openhands.dev/sdk/guides/agent-acp
- https://docs.openhands.dev/sdk/guides/agent-server/overview

### Durable execution frameworks
Temporal provides crash-proof durable workflow execution. LangGraph provides persisted interrupts and resume for human-in-the-loop workflows. These are references/options, not automatic dependencies.

Sources:
- https://docs.temporal.io/
- https://docs.langchain.com/oss/python/langgraph/interrupts

### Meta Muse / Anthropic reference patterns
Useful reference patterns include persistent background subagents, append-only event history, checkpointing, hooks and background tasks. Courier should copy the principles only where they reduce human orchestration or improve deterministic recovery.

Sources:
- https://research.meta.ai/blog/security-and-safety-for-ai-agents-our-approach-with-muse
- https://www.anthropic.com/news/enabling-claude-code-to-work-more-autonomously

## 12. Build-vs-adopt decision

Do not prematurely implement a full Temporal/OpenHands/LangGraph stack.

Decision order:
1. reuse current Courier primitives if they already satisfy durability;
2. build the smallest native Gemini/CLI1 gateway vertical slice;
3. if durable runtime remains fragile, evaluate DBOS first for lightweight SQLite/Postgres durability, then Temporal for stronger workflow durability;
4. evaluate ACP/OpenHands only if it reduces adapter/remote-worker complexity materially;
5. never add a framework simply because it is popular.

Every dependency must answer: **does this reduce human copy-paste or increase proven reliability faster than a minimal native implementation?**

## 13. 20-proof definition of done, compressed into one campaign

The campaign eventually covers:
1. truth/evidence;
2. stable identity;
3. no-stacking;
4. crash before dispatch;
5. crash during dispatch;
6. crash after result;
7. fallback/no duplicate effect;
8. human gates;
9. result customs;
10. border/TOCTOU;
11. process supervisor;
12. per-machine resources;
13. checkpoint/resume;
14. long-run mission;
15. multi-defect marathon;
16. trajectory/anti-loop;
17. real CLI1 worker;
18. real Gemini worker;
19. real multi-agent goal;
20. founder/money-factory goal.

These are **not** separate human prompts.

## 14. Immediate sequencing constraint

Do not stack new writer work onto workers already IN_FLIGHT. Current running Mac/Codex work must return evidence first. The next integration task should use that evidence to avoid repeating already-proven work.

## 15. Definition of success

Courier is ready for infrastructure freeze when:
- a user can submit one high-level goal;
- Courier programmatically invokes the appropriate worker(s);
- work can continue safely for long periods without manual `weiter`;
- state survives restart/context loss;
- conflicting writer work cannot stack;
- fake/simulated evidence cannot close real gates;
- independent verification controls terminal success;
- only true human gates interrupt the user;
- at least one real multi-step end-to-end goal completes this way.

After that: **move capacity to product/Money Factory.**

## 16. Permanent reminder

> The user is not Courier. Chief is not Courier. Courier is Courier.
>
> The purpose of this plan is to end manual relay work as fast as safely possible, not to create another long Courier infrastructure program.
