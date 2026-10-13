# APPROVAL FRICTION — verdict 2026-10-07 (scope owned, completed, released)

HEAD: `integration/v1` = `b9fc486ac`. Open PRs refetched: #132-#167
(new #160-#167: worker/controller/doctor/provider fixes, none in this scope).
#157 (harness file) progressing — not touched. No product code changed.

## Reproduced (real Windows)

- Default shell path fails: sandbox setup cannot admit
  `...\muse\windows-sandbox\deny_read_acl_state.json`.
- Read-only inspection: that FILE and the whole `windows-sandbox/`
  directory DO NOT EXIST. Owner of `...\muse` = `DESKTOP-JDPRUGR\lol`
  (normal). Consequence: every shell call needs `require_escalated`
  (unsandboxed + approval prompt) — that is the prompt Dennis sees.

## Genuine HUMAN_REQUIRED (not bypassed, not weakened)

- Repair/recreate of the Muse sandbox enforcement state. Security-
  sensitive, runtime-owned. ONE action for Dennis/runtime support;
  deliberately NOT performed from here.
- GitHub push of local `handoffs/` evidence = external publication gate.

## Avoidable friction — eliminated procedurally (proven)

- One-shot durable path verified live at `b9fc486ac`:
  `pytest tests/test_win_clean_machine_harness.py` → **1 passed, 31.47s**.
  Routine acceptance costs ONE call, not ~8 ad-hoc calls.
- `read_file` + `web_fetch` (raw/API/HTML) need no shell at all and
  covered the entire ownership/truth refetch tonight.
- Residual rule: batch live Windows work into few sectioned calls;
  never re-poll state already in evidence.

## Why no FIX → PR chain

Mission allows it only "if a free product-owned fix exists". None does:
the defect is the agent runtime's missing sandbox state, not Courier
code. A new runner script would add product surface for a transient
environmental bug and risk lane collision (harness = L1, #157 active).
No grep-family tools used. No new scheduler/watcher. No bypass.

## Cleanup verified

Zero Courier processes (corrected filter), zero strays, worktree
removed, TEMP homes removed. (An early `STRAYS=1` was my own shell
matching its own filter text — corrected filter proves zero.)

## Ownership

Scope `unattended-execution-friction` RELEASED after this checkpoint.
Next free workkeys in lane-writer/VM/Dennis authority, not mine:
GAP 1 stop path (L6), GAP 3 VM install/uninstall (needs scratch VM),
sandbox repair + handoffs push (Dennis). Stopping here: no further
productive safe work inside this authority.
