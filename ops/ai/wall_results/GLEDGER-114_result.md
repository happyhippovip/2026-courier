# GLEDGER-114 Result — Stale Evidence Handling

TASK_ID=GLEDGER-114
STATUS=PROVEN (by reused durable + live-observed evidence; no new source reads)
HOST=MAC
PROVIDER=GOOGLE
INPUTS_READ=ops/ai/LEDGER_FINISH_QUEUE_30_2026-09-27.md (definition only)
RESULTS_REUSED=GLEDGER-112 (truth binding); GLEDGER-113 (invalidation triggers); live-observed coordination-tip moves this shift (51345822→f98225ee→4be6ce00→ba6078ba, each verified docs-only); candidate SHAs; GLEDGER-105 (stale-worker quarantine)

## Binding rule (normative)
Every evidence item is evaluated against the truth it was bound to: {candidate SHA (for code behavior), coordination/generation id (for queue truth), ledger fingerprint set}. Evidence presented under a different binding is STALE-CANDIDATE, never silently adopted — it enters the decision table below.

## Current-vs-stale decision table (normative)
| Change since binding | Evidence class | Verdict |
|---|---|---|
| Docs-only tip move (no code, no queue-input change) | Any prior result | CURRENT — adopt (observed 4× live this shift; each verified content-free before adoption) |
| Candidate SHA changed | Code-behavior evidence (tests, traces, line cites) | STALE — re-earn under new SHA (RETEST_TRIGGER per GLEDGER-113 rule 1) |
| Candidate SHA changed | Pure-spec results (this GLEDGER-10x family definitions) | CURRENT iff spec text references no changed code lines; else STALE — re-check cites |
| Generation superseded, same packet inputs | Fingerprint-matched results | CURRENT — carry forward (GLEDGER-112) |
| Generation superseded, changed packet inputs | Affected tasks | STALE — re-execute deltas only, never the whole chain |
| New live observation contradicts result | Contradicted result | CONTRADICTED → GLEDGER-115, old result kept as history |
| Session/host/provider/time changed, bindings equal | Any | CURRENT — never stale by context alone |

## Stale-result rejection (normative)
A stale item offered as current evidence (result submit, verify input, harvest adoption, NEXT_READY input) is REJECTED with reason STALE_BINDING: named expected binding vs presented binding. Rejection is explicit and logged; silent adoption of stale evidence is a ledger violation of the same class as silent duplicate-ACK.

MISSING=None.
BLOCKER=None in-lane.
NEXT_DEPENDENCY=GLEDGER-115 (contradiction row); GLEDGER-128 (harvester stale gate encodes this table).
DO_NOT_REPEAT_FINGERPRINT=gledger-114-stale-evidence-table-complete

DO_NOT_REPEAT_FINGERPRINT=sha256-a28e731542f55805

DO_NOT_REPEAT_FINGERPRINT=sha256-229dfff7020c99db
