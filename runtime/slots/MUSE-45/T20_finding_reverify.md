# T20 RESULT — Prior-finding re-verification sample vs current tree (read-only)

MODE: shell-less LIGHT. Sampled 3 findings from AUTO_starter_review.md +
WALL_config_note.md; checked whether owner action landed since.

## 1. C-1 minimum_free_memory_mb never enforced — STILL OPEN (RE-CONFIRMED)
- Repo-wide search: key appears ONLY in scripts/windows_muse_wall/config.json
  + 5 test fixtures (test_muse_wall_gaps/jobs/staged_scaling, test_supervisor,
  test_windows_muse_wall). Zero production reads.
- supervisor.admitted_count (re-read this session, lines 222-225): checks
  staged_levels/active_limit/desired_slots only. No psutil memory gate added.

## 2. A-2 stage PASS does not prove live sessions — STILL OPEN (RE-CONFIRMED)
- launch_32_auto.ps1:126-127 still embeds OPERATOR checklist strings
  (no-popup confirm; type-a-char-in-MUSE-01). No Get-Process muse* machine
  count, no Read-Host confirmation gate anywhere in scripts/windows_muse_wall.
- Stage PASS still means "wall alive + state clean", NOT "N live sessions".

## 3. I-3 YOLO shortcut only for 32 — STILL OPEN (RE-CONFIRMED)
- install_desktop_shortcuts.ps1 creates 'Muse 16 Auto' (no -Yolo flag),
  'Muse 32 Auto', conditional 'Muse 32 YOLO'. No 'Muse 16 YOLO' shortcut
  despite user wish YOLO-16. Installer change remains wall-owner call.

## Method note
No fixes attempted (wall scope owned by overnight loop; RC planning frozen).
Deltas only; owners keep write authority.
