# O7-02 · B1 CostGate · estimated_cost_eur = None/leer wird als 0 gewertet · Claude Opus (FENSTER 7)

| Feld | Wert |
|---|---|
| Basis | `integration/v1` = `81bbf224b0aeeca4a2b92db29dfc7220b707043a` |
| Testdatei | `O7-02_test_missing_estimate_not_zero.py` · sha256 `52596654e8daa40d52bc4e63bfe3554d3aeb42dda91f23aa89523da7845929c2` |
| Marker | `xfail(strict=True, raises=AssertionError)`, 3 Parameter; dazu 2 Schutztests ohne xfail |
| Lauf auf Basis | `2 passed, 3 xfailed`, Exit 0; mit `--runxfail`: `AssertionError: assert [(['powershell', '-EncodedCommand', …],)] == []` (PowerShell wurde gestartet) |
| Kosten | 0 €, `subprocess.Popen` gemockt, nichts ausgeführt |

## Befund (VERIFIED)
- `courier_core/cost_transparency.py` (Input laut Katalog) liest `estimated_cost_eur` **nicht**. Dort gibt es dazu keinen Befund (**nicht gefunden**). Fehlende `cost_class` wird nur bei lokalen Providern als `free` gewertet (`cost_transparency.py:137-141`), sonst als `unknown`. `tests/core/test_cost_zero_class.py` pinnt nur den numerischen Wert 0.
- **Echter Defekt:** `scripts/windows_worker/daemon.py:359-361`
  ```python
  cost_val = task.get("estimated_cost_eur")
  if cost_val is None and cost_class in ("included_quota", "free", "local"):
      cost_val = 0.0
  ```
  Eine fehlende Schätzung wird zu 0.0, sobald der Auftrag selbst eine dieser Klassen behauptet. CostGate (`scripts/resource_policy.py:150-158`) sieht dann nicht „fehlt“ und lässt den Auftrag durch. PowerShell startet (`daemon.py:391-393`).
- Schutz bereits vorhanden (2 passed): Ohne Klasse werden `None` und `""` mit UNKNOWN_COST blockiert.

## Konflikt mit bestehendem Test
`tests/test_windows_costgate_and_writer_lease.py:52-56` (task2) erwartet heute, dass `included_quota` ohne Schätzung SUCCESS ergibt. Der Fix muss diesen Test mitändern.

## Fix-Lage
- `included_quota`: wird durch **WIN-COST-1 v3** (`claude/v38-win` `4ed111395`, nicht gemergt) behoben. Nach dessen Merge wird dieser Parameter XPASS, also strict-Fehler, also xfail nur für `included_quota` entfernen (C1-17).
- `free` / `local`: bleiben auch mit WIN-COST-1 v3 0.0. Ob eine **vom Auftrag selbst behauptete** Klasse eine fehlende Schätzung ersetzen darf, ist eine Policy-Entscheidung (L6 bzw. Dennis, vgl. POL-1). Bis dahin bleiben diese Parameter strict xfail.
sha256: 8366b43c679f22e6407394ee14595e17e9325776293f882cbbb78be4c094a0eb
