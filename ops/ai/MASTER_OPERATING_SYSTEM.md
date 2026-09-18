# Courier Symphony Muse — Canonical AI Engineering Operating System

CODE_BASE_HEAD: 0c8d1eddacb15dedbebb8406e475917dc2ab1c2b
UPDATED_AT: 2026-09-18T09:23:33+02:00

## Objective

Maximize verified engineering output per hour and per scarce independent-review
unit while preserving one runtime authority and truthful acceptance.

## Flow

NEWSY read-only prefetch → MUSE invariant and packet QA → GOOGLE implementation
and Windows/runtime → T0 → T1 → T2 → T3 adversarial gate → CODEX independent
review when justified → T4 at an integration boundary → artifact update.

## Authorities

- The Motor is the sole scheduler and claim authority.
- Canonical server state is runtime truth.
- The Ledger is durable evidence/handoff state, never a scheduler or proof
  producer.
- The cockpit is an observer, never runtime truth.
- Worker/provider metadata is capacity information, not workflow truth.

## Task packet

Implementation packets require task identity, current SHA, owner, evidence,
exact file/function, reproducer, invariant, bad behavior, targeted and negative
tests, affected suite, replay/restart/concurrency/provider-wait cases,
dependencies, batchability, and readiness.

Codex review packets additionally require commits under review, T2/T3 results,
known attacks, bounded files to read, and explicit questions.

## Tests

T0 is syntax/import/schema/isolation sanity. T1 is the exact regression. T2 is
the affected component suite. T3 is the small adversarial truth gate. T4 is a
sharded integration boundary, not a routine inner-loop test.

Every process has a bounded lifetime and an owned PID. Generic process kills are
forbidden. Shared-state and physical tests run serially.

## External boundaries

Payment, customer contact, publication, public deployment, pilot onboarding,
credential rotation, unattended merge, and irreversible external actions remain
explicit human gates. Preparing an action is never proof it occurred.

## Truth law

REAL EVENT → DURABLE STATE → EVIDENCE → INDEPENDENT VALIDATION →
SHA/RUNTIME/FRESHNESS CHECK → ACCEPTANCE GUARD → LEDGER LAST.
