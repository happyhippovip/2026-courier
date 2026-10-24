# R-133 · Doku `docs/HOST_ENDURANCE_BASELINE.md` · FENSTER O
Basis `integration/v1` `81bbf224`, nur gelesen. sha256 `a458cb53016db1aa0e07a302b8bb26d630e8fc12e659d363dbedef102b07187d`, 99 Zeilen, letzter Commit 2026-10-02.

| Aussage | Zeile | Urteil | Beleg |
|---|---|---|---|
| Guardian-Architektur u. a. `scripts/host_capacity.py` | 5, 13, 91, 98 | **WIDERSPRUCH / überholt** | `scripts/host_capacity.py` existiert auf 81bbf224 **nicht** (Z. 98 sagt selbst „still untracked“) |
| `tests/test_host_endurance.py` (17 Tests, 17 passed) | 70, 79 | **WIDERSPRUCH** | Datei existiert auf 81bbf224 **nicht**. Der Testnachweis ist auf dem Trunk nicht reproduzierbar |
| übrige Dateien (`host.py`, `service.py`, `resource_governor.py`, `host_budgets.py`, `scripts/soak/*`, `tests/test_host_budgets.py`, `tests/test_l3_worker_host.py`) | 4-90 | **VERIFIED** (vorhanden) | `ls` |
| HEAVY = 1 Heavy-Job | – | **VERIFIED** | `scripts/host_budgets.py:104` `"HEAVY": {"heavy_jobs": 1, …}` |
sha256: 1061f1a3d7c12327306ae71bb7bfa79dab2a698e54a026870ef7e6af54788194
