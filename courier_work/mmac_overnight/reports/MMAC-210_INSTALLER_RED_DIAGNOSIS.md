# MMAC-210 — Installer lanes: #253/#254 genuine, #251 red-CI root cause (read-only)

Base `origin/integration/v1` = `f425d328`. Host load ~8.5: tight bounded reads only. All three lanes live (Cursor L6) — zero touches.

## #253 dist-install / #254 dist-uninstall: VERIFIED genuine
Copy failure → exit 1 + dir-exists check; removal failure → exit 1 + remains-check. Fail-closed "not proven" language throughout. Tests pin both polarities (failed-copy not-installed / copied-files installed; failed-removal not-complete / removed-dir complete). #253 windows pending, #254 windows pending (not polled).

## #251 launcher-build: genuine change, RED on Windows — FINDING-251-WIN-STUB (owner: Cursor lane author)
Prod change is real (missing-csc / nonzero-exit / missing-artifact all fail closed with explicit exits). But `test_written_exe_reports_success` fails on windows-latest (run 37723504080, 6m52s): the stub `csc.exe` is a `#!/bin/sh` text file, which Windows cannot execute as PE (`ResourceUnavailable`, exit 1). The three negative tests pass on Windows vacuously (stub never runs). The file's own docstring concedes "This is not a Windows machine" while the CI matrix runs it there.
- Owner fix options: (a) `skipif(os.name != "posix")` on the positive test — minimal and honest; (b) compile the trivial `CourierLauncher.cs` with the real `csc.exe` present on windows-latest images — true positive-path proof.
