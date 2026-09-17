# Courier Autonomous Execution Plan

This is the durable remaining-work roadmap for Courier. It guides unattended execution while Motor remains the sole runtime scheduler.

## Canonical execution policy: MAXIMUM SAFE PARALLELISM

Courier optimizes for **verified useful progress per unit time**, not for token burn, agent count, or chat activity.

- Continuously compute the complete safe executable frontier, not only the next single task.
- Dispatch independent, non-overlapping scopes concurrently to all legitimately available and authorized workers when Motor eligibility, capabilities, authority, and resource ownership allow it.
- Mac Antigravity, Windows Antigravity, Google CLI, and future authorized workers may execute concurrently. Provider identity is worker metadata, never workflow truth.
- One writer per logical scope/resource. Never create concurrency by allowing overlapping writers.
- A busy worker, provider wait, quota/session end, human gate, money gate, or writer collision blocks only its causally affected scope. Unrelated safe work continues.
- Prefer the cheapest sufficient worker/model for deterministic bounded work; use the strongest available worker where it materially increases verified throughput or resolves hard blockers.
- Reuse valid evidence and minimal context packages. Do not spend tokens rebuilding context that is already durable.
- Worker/session replacement is normal: CHECKPOINT -> PUSH -> CLEAN OWNED PROCESSES -> YIELD. A fresh authorized worker reconstructs from canonical repository/Ledger state, not old chat.
- Do not automate account rotation, quota circumvention, or provider-limit evasion. Multiple legitimately authorized workers/accounts may be used manually or through provider-supported mechanisms only within their terms and limits.
- No LLM polling, fake background loops, second scheduler, second queue, or second truth store. Motor remains the sole runtime scheduler/claim authority; Ledger remains coordination/evidence/handoff.
- No auto-spend, payment-provider signup, unattended merge, credential/security-control bypass, unsolicited external sales messages, fake PASS, or destructive broad cleanup.
- Native OS/provider scheduling or background-agent facilities may only wake/start the canonical Courier continuation/Motor path; they must not decide Courier task ownership themselves.
- Success metric: maximize causally verified completed tasks/hour while preserving acceptance, safety, ownership, and reproducibility.

## Intelligent cross-machine worker routing

The Motor owns one canonical executable frontier shared by every authorized Courier worker. There is **no Antigravity queue, Mac queue, Windows queue, or CLI queue**. Workers advertise what they can actually do; Motor matches work to them.

### Worker descriptor

Every participating worker/session should expose durable or reconstructable metadata sufficient for eligibility decisions:

`WORKER_ID`, `HOST_ID`, `OS`, `PROVIDER`, `INTERFACE`, `CAPABILITIES`, `AUTHORITIES`, `AVAILABLE_RESOURCES`, `OWNED_SCOPES`, `CONTEXT_BUDGET`, `AVAILABILITY`.

Provider names are hints, not workflow truth. Mac, Windows, CLI, GUI agents, and future providers are interchangeable whenever their capabilities and authority satisfy the task.

### Task descriptor / Minimal Task Packet

Before delegation, derive the smallest sufficient packet from canonical state:

`GOAL_ID`, `TASK_ID`, `CURRENT_RUNTIME_SHA`, `OBJECTIVE`, `REQUIRED_CAPABILITIES`, `REQUIRED_AUTHORITY`, `RELEVANT_FILES`, `RELEVANT_EVIDENCE`, `ACCEPTANCE_PREDICATES`, `RESOURCE_SCOPE`, `DO_NOT_TOUCH`, `FIRST_CAUSAL_BLOCKER`, `NEXT_EXECUTABLE_ACTION`, `CONTEXT_BUDGET`.

Never route raw chat history when repository/Ledger evidence is sufficient.

### Routing decision

For every READY task, Motor filters workers by hard constraints first: capability, authority, platform/resource access, writer/resource collision, safety gate, and availability. Among eligible workers it prefers the worker expected to produce the most verified progress with the least unnecessary context/cost.

Default preference is:

1. deterministic local tool/script when no model reasoning is required;
2. bounded CLI worker for mechanical, inspect/build/test/hash/git/evidence work;
3. Antigravity reasoning worker for uncertain debugging, architecture, causal analysis, multi-file implementation, integration and acceptance reasoning;
4. another authorized worker/provider only when it is the better eligible fit or the preferred worker is unavailable/insufficient.

This is a preference, not a hardcoded provider dependency. The same rule runs on Mac and Windows. A Mac worker does not need to know a specific Windows bot name and a Windows worker does not need to know a specific Mac bot name; both ask the Motor frontier for an eligible claim using task/worker descriptors.

### Mutual delegation and continuous participation

A worker that discovers a bounded subtask does not ask the human where to send it. It records/submits the subtask through the existing Motor task mechanism with required capabilities, authority, resource scope and acceptance predicates. Motor decides who may claim it.

`DISCOVER SUBTASK -> DESCRIBE -> MOTOR ELIGIBILITY/CLAIM -> WORKER EXECUTES -> VERIFY -> LEDGER CHECKPOINT -> RECOMPUTE FRONTIER`

After completing a task, Antigravity or any other worker should immediately request/claim the next eligible task instead of returning to the human merely for `continue`. Antigravity remains the current preferred main reasoning worker while available, but it has no private queue and no permanent ownership of unrelated work.

Parallel execution is allowed only for genuinely independent non-overlapping resource scopes. Same logical scope/resource means one writer. Independent verification may use another worker when that adds acceptance value.

On session/quota/worker loss: `CHECKPOINT -> PUSH -> CLEAN OWNED PROCESSES -> CANONICAL YIELD/RELEASE WHEN SAFE -> MOTOR RECOMPUTES -> NEXT ELIGIBLE WORKER`. Never bypass ownership and never automate account rotation or quota circumvention.

### Cross-machine command contract

Every authorized machine/program receives the same bootstrap contract:

`python3 scripts/courier_continue.py --run`

That command must reconstruct canonical state, identify the local worker descriptor, ask the existing Motor/eligibility path for safe work, consume eligible work, checkpoint verified results, and continue until the full safe frontier is exhausted or a true global gate exists. OS launch/service mechanisms may start this command, but may not implement task scheduling themselves.

### Efficiency contract

Use `DETERMINISTIC FIRST -> MINIMAL CONTEXT -> HASH/DIFF FIRST -> REUSE VALID EVIDENCE -> BATCH SAFE RELATED ACTIONS -> VERIFY`. Do not duplicate reasoning, reread unchanged context without causal need, or escalate models merely because they are available. Optimize verified tasks per worker-minute/token without weakening acceptance or safety.

### Routing acceptance predicates

The implementation is complete only when deterministic tests/evidence prove:

1. deterministic task prefers deterministic/bounded execution;
2. reasoning-heavy task is eligible for Antigravity-class reasoning capability;
3. insufficient capability/authority cannot claim;
4. unavailable worker permits another eligible worker to claim;
5. Mac/Windows workers use the same capability/authority contract;
6. overlapping resource scope never has two writers;
7. independent scopes may be claimed concurrently;
8. worker loss checkpoints/yields and another eligible worker can continue without old chat;
9. no eligible worker creates a durable scope-local blocker while unrelated work continues;
10. completing task N automatically leads to recomputation/claim of task N+1 without a human continue message;
11. no second scheduler, queue, or truth store is introduced.

### Frontier invariants

The continuation path must satisfy these behaviors:

1. blocked scope + independent work => continue independent work
2. writer collision + unrelated work => continue unrelated work
3. money gate + free work => continue free work
4. provider unavailable/busy + another eligible worker => dispatch to eligible worker
5. multiple independent eligible tasks/workers => execute concurrently when resources do not collide
6. stale or invalid Ledger => fail closed for affected claims; do not fabricate state
7. all remaining scopes genuinely blocked/completed => CLEAN_IDLE / true global stop

## Milestones

### 1. LEDGER/HANDOFF
- **Objective**: Establish the machine-readable, zero-chat handoff primitive.
- **Dependencies**: None.
- **Required Capabilities**: File write, Git.
- **Required Authority**: eligible authorized writer.
- **Human Gates**: None.
- **Money Gates**: None.
- **Acceptance Predicates**: Ledger file is parsable and verifiable.
- **Evidence Required**: agent_handoff_ledger.json exists with schema v2.
- **Safe Automatic Actions**: Initialize ledger, update state.
- **Forbidden Actions**: Tampering with current_sha.
- **Next Executable Action**: PR41 ACCEPTANCE

### 2. PR41 ACCEPTANCE
- **Objective**: Evaluate and integrate PR41 motor eligibility if writer lock allows.
- **Dependencies**: LEDGER/HANDOFF
- **Required Capabilities**: Git merge, Code analysis.
- **Required Authority**: protected merge authorization where required.
- **Human Gates**: HUMAN_REQUIRED_MERGE when canonical policy requires human merge authorization.
- **Money Gates**: None.
- **Acceptance Predicates**: Code integrated securely.
- **Evidence Required**: Git SHA of integration and causally relevant acceptance evidence.
- **Safe Automatic Actions**: Check ownership, verify PR; continue unrelated scopes while blocked.
- **Forbidden Actions**: Unattended merge where prohibited; bypassing writer ownership.
- **Next Executable Action**: RELEASE

### 3. RELEASE
- **Objective**: Prepare the release candidate for public distribution.
- **Dependencies**: LEDGER/HANDOFF (and PR41 only where causally required)
- **Required Capabilities**: Shell, Build tools.
- **Required Authority**: eligible authorized writer.
- **Human Gates**: None.
- **Money Gates**: None.
- **Acceptance Predicates**: Release builds cleanly.
- **Evidence Required**: Build/test evidence.
- **Safe Automatic Actions**: Build, test.
- **Forbidden Actions**: Publishing untested artifacts.
- **Next Executable Action**: PUBLIC DEPLOYMENT

### 4. PUBLIC DEPLOYMENT
- **Objective**: Deploy the public Courier site.
- **Dependencies**: RELEASE
- **Required Capabilities**: GitHub Actions, API.
- **Required Authority**: authorized deployment worker.
- **Human Gates**: HUMAN_REQUIRED_PUBLIC_REPO_VISIBILITY only if genuinely required.
- **Money Gates**: None unless an unavoidable paid action is causally required.
- **Acceptance Predicates**: Deployment completes successfully; triggering alone is not proof.
- **Evidence Required**: Terminal workflow/deployment result and deployment identity.
- **Safe Automatic Actions**: Trigger authorized free workflows and inspect terminal result.
- **Forbidden Actions**: Auto-spend; marking publication proven from trigger/local build alone.
- **Next Executable Action**: PUBLICATION VERIFICATION

### 5. PUBLICATION VERIFICATION
- **Objective**: Verify that the deployed site is publicly reachable.
- **Dependencies**: PUBLIC DEPLOYMENT
- **Required Capabilities**: HTTP Client.
- **Required Authority**: eligible authorized worker.
- **Human Gates**: None.
- **Money Gates**: None.
- **Acceptance Predicates**: Public URL responds successfully and configured contact destination is present.
- **Evidence Required**: Actual public HTTP response/equivalent causal deployment evidence.
- **Safe Automatic Actions**: Request URL, parse response.
- **Forbidden Actions**: Assuming deployment pass without checking.
- **Next Executable Action**: PILOT INTAKE

### 6. PILOT INTAKE
- **Objective**: Prepare intake processing for pilot inquiries.
- **Dependencies**: PUBLICATION VERIFICATION
- **Required Capabilities**: Email/Form processing setup.
- **Required Authority**: eligible authorized worker.
- **Human Gates**: None.
- **Money Gates**: None.
- **Acceptance Predicates**: Configured intake forms or endpoints.
- **Evidence Required**: Config/evidence for intake processing.
- **Safe Automatic Actions**: Generate configs, save authorized defaults.
- **Forbidden Actions**: Sending unsolicited emails, fake contact data.
- **Next Executable Action**: SALES PACKAGE

### 7. SALES PACKAGE
- **Objective**: Produce the sales collateral and pilot qualification requirements.
- **Dependencies**: PILOT INTAKE
- **Required Capabilities**: Markdown, File write.
- **Required Authority**: eligible authorized worker.
- **Human Gates**: None.
- **Money Gates**: None.
- **Acceptance Predicates**: Collateral files exist and are finalized.
- **Evidence Required**: Versioned sales/pilot collateral.
- **Safe Automatic Actions**: Draft/refine collateral.
- **Forbidden Actions**: External sales messages without authorization.
- **Next Executable Action**: FIRST PILOT

### 8. FIRST PILOT
- **Objective**: Prepare and onboard the first real pilot customer.
- **Dependencies**: SALES PACKAGE
- **Required Capabilities**: Intake execution.
- **Required Authority**: eligible authorized worker.
- **Human Gates**: HUMAN_REQUIRED_CUSTOMER_AGREEMENT only when a real customer's agreement/action is required.
- **Money Gates**: None before money actually needs to be collected.
- **Acceptance Predicates**: Real customer agrees to applicable terms.
- **Evidence Required**: Real intake/agreement record.
- **Safe Automatic Actions**: Parse real intake responses, prepare onboarding record/package.
- **Forbidden Actions**: Fake prospects, unsolicited outreach, fabricated agreement.
- **Next Executable Action**: PAYMENT ONLY WHEN ACTUALLY REQUIRED

### 9. PAYMENT ONLY WHEN ACTUALLY REQUIRED
- **Objective**: Collect pilot payment when a real agreed transaction actually requires it.
- **Dependencies**: FIRST PILOT
- **Required Capabilities**: Authorized payment mechanism.
- **Required Authority**: Explicitly authorized payment action.
- **Human Gates**: As required by the real payment/account setup.
- **Money Gates**: MONEY_REQUIRED_PAYMENT_GATEWAY only at the first action genuinely requiring payment collection/setup.
- **Acceptance Predicates**: Payment mechanism/action is real and authorized.
- **Evidence Required**: Appropriate transaction/setup evidence without exposing secrets.
- **Safe Automatic Actions**: Read already-authorized status/evidence where available.
- **Forbidden Actions**: Buying/configuring payment providers or spending without explicit authorization.
- **Next Executable Action**: POST-PILOT HARDENING

### 10. POST-PILOT HARDENING
- **Objective**: Harden systems after pilot execution.
- **Dependencies**: Relevant pilot evidence; unrelated safe hardening may run earlier when independent.
- **Required Capabilities**: Refactoring, Testing.
- **Required Authority**: eligible authorized worker.
- **Human Gates**: None for safe internal work.
- **Money Gates**: None.
- **Acceptance Predicates**: Defined hardening acceptance predicates pass; do not use vague perfection claims.
- **Evidence Required**: Audit/test report.
- **Safe Automatic Actions**: Audit code, run tests, apply owned safe fixes.
- **Forbidden Actions**: Destructive broad cleanup.
- **Next Executable Action**: NONE when the full frontier is genuinely complete/blocked.

---
**LEDGER_V1=COMPLETE**
*Ledger/autonomy milestone proven in canonical state. Ledger V1 is frozen except for future bug fixes.*

### Permanent Operating Rule (Ledger V1 Frozen)

**GOAL → MOTOR → WORKER → VERIFIED RESULT → LEDGER CHECKPOINT → NEXT EXECUTABLE ACTION**

**Permanent invariants:**
- Motor remains the sole runtime scheduler/execution authority.
- Ledger stores only durable execution state, ownership, blockers, evidence, acceptance state and minimal handoff context.
- Ledger is NOT a scheduler, queue, second Motor or second truth store.
- Never persist raw chat as runtime context.
- Every fresh/disposable worker resumes with: `python3 scripts/courier_continue.py --run`
- Session/account/provider replacement requires no old chat reconstruction.
- Human/money/provider gates remain scope-local whenever independent safe work exists.
- Ledger V1 may be changed after freeze only for a reproducible correctness/reliability defect, not speculative improvements.

**LEDGER_V1=COMPLETE**
**LEDGER_V1_FROZEN=YES**
**LEDGER_ACTIVE_DEVELOPMENT=NO**

### Execution Efficiency Policy (Maximum Verified Work Per Token)

**DETERMINISTIC FIRST → MINIMAL CONTEXT → CHEAPEST SUFFICIENT WORKER → LLM ONLY FOR REASONING → VERIFY → REUSE EVIDENCE**

**Core Directives:**
- Never send raw chat history to workers.
- Build every worker context from Ledger + relevant diff + causally relevant files/evidence only.
- Use `ChiefContextPackageBuilder`, `FileManifestTracker`, and `TaskDedupeEngine` to avoid retransmitting/reprocessing unchanged context.
- Do not repeatedly inspect files whose manifest/hash has not changed unless causally required.
- Reuse still-valid acceptance evidence instead of rerunning entire proof suites.
- For a code change, re-prove affected causal edges first; run broader suites only when required.
- Use deterministic Python/shell/Git/GitHub operations instead of LLM reasoning whenever the operation is deterministic.
- Batch related safe operations into one worker assignment instead of repeated worker round-trips.
- Do not ask the human for continue.
- Do not generate intermediate narrative reports while autonomous execution can continue.
- Do not spawn duplicate reasoning workers for the same task unless independent verification is required.
- Provider/model escalation only when the current worker demonstrably cannot complete the task.
- Never use background LLM polling.
- Never sacrifice acceptance predicates, evidence quality, safety or correctness to save tokens.

**Tracked Metrics (When Observable):**
- INPUT_TOKENS
- OUTPUT_TOKENS
- CONTEXT_SIZE
- RETRIES
- WORKER
- VERIFIED_TASK_RESULT
- TOKENS_PER_VERIFIED_TASK

**Optimization Goal:**
Maximize *verified completed Courier work per token and per worker-minute*, not merely the lowest raw token count.
