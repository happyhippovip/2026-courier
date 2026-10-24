# R-134 · Doku `docs/HOST_OVERHEAT_INCIDENT_AND_RESUME_GATE.md` · FENSTER O
Basis `integration/v1` `81bbf224`, nur gelesen. sha256 `bcd998fa5d0869541e2306fb8f227d2b0928729670e908b4b9f3a7aeca36d99b`, 218 Zeilen, letzter Commit 2026-09-16.

| Audit-Punkt | Zeile | Urteil | Beleg |
|---|---|---|---|
| 5. Native AGY ohne harte Timeout-Obergrenze | 40 | **überholt (behoben)** | `scripts/mac_worker/daemon.py:543` `min(float(raw_timeout), 3600)`, `:705` ebenso |
| 11. Heavy-Guard darf nicht nur ein prozessinterner Zähler sein | 46 | **gültig, offen** | `scripts/resource_governor.py:15,54`: nur `self.active_jobs`, kein Datei-Lock |
| 14. Spawn-Fehler muss Lock/Lease freigeben | 49 | **nicht geprüft** (nur gelesen) | |
| Verweis `docs/COMPUTE_RESOURCE_SAFETY_POLICY.md` | 217 | **VERIFIED** (vorhanden) | |
| Resume-Gate als harter Blocker bei unbegrenzter Nebenläufigkeit | 9-11 | **gültig** | HEAVY_JOB_LIMIT=1 |
sha256: 12a29bc0fedc30713054f844f651a7f68341048614692dea9452f72e89e1bfe0
