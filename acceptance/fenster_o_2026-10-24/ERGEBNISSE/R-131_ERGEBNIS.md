# R-131 · Doku `docs/HEAVY_PROCESS_SUPERVISOR_DESIGN.md` · FENSTER O
Basis `integration/v1` `81bbf224`, nur gelesen. sha256 `c7f5d6ce6c20927c7c6afe04ab0f3dca88e959b1b8c082ac1f5cbdd02be0b081`, 107 Zeilen, letzter Commit 2026-09-16.

| Aussage | Zeile | Urteil | Beleg |
|---|---|---|---|
| Zweiter Prozess ohne Lock: `RESOURCE_GUARD_BUSY` vor jedem Spawn | 21 | **nicht implementiert** | `git grep RESOURCE_GUARD_BUSY -- '*.py'` außerhalb von Tests: leer |
| Nur ein Heavy-Job über **alle** Courier-Prozesse | 89 | **WIDERSPRUCH zum Code** | `scripts/resource_governor.py:9` `MAX_HEAVY_JOBS = 1`, aber gezählt wird nur prozessintern (`self.active_jobs`, `:15`, Prüfung `:54`) ohne Datei-Lock, also nicht prozessübergreifend |
| Endliches Timeout, auf ein globales Maximum begrenzt | 50 | **VERIFIED (Mac)** | `scripts/mac_worker/daemon.py:388` `min(…, 600)`, `:543` und `:705` `min(…, 3600)` |
| Volle Regression nur mit menschlicher Freigabe, über den Supervisor | 88 | **gültig als Regel** | Deckt sich mit HEAVY_JOB_LIMIT=1 |
sha256: f1b99d9312d550e16e8abf7fa80a2caf4a4ada9db6e3d205a6b95b1deecac76e
