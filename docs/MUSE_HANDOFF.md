# MUSE HANDOFF — Courier Symphony

Stand: 23.09.2026

Read first:
1. `docs/MASTERPLAN_COURIER.md`
2. `docs/STATUS.md`
3. `AGENTS.md`
4. `CLAUDE.md` only for shared repository rules, not because Claude is currently available

## Current mission

Only **Cannon V1 freeze**.

Do not expand the product, do not start Ledger/V2/UI/Community work, and do not redesign the architecture unless a reproducible blocker proves it is necessary for Cannon V1.

## Mac-first operating mode

Current active focus is the Mac side.

Available Google capacity on Mac: 7 worker slots.
Windows work is deferred and must not interrupt Mac progress unless a Mac acceptance condition truly depends on it.

Claude is unavailable until Saturday, so do not wait for Claude to continue factual Mac work.

## Fast-path rule

Dennis explicitly wants the shortest safe route.

Therefore:
- no endless review loops;
- no repeated audits of already evidenced facts;
- no second reviewer just to re-review another reviewer;
- no broad regression after every small change;
- no speculative refactors while a smaller causal fix exists;
- reuse strong existing evidence;
- targeted test after a change;
- full/acceptance verification only at the Cannon V1 freeze boundary or when a real risk requires it.

"Kein Beleg = kein PASS" still applies, but evidence should be **minimal sufficient evidence**, not maximum possible evidence.

## Known state

- `pre-yolo-patch(-v2)` = `49150d3f`
- `yolo-patch-applied-v2` = `e98ce2cc`
- official baseline between those references = UNKNOWN until proven
- exact live-text failure = UNKNOWN until reproduced
- Cannon V1 acceptance target includes:
  - result_id bound to full commit hash
  - duplicate executions = 0
  - lost results = 0
  - emergency stop < 15 s
  - 5-run acceptance green
  - infinite-run evidence evaluated
  - Mac acceptance evidence
  - Windows acceptance evidence later, without blocking current Mac diagnosis unless strictly required

## Recommended 7 Mac worker lanes

All lanes are read-only by default until a causal fix is identified.

1. **Baseline lane** — determine the authoritative `pre-yolo-patch` baseline from Git history/tags/tests. Output evidence only.
2. **Live-text lane** — reproduce the live-text failure and isolate the smallest root cause. Output exact command + failure + file/line suspects.
3. **Current-test lane** — produce one concise snapshot of currently failing Cannon tests; do not repeatedly rerun broad suites.
4. **Infinite-run lane** — inspect the existing endlos-run artifacts and extract task count, hangs, duplicates, lost results, result_id/commit binding evidence.
5. **5-run lane** — identify the exact existing 5-run acceptance command/harness and blockers. Do not invent a new harness if one exists.
6. **Freeze lane** — prepare the minimum freeze checklist/bundle/tag steps, but do not tag/push/release without Dennis approval.
7. **Repo-state lane** — identify only conflicts/dirty state/branch hazards that could invalidate Cannon evidence. No architecture review.

After these outputs return, choose **one writer lane only** for the smallest required code change. Other workers stop or remain read-only.

## Output format

Keep every result short:

- LANE:
- BRANCH:
- FULL_SHA:
- STATUS: BELEGT | BEHAUPTET | VERMUTET | UNKNOWN
- FINDING:
- EVIDENCE:
- SMALLEST_NEXT_ACTION:
- CODE_CHANGE_NEEDED: YES/NO

Do not merge, push to canonical/main, tag a release, spend money, change accounts, publish, or expose secrets without Dennis's approval.
