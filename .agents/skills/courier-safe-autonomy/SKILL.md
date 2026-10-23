---
name: courier-safe-autonomy
description: Persistent Courier Symphony engineering mode. Use when an authorized session should continue one leased workkey at a time, reproduce failures before any repair, and stop quiescent when no safe work remains.
disable-model-invocation: true
color: blue
---

# Courier safe autonomy

Use this as a Custom Mode by invoking `/courier-safe-autonomy` and choosing Use as Mode. It stays in force until the mode is exited.

This mode does not replace `AGENTS.md`, `courier-orchestrate`, or `courier-night-loop`. Load those first. When they disagree with this file, the stricter existing rule wins.

## Load

1. Read the newest private checkpoint for this lane. Take role, file scope, owner, lease, HEAD, and the next workkey from that checkpoint. Do not assume an old SHA.
2. Read `AGENTS.md` before any product edit. Six writer lanes only. L1 is the only merge lane.
3. If `courier-night-loop` is the invocation, follow that skill and stop. Do not spawn subagents or edit product source on a night-loop wake.
4. If no writer lease is held, do not edit product files. Read-only review is allowed inside the checkpoint's role.

## Work

- Never dispatch a finished workkey again.
- After a real PASS, take the next distinct authorized workkey in this role. Do not invent one.
- Reproduce a failure with one negative test before a repair. Then make the smallest repair that makes that test pass. Do not widen the diff.
- One writer for a conflict area. Do not edit a file another open pull request already changes.
- No merge and no force-push into `integration/v1` without an explicit GO from L1.
- A missing, non-finite, or unknown cost is not free. Do not label an unknown cost as 0. Do not start a paid provider or a new cloud agent when the cost is unknown.
- No real provider call, trade, or wallet signature without an explicit approval.
- Light read-only subagents may inspect separate questions in parallel. They do not edit, merge, or run a second heavy test. One heavy test job per host. Stop spawning helpers on EMFILE or host pressure.
- After five finished workkeys, write one new private checkpoint. Do not overwrite an older checkpoint.
- Skip chat status when nothing changed.

## Stop

When the queue for this role is empty, the lease is missing, the cost is unknown, or the host is under pressure: write one private checkpoint marked `QUIESCENT_SAFE` and end. Do not arm a second loop, a stop hook, or a review cycle to fill the silence.
