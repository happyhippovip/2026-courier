# Mac + Muse Finish-Day Expansion — 2026-09-28

Current durable hard blocker at creation:
PRE_CODEX_STATE=DURABILITY_PENDING.
Only one gate persistence owner may work that blocker.

## Mac: use concrete finish deliverables

Start 12 Mac logical windows:
- 01-04 infrastructure binding/ownership packets
- 05-08 artifact/event/A-once/zero-relay packets
- 09-12 failure/replay/verify/reconcile/NEXT_READY packets

When those complete, switch those same windows to:
- 13-18 RUN_1/RUN_2 operator/result/Proof Card/Core Freeze packets

Then:
- 19-20 retest/evidence index
- 21-23 pilot packets only after Core Freeze becomes real
- 24 Product Shell gate packet only after positive real pilot signal

Recommended active Mac logical windows: 12-18.
MAX_HEAVY_JOBS=1.

## Muse day wall

Round A — 12 windows:
- 01 Ledger finish acceptance
- 02 gate durability observer
- 03 final-candidate handoff QA
- 04 exact 12-case matrix QA
- 05 trusted-hash semantics
- 06 replay semantics
- 07 RUN_1 falsifiability
- 08 RUN_1 evidence minimality
- 09 RUN_2 falsifiability
- 10 restart-race QA
- 11 failed-execution QA
- 12 human-relay QA

Round B — after A results are durable:
- 13 runtime binding
- 14 process isolation
- 15 Proof Card
- 16 Core Freeze gate
- 17 result cache
- 18 cross-host handoff
- 19 cross-provider handoff
- 20 resource bounds

Round C — only when phase permits:
- 21 pilot consent
- 22 pilot metric QA
- 23 pilot value signal
- 24 Product Shell scope after positive pilot signal

Recommended Muse concurrency:
12 first round, then 8 second round.
Do not keep old Ledger/restart walls alive after their fingerprints are complete.

## Goal

These are not filler queues.
Every task must create one closure packet, acceptance verdict, or exact blocker that directly supports:
PRE_CODEX -> Codex -> RUN_1 -> RUN_2 -> Core Freeze -> Pilot -> Product Shell.
