# Courier Maximum Throughput Rule

Status: **CANONICAL OPERATING RULE**

Purpose: maximize **verified useful work completed per unit of wall-clock time** while preserving Courier's ownership, acceptance, safety, reproducibility, and cost controls.

This rule complements `COURIER_AUTONOMOUS_EXECUTION_PLAN.md`. It does not create a scheduler, queue, Motor, or truth store.

## 1. Core rule

**SYNC CANONICAL STATE -> COMPLETE FRONTIER -> MAXIMUM SAFE PARALLELISM -> VERIFY -> LEDGER -> CHECKPOINT -> RECOMPUTE -> CONTINUE**

Courier must continuously expose the complete safe executable frontier. Independent, non-overlapping READY work should be executed concurrently whenever eligible authorized worker capacity exists.

The objective is not maximum agent count, token consumption, CPU activity, terminal processes, or chat activity. The objective is maximum **causally verified completed tasks/hour** and minimum READY wait time.

## 2. Permanent anti-bottleneck rule

The foreground AI chat is a control surface, never Courier's execution engine.

**Forbidden dependency:** `human message -> foreground turn -> queued message -> next task`.

Courier autonomy must instead follow:

`CANONICAL STATE -> MOTOR READY FRONTIER -> ELIGIBLE WORKER CLAIM -> EXECUTE -> VERIFY -> LEDGER/CHECKPOINT -> NEXT CLAIM`.

Therefore:

- Antigravity `Queued Messages` are convenience UI only. They are not durable work, scheduling state, or a prerequisite for progress.
- A foreground Antigravity turn may coordinate/decompose work, but independent workers/sub-agents/services must not wait for that turn to finish when Motor already exposes eligible READY work.
- Passive terminal commands, log tails, watchers, idle shells, and sleeping/polling processes must never consume a logical productive-worker slot or make the system appear busy.
- If the foreground agent returns while safe READY work exists, that is an autonomy defect unless the remaining work genuinely requires foreground-only capability/authority.
- Repeated human `continue`, prompt copying, queue feeding, account/session context reconstruction, or manual worker restart is a defect to remove, not an operating procedure.
- Provider-supported multi-agent/sub-agent/background capacity may be used as execution capacity, but Motor alone decides Courier task eligibility/ownership.

This anti-bottleneck rule is permanent because serial foreground queues previously caused large wall-clock delays despite available compute/worker capacity.

## 3. Authority boundaries

- Motor remains the sole runtime scheduler, eligibility/claim authority, and owner of executable task routing.
- Ledger remains durable coordination/evidence/handoff state; it is not a scheduler or queue.
- Provider/OS background or scheduled-agent facilities may provide worker capacity or wake/recovery only. They must not decide Courier task ownership.
- One writer per logical scope/resource. Parallelism never overrides ownership.
- Human, money, provider, permission, safety, and writer gates are scope-local unless the complete safe frontier is blocked.
- Do not create a second Motor, scheduler, durable task queue, or truth store to solve a throughput problem.

## 4. Safe repository synchronization contract

Workers must synchronize without destroying local work or creating merge races.

Canonical pattern before claiming new work:

`INSPECT -> FETCH -> COMPARE -> RECONCILE SAFELY -> CLAIM -> WORK -> VERIFY -> CHECKPOINT -> PUSH`.

Rules:

- Prefer `git fetch` first because it updates remote knowledge without mutating the current working tree.
- Inspect branch, HEAD, upstream divergence, working-tree state, active writer/resource ownership, and relevant canonical Ledger state before integration.
- Do not blindly `git pull` over uncommitted/owned work. Pull/rebase/merge strategy must be chosen from actual repository state and project policy.
- Never use force push, destructive reset, broad checkout/clean, or stash-as-a-trashcan merely to make synchronization convenient.
- If local work and upstream work touch independent scopes, preserve both and reconcile through normal Git semantics.
- If they collide in the same logical writer scope, fail closed for that scope and continue unrelated safe work.
- After verified portable changes, checkpoint/commit/push promptly enough that another authorized worker can recover without chat history.
- A worker must not treat its local checkout as canonical merely because it is newer locally; canonical truth is established by repository/Ledger/ownership rules.
- Avoid self-referential Ledger SHA loops: runtime/evidence SHA and the commit containing a Ledger checkpoint are distinct concepts where required by the canonical Ledger schema.

## 5. Worker pool and real parallelism

Courier may use all legitimately available authorized capacity, including Mac Antigravity, Windows Antigravity, Google CLI, deterministic local scripts/tools, and future authorized workers/providers.

Workers are matched generically using declared task requirements and worker descriptors rather than hardcoded provider names.

A busy/unavailable worker, provider wait, session/quota end, human gate, money gate, or writer collision blocks only its causally affected scope. Independent safe work continues.

Bound concurrency by READY work, resource ownership, machine capacity, provider-supported limits, and acceptance needs. Do not spawn agents merely to consume credits.

Do not automate account rotation, quota circumvention, or provider-limit evasion.

## 6. Productive work vs fake activity

Productive capacity means a worker is claiming/executing/verifying eligible Courier work.

The following do NOT count as productive progress by themselves:

- `Get-Content -Wait`, `tail -f`, or passive log watchers;
- sleeping/polling shells;
- idle terminals;
- queued chat messages waiting for a foreground turn;
- plans, prompts, branches, PRs, logs, or code inspection without acceptance evidence;
- duplicate workers reasoning about the same scope without an explicit independent-verification purpose;
- a workflow being triggered when its terminal result is the required evidence;
- a local build when public deployment is the required evidence.

Long-lived required Motor/worker services are infrastructure, not completed-task evidence.

## 7. Generic future-pipeline contract

Motor scheduling logic must not hardcode Courier release milestones, YouTube, TikTok, websites, lead intake, customer workflows, analytics, or any future provider/workflow name.

New workflows must be expressible primarily through durable task/plan definitions using:

`TASK -> DEPENDENCIES -> CAPABILITIES -> AUTHORITY -> RESOURCE OWNERSHIP -> GATES -> ACCEPTANCE -> EVIDENCE`.

A completely new future pipeline should be addable without rewriting Motor scheduling logic when its tasks correctly declare those properties.

Multiple goals/pipelines may coexist. A gate in one pipeline must not freeze unrelated READY work in another. Fairness/bounded concurrency must prevent one large pipeline from permanently starving unrelated READY work.

Fan-out/fan-in must be generic: independent preparation/render/test/metadata/analysis/distribution tasks may run concurrently; downstream tasks become READY only when their declared dependencies and acceptance evidence are satisfied.

## 8. Worker selection efficiency

Default preference:

1. deterministic script/tool when reasoning is unnecessary;
2. bounded CLI worker for mechanical inspect/build/test/hash/git/evidence work;
3. strongest suitable reasoning worker for uncertain debugging, architecture, causal analysis, multi-file implementation, integration, and acceptance reasoning;
4. another authorized eligible worker when it provides better throughput or the preferred worker is unavailable.

Use minimal task packets, relevant diffs/files/evidence, hashes/manifests, dedupe, and still-valid causal evidence. Do not reconstruct context from old chat when canonical state is sufficient.

Use full-capability workers where they materially increase verified throughput. Do not artificially underpower difficult work merely to minimize tokens.

## 9. Continuous participation and recovery

After every verified task:

`RESULT -> VERIFY -> LEDGER CHECKPOINT -> MOTOR RECOMPUTES COMPLETE FRONTIER -> CLAIM NEXT ELIGIBLE WORK`.

A worker must not return to the human merely for `continue` while safe authorized work remains.

On worker/session loss:

`CHECKPOINT -> PUSH -> CLEAN OWNED TEMP PROCESSES -> SAFE YIELD/RELEASE -> MOTOR RECOMPUTES -> REPLACEMENT WORKER CONTINUES`.

A fresh authorized worker must be able to reconstruct from canonical repository/Ledger state without old chat.

OS/provider scheduling may wake the canonical continuation path after reboot/session loss, but must not contain Courier scheduling decisions. No LLM polling or arbitrary sleep loop is autonomy.

## 10. Similar bottlenecks to prevent proactively

Treat these as the same class of defect as the chat-queue bottleneck:

- one blocked task freezing an entire goal/pipeline;
- one busy machine/provider causing unrelated READY work to wait;
- stale writer ownership permanently stranding work after a worker/session disappears;
- a verifier becoming a global serial bottleneck when independent verification can be safely parallelized;
- broad test suites rerunning when only causally affected evidence needs renewal;
- repeatedly transmitting unchanged context/files to workers;
- a human gate being raised before all independent safe preparation is exhausted;
- payment configuration blocking pre-payment acquisition/onboarding work;
- deployment trigger being mistaken for successful public deployment;
- background watchers being mistaken for autonomous execution;
- worker count being fixed rather than derived from safe READY frontier and resource capacity;
- one large pipeline starving smaller unrelated READY pipelines;
- machine reboot/session close requiring manual reconstruction;
- local-only fixes not being checkpointed/pushed, making replacement workers redo work;
- retry loops repeating the same failure without new causal information.

Anti-loop invariant: the same meaningful failure twice without new information must trigger deeper causal diagnosis or a durable blocker, not blind repetition.

## 11. Night/unattended safety

Unattended work is limited to already-authorized safe/free/reversible actions. Never autonomously:

- spend money or configure/buy paid services;
- perform prohibited unattended merges;
- change credentials or bypass security controls;
- send unsolicited external sales/social messages;
- fabricate customers, agreements, contact data, payments, deployment proof, or PASS evidence;
- perform destructive broad cleanup.

These are scope-local gates while unrelated safe work continues.

## 12. Required acceptance behavior

The implementation is not complete merely because this document exists. Deterministic tests/evidence should prove:

1. multiple independent READY tasks + multiple eligible workers => concurrent claims/progress;
2. writer/resource collision => only colliding scope serializes;
3. busy foreground agent => independent eligible background workers can progress;
4. human gate + independent work => independent work continues;
5. money gate + free independent work => free work continues;
6. unavailable provider + alternate eligible worker => alternate can claim;
7. passive log watcher/idle shell => not counted as productive worker capacity;
8. worker completion => frontier automatically recomputed without human `continue`;
9. worker/session loss => replacement resumes from durable state without old chat;
10. synthetic unknown future pipeline => schedulable without provider/milestone hardcoding;
11. no READY work => no wasteful worker/model spawning;
12. true global stop => only when the complete safe frontier is blocked or complete;
13. Motor remains the sole scheduler/claim authority and no second queue/truth store exists;
14. dirty working tree + upstream update => synchronization preserves owned work and fails closed only on real collision;
15. foreground queued messages absent => Motor/eligible workers can still make progress;
16. reboot/fresh process => canonical bootstrap reconstructs executable state;
17. stale worker/writer lifecycle => ownership is never silently bypassed and does not freeze unrelated scopes;
18. fan-out/fan-in future pipeline => independent branches progress concurrently and downstream readiness respects evidence;
19. repeated identical failure => no infinite blind retry loop.

## 13. Success metrics

When observable, track:

`VERIFIED_TASKS_PER_HOUR`, `READY_WAIT_TIME`, `ACTIVE_PRODUCTIVE_WORKERS`, `READY_BUT_UNCLAIMED`, `WORKER_UTILIZATION`, `WORKER_MINUTES_PER_VERIFIED_TASK`, `TOKENS_PER_VERIFIED_TASK`, `RETRIES`, `DUPLICATE_WORK`, `RESOURCE_COLLISIONS`, `HUMAN_CONTINUE_MESSAGES`, `FOREGROUND_QUEUE_DEPENDENCIES`, `RECOVERY_TIME_AFTER_WORKER_LOSS`.

Target: increase verified throughput and reduce READY wait time, READY-but-unclaimed work, duplicate work, unnecessary context, recovery time, and human orchestration while never weakening acceptance or safety.

## Permanent invariants

**FULL POWER means maximum safe verified throughput, not maximum resource consumption.**

**If safe READY work exists and eligible authorized capacity exists, Courier should not be waiting on a foreground chat queue.**

**A human should be required for decisions/permissions that genuinely require a human, not for keeping the machine moving.**
