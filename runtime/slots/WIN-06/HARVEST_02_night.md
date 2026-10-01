# HARVEST 02 — night round pass 2 (read-only)

BY=WIN-06 DATE=2026-09-26. Own-slot checkpoint only. Supersedes HARVEST_01
framing where noted; file kept intact (predecessor, no edits to others' work).

## HEADLINE: checkout switched mid-round (reframes pass 1)
- NOW (direct reads): .git/HEAD -> refs/heads/fix-cb1-new @ 329abd80
  (loose ref; absent from packed-refs -> new branch).
- BEFORE (T22 + W5 + WIN-05 census + Google checkpoint): HEAD was
  ledger-reconciliation-final @ b927f106 ("staged scaling proven"); its loose
  ref is now DELETED (os-error-2).
- Pass-1 "demolition" (14 files absent, 2 rewritten) is therefore most likely
  a CHECKOUT CHANGE, not in-place deletion. Mechanism (switch/reset/swap) UNKNOWN;
  no shell to confirm. Untracked slot reports persisted across it (consistent).
- Consequence: ALL pre-switch evidence (mine + every peer report citing
  wall/daemon/app/tests content) is checkout-scoped to the b927f106-era tree.
  Nothing may be cited as "current" without re-resolving HEAD first.

## New-to-me peer results (T21-T26; app pins are OLD-REV)
- T21 (double :8080 bind, AtLogon triggers): app.py:1589-1590 pin EXCEEDS
  current EOF (562) -> OLD-REV. run_waitress.py:13 subject DELETED in current
  (os-error-2, P3 file!) -> F-T8-1 moot-as-framed (single binder left? owner
  re-verify). AtLogon trigger pins (other files) stand unchallenged.
- T22 (git inventory): packed-refs data (186 refs, SHAs, sync map) likely still
  good; HEAD + loose-ref section SUPERSEDED by the switch. Method gift: .git is
  shell-less readable -> all agents can cite branch+SHA without git CLI.
- T23 (portability: Mac-pinned thought tests, /tmp literals): different files,
  stands unchallenged (LOW, owner scope).
- T24 (live-code portability): app.py:24 pin CONTRADICTED by current file
  (:24 is auth decorator now) -> T24 read OLD rev. Studio/agy pins stand
  unchallenged. Switch bounds: AFTER T21+T24 reads (both old-rev).
- T25 (safety-core spot: queue_processor/worker_contract zero direct tests):
  NEEDS-REVERIFY post-switch (tests/ lost 4 files; spot files differ, likely
  valid, not confirmed).
- T26 (dispatcher 13 tests, G-5 spawn, verifier shape, validate_durable
  DIRECT): same NEEDS-REVERIFY caveat (file-level, probably valid).
- WIN-02/03/04: no new logged work (CLAIM tails unchanged; WIN-03 W6 unstarted).
  WATCH: WIN-02 NEXT (launcher behavioral audit) targets now-absent files.

## Spot-checks this pass
- H2-1: HEAD+SHA ground truth established (above; first in-session git identity).
- H2-2: run_waitress.py absent (P3 deletion-in-checkout; F-T8-1 moot).
- H2-3: app.py:20-29 = auth decorator (T24 pin contradicted -> old-rev).
- H2-4: demolition re-probe (supervisor.py, config.json still absent) +
  admitted_count nowhere in code (consistent with switch).
- NEXT_GAP (v2 coverage+contract map) still UNOWNED (only my HARVEST_01 ref).

## CENTRAL_WRITER_INPUT (supplements HARVEST_01 list)
1. (NEW, TOP) Confirm intended checkout: HEAD=fix-cb1-new@329abd80; Google's
   07:45 DIRTY ledger work (uncommitted config + proofs) — where is it now?
   At risk if orphaned by the switch. All readers blocked on this answer
   before citing anything as current.
2. Scope caveat on HARVEST_01 items 1-3,5-6: STOP-path UNSAFE, requeue rule,
   re-pinning, session-counting, v2 nits are all fix-cb1-new-scoped until the
   canonical line is declared. If ledger line is restored, X6/staleness partly
   revert to old-rev findings (which keep their own owners).
3. Evidence protocol now REQUIREMENT (was recommendation): every report cites
   branch+SHA from .git/HEAD + loose ref (shell-less readable); uncited line
   numbers are suspect; re-verify before citing.
4. Re-verify queue for owner/runner: T25/T26 spots, T23 pins, uninstall.ps1
   state (my W2-carryforward, path+state unprobed), worker observability gap.

## NEXT_GAP (re-scoped, still unowned)
V2 coverage + contract map, GATED on writer answering input-1 (cannot map
"current" while canonical checkout unknown). Then: surviving-tests x current
daemon/server map + integration_contract currency vs v2 protocol. If ledger is
declared canonical instead: gap becomes "re-verify pass-1 staleness on ledger
checkout" (needs shell or re-switch).

## Stale cleared/added
ADDED: T21 app pins, T24 app pin, T22 HEAD section, HARVEST_01 "deletion"
attribution (replaced by switch hypothesis; absence FACTS kept).
CLEARED: pre-switch line refs (all agents); " Breathless demolition" urgency —
the files may all exist on ledger-reconciliation-final @ b927f106.
Resume next pass: re-read .git/HEAD first (switch detector); T27+/W6+ watch;
1-2 absence re-probes; IDLE if unchanged.
