# WALL-P2 TRUST/EVIDENCE SECTION (PREP ONLY, no publish)

WORKER=MUSE-19 · HOST=MAC · MODE=READ_ONLY · 2026-09-26
SOURCES: docs/WEBSITE_BLUEPRINT_2026.md (§5 live proof, §6 security, Evidence system, §10 company page),
Z10 claim discipline (muse_zero_interference), WALL_STATUS.md (first core blocker),
RV04_PROOF_TO_SALE.md + RV08_EVIDENCE_CARD_SPEC.md (card shapes, burn30 reports).
REPO UNTOUCHED. No metrics invented. No Product Shell.

## Placement (per blueprint core pages)
Section lives on `/product` (proof block) with a one-line summary on `/`
and the full evidence log feeding `/funding` (blueprint §7: milestones +
measured reliability + technical evidence). Security items (§6 list) live on
`/security`; this section links there instead of duplicating.

## Copy blocks (draft, gated per claim below)

HEADLINE: "Proof, not promises."
SUB: "Every technical claim on this page points to evidence you can check.
Where the evidence is not finished yet, we say so — in the same place,
not in a footnote."

BLOCK 1 — How we prove things (publishable now):
"Our rule: a finished step has a recorded run, an independent check, and a
card you can re-verify. The worker that does the work never certifies its
own result — a second, independent check must pass first. Cards are
append-only: corrections add lines, history is never rewritten."

BLOCK 2 — What we show today (honest status):
"Today we show the process and the design: the execution chain
(TASK → ADMIT → EXECUTE → RESULT → PERSIST → VERIFY → RECONCILE → DONE → NEXT),
the status words (RUNNING / WAITING / BLOCKED / UNKNOWN / DONE), and sample
proof cards with placeholder values. Live numbers — completed tasks, uptime,
duplicate rate, recovery time — appear here only after a witnessed run.
Until then this panel says NOT YET MEASURED."

BLOCK 3 — Security posture (intent-labeled):
"Designed for least privilege: temporary credentials, no long-lived keys in
workers, encrypted storage, audit trail, reproducible restore, and UNKNOWN
outcomes handled fail-closed — the system pauses rather than guessing."
(Mandatory label: "design intent, implementation in progress" until drilled.)

## Claim table (binding — do not publish YES rows without their qualifier)

CLAIM=independent verification before advance
CURRENTLY_PROVEN=PARTIAL (contract implemented in repo; 3 verification test
files uncollectable per RV19 GAP-2; end-to-end witnessed run pending)
EVIDENCE_SOURCE=server/app.py claim/result/verify/resume paths (read-only) +
MUSE_A2B_EVIDENCE_CARD design
SAFE_TO_PUBLISH_NOW=YES only as "by design" with NOT-YET-DRILLED qualifier

CLAIM=prover chain / execution lineage (TASK→…→NEXT with attempt identities)
CURRENTLY_PROVEN=PARTIAL (chain works hermetic single-process; physical A→B
unwitnessed in this worker's window)
EVIDENCE_SOURCE=blueprint §2 product proof + RV08 card lifecycle rules
SAFE_TO_PUBLISH_NOW=YES only with sample-card labeling ("illustrative shape,
not a run result")

CLAIM=live metrics (completed tasks, uptime, duplicate/lost-result rates,
cost per task, recovery time, workflow version)
CURRENTLY_PROVEN=NO
EVIDENCE_SOURCE=none yet (blueprint §5 list is the spec, not the data)
SAFE_TO_PUBLISH_NOW=NO — panel shows NOT YET MEASURED, never zeros, never
placeholders that look like data

CLAIM=recovery drill (kill mid-run → resume, no replay)
CURRENTLY_PROVEN=NO (specified MM2/CLI4, run not done; verifier-fail-gate
M45 still OPEN per WALL_STATUS)
EVIDENCE_SOURCE=design docs only
SAFE_TO_PUBLISH_NOW=NO — listed under "next proofs", never as done

CLAIM=least-privilege / audit-trail security list
CURRENTLY_PROVEN=NO (blueprint §6 is a build list)
EVIDENCE_SOURCE=docs/WEBSITE_BLUEPRINT_2026.md §6
SAFE_TO_PUBLISH_NOW=YES only labeled design intent

## NEVER on this section (blueprint §10 + §5 rules)
- No numeric counters of any kind (no "0 tasks lost", no uptime %).
- No customer names, logos, quotes, counts. No investors, partners, offices,
  employees. No AWS partnership claim (blueprint: portable, AWS preferred,
  partnership only if confirmed — it is not).
- No "verified/secure/certified" badges. No fake dashboard (blueprint visual
  direction: no fake dashboards, no glowing gradients).
- No use-case page entries beyond demonstrable ones.

## Open unknowns (stay UNKNOWN, block publish of dependent copy)
- docs/COURIER_GRANDMA_TEST.md, docs/COURIER_PERMISSION_AND_COMMUNICATION_RULES_2026-09-26.md,
  docs/COURIER_FAST_TRACK_48H_MODE_2026-09-26.md do NOT exist in repo docs/
  (checked 2026-09-26). FAST_TRACK_48H_EXPLANATION therefore deferred to a
  later task with real sources — not drafted here.
- Canonical product plan not yet re-read this turn (cited second-hand via
  WALL-P2-GRANDMA-NOSPAM-MUSE-SUP); next worker should quote it directly
  before finalizing L1 copy.
