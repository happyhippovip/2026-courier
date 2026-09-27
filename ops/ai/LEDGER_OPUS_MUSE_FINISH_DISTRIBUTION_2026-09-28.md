# Ledger Finish — Opus + Muse Distribution Plan — 2026-09-28

Goal: finish Ledger preparation/QA without duplicating Google deterministic work.

## Opus 4.6

Recommended active windows:
- 2 windows default
- 3 windows if distinct OL tasks remain
- 4 maximum for a short burst
- do not use more merely because accounts are available

Suggested split:
- Opus 1: OL-01..OL-04
- Opus 2: OL-05..OL-08
- Opus 3: OL-09..OL-12
- Opus 4: OL-13 synthesis only when enough prerequisites are complete

Prompt:
ops/ai/OPUS46_LEDGER_FINAL_CONVERGENCE_WORKER_PROMPT.txt

## Muse

When Muse is available:
- 4 windows default
- 6 windows is good if ML claims are free
- 8 maximum only with distinct unclaimed ML tasks

Suggested split:
- Muse 1: ML-01 / ML-02
- Muse 2: ML-03 / ML-04
- Muse 3: ML-05 / ML-06
- Muse 4: ML-07 / ML-08
- Muse 5: ML-09 / ML-10
- Muse 6: ML-11 then ML-12

Prompt:
ops/ai/MUSE_LEDGER_ADVERSARIAL_FINISH_WORKER_PROMPT.txt

## Google

Keep Google on deterministic Ledger tasks and exact targeted checks.
Do not move C0/C1 work to Opus/Muse.

## Finish condition

Ledger finish is not "many reviews."
Finish when:
- GLEDGER-130 is complete or exact blockers are known;
- OL-13 converges semantics;
- ML-12 independently QA's the finish gate;
- Central Writer packet is ready or exact source blockers remain;
- no gate-violating Ledger UNKNOWN remains.

Then:
LEDGER_PREP_COMPLETE=YES
and stop creating more Ledger-review queues unless a RETEST_TRIGGER changes.
