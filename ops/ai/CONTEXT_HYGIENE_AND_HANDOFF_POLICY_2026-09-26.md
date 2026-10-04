# Courier Context Hygiene + Featherlight Handoff Policy — 2026-09-26

Status: HARD OPERATING RULE FOR AGENT/CHAT WORK

## Purpose

Long-lived AI chats and agent sessions accumulate stale history, duplicate instructions, obsolete branches, repeated logs and irrelevant tool output. That increases latency, token/API cost, confusion risk and local client/resource pressure.

The operational response is **checkpoint -> clear -> reload only current truth**.

This is a performance and correctness rule. It is not a claim that computers literally explode; the concrete risks are context bloat, slower turns, higher cost, stale reasoning, duplicate work and unnecessary host load.

## Core invariant

**PAST THAT NO LONGER CHANGES THE NEXT DECISION MUST NOT STAY IN ACTIVE CONTEXT.**

Do not carry old conversation history merely because it exists.

## Required transition

Before any deliberate /clear, new chat, provider switch, agent handoff or major phase change:

1. persist durable evidence/results that matter;
2. update the authoritative checkpoint/ledger;
3. record unresolved blockers and the exact next action;
4. remove secrets/transient logs from the handoff;
5. CLEAR / start a fresh session;
6. reload only the smallest current truth package;
7. continue from durable state, not conversational memory.

## Clear triggers

CLEAR is strongly preferred when any of these are true:

- current task/phase is finished;
- candidate/base/plan moved forward and old analysis is stale;
- the session contains large logs no longer needed;
- the model repeats earlier work;
- response latency rises materially because of conversation size;
- more than one old plan/version competes in context;
- the next task needs less than roughly one quarter of the current session history;
- an agent/provider/host changes;
- a long overnight round finishes;
- a reviewer hands back to the writer/coordinator;
- an old diagnostic thread is no longer relevant.

Do not clear in the middle of an uncheckpointed mutation or before preserving the only copy of evidence.

## Featherlight handoff capsule

A normal handoff should contain only:

- GOAL
- CURRENT_CANONICAL_BASE / SHA
- CURRENT_GATE
- OWNERSHIP / WRITER
- PROVEN
- OPEN
- BLOCKED
- DO_NOT_REPEAT
- NEXT_EXACT_ACTION
- SAFETY / MONEY / PERMISSION GATES
- pointers to durable repo evidence

Prefer pointers to repo artifacts over pasted megabyte logs.

## Session bootstrap rule

Fresh sessions must read durable coordination state first.

For Courier today that includes, as applicable:

- ops/ai/COURIER_SESSION_STATE_2026-09-26.json
- ops/ai/RETURNED_RESULT_POLICY.md
- ops/ai/WALL_CONTROL_INDEX_2026-09-26.md
- the exact current mission file

Do not replay the whole project history.

## YOLO / auto-approval startup

The user may explicitly choose a provider's YOLO/auto-approval mode for trusted local work.

Rules:

- it is an **execution convenience**, never authority to bypass Courier safety;
- human/money/credential/publication/deployment/destructive gates remain gates;
- repo writer ownership remains binding;
- host/resource guards remain binding;
- broad deletes, process kills, payments, account changes and irreversible external actions are never implied by YOLO;
- use only where the provider/runtime supports it and the user has explicitly selected it.

Never silently convert a normal session into YOLO.

## Handoff quality metric

A good handoff lets a fresh capable agent answer within minutes:

1. What are we trying to prove/do?
2. What is already proven?
3. What must not be repeated?
4. Who owns writes?
5. What exact action comes next?

If the handoff cannot do that without reading old chat history, it is too heavy.

## Anti-regression

Every future wall/agent system should treat context as a bounded resource alongside:

- CPU
- RAM
- API quota
- money
- wall-clock time

Context compaction/clear is part of resource safety and continuation correctness.
