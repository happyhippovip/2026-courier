# ChatGPT Courier Handoff — 2026-09-24

Status: coordination handoff only. No claim that implementation is complete.

## Purpose

This file preserves the current working direction so a new session can resume without reconstructing the project from chat history. It complements, and does not replace, the canonical runtime, the agent handoff ledger, or existing project documentation.

## Current Mac / Terminal Wall target

- Developer wall target: **64 Muse + 6 Anti-Gravity** sessions.
- Muse command: `muse --yolo`.
- Anti-Gravity command: `HOME=/Users/user/.gemini_alt agy`.
- Visible layout target: Muse **8x8**, Anti-Gravity **2x3**.
- Keep the two-step architecture:
  1. **WALL-AUFBAUEN** — restore/create and arrange only the intended wall slots.
  2. **WALL-STARTEN** — start the expected process in each verified slot.
- Restore and process start stay separate on purpose.
- Do not auto-start all provider sessions at macOS login.
- Do not adopt arbitrary idle Terminal windows. A slot needs a persistent wall identity / inventory.
- Double-start protection must not rely on Terminal `busy` alone.
- Future customer packaging should support configurable 32/64 counts without duplicating the architecture.
- Future background mode should reuse the same slot/inventory model instead of requiring 32/64 visible Terminal windows.

## Current Mac concern

At the time of handoff the visible desktop still contains a large terminal wall and many sessions appear to have been present since the previous evening. Earlier measurements reported very high swap and GUI load. Treat the exact current process state as UNKNOWN until a fresh read-only inventory is run.

Before reboot or cleanup:
- preserve recoverable wall/session state,
- identify the actual files controlling restore/start,
- do not use broad `kill`, `pkill`, `killall`, `launchctl unload`, or `bootout`,
- do not overwrite unrelated terminal sessions.

After reboot:
1. inspect the clean resource baseline,
2. run WALL-AUFBAUEN only,
3. verify exact intended slots,
4. then run WALL-STARTEN,
5. confirm no duplicate Muse/AG processes.

## Courier program order

Keep the existing P0-P6 plan and do not invent a parallel core:

- **P0** — establish one evidenced starting point: repo/branch/SHA, ledger revision/hash, active writers, runtime/process inventory.
- **P1** — prove ledger/handoff use with a cold-start reconstruction test.
- **P2** — repair evidenced completion/continuation semantics minimally.
- **P3** — run a real isolated operational proof with >=2 real workers, >=10 acceptable completions, interruption/resume, no duplicate external effect, honest DONE/CLEAN_IDLE.
- **P4** — complete one small solo customer pilot end to end.
- **P5** — add product extensions only as separately accepted packages.
- **P6** — calculate pilot economics from measured costs.

## Known coordination conflict to resolve in P0

A previously reported local Mac ledger revision and the GitHub ledger revision differ. Never merge or overwrite competing ledger histories by hand. Determine the valid line from actual checkout SHA, ledger CLI output, history/hash chain, runtime state, and writer ownership.

## Windows workstream

The Windows port must not be treated as "done" just because a previous agent has no immediate task. First establish the real Windows checkout and runtime state read-only. The previously referenced Windows branch was not confirmed on public GitHub at the time of the planning handoff.

Windows work must:
- inventory repo path, branch, HEAD, dirty files, ledger revision/current SHA/writer/blocker,
- identify Windows-specific scripts/services/processes and their restart behaviour,
- run only small isolated tests,
- avoid changing shared collision scopes while another writer owns them,
- document genuine Windows defects or missing parity against the canonical Mac/runtime behaviour,
- stop and report BLOCKED rather than create busywork when no safe independent scope exists.

## Safety / publication

- No secrets, raw chat logs, private account data, or screenshots should be committed to the public repository.
- This document contains only sanitized technical coordination information.
- Repository documentation is not runtime truth.
- Merges and external irreversible actions remain human-gated.

## Immediate next steps for 2026-09-24

1. Make the Mac wall reboot-safe without starting additional provider sessions.
2. Reboot once recoverable state is secured.
3. Rebuild the wall without starting Muse/AG, verify slots, then start them once.
4. Run P0 and resolve the ledger/repo/writer mismatch.
5. Assign one safe, independent Windows scope from the P0 evidence.
6. Continue P1 -> P2 -> P3 before product expansion.
