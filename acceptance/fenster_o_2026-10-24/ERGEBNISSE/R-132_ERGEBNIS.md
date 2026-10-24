# R-132 · Doku `docs/HEAVY_PROCESS_SUPERVISOR_RESEARCH_NOTES.md` · FENSTER O
Basis `integration/v1` `81bbf224`, nur gelesen. sha256 `bb2d513a651cb2a5cec6ee08fce1a3abfa742a2bb48e627bb9fd4a8baf2effe9`, 44 Zeilen, letzter Commit 2026-09-16.

| Aussage | Zeile | Urteil | Beleg |
|---|---|---|---|
| Prozessübergreifender Ausschluss nötig | 5 | **gültig, offen** | wie R-131: Der Governor zählt nur prozessintern (`scripts/resource_governor.py:15,54`) |
| `communicate()`-Timeout räumt das Kind nicht von selbst ab, eigenes Terminate nötig | 28 | **gültig** | Bekanntes Python-Verhalten; der Windows-Daemon beendet explizit (`scripts/windows_worker/daemon.py:330-334`, taskkill /T /F) |
| Kosten / PAYG | – | **nicht gefunden** | |
sha256: ebb299c0a9a2c29dcda5469b25080a8c53be485cbe05a438488ba6d3eb160f84
