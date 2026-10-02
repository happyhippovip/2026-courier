# Windows GUI Freeze Incident (2026-10-02) and Freeze / Interruption Recovery Gate

## Status

- Incident class: **customer-trust failure** (no data loss proven, no data safety proven)
- Gate created: **FREEZE / INTERRUPTION RECOVERY GATE**
  (`docs/V1_PRODUCT_QUALITY_BAR.md` §4 class 10 and §10; matrix in
  `docs/COURIER_SYMPHONY_CANONICAL_PRODUCT_PLAN.md` §9 Gate 4)
- Root cause: **NOT PROVEN** (see confidence below)
- Recovery outcome: **NOT RECORDED HERE YET** — to be filled from the local
  Windows session's evidence; this record must not be completed from memory.

This file is the evidence record for the incident. The permanent requirement
lives in the quality bar and the canonical plan, not here.

## Canonical invariant

**A BROKEN SURFACE MUST NEVER IMPLY LOST WORK.**

Courier separates five layers and must be able to lose one without losing the others:

| Layer | Example on 2026-10-02 |
|---|---|
| WORK EXECUTION | worker/agent processes doing the task |
| SURFACE / UI | Windows desktop, taskbar, IDE window |
| TERMINAL HOST | VS Code/Antigravity integrated terminal, PowerShell Editor Services |
| AGENT SESSION | the Claude/Codex/Muse session driving the work |
| PERSISTENT STATE | git working tree, commits, ledger, outbox |

## Customer impact

The human could no longer determine:

- whether work was still running;
- whether changes were saved;
- whether a reboot was safe;
- whether terminating the machine would destroy work.

For a customer-facing autonomous-work product this is unacceptable even if no
byte was lost: uncertainty about hours of work is itself the failure.

## Incident record (evidence only)

Source of every fact below is stated. Nothing was measured on the host by the
author of this record (a cloud session without access to the machine).

### Timeline

| Time | Event | Source |
|---|---|---|
| 2026-10-02 ~23:31 local | Desktop effectively non-interactive: switching windows, taskbar, search and normal application windows unreliable | operator report + photo of the screen (taskbar clock 23:31, 02.10.2026) |
| 2026-10-02 23:34 local (21:34 UTC) | Emergency recovery prompt sent to a **cloud** Claude session (host `vm`, Linux) instead of the local Windows session; that session had no route to the machine and reported `RECOVERY CONTROL PLANE: LOST` | cloud session transcript |
| after that | Operator sent the photo; cloud session gave keyboard-only, non-destructive guidance (save/push first, Task Manager via Ctrl+Shift+Esc, Win+Ctrl+Shift+B, no broad kills, reboot last) | cloud session transcript |
| later | First recovery: the machine became usable again. Who acted and what was done: **UNKNOWN** — not this record's author; must come from the local Windows session's own history | operator report |
| minutes after recovery #1 | **Recurrence:** the same or a very similar freeze returned | operator report |
| — | Second capture/recovery | **UNKNOWN — must come from the local Windows session** |

### Host

- Huawei laptop, Windows (desktop with taskbar, German locale). Hostname, Windows
  build: **UNKNOWN**.

### Active worktrees (as visible on screen)

- Antigravity IDE window `2026-workspace`, folder `2026-courier`
  (path prefix `C:\Users\lol\courier_work\...`, partially visible).
- Status bar: branch **`lane/L6-windows-packaging*`** — `*` = uncommitted changes.
- Explorer decorations: modified markers on `2026-courier/` and `scripts/`.
- An open review of `host.py` (`+54 -64`, "single-flight bounded execution engine
  (lane L3)", `WorkerHost` holds at most one live dispatch) and an open
  `G201.result.md`.
- Several terminals (Codex/Claude-style CLIs, `muse-spark`, Command Prompt) with
  in-progress output; exact processes **UNKNOWN**.

### Uncommitted work

- **YES** on `lane/L6-windows-packaging` (status bar `*`). Size/content **UNKNOWN**.

### Unpushed commits

- **71 outgoing commits** on `lane/L6-windows-packaging` (status bar `0↓ 71↑`).
  This is the largest quantity of work at risk visible in the evidence.

### Processes still alive

- Screen still rendered (clock, windows, notifications), so the OS and DWM were
  at least partly alive. Whether worker/agent processes kept running: **UNKNOWN**.

### Resource state

- CPU / RAM / disk / handle counts: **UNKNOWN** (not captured).
- Visible load indicators: very many overlapping terminal/IDE/browser windows;
  62 unread notifications; Settings "Apps & Features" open.

### Failure classification (evidence-backed parts only)

| Classification | Evidence | Status |
|---|---|---|
| GUI_SHELL_FROZEN | operator report | REPORTED, not measured |
| POWERSHELL_EDITOR_SERVICE_FAILED | IDE toast: "Connection to PowerShell Editor Services (the Extension Terminal) was closed" | **OBSERVED** |
| TERMINAL_HOST_FAILED | follows from the toast for the IDE extension terminal only | OBSERVED (partial) |
| RESOURCE_EXHAUSTION / MEMORY_PRESSURE / CPU_SATURATION / DISK_PRESSURE | none measured | UNKNOWN |
| GPU/DWM_PROBLEM | none measured | UNKNOWN |
| ANTIGRAVITY_PROBLEM | two installs present ("Antigravity 2.17.0", "Antigravity IDE (User)") — a risk, not a cause | UNKNOWN |
| WORK_FAILED | no evidence that any task failed | NOT PROVEN |

### Recovery action

- None performed or verified by this record's author. Guidance given:
  push the 71 commits first; inspect Task Manager without killing; graphics-driver
  reset (Win+Ctrl+Shift+B) before anything destructive; restart only the failed
  PowerShell extension; reboot last.

### Data loss

- **UNKNOWN** at time of writing.

### Recurrence (2026-10-02, reported)

- The freeze returned within minutes of the first recovery (exact interval
  **UNKNOWN**).
- Consequence for the analysis: whatever the first recovery did treated a
  **symptom**, not the cause. A recurring freeze shortly after a restart points
  toward an ongoing load or leak source that restarts with the session
  (hypothesis, **NOT PROVEN**), rather than a one-off transient.
- The first recovery left no captured before/after evidence, so the recurrence
  cannot be compared against it. This is itself a finding: recovery without
  capture destroys the evidence needed to prevent recurrence.

### Root cause confidence

- **LOW / NOT PROVEN.** The only hard signal is the PowerShell Editor Services
  crash, which explains a dead IDE terminal but does not by itself explain a
  frozen desktop. Resource pressure from many concurrent windows/agents is
  plausible but unmeasured.

### What saved the work

- Nothing automatic is evidenced. Whatever was already committed locally survives
  a GUI freeze (git objects on disk); the 71 commits were **local only**.

### What failed to save the work

1. **No continuous off-machine checkpoint:** 71 commits accumulated without a push.
2. **No machine-readable status outside the GUI:** the human had no way to ask
   "what is running, what is saved, is reboot safe?" without a working desktop.
3. **Wrong-host control plane:** the emergency prompt reached a cloud session
   that could not reach the machine; nothing told the human which session owns
   which host.
4. **No surface-independent recovery channel** prepared before the incident.
5. **No Recovery Receipt** and no SAFE_TO_REBOOT / NOT_SAFE_TO_REBOOT verdict.

## Primitives this incident validates or strengthens

| Primitive | Effect of this incident |
|---|---|
| Critical Snapshot Level 0 | **Strengthened:** must be capturable headlessly in seconds while the GUI is unusable (worktrees, dirty/unpushed state, owned processes, resources). |
| Device Health | **Strengthened:** CPU/RAM/disk/handles/explorer/DWM responsiveness must be recorded continuously so a freeze has before/after evidence. |
| Process Ownership | **Validated:** recovery must target exact owned PIDs; the guidance "never kill by name" was the only safe option. |
| Work Lease | **Validated:** a live lease + last-progress time would have answered "is work still running?" |
| Checkpointing | **Strengthened:** local commits are not a checkpoint against machine loss; checkpoint = durable off-machine (push or bundle). |
| Recovery Receipt | **Validated:** missing; the human had nothing to read. |
| Verified Memory | **Strengthened:** the incident state must be written to durable memory, not reconstructed from chat. |
| Verified Continuation | **Validated:** after reboot, the resume point must be computed, not guessed. |
| Right-Host Evidence | **New hard requirement:** every recovery/ops command must first prove it runs on the target host; a wrong host must stop immediately. |

## Answer: what Courier must implement

So the user never again wonders whether hours of work are gone, Courier must:

1. **Keep work off the single machine continuously** — bounded unpushed/uncheckpointed work, auto-push or bundle of owned lanes.
2. **Answer "what is running and what is saved?" without the GUI** — a headless status/snapshot command and file that work when explorer/IDE are frozen.
3. **Give a reboot verdict** — SAFE_TO_REBOOT / NOT_SAFE_TO_REBOOT with reasons, plus a Recovery Receipt.
4. **Separate layers in state** — surface/terminal/agent/work health tracked independently, so a dead terminal is never reported as failed work.
5. **Route recovery to the right host** — device identity in every session and a refusal when the target host is wrong.
6. **Resume deterministically** — after restart, compute the safe resume point from durable state and verify continuation.

These are the implementation workkeys `FRZ-01` … `FRZ-10` in
`docs/V1_PRODUCT_QUALITY_BAR.md` §10 (FREEZE / INTERRUPTION RECOVERY GATE).
