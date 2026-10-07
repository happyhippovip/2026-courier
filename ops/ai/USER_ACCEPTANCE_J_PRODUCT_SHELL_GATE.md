# User Acceptance J — Product-Shell Gate: "Nur nach positivem Pilot-Signal"

Status: OPERATOR ACCEPTANCE (USER WINDOW) — 2026-09-28
Product Shell: NOT unlocked. This file LOCKS the gate; it does not design the shell.

## USER_PROBLEM
Without a single explicit gate, product-shell work can start speculatively on
stale/contradictory "ready" claims (see items D and E: READY=YES next to SCOPE_OK=NO
and unmet gate conditions). The user needs one place that says LOCKED and what
unlocks it.

## CURRENT_RUNTIME_TRUTH (verified by reads, shell down, no execution)
- Gate is LOCKED in every canonical place (good, keep it):
  `PRODUCT_SHELL_UNLOCKED=NO` (`ops/ai/PILOT_READINESS_DECLARATION.md:35`);
  unlock ONLY on strictly Positive signal
  (`ops/ai/PILOT_METRICS_AND_SIGNAL_SPEC.md:15,22`);
  "MUST NOT be unlocked until Pilot-Value-Signal is Positive"
  (`ops/ai/PILOT_METRICS_AND_CONTRACT.md:22`);
  shell only in playbook Phase 8 after pilot (`ops/ai/END_TO_END_FINISH_TO_PILOT_PLAYBOOK_2026-09-27.md:298-313`).
- No positive pilot signal exists (no live cohort has run; metrics have no values).
- This pass added NO shell code and NO shell design — acceptance/observability prep
  only (items A–I), per instruction.

## ACCEPTANCE_REQUIREMENT
J-1: Unlock requires ALL of: (a) GREEN signal per the UNIFIED metric dictionary
  (item I — must exist first; today's acronym collisions block any signal claim);
  (b) Core Freeze record from physical RUN_1/RUN_2 evidence (items C–D repairs
  must land first); (c) named pilot cohort evidence (item I-3 records);
  (d) explicit human unlock citing (a)–(c).
J-2: Until unlock: acceptance/observability PREP ONLY. No shell implementation,
  no installer, no dashboard-as-product. (Beacon/status work from item A counts as
  observability prep and likewise needs (a)–(d) for rollout.)
J-3: Any READY/unlock claim MUST cite this gate file + the three evidence refs;
  standalone READY flags without citations are invalid.

## MISSING_SYSTEM_SUPPORT
- Unified metric dictionary (item I), freeze record (pending RUNs), cohort (pending).

## PREPARABLE_NOW (no code, this pass)
- This gate checklist. Nothing else.

## BLOCKED_UNTIL
- Pilot GREEN + freeze + cohort + human unlock. Then the FIRST shell scope is the
  minimal path only: Connect → Goal → Arbeitet → Braucht dich → Fertig
  (playbook Phase 8), no giant dashboard.

## NEXT
Loop back to A: re-read GATE/WALL/proof files after writer/review lanes move, and
retire or tighten items A–J against fresh evidence. No new scope without a new
user-visible unclarity.
