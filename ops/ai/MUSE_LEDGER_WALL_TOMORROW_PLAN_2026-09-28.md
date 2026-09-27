# Muse Ledger Wall — Tomorrow Plan — 2026-09-28

Status: PREP ONLY. Activate after Google ledger writer produces a tested isolated ledger foundation and taskbank.

## Goal

Use Muse windows tomorrow as bounded ledger workers without making Muse the control-plane authority.

## Activation prerequisites

- Google ledger isolated branch exists
- focused ledger tests pass
- MUSE_LEDGER_WALL_TASKBANK_2026-09-28.md exists
- Windows final-candidate writer is not disturbed
- no task requires editing the five Windows-owned final-candidate files
- Mac resource admission is checked before any heavy execution

## Default wall composition

Start small:
- 1 coordinator/read-only Muse window
- 3 bounded ledger task windows
- remaining windows idle

Only expand if unique taskbank items remain.

No duplicate assignments.

## Good Muse tasks

- ledger fixtures
- schema validation
- restart/read tests
- customer projection redaction tests
- complaint/refund state-machine fixture tests
- entitlement evidence fixtures
- event ordering/integrity tests
- documentation extraction
- contradiction hunting
- integration-hook review

## Forbidden

- second scheduler
- second queue authority
- changing Windows final-candidate files
- running physical Canary
- payment-provider live actions
- real refunds
- storing credentials
- heavy fan-out because the Mac happens to be idle

## Cool-machine bonus rule

If Mac resource admission reports enough headroom:
- allow one additional bounded Muse execution at a time
- prefer CPU/light test/doc tasks
- reevaluate after each heavy task

Do not infer safety from temperature feeling alone. Use resource evidence.

## Customer safety

All ledger/customer work must preserve:
- append-only corrections/refunds
- unknown money state stays unknown
- provider IDs as references
- no payment secrets in ledger
- customer-only projection/export
- complaint/resolution traceability

## End condition

When taskbank has no unique P0/P1 ready tasks:
MUSE_LEDGER_WALL_DONE=YES
and stop the wall.

Do not create filler work.
