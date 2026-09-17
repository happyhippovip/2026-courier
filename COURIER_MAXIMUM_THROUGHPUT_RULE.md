# Courier Maximum Throughput Rule

Status: **CANONICAL OPERATING RULE**

Purpose: maximize **verified useful work completed per unit of wall-clock time** while preserving Courier's ownership, acceptance, safety, reproducibility, and cost controls.

This rule complements `COURIER_AUTONOMOUS_EXECUTION_PLAN.md`. It does not create a scheduler, queue, Motor, or truth store.

## 1. Core rule

**COMPLETE FRONTIER -> MAXIMUM SAFE PARALLELISM -> VERIFY -> LEDGER -> RECOMPUTE -> CONTINUE**

Courier must continuously expose the complete safe executable frontier. Independent, non-overlapping READY work should be executed concurrently whenever eligible authorized worker capacity exists.

The objective is not maximum agent count, token consumption, CPU activity, terminal processes, or chat activity. The objective is maximum **causally verified completed tasks/hour**.

## 2. Authority boundaries

- Motor remains the sole runtime scheduler, eligibility/claim authority, and owner of executable task routing.
- Ledger remains durable coordination/evidence/handoff state; it is not a scheduler or queue.
- Antigravity chat Queued Messages are not Courier's task queue and must never be required for durable autonomy.
- Provider/OS background or scheduled-agent facilities may provide worker capacity or wake/recovery only. They must not decide Courier task ownership.
- One writer per logical scope/resource. Parallelism never overrides ownership.

## 3. Worker pool

Courier may use all legitimately available authorized capacity, including Mac Antigravity, Windows Antigravity, Google CLI, deterministic local scripts/tools, and future authorized workers/providers.

Workers are matched generically using declared task requirements and worker descriptors rather than hardcoded provider names.

A busy/unavailable worker, provider wait, session/quota end, human gate, money gate, or writer collision blocks only its causally affected scope. Independent safe work continues.

Do not automate account rotation, quota circumvention, or provider-limit evasion.

## 4. Productive work vs fake activity

Productive capacity means a worker is claiming/executing/verifying eligible Courier work.

The following do NOT count as productive progress by themselves:

- `Get-Content -Wait`, `tail -f`, or passive log watchers;
- sleeping/polling shells;
- idle terminals;
- queued chat messages waiting for a foreground turn;
- plans, prompts, branches, PRs, logs, or code inspection without acceptance evidence;
- duplicate workers reasoning about the same scope without an explicit independent-verification purpose.

Long-lived required Motor/worker services are infrastructure, not completed-task evidence.

## 5. Generic future-pipeline contract

Motor scheduling logic must not hardcode Courier release milestones, YouTube, TikTok, websites, lead intake, customer workflows, analytics, or any future provider/workflow name.

New workflows must be expressible primarily through durable task/plan definitions using:

`TASK -> DEPENDENCIES -> CAPABILITIES -> AUTHORITY -> RESOURCE OWNERSHIP -> GATES -> ACCEPTANCE -> EVIDENCE`

A completely new future pipeline should be addable without rewriting Motor scheduling logic when its tasks correctly declare those properties.

Multiple goals/pipelines may coexist. A gate in one pipeline must not freeze unrelated READY work in another. Fairness/bounded concurrency must prevent one large pipeline from permanently starving unrelated READY work.

## 6. Worker selection efficiency

Default preference:

1. deterministic script/tool when reasoning is unnecessary;
2. bounded CLI worker for mechanical inspect/build/test/hash/git/evidence work;
3. strongest suitable reasoning worker for uncertain debugging, architecture, causal analysis, multi-file implementation, integration, and acceptance reasoning;
4. another authorized eligible worker when it provides better throughput or the preferred worker is unavailable.

Use minimal task packets, relevant diffs/files/evidence, hashes/manifests, dedupe, and still-valid causal evidence. Do not reconstruct context from old chat when canonical state is sufficient.

Use full-capability workers where they materially increase verified throughput. Do not artificially underpower difficult work merely to minimize tokens.

## 7. Continuous participation

After every verified task:

`RESULT -> VERIFY -> LEDGER CHECKPOINT -> MOTOR RECOMPUTES COMPLETE FRONTIER -> CLAIM NEXT ELIGIBLE WORK`

A worker must not return to the human merely for `continue` while safe authorized work remains.

On worker/session loss:

`CHECKPOINT -> PUSH -> CLEAN OWNED TEMP PROCESSES -> SAFE YIELD/RELEASE -> MOTOR RECOMPUTES -> REPLACEMENT WORKER CONTINUES`

A fresh authorized worker must be able to reconstruct from canonical repository/Ledger state without old chat.

## 8. Night/unattended safety

Unattended work is limited to already-authorized safe/free/reversible actions. Never autonomously:

- spend money or configure/buy paid services;
- perform prohibited unattended merges;
- change credentials or bypass security controls;
- send unsolicited external sales/social messages;
- fabricate customers, agreements, contact data, payments, deployment proof, or PASS evidence;
- perform destructive broad cleanup.

These are scope-local gates while unrelated safe work continues.

## 9. Required acceptance behavior

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
13. Motor remains the sole scheduler/claim authority and no second queue/truth store exists.

## 10. Success metrics

When observable, track:

`VERIFIED_TASKS_PER_HOUR`, `WORKER_MINUTES_PER_VERIFIED_TASK`, `TOKENS_PER_VERIFIED_TASK`, `RETRIES`, `DUPLICATE_WORK`, `READY_WAIT_TIME`, `ACTIVE_PRODUCTIVE_WORKERS`, `RESOURCE_COLLISIONS`, `HUMAN_CONTINUE_MESSAGES`.

Target: increase verified throughput and reduce READY wait time, duplicate work, unnecessary context, and human orchestration while never weakening acceptance or safety.

## Permanent invariant

**FULL POWER means maximum safe verified throughput, not maximum resource consumption.**
