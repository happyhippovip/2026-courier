# MUSE MAC WINDOW 8 — Proof Cards & Core Freeze False-Green Review

STATUS=COMPLETE (audit only — no execution, no source edits, no physical runs)
BASE=origin/candidate-b-1@4c1e24ccc522042af826bc4c2b595daf85d097f9
SESSION=cloud-octans (MUSE, MAC) · DATE=2026-09-28
GATE=PRE_CODEX_STATE=DURABILITY_PENDING, AUTHORITATIVE_READY=NO
AUDITED (bounded, exact durable summaries + `git show` on BASE):
- `courier_work/muse_mac_wall/reports/GATEB18-RUN1-PROOF-CARD.md`
- `courier_work/muse_mac_wall/results/MMAC-117_TWELVE_CASE_ACCEPTANCE_PROOF.md`
- `courier_work/muse_mac_wall/reports/FINAL-GATE-STALE-PROOF-AUDIT-20260926.md`
- `courier_work/muse_mac_wall/reports/M10_RUN1_EVIDENCE_REQUIREMENTS.md`
- `courier_work/muse_mac_wall/results/MMAC-031-L4-RESTART-DURABILITY-CRASH-WINDOW-MAP__google-mac.md`
- `courier_work/muse_zero_interference/MAC-06-01a0d7e1-20260926T144729Z/RUN_1_INVALIDATION.md`
- BASE `server/app.py:355-380` (intake), `:521-544` (resume), `:416-454` (reclaim),
  `:185-215` (restarted-worker), `:50-80` (atomic save); `scripts/artifact_store.py:23`
- `git rev-parse origin/candidate-b-3` → fatal (absent); `/Users/user/.local/bin/muse` present

## Classification ledger

PROVEN:
- P1 fixture hashes independently reproduced (stale-audit 4/4: d651ebc0 14B,
  0028c9c7 18B, 57511433 13B, newline variant) — content hashes, not commits.
- 12-case code mapping exists on BASE for the *tested* sub-cases (117 table).
- Atomic persistence: `save_state` tmp+fsync+`os.replace`; daemon `atomic_json`.
- Resume semantics: retry→QUEUED+fresh attempt/dispatch; `force_success`→400.
- Reclaim: stale→quarantine (`STALE_WORKER_EFFECT_AMBIGUOUS`, reclaimed: 0).
- Intake branches as coded: 3-field triple→ACK_DUPLICATE, else 409.

PREPARABLE_NOW:
- GATEB18 skeleton pre-fill for b-1-bound non-starred fields (paths, IDs).
- RUN_1 command binder with FINAL_SHA as explicit placeholder (per MAC-HNI-01 rule).
- This file = the Core-Freeze False-Green Review (see BACKUP).

RUN1_DEPENDENT:
- M10 E1–E14 physical evidence chain; GATEB18 starred fields (attempt_A/B,
  artifact_A/B hashes, ack/verify log refs, final_state sha256).
- `relay_audit` + `human_interventions`: template fields, zero runs → unproven.

RUN2_DEPENDENT:
- Z07 kill-restart segment; W1–W8 physical confirmation (031 is map-only).
- No-A-replay + B-continuation on hardware; `MAC06_RUN2_RESTART.md` execution
  (currently PREPARED_NOT_EXECUTED, gate closed).

UNKNOWN (writer decisions, not mine to take):
- U1 F1/F2: same-triple/changed-payload resend semantics (ACK vs 409).
- U2 R1: post-resume superseded-result replay semantics (200 vs 400/409).
- U3 FINAL_SHA 34b0a42… resolvability/authoritative readiness.

BLOCKING:
- B1 M10-E1 pins `origin/candidate-b-3` — ref absent (re-verified today).
- B2 PRE_CODEX DURABILITY_PENDING — single persistence owner only; no second validator.
- B3 Physical RUN_1 on Mac Antigravity (operator/hardware-gated).

## Concrete findings (5)

F1 — UNKNOWN als PASS (MMAC-117 cases 8/10/12): the table stamps PROVEN, but
BASE `app.py:366-368` ACKs on the bare `(dispatch_id, result_id, status)`
triple ignoring worker/artifacts, and `resume retry` clears no stored result.
Same-triple/changed-payload resends (F1/F2) and post-resume superseded replays
(R1) ACK 200 on untested sub-cases the strict table does not cover. The PASS
stamp exceeds its tested surface — writer decision U1/U2 required before any
freeze-grade claim.

F2 — Stale fingerprint (M10-E1): evidence matrix demands candidate binding to
`origin/candidate-b-3`; the ref does not resolve (`fatal: unknown revision`,
checked 2026-09-28). No E1-compliant run is constructible today. E1 as written
is BLOCKING (B1), not merely pending.

F3 — Covered Surface zu groß (MMAC-117 "five-file scope"): the proof's own
table grounds cases 1/4/5/6/10/12 in `contract.py:43-140`, yet the binding
tuple it relies on (`result_id = hash(identity)`) is defined in
`scripts/artifact_store.py:23` (`BINDING_FIELDS`) — a sixth file outside the
declared scope. The scope boundary is overstated; freeze evidence must cite
artifact_store.py explicitly.

F4 — Fehlende restart evidence: the only restart artifact is MMAC-031, a
code-read crash-window *map* (W1–W8, DURABILITY_AUDIT_COMPLETE, zero heavy
jobs). Zero physical kill-restart segments exist; GATEB18 (RUN_1 card) has no
restart field by design; `MAC06_RUN2_RESTART.md` is prepared, gate closed.
Core Freeze requires RUN_2 evidence per the critical path — currently
RUN2_DEPENDENT with nothing executable.

F5 — Fehlende human-intervention evidence: `relay_audit` (3 queries, file 08)
and `human_interventions` (0 + attestation + shell-history path) exist only as
GATEB18 template lines; M10-E13 needs shell history + JSONL trace with
HUMAN_RELAY_COUNT==0. With no run, zero-relay is an assertion, not evidence —
RUN1_DEPENDENT, and any current PASS would be F1-class false-green.

## Freeze verdict

CORE_FREEZE=NOT_READY. Chain state: Exact Binding partial (F3 scope fix +
binder placeholders PREPARABLE_NOW) → RUN_1 prep done-as-spec (MMAC-128,
GATEB18 skeleton) but RUN1_DEPENDENT for all physical evidence → RUN_2 prep
done-as-plan (MAC06, MMAC-031 map) but RUN2_DEPENDENT → Freeze BLOCKED on
B1/B2/B3 + U1/U2. No SLOT_IDLE: next exact action is the binder-placeholder
packet (MAC-HNI-01 rule) or re-audit on RUN_1 PASS — not claimed here to avoid
duplicating the live MMAC-178 family scope.

BACKUP=Core-Freeze False-Green Review (this file): F1–F5 are the false-green
patterns that must each close before freeze — PROVEN-stamp over untested
sub-cases, b-3-bound E1, five-file scope claim, map-as-restart-evidence,
assertion-as-zero-relay-evidence.

DO_NOT_REPEAT_FINGERPRINT=MUSE-MAC08-PROOF-FREEZE-b1-4c1e24cc-F1F5
