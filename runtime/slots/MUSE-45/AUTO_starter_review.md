# AUTO-STARTER REVIEW — launch_32_auto + installer + probe + stop (static)

Files: launch_32_auto.ps1, install_desktop_shortcuts.ps1, probe_muse.ps1,
stop_all_slots.ps1. Read-only; wall scope owned by overnight loop.

## Corroborated GOOD
- Fresh on-machine probe every starter run; YOLO fail-closed when help text
  lacks --yolo; explicit TARGET_GATE; resume-next-unproven 1->4->8->16->32
  (->64); 64 chain-gated on 32 PASS; corrupt/missing proofs fail closed;
  atomic proof writes; no busy loop (2s poll); no Invoke-Expression.
- Installer writes ONLY the trio (+conditional YOLO-32): Muse Original is
  presence-checked, never created/modified/deleted. No kills/creds/ACL.
- Probe: PATH resolution, 30s job timeout, fail-closed throws, host+timestamp
  recorded, yolo from REAL help text only, never launches a session.
- stop_all_slots: per-slot exact supervisor stop (PID+create_time), 200ms
  spacing, no broad kills; scope honestly documented (tracked jobs only).

## A-2 (MEDIUM-LOW, proof-strength) Stage PASS does not prove live sessions
- Machine checks: wt process alive + stage workdirs exist + zero CRASHED/
  BLOCKED in supervisor status. Interactive panes leave no supervisor PID
  (acknowledged in-script), so an open wall with EMPTY/DEAD panes also
  passes all machine checks.
- Real session proof is delegated to OPERATOR checklist strings embedded in
  the proof JSON (no-popup, type-a-char-in-MUSE-01) — but nothing blocks on
  them; PASS is written regardless of operator action.
- Morning-flow consequence: "stage 16 PASS" is hollow unless the operator
  actually performs the checklist each stage. Suggested owner hardening
  (pick one): (a) machine-count muse processes (Get-Process muse*) as an
  extra check, (b) Read-Host operator confirmation before writing PASS.
  Until then, treat stage PASS as "wall alive + state clean", NOT as
  "N live Muse sessions".

## A-4 (LOW) Admit result printed but not enforced
- admit --level N output is informational; launcher starts the full stage
  regardless. With active_limit=16, Target-32/64 starters over-admit by
  construction. Align: enforce admitted count or document that active_limit
  does not apply to the interactive wall (same family as C-1).

## Smaller notes
- I-3: YOLO shortcut exists only for 32 (Muse 32 YOLO); user wish per memory
  is YOLO-16 (+32/64 buttons). Installer change is wall-owner call.
- A-5: default StabilitySeconds=20; 10-15min soak needs explicit
  -StabilitySeconds 600/900 (supported, just not default).
- A-7: -SkipGate allows forcing any stage incl. 64 — explicit escape hatch,
  acceptable, noted.
- Pr-1: installer trusts probe.json yolo flag without freshness/host check;
  only bites with explicit -SkipProbe (default path always re-probes). INFO.
- stop default Slots=32: slots 33-64 need explicit -Slots 64. Cosmetic.
