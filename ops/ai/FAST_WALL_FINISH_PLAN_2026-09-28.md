# Fast Wall Finish Plan — 2026-09-28

Verified taskbank capacity:
- windows-google: 192 tasks
- mac-google: 64 tasks
- muse: 288 tasks
- muse-windows: 144 tasks
- muse-mac: 144 tasks

Use one identical self-distributing prompt per window. Atomic local claims prevent two windows from intentionally taking the same task. SOURCE_WRITE tasks also use the exclusive SOURCE_WRITE lock.

Recommended high-throughput profile:
- 48-64 Windows Google windows using WINDOWS_GOOGLE_100X_REPEATABLE_PROMPT.txt
- 8-16 Muse windows using MUSE_100X_REPEATABLE_PROMPT.txt
- one harvest/router window every meaningful batch/phase change
- Mac existing queue continues; one physical owner only when gate opens

Do not queue 100 identical messages inside each window. One message already loops through multiple unique tasks. A second copy later is safe and useful only if the first session stopped/returned.

Finish order:
1. drain current Windows failed/skipped/local-diff issues through claimed tasks
2. harvest
3. Claude/Codex exact decision
4. Windows sole writer closes admitted BEFORE_RUN1 work
5. exact Mac binding
6. RUN_1 physical once
7. RUN_2 restart/no-replay once
8. Core Freeze
9. minimum real pilot
10. Product Shell only after positive pilot signal

Meeting a clock target never overrides FAILED/SKIPPED/evidence gates.
