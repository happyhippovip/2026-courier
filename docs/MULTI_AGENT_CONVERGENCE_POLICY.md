# Multi-Agent Convergence Policy

## Purpose
Prevent Courier from acting on a single incomplete agent conclusion when multiple independent agents are intentionally working on the same safety-critical problem.

This policy is especially relevant to host safety, subprocess control, resource guards, retries, autonomy loops, billing/authentication safety, and other P0/P1 system risks.

## Core rule

**When multiple independent reviewers are active for the same safety-critical decision, Courier must wait for all required reviews before resuming production or declaring the issue solved.**

A faster answer from one agent does not cancel the pending review from another required agent.

Canonical decision flow:

`SINGLE_WRITER -> INDEPENDENT_REVIEWERS -> COLLECT_REQUIRED_REPORTS -> RECONCILE -> RESOLVE_DISAGREEMENTS -> PROVE -> RESUME`

If one required report is still pending:

`WAIT_FOR_REQUIRED_REVIEW / NO RESUME`

If reviewers materially disagree:

`CONFLICT -> NO RESUME -> EVIDENCE-BASED RECONCILIATION`

## Roles

### Single writer
Exactly one agent may modify the protected production files for the active fix.

### Independent reviewer
A reviewer may inspect code, research failure modes, design bounded tests, and challenge the writer's approach, but must not concurrently overwrite the writer's production changes.

### Red-team researcher
A red-team agent may search for edge cases, OS/runtime failure modes, concurrency races, crash windows, and missing safeguards. Its findings are advisory until independently verified against authoritative evidence and the actual code.

### Coordinator
The coordinator merges reports, distinguishes verified facts from hypotheses, identifies contradictions, and decides whether the resume gate can be evaluated.

## Required waiting behavior

For a safety-critical task, the coordinator must explicitly track which reports are required before the next state transition.

Example:
- Google/Antigravity Mac: implementation + live host validation
- Codex: independent code/architecture review
- Google Windows: adversarial research report

If Mac implementation and Codex review are required, Courier must not resume merely because Windows research or the writer finishes first.

## Evidence hierarchy

When reports conflict, prefer in this order:

1. Reproducible local execution evidence from bounded tests
2. Actual current source code / diff
3. OS-observed process state and durable logs
4. Authoritative platform/runtime documentation
5. Independent technical review
6. Agent inference/speculation

No agent's self-declared `FIXED`, `SAFE`, or `RESUME` statement is sufficient by itself.

## Research claims are not automatically implementation requirements

Red-team findings may contain mistakes, platform-version differences, or overconfident conclusions.

Before converting a research claim into P0 production code:
- verify it against authoritative documentation or a bounded local reproduction;
- ensure the mitigation does not create a larger safety problem;
- record whether the claim is VERIFIED, PLAUSIBLE, DISPROVEN, or UNRESOLVED.

## Convergence gate

A multi-agent safety task is ready for final evaluation only when:

- required writer report received;
- required independent reviewer report received;
- relevant red-team findings triaged;
- contradictions explicitly reconciled;
- P0 items have concrete code/test evidence;
- no required review remains pending;
- host/system observation period required by the active safety policy is complete.

Then and only then may the normal resume gate be evaluated.

## No automatic majority vote

Two agents agreeing does not override one reviewer with stronger evidence.

The system uses evidence-weighted reconciliation, not majority voting.

## No unnecessary waiting

Waiting is required only for reviews declared necessary for the active gate. Independent low-risk tasks may continue elsewhere if they cannot interfere with the protected host/code path.

## Permanent lesson from host-overheat incident

The Mac host-safety incident demonstrated that implementation, code audit, and adversarial platform research can reveal different classes of failure. Future P0 host-safety fixes must allow the coordinator to intentionally wait for multiple independent results instead of accepting the first confident completion message.

## Operational requirement

Any future agent coordinating a P0/P1 multi-agent repair must read this document together with the active incident/resume-gate policy before declaring production safe to resume.
