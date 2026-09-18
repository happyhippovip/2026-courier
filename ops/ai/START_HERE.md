# COURIER SYMPHONY MUSE — START HERE

This directory is the shared engineering memory for MUSE, Google Antigravity, Codex, NEWSY/read-only scouts, and human operators.

## Artifact binding
BOUND_TO_CODE_HEAD: 7c495f8c1b31293f8d3a5465035d2d3f61cbd3a7
UPDATED_AT_UTC: 2026-09-18

The binding describes the code state used to create this pack. Always revalidate current HEAD, runtime, and ownership before acting.

## Agent startup rule
Every new agent starts here before broad discovery:

1. Read this file.
2. Verify current HEAD and current remote/candidate HEAD.
3. Read `OWNERSHIP_MAP.yaml`.
4. Read only the artifact relevant to the assigned task.
5. Inspect the delta since the artifact's bound code HEAD.
6. Do not rediscover documented facts unless current evidence contradicts them.

## Hard role split

- **MUSE** — primary broker; architecture; invariants; Ledger/Guard/Motor causal reasoning; task factory; artifact QA; difficult cross-component reasoning.
- **GOOGLE ANTIGRAVITY** — primary implementation worker; Windows/runtime; prepared packet execution; T0→T1→T2; integration.
- **NEWSY / READ-ONLY SCOUT** — trace, grep, reproduction, source/test mapping, packet prefetch. No canonical code writes.
- **CODEX** — scarce independent verifier; adversarial review; hard restart/concurrency/root-cause work; final integration/physical-proof verification.

One writer per sensitive scope.

## Required engineering flow

NEWSY prefetch (N+1/N+2/N+3)
→ MUSE invariant + packet QA
→ GOOGLE implementation
→ T0
→ T1 fast
→ T1 full
→ T2 affected suite
→ related fixes batched where safe
→ T3 adversarial gate
→ CODEX independent review when justified
→ T4 at integration boundary
→ close

If Codex receives an incomplete packet, return `PACKET_INCOMPLETE` to MUSE/NEWSY instead of spending Codex on repo archaeology.

## Truth chain

REAL EVENT
→ DURABLE STATE
→ REAL EVIDENCE
→ INDEPENDENT VALIDATION
→ SHA / RUNTIME / FRESHNESS CHECK
→ ACCEPTANCE GUARD
→ LEDGER LAST

Never patch desired Ledger state to manufacture completion.

## Physical acceptance

Software tests and mocks are not physical proof. Physical proof must bind to the actual canonical Windows runtime, exact reviewed SHA, actual process identity, durable restart/resume, and real observed task flow.

## Permanent short rule

**PACKET FIRST. ONE WRITER. T0→T1→T2. T3 BEFORE CODEX. T4 ONLY AT BOUNDARIES. BLOCKED TASK != BLOCKED PROJECT. LEDGER LAST. NO FAKE GREEN.**
