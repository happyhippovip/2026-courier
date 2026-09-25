# Multi-Agent Task Group Protocol

## Purpose
Prevent safety-critical Courier work from being resumed, signed, or dispatched based on an incomplete subset of required agent work. This protocol defines how multiple agents may work in parallel without interfering with one another, how required reports are counted, when waiting is mandatory, and how a coordinator / Super Advisor / gatekeeper can know whether a task group is actually complete.

## Core rule

For every P0/P1 safety-critical repair, create a **Task Group** before or at the moment work is fanned out.

A Task Group is not complete when the first agent says `DONE`.
It is complete only when all **required** roles for that phase have reported and the reconciliation gate has passed.

Canonical flow:

`PLAN_TASK_GROUP -> DECLARE_REQUIRED_ROLES -> DECLARE_PARALLELISM -> RUN -> COLLECT -> RECONCILE -> PROVE -> SIGN -> RESUME`

If required reports are incomplete:

`WAIT_FOR_REQUIRED_REPORTS / NO SIGN / NO RESUME`

If agents conflict:

`CONFLICT -> NO SIGN -> EVIDENCE-BASED RECONCILIATION`

## Task Group Manifest

Every safety-critical Task Group should have a manifest with at least:

- `task_group_id`
- objective
- risk class (`P0`, `P1`, etc.)
- protected host(s)
- protected files / write scope
- required roles
- optional roles
- current report count, e.g. `1/3`, `2/3`, `3/3`
- dependency graph
- `max_parallel_agents`
- `max_parallel_heavy_jobs`
- per-host heavy-job budget
- writer assignment
- reviewer assignments
- red-team assignment
- required evidence before sign-off
- timeout / TTL for every subtask
- cleanup / cancellation rule
- final signer
- final gatekeeper

The counter `1/3` means **one of three required reports has been received**. It does not mean the task is one-third safe or that a majority may proceed.

## Parallelism decision

Not all work should run simultaneously.

Before launching 2/3 or 3/3 tasks in parallel, the coordinator must evaluate:

1. **Write conflict** — do two agents modify the same protected files?
2. **Host conflict** — do two tasks create heavy load on the same machine?
3. **Dependency conflict** — does reviewer B need writer A's patch before B can produce meaningful results?
4. **Evidence conflict** — would concurrent mutation make the evidence non-reproducible?
5. **Resource conflict** — could combined CPU/RAM/disk/process load violate the host safety guard?

Only compatible tasks may run concurrently.

## Default roles for P0 host-safety work

### Single Writer
Exactly one agent owns production-file modifications for the active repair phase.

### Independent Reviewer
Read-only / review role. It may inspect code and design or run explicitly bounded tests after the writer reaches a stable checkpoint, but must not overwrite the writer's protected files in parallel.

### Red-Team Researcher
Researches OS/runtime edge cases and adversarial failure modes. It does not become a production-code writer unless a later phase explicitly reassigns that role.

### Coordinator / Super Advisor
Maintains the Task Group manifest, knows which required reports are pending, reconciles evidence, and may recommend sign-off only when the gate is complete.

### Gatekeeper / Zoll
Checks the manifest before a signed mission may progress. It must be able to answer:
- How many required reports exist?
- How many are complete?
- Which are pending?
- Were any required reports skipped?
- Were concurrent tasks compatible?
- Is the host/resource gate satisfied?
- Is there unresolved disagreement?

If any answer is unsafe or unknown: `NO PASS`.

## Sign-off rule

A Super Advisor or signer must never sign a P0/P1 task based only on the first successful agent response.

Required sign-off input:

- all required reports for the current phase
- reconciliation matrix
- test/evidence proof
- host/resource status
- unresolved-risk list
- explicit `PASS` or `FAIL` recommendation

No ordinary human approval overrides missing required reviews or a host safety failure.

## Phase-aware waiting

Some reviewers should start immediately; others should wait.

Examples:

### Safe parallel example
- Mac Google: single writer / live host implementation
- Windows Google: red-team research on separate machine

These may run concurrently because they do not modify the same production tree and do not compete for the same Mac resources.

### Must-wait example
- Codex final patch review requiring the exact final Google diff

Codex may perform architecture research early, but the **final verdict** must wait for the writer's stable patch/commit.

Therefore one Codex task can have two stages:
1. pre-patch architecture review
2. post-patch final verification

Stage 2 cannot be marked complete before the writer checkpoint exists.

## Task interference prevention

Every subtask should declare:

- `mode`: WRITE / READ_ONLY / RESEARCH / TEST
- `host`
- `write_scope`
- `heavy`: true/false
- `depends_on`
- `blocks`
- `timeout`

The scheduler/coordinator may parallelize only when:

- write scopes do not conflict, and
- host heavy-job limits are respected, and
- dependency prerequisites are complete.

For the overheated Mac:

`MAX_HEAVY_JOBS_ON_MAC = 1`

Lightweight read-only analysis may run concurrently only if it does not materially increase resource pressure or alter the evidence under inspection.

## Required checkpoints

A safety-critical Task Group should expose explicit checkpoints:

- `TG_PLANNED`
- `TG_RUNNING_1_OF_N`
- `TG_RUNNING_2_OF_N`
- `TG_WAITING_FOR_REQUIRED_REPORT`
- `TG_WRITER_CHECKPOINT_READY`
- `TG_RECONCILING`
- `TG_CONFLICT`
- `TG_PROOF_PENDING`
- `TG_SIGNOFF_PENDING`
- `TG_PASS`
- `TG_FAIL`

Courier production must not resume from any intermediate state.

## Dynamic findings

If a reviewer discovers a new P0 issue while the Task Group is running:

1. add it to the manifest;
2. invalidate any premature sign-off candidate;
3. determine whether another required reviewer/test is now needed;
4. update `required_reports` and the denominator if necessary;
5. return to `WAIT_FOR_REQUIRED_REPORTS` or `TG_PROOF_PENDING`.

The system must not preserve an old `3/3` badge after the acceptance criteria changed.

## No majority vote

`2/3` agreement is not sufficient when the third required reviewer has stronger contradictory evidence.

Evidence hierarchy:
1. bounded reproducible execution proof
2. actual source/diff
3. OS process/resource evidence
4. authoritative runtime/platform documentation
5. reviewer analysis
6. agent assertion

## Timeout and stuck-task protection

Every subtask in the Task Group must be bounded.

The coordinator must track:
- start time
- deadline
- heartbeat/progress checkpoint
- expected artifact
- cancellation/cleanup behavior

If a reviewer or writer stalls:
- do not silently replace its result with another agent's answer;
- mark the required report `TIMED_OUT`;
- decide explicitly whether to retry, reassign, or fail the Task Group.

No infinite `TASK RUNNING` state is acceptable.

## Current host-overheat Task Group example

Recommended required roles:

1. **Google/Antigravity Mac** — single writer + live host validation
2. **Codex** — independent architecture/code reviewer; final verdict after writer checkpoint
3. **Google Windows** — independent red-team research; may finish earlier on separate host

Current safety rule:
- Windows research may run in parallel.
- Codex pre-review may run in parallel if read-only/lightweight.
- Codex final verification must wait for Google Mac's stable patch/report.
- No Courier production resume until required final reports are reconciled.

## Permanent operational rule

Before the Super Advisor signs any future safety-critical multi-agent mission, the Task Group manifest must explicitly answer:

`WHY 1 AGENT? WHY 2 IN PARALLEL? WHY 3 IN PARALLEL? WHY WAIT?`

The chosen degree of parallelism must be justified by dependencies, write isolation, host resources, and evidence integrity — not by available quota alone.

**More available model limit is not a reason to create unsafe concurrency.**

The system optimizes for safe convergence, not maximum simultaneous agent count.
