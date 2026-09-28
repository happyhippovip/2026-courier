# Turbo 3h Finish Plan + Window Routing — 2026-09-28 14:50

Status: ACTIVE ENDGAME ROUTING

## Current split-brain to resolve first
Local Muse convergence reports:
- PRE_CODEX_STATE=DURABLE
- AUTHORITATIVE_READY=YES
- READY_TO_SKIP_OPUS=YES
- CODEX_WHEN=NOW
- FINAL_SHA=34b0a426...
- no causal BEFORE_CODEX defect

Canonical coordination branch currently still says:
- PRE_CODEX_STATE=DURABILITY_PENDING
- AUTHORITATIVE_READY=NO
- reported FINAL_SHA unresolved

Therefore the FIRST and ONLY gate-write action is:
one Windows Central Writer reconciles/publishes canonical gate/handoff truth.
No other writer may touch final-candidate application source until this split is resolved.

## Model budget
- Opus 4.6 now: 1 XHIGH arbitration call. Optional second only if actually available and a real ambiguity remains.
- Supercode: 0 before Codex. Reserve for a concrete nontrivial Codex/RUN failure repair.
- Codex: one HIGH review on exact authoritative fixed candidate. Material source delta after review invalidates that review.
- Muse: 16 read-only C2 windows, distinct tasks.
- Google Windows: 1 writer + 5 read-only C1 windows.
- Google Mac: 4 prep windows until Codex GREEN.
- Heavy jobs: max 1 per host.

## Critical invariant
Do not silently apply application-source patches after Codex GREEN and then run physical proof.
If a required BEFORE_RUN1 packet changes reviewed application source:
NEW FINAL_SHA -> invalidated targeted evidence only -> authoritative gate -> Codex review for the new material fingerprint.

## 14:50-15:05
W1 resolves canonical gate split.
O1 resolves finality/review-order ambiguity.
Muse M1-M16 and Google read-only windows prepare post-Codex packets.

## 15:05-15:30
If authoritative gate is green: Codex HIGH once.
If not: only W1 continues gate work. Do not duplicate.

## 15:30-16:10
Codex BLOCKED: smallest defect packet -> sole writer -> minimal retest -> new SHA/review only if material source changed.
Codex GREEN: exact Mac handoff. Apply only proof/ops tooling that does not invalidate reviewed application source.

## 16:10-16:45
RUN_1 one physical owner. Any FAILED execution invalidates verdict.
Muse switches to actual-instance QA immediately.

## 16:45-17:15
RUN_2 only after RUN_1 PASS. Restart/no-A-replay/B continuation/A-count=1.

## 17:15-17:35
Core Freeze.

## 17:35-18:00
Minimum real pilot and release/product-shell decision.
Positive real pilot signal required for Product Shell unlock.

## Muse assignments
M01 A1 adapter-confinement packet
M02 Q1 take-latest binding packet
M03 Q3 crash-window/quarantine packet
M04 replay ACK worker-sensitive equivalence
M05 kill/reap process cleanup
M06 TIMEOUT->FAILED mapping
M07 T1-T6 acceptance matrix
M08 VIS P0/P1 truth-batch packet
M09 RUN_1 independent witness layout
M10 RUN_2 restart/no-replay witness
M11 Mac exact-binding/isolation packet
M12 proof-hash/exit/failure evidence coverage
M13 returned-result autonomy / successor dispatcher
M14 subagent budget + usage telemetry review
M15 window-capacity control safety review
M16 Core-Freeze + pilot minimality

## Google Windows assignments
W1 sole Central Writer: canonical gate/handoff reconciliation.
W2 read-only writer-patch dependency graph.
W3 read-only minimal retest/invalidation matrix.
W4 read-only Mac handoff build.
W5 read-only window-capacity/usage-telemetry integration check.
W6 read-only no-Opus deterministic convergence.

## Google Mac assignments
GM1 exact binding slots.
GM2 process/resource/isolation.
GM3 RUN_1 commands/evidence.
GM4 RUN_2 restart/evidence.

## Stop rules
- old 65-96 = STOP.
- family complete = do not repeat.
- blocked other owner = route away.
- no full-suite unless material trigger.
- no Opus bulk scans.
- no Supercode before a concrete blocker.
- no product-shell claims before positive pilot.
